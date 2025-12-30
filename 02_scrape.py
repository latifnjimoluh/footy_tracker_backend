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

# --- CONFIGURATION DATE STRICTE ---
MOIS_FR = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
    7: "juillet", 8: "août", 9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre"
}

now = datetime.now()
# Format 1 : "29/12"
TODAY_SLASH = now.strftime("%d/%m") 
# Format 2 : "29 décembre"
TODAY_LONG = f"{now.day} {MOIS_FR[now.month]}"

print(f"📅 FILTRE STRICT ACTIVÉ : On ne garde que [{TODAY_SLASH}] ou [{TODAY_LONG}]")

# Mots à bannir
BANNED_TEAMS = [
    "à domicile", "à l'extérieur", "home", "away", 
    "buts", "goals", "corner", "carton", "penalty",
    "équipe", "team", "joueur", "player", "ace", "faute",
    "first", "second", "period", "half"
]

async def handle_popup_after_nav(page):
    """ Gestion du popup après navigation """
    # print("      ⏳ Vérif popup...")
    btn_selector = ".notification-age-restriction__actions button"
    try:
        await page.locator(btn_selector).wait_for(state="visible", timeout=10000)
        await asyncio.sleep(0.5)
        await page.locator(btn_selector).click(force=True)
        try:
            await page.locator(btn_selector).wait_for(state="hidden", timeout=3000)
        except: pass
    except: pass

async def wait_for_data_load(page):
    """ Scroll et attente des cotes """
    await page.evaluate("window.scrollBy(0, 400)")
    try:
        await page.locator(".ui-market__value:text-matches('\\d+\\.\\d+')").first.wait_for(state="visible", timeout=5000)
    except: pass

def parse_match_html(match_html, league_name):
    """Analyse le HTML et filtre STRICTEMENT la date"""
    soup = BeautifulSoup(str(match_html), 'html.parser')
    
    try:
        # 1. Équipes
        team_elements = soup.select(".dashboard-game-team-info__name")
        if len(team_elements) < 2: return None
        
        home_team = team_elements[0].get_text(strip=True)
        away_team = team_elements[1].get_text(strip=True)
        
        # 2. Filtrage Mots Bannis
        if any(b in home_team.lower() for b in BANNED_TEAMS) or \
           any(b in away_team.lower() for b in BANNED_TEAMS):
            return None

        # 3. DATE ET HEURE (VÉRIFICATION STRICTE)
        date_elem = soup.select_one(".dashboard-game-info__date")
        time_elem = soup.select_one(".dashboard-game-info__time")
        
        # Récupération propre de la date
        raw_date = date_elem.get_text(strip=True) if date_elem else ""
        start_time = time_elem.get_text(strip=True) if time_elem else "N/A"
        
        # --- LOGIQUE DE FILTRAGE DATE ---
        # Si une date est présente (si vide, c'est parfois du live ou "tout de suite", on garde par prudence si time existe)
        if raw_date:
            raw_date_clean = raw_date.lower().strip()
            
            # Cas 1 : Format "29/12" (Slash détecté)
            if "/" in raw_date_clean:
                if TODAY_SLASH not in raw_date_clean:
                    return None # C'est une autre date (ex: 30/12)

            # Cas 2 : Format "29 décembre" (Pas de slash, mais texte)
            elif any(char.isalpha() for char in raw_date_clean):
                if TODAY_LONG.lower() not in raw_date_clean:
                    return None # C'est une autre date (ex: 30 décembre)
            
            # Cas 3 : Format "29.12" (Point détecté - au cas où 1xbet change)
            elif "." in raw_date_clean:
                today_dot = now.strftime("%d.%m")
                if today_dot not in raw_date_clean:
                    return None

        # 4. ID et Lien
        link_elem = soup.select_one(".dashboard-game-block__link")
        match_url = link_elem.get('href') if link_elem else ""
        
        match_id = "N/A"
        if match_url:
            parts = match_url.split('/')
            if parts:
                last_part = parts[-1]
                match_id = last_part.split('-')[0] if '-' in last_part else last_part

        # 5. Cotes
        odds = {"1": "-", "X": "-", "2": "-"}
        markets = soup.select(".dashboard-markets__market")
        
        for market in markets:
            btn = market.select_one(".ui-market__toggle")
            val = market.select_one(".ui-market__value")
            
            if btn and val:
                label = btn.get("aria-label")
                odd_value = val.get_text(strip=True)
                
                if odd_value and odd_value != "-":
                    if label == "V1": odds["1"] = odd_value
                    elif label == "X": odds["X"] = odd_value
                    elif label == "V2": odds["2"] = odd_value

        return {
            "id": match_id,
            "league": league_name,
            "home": home_team,
            "away": away_team,
            "date": raw_date if raw_date else TODAY_SLASH, # On met la date du jour si vide
            "time": start_time,
            "odds": odds,
            "url": match_url
        }
    except: return None

async def extract_matches_from_league(page, league_url, league_name):
    full_url = BASE_URL + league_url if not league_url.startswith("http") else league_url
    print(f"   🌍 Navigation : {league_name}")
    
    try:
        await page.goto(full_url, wait_until="domcontentloaded", timeout=60000)
        await handle_popup_after_nav(page)

        try:
            await page.locator(".dashboard-game").first.wait_for(state="visible", timeout=10000)
        except:
            print("      ⚠️ Aucun match détecté.")
            return []

        await wait_for_data_load(page)
        
        match_elements = await page.locator("li.dashboard-game").all()
        matches_found = []
        
        for match_locator in match_elements:
            html = await match_locator.inner_html()
            # Le filtrage de date se fait ici
            match_data = parse_match_html(html, league_name)
            
            if match_data and match_data['time'] != "N/A":
                 matches_found.append(match_data)
        
        print(f"      ⚽ {len(matches_found)} matchs valides pour AUJOURD'HUI.")
        return matches_found

    except Exception as e:
        print(f"      ❌ Erreur technique : {e}")
        return []

async def run_scraper():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Fichier d'entrée manquant : {INPUT_FILE}")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        leagues_list = json.load(f)
    
    print(f"📂 {len(leagues_list)} championnats à traiter.")

    # 1. CHARGEMENT DES DONNÉES EXISTANTES
    all_matches = []
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    all_matches = json.loads(content)
            print(f"🔄 Reprise : {len(all_matches)} matchs déjà existants chargés.")
        except Exception as e:
            print(f"⚠️ Erreur lecture fichier existant ({e}), on repart à zéro.")
            all_matches = []
    
    # Création d'un Set d'IDs pour éviter les doublons rapidement
    existing_ids = {m['id'] for m in all_matches}

    async with async_playwright() as p:
        print("🚀 Lancement...")
        browser = await p.chromium.launch(headless=True, slow_mo=500, args=["--start-maximized"])
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        print("🌐 Démarrage...")

        for i, league in enumerate(leagues_list):
            matches = await extract_matches_from_league(page, league['url'], league['name'])
            
            # 2. FUSION INTELLIGENTE (MERGE)
            added_count = 0
            for m in matches:
                # On ajoute seulement si l'ID n'est pas déjà connu
                if m['id'] not in existing_ids:
                    all_matches.append(m)
                    existing_ids.add(m['id'])
                    added_count += 1
            
            if added_count > 0:
                print(f"      ➕ {added_count} nouveaux matchs ajoutés.")

            # Sauvegarde intermédiaire (Ecrit TOUT : anciens + nouveaux)
            if i % 3 == 0:
                with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                    json.dump(all_matches, f, indent=4, ensure_ascii=False)
            
            await asyncio.sleep(random.uniform(2, 5))

        # Sauvegarde finale
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(all_matches, f, indent=4, ensure_ascii=False)
        
        print(f"\n🎉 TERMINÉ ! {len(all_matches)} matchs au total sauvegardés (Date validée : {TODAY_SLASH})")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())