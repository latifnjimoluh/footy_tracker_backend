import asyncio
import json
import os
import random
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
BASE_URL = "https://1xbet.cm"
DATE_STR = datetime.now().strftime("%Y-%m-%d")

# Dossiers
INPUT_DIR = os.path.join("match", DATE_STR)
INPUT_FILE = os.path.join(INPUT_DIR, "ids_championnats_24h.json")
OUTPUT_FILE = os.path.join(INPUT_DIR, "matchs_details.json")

# Mots à bannir
BANNED_TEAMS = [
    "à domicile", "à l'extérieur", "home", "away", 
    "buts", "goals", "corner", "carton", "penalty",
    "équipe", "team", "joueur", "player", "ace", "faute",
    "first", "second", "period", "half"
]

async def check_and_close_popup(page):
    """Ferme le popup s'il apparaît"""
    try:
        btn = page.locator(".notification-age-restriction__actions button").first
        if await btn.is_visible(timeout=1000):
            print("      🔞 Popup détecté ! Fermeture...")
            await btn.click(force=True)
            await asyncio.sleep(1)
    except: pass

def parse_match_html(match_html, league_name):
    """Analyse le HTML d'un seul bloc de match"""
    soup = BeautifulSoup(str(match_html), 'html.parser')
    
    try:
        # 1. Équipes
        team_elements = soup.select(".dashboard-game-team-info__name")
        if len(team_elements) < 2: return None
        
        home_team = team_elements[0].get_text(strip=True)
        away_team = team_elements[1].get_text(strip=True)
        
        # 2. Filtrage strict
        if any(b in home_team.lower() for b in BANNED_TEAMS) or \
           any(b in away_team.lower() for b in BANNED_TEAMS):
            return None

        # 3. Date et Heure
        date_text = soup.select_one(".dashboard-game-info__date")
        time_text = soup.select_one(".dashboard-game-info__time")
        
        start_date = date_text.get_text(strip=True) if date_text else "N/A"
        start_time = time_text.get_text(strip=True) if time_text else "N/A"
        
        # 4. ID et Lien
        link_elem = soup.select_one(".dashboard-game-block__link")
        match_url = link_elem.get('href') if link_elem else ""
        
        match_id = "N/A"
        if match_url:
            parts = match_url.split('/')
            if parts:
                last_part = parts[-1]
                match_id = last_part.split('-')[0] if '-' in last_part else last_part

        # 5. Cotes (Vérification si vide)
        odds = {"1": "-", "X": "-", "2": "-"}
        markets = soup.select(".dashboard-markets__market")
        
        for market in markets:
            btn = market.select_one(".ui-market__toggle")
            val = market.select_one(".ui-market__value")
            
            if btn and val:
                label = btn.get("aria-label")
                odd_value = val.get_text(strip=True)
                
                # On ignore si la cote est "-" ou vide
                if odd_value and odd_value != "-":
                    if label == "V1": odds["1"] = odd_value
                    elif label == "X": odds["X"] = odd_value
                    elif label == "V2": odds["2"] = odd_value

        return {
            "id": match_id,
            "league": league_name,
            "home": home_team,
            "away": away_team,
            "date": start_date,
            "time": start_time,
            "odds": odds,
            "url": match_url
        }
    except: return None

async def wait_for_data_load(page):
    """
    Attend intelligemment que les données soient chargées.
    Scrolle vers le bas pour forcer le chargement (lazy loading).
    """
    # Petit scroll pour déclencher le chargement des éléments bas de page
    await page.evaluate("window.scrollBy(0, 300)")
    await asyncio.sleep(1)
    
    # On attend que les cotes ne soient plus vides ou juste des tirets
    # On cherche un élément de cote qui contient un point (ex: 1.50)
    try:
        # On attend jusqu'à 10s qu'au moins une cote valide apparaisse
        await page.locator(".ui-market__value:text-matches('\\d+\\.\\d+')").first.wait_for(state="visible", timeout=10000)
    except:
        # Si ça timeout, c'est pas grave, on prendra ce qu'il y a
        pass

async def extract_matches_from_league(page, league_url, league_name):
    full_url = BASE_URL + league_url if not league_url.startswith("http") else league_url
    print(f"   🌍 Navigation : {league_name}")
    
    try:
        await page.goto(full_url, wait_until="domcontentloaded", timeout=60000)
        
        # 1. Attente initiale
        await asyncio.sleep(3)
        await check_and_close_popup(page)

        # 2. Attente que la liste existe
        try:
            await page.locator(".dashboard-game").first.wait_for(state="visible", timeout=20000)
        except:
            print("      ⚠️ Aucun match affiché (page vide ?).")
            return []

        # 3. Attente intelligente des DONNÉES (Cotes, Heures)
        await wait_for_data_load(page)
        
        # 4. Extraction
        match_elements = await page.locator("li.dashboard-game").all()
        matches_found = []
        
        for match_locator in match_elements:
            html = await match_locator.inner_html()
            match_data = parse_match_html(html, league_name)
            
            # On vérifie si les données sont complètes (pas de N/A critique)
            if match_data:
                # Si date/heure manquant, on essaie de ré-extraire plus tard ou on garde tel quel
                if match_data['time'] != "N/A":
                     matches_found.append(match_data)
        
        print(f"      ⚽ {len(matches_found)} matchs valides récupérés.")
        return matches_found

    except Exception as e:
        print(f"      ❌ Erreur : {e}")
        return []

async def run_scraper():
    if not os.path.exists(INPUT_FILE):
        print("❌ Fichier d'entrée manquant.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        leagues_list = json.load(f)
    
    print(f"📂 Chargement de {len(leagues_list)} championnats.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500, args=["--start-maximized"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        print("🚀 Initialisation...")
        await page.goto(BASE_URL, wait_until="domcontentloaded")
        await asyncio.sleep(5)
        await check_and_close_popup(page)

        all_matches = []

        for i, league in enumerate(leagues_list):
            matches = await extract_matches_from_league(page, league['url'], league['name'])
            all_matches.extend(matches)
            
            if i % 3 == 0:
                with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                    json.dump(all_matches, f, indent=4, ensure_ascii=False)
            
            # Pause aléatoire pour laisser le site tranquille
            await asyncio.sleep(random.uniform(4, 7))

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(all_matches, f, indent=4, ensure_ascii=False)
        
        print(f"\n🎉 TERMINÉ ! {len(all_matches)} matchs sauvegardés dans {OUTPUT_FILE}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())