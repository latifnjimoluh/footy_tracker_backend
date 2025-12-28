import asyncio
import json
import os
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
URL_1XBET = "https://1xbet.cm/fr/line/football"

# Création du chemin de sortie structuré : match/YYYY-MM-DD/ids_championnats_24h.json
DATE_STR = datetime.now().strftime("%Y-%m-%d")
BASE_DIR = os.path.join("match", DATE_STR)
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)
OUTPUT_FILE = os.path.join(BASE_DIR, "ids_championnats_24h.json")

async def hover_sidebar_area(page):
    viewport = page.viewport_size
    if not viewport: return
    x = 50 
    y = viewport["height"] // 2 
    print("   🖱️ Mouvement souris vers le menu (Gauche)...")
    await page.mouse.move(x, y)
    await asyncio.sleep(1)

async def step_1_handle_popup(page):
    print("\n🛑 ÉTAPE 1/4 : GESTION DU POPUP AGE")
    btn_selector = ".notification-age-restriction__actions button"

    try:
        button = page.locator(btn_selector).first
        if await button.is_visible(timeout=10000):
            print("   ✅ Popup détecté. Clic...")
            await asyncio.sleep(0.5)
            await button.click(force=True)
            try:
                await button.wait_for(state="hidden", timeout=5000)
                print("   ✅ Popup fermé.")
            except: pass
            await asyncio.sleep(3)
            return True
        else:
            print("   ℹ️ Aucun popup apparu.")
            return True
    except Exception as e:
        print(f"   ❌ Erreur Étape 1 : {e}")
        return False

async def step_2_open_sidebar(page):
    print("\n📂 ÉTAPE 2/4 : OUVERTURE DU MENU")
    await hover_sidebar_area(page)
    compact_sidebar = page.locator(".sports-menu-compact")
    
    if await compact_sidebar.is_visible():
        print("   ⚠️ Menu détecté en mode COMPACT.")
        toggle_btn = page.locator(".sports-menu-compact-template__tab").first
        
        if await toggle_btn.is_visible():
            print("   👉 Clic JS sur le bouton d'ouverture...")
            await toggle_btn.evaluate("e => e.click()")
            await asyncio.sleep(2)
            filter_selector = ".sports-menu-filter-time-trigger"
            try:
                await page.locator(filter_selector).wait_for(state="visible", timeout=10000)
                print("   ✅ Menu ouvert, filtre visible !")
                return True
            except:
                print("   ❌ Le menu semble bloqué.")
                return False
        else:
            print("   ❌ Bouton introuvable.")
            return False
    else:
        print("   ✅ Le menu est déjà ouvert.")
        return True

async def step_3_apply_filter(page):
    print("\n⏳ ÉTAPE 3/4 : APPLICATION DU FILTRE")
    trigger_selector = ".sports-menu-filter-time-trigger"
    
    try:
        trigger = page.locator(trigger_selector).first
        await trigger.wait_for(state="visible", timeout=10000)
        
        box = await trigger.bounding_box()
        if box:
            print("   🖱️ Survol du filtre...")
            await page.mouse.move(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
            await asyncio.sleep(0.5)
        
        print("   👉 Clic Filtre...")
        await trigger.click(force=True)
        await asyncio.sleep(1)

        par_jour = page.locator("text='Par jour'").first
        if await par_jour.is_visible():
            print("   👉 Clic 'Par jour'...")
            await par_jour.click(force=True)
            await asyncio.sleep(1)
            
            today = page.locator("text=\"Aujourd'hui\"").first
            if await today.is_visible():
                print("   👉 Clic 'Aujourd'hui'...")
                await today.click(force=True)
                print("   ⏳ Chargement (8s)...")
                await asyncio.sleep(8)
                return True
            else:
                print("   ❌ 'Aujourd'hui' introuvable.")
                return False
        else:
            print("   ❌ 'Par jour' introuvable.")
            return False
    except Exception as e:
        print(f"   ❌ Erreur Étape 3 : {e}")
        return False

async def step_4_extract_data(page):
    print("\n📥 ÉTAPE 4/4 : EXTRACTION & FILTRAGE")
    sidebar = page.locator(".sports-menu-main").first
    try:
        html = await sidebar.inner_html()
        soup = BeautifulSoup(html, 'html.parser')
        leagues = []
        seen = set()
        
        links = soup.select('a[href*="/line/football/"]')
        print(f"   🔍 {len(links)} liens bruts trouvés.")
        
        # Mots-clés interdits (Minuscules pour comparaison)
        BANNED_KEYWORDS = [
            'alternative', 'special', 'cyber', 'rules', 'srl', 
            'virtual', 'simulated', 'penalty', 'corner', 'carton', 
            'statist', 'buts', 'player', 'joueur', 'gagnant', 
            'long terme', 'long-term', 'ante-post', 'antepost',
            'équipe vs', 'team vs'
        ]

        for link in links:
            href = link.get('href', '').lower()
            
            # Extraction du nom pour filtrage supplémentaire
            name_tag = link.select_one(".ui-nav-link-caption__label")
            text = link.get_text(strip=True)
            clean_name = name_tag.get_text(strip=True) if name_tag else text
            clean_name_lower = clean_name.lower()
            
            # --- FILTRAGE STRICT ---
            # 1. Vérifier l'URL pour les mots interdits
            if any(ban in href for ban in BANNED_KEYWORDS):
                continue
            
            # 2. Vérifier le nom affiché pour les mots interdits
            if any(ban in clean_name_lower for ban in BANNED_KEYWORDS):
                continue

            # 3. Vérifier la structure de l'URL
            # On veut éviter /line/football/champ-id-name/match-id-name (liens de matchs directs)
            # On ne veut garder que les championnats
            parts = [p for p in href.split('/') if p]
            
            try:
                if 'football' in parts:
                    idx = parts.index('football')
                    if len(parts) > idx + 1:
                        # Le segment après football est l'ID du championnat
                        segment = parts[idx+1]
                        l_id = segment.split('-')[0] if '-' in segment else segment
                        
                        # Si l'ID est numérique et pas encore vu
                        if l_id.isdigit() and l_id not in seen:
                            
                            # On ajoute uniquement les "vrais" championnats
                            leagues.append({
                                "id": l_id,
                                "name": clean_name,
                                "url": link.get('href') # On garde l'URL originale (casse respectée)
                            })
                            seen.add(l_id)
            except: continue
            
        if leagues:
            print(f"   ✅ {len(leagues)} championnats valides (après filtrage) !")
            
            # Sauvegarde dans le dossier structuré
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(leagues, f, indent=4, ensure_ascii=False)
            
            print(f"   📁 Sauvegardé : {OUTPUT_FILE}")
            return True
        else:
            print("   ❌ Aucun championnat trouvé après filtrage.")
            return False
            
    except Exception as e:
        print(f"   ❌ Erreur extraction : {e}")
        return False

async def run_scraper():
    async with async_playwright() as p:
        print("🚀 Lancement...")
        browser = await p.chromium.launch(headless=False, slow_mo=1000, args=["--start-maximized"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        print(f"🌐 Connexion : {URL_1XBET}")
        try:
            await page.goto(URL_1XBET, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)
        except: print("⚠️ Timeout.")

        if not await step_1_handle_popup(page): return
        if not await step_2_open_sidebar(page): return
        if not await step_3_apply_filter(page): return
        if await step_4_extract_data(page): print("\n✨ TERMINÉ AVEC SUCCÈS ✨")
        
        print("Fermeture dans 10s...")
        await asyncio.sleep(10)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())