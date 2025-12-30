import asyncio
import json
import os
import re  # 👈 AJOUTÉ POUR LE NETTOYAGE DU NOM
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
URL_1XBET = "https://1xbet.cm/fr/line/football"

# Création du chemin de sortie
DATE_STR = datetime.now().strftime("%Y-%m-%d")
BASE_DIR = os.path.join("match", DATE_STR)
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)
OUTPUT_FILE = os.path.join(BASE_DIR, "ids_championnats_24h.json")

async def hover_sidebar_area(page):
    try:
        viewport = page.viewport_size
        if not viewport: return
        x = 50 
        y = viewport["height"] // 2 
        await page.mouse.move(x, y)
    except: pass

async def step_1_force_popup_close(page):
    """
    BOUCLE BLOQUANTE (Max 60s)
    """
    print("\n🛑 ÉTAPE 1 : GESTION DU POPUP")
    btn_selector = ".notification-age-restriction__actions button"
    
    attempt = 0
    max_attempts = 60 
    
    while attempt < max_attempts:
        if await page.locator(btn_selector).is_visible():
            print("   👀 Popup DÉTECTÉ ! Clic...")
            try:
                await page.locator(btn_selector).click(force=True)
                await asyncio.sleep(1)
                if not await page.locator(btn_selector).is_visible():
                    print("   ✅ Popup FERMÉ.")
                    return True
            except: pass
        else:
            if attempt % 5 == 0:
                print(f"   ⏳ En attente du popup... ({attempt}s)")
        
        await asyncio.sleep(1)
        attempt += 1

    print("   ❌ TIMEOUT Popup. On continue quand même.")
    return True 

async def step_2_open_sidebar(page):
    print("\n📂 ÉTAPE 2 : OUVERTURE DU MENU")
    await hover_sidebar_area(page)
    compact_sidebar = page.locator(".sports-menu-compact")
    try:
        await compact_sidebar.wait_for(state="attached", timeout=5000)
    except: pass

    if await compact_sidebar.is_visible():
        print("   ⚠️ Menu détecté en mode COMPACT.")
        toggle_btn = page.locator(".sports-menu-compact-template__tab").first
        if await toggle_btn.is_visible():
            print("   👉 Ouverture du menu...")
            await toggle_btn.evaluate("e => e.click()")
            await asyncio.sleep(2)
            return True
        else:
            print("   ❌ Bouton menu introuvable.")
            return False
    else:
        print("   ✅ Menu déjà ouvert (Mode Large).")
        return True

async def step_3_apply_filter(page):
    print("\n⏳ ÉTAPE 3 : APPLICATION DU FILTRE")
    trigger_selector = ".sports-menu-filter-time-trigger"
    print("   🕵️ Recherche du bouton filtre (Attente max 20s)...")
    
    try:
        trigger = page.locator(trigger_selector).first
        await trigger.wait_for(state="visible", timeout=20000)
        
        box = await trigger.bounding_box()
        if box:
            await page.mouse.move(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
        
        print("   👉 Clic sur le filtre...")
        await trigger.click(force=True)
        await asyncio.sleep(1)

        par_jour = page.locator("text='Par jour'").first
        try:
            await par_jour.wait_for(state="visible", timeout=5000)
            await par_jour.click(force=True)
            await asyncio.sleep(1)
        except: pass

        today = page.locator("text=\"Aujourd'hui\"").first
        try:
            await today.wait_for(state="visible", timeout=5000)
            print("   👉 Clic 'Aujourd'hui'...")
            await today.click(force=True)
            print("   ⏳ Chargement des données matchs (10s)...")
            await asyncio.sleep(10)
            return True
        except:
            print("   ❌ Impossible de cliquer sur 'Aujourd'hui'.")
            return False
    except Exception as e:
        print(f"   ❌ ERREUR CRITIQUE ÉTAPE 3 : {e}")
        return False

# --- NOUVELLE FONCTION POUR DÉPLIER LES MENUS ---
async def expand_all_sub_menus(page, sidebar):
    print("   📂 Déploiement des sous-menus (Pays/Ligues)...")
    
    # 1. On scrolle vers le bas de la sidebar pour forcer le chargement de tous les éléments
    try:
        # On scrolle progressivement pour déclencher le rendu
        for _ in range(3):
            await sidebar.evaluate("el => el.scrollTop = el.scrollHeight")
            await asyncio.sleep(1)
    except: pass

    # 2. On cherche les boutons "Toggle" qui ne sont PAS encore ouverts
    toggle_selector = ".sports-menu-app-champ-with-sub-champs-group__toggle"
    
    # On récupère tous les boutons toggles
    toggles = await sidebar.locator(toggle_selector).all()
    print(f"   👀 {len(toggles)} groupes détectés. Vérification ouverture...")

    count_opened = 0
    for toggle in toggles:
        try:
            # On vérifie si c'est déjà ouvert via la classe CSS
            class_attr = await toggle.get_attribute("class")
            if "ui-nav-link-toggle--is-toggled" not in class_attr:
                # Si c'est fermé, on clique pour ouvrir
                if await toggle.is_visible():
                    await toggle.click(force=True)
                    count_opened += 1
                    # Petite pause pour ne pas saturer le navigateur
                    await asyncio.sleep(0.1)
        except:
            continue
            
    if count_opened > 0:
        print(f"   ✅ {count_opened} sous-menus ouverts. Pause de stabilisation (3s)...")
        await asyncio.sleep(3)
    else:
        print("   ℹ️ Tous les menus semblaient déjà ouverts ou aucun trouvé.")


async def step_4_extract_data(page):
    print("\n📥 ÉTAPE 4 : EXTRACTION")
    sidebar = page.locator(".sports-menu-main").first
    try:
        await sidebar.wait_for(state="visible", timeout=10000)
        
        # --- DÉPLIER LES GROUPES ---
        await expand_all_sub_menus(page, sidebar)
        # ---------------------------

        html = await sidebar.inner_html()
        soup = BeautifulSoup(html, 'html.parser')
        leagues = []
        seen = set() # Pour éviter les doublons DANS la page actuelle
        
        # On cherche tous les liens qui contiennent /line/football/
        links = soup.select('a[href*="/line/football/"]')
        print(f"   🔍 {len(links)} liens trouvés au total.")
        
        # 🟢 AJOUT "mls+" DANS LA LISTE DES BANNIS
        BANNED = ['special', 'cyber', 'simulated', 'penalty', 'corner', 'carton', 'statist', 'buts', 'player', 'gagnant', 'ante-post', 'srl', 'équipe vs', 'mls+']

        for link in links:
            href = link.get('href', '').lower()
            
            # --- NETTOYAGE DU NOM ---
            # On récupère le texte brut
            raw_text = link.get_text(strip=True)
            # On utilise regex pour supprimer les chiffres à la toute fin de la chaîne
            # Ex: "Cuba. Liga de Barrios2" devient "Cuba. Liga de Barrios"
            text = re.sub(r'\d+$', '', raw_text).strip()
            
            text_lower = text.lower()
            
            # Filtrage
            if any(b in href for b in BANNED) or any(b in text_lower for b in BANNED): continue

            # Analyse URL : /fr/line/football/88637-england-premier-league
            parts = [p for p in href.split('/') if p]
            if 'football' in parts:
                try:
                    idx = parts.index('football')
                    if len(parts) > idx + 1:
                        segment = parts[idx+1]
                        # Extraction ID : 88637 de "88637-england..."
                        l_id = segment.split('-')[0]
                        
                        if l_id.isdigit() and l_id not in seen:
                            leagues.append({
                                "id": l_id, 
                                "name": text, # Nom propre nettoyé
                                "url": link.get('href')
                            })
                            seen.add(l_id)
                except: continue
            
        if leagues:
            print(f"   ✅ {len(leagues)} championnats trouvés sur la page.")
            
            # --- LOGIQUE DE FUSION (MERGE) ---
            existing_data = []
            
            # 1. Tenter de lire le fichier existant
            if os.path.exists(OUTPUT_FILE):
                try:
                    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            existing_data = json.loads(content)
                except Exception as e:
                    print(f"   ⚠️ Fichier existant corrompu ou illisible, on repart à zéro. ({e})")
                    existing_data = []

            # 2. Créer un Set des IDs existants pour une recherche rapide
            existing_ids = {item['id'] for item in existing_data}
            
            # 3. Ajouter seulement ce qui manque
            added_count = 0
            for l in leagues:
                if l['id'] not in existing_ids:
                    existing_data.append(l)
                    added_count += 1
            
            print(f"   🔄 FUSION : {added_count} nouveaux championnats ajoutés. Total dans le fichier : {len(existing_data)}")

            # 4. Sauvegarder la liste consolidée
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, indent=4, ensure_ascii=False)
            
            return True
        return False
            
    except Exception as e:
        print(f"   ❌ Erreur extraction : {e}")
        return False

async def run_scraper():
    async with async_playwright() as p:
        print("🚀 Lancement...")
        
        # 🟢 COMMENTAIRE AJOUTÉ ICI : AFFICHE LE NAVIGATEUR
        # C'est ici que l'on configure le navigateur pour qu'il soit visible (headless=False)
        browser = await p.chromium.launch(headless=True, slow_mo=200, args=["--start-maximized"])
        
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()
        
        print(f"🌐 Connexion...")
        try:
            await page.goto(URL_1XBET, wait_until="domcontentloaded", timeout=60000)
        except: pass

        await step_1_force_popup_close(page)
        if not await step_2_open_sidebar(page): return
        if not await step_3_apply_filter(page): return
        if await step_4_extract_data(page):
            print("\n✨ SUCCÈS TOTAL ✨")
        
        print("Fin dans 10s...")
        await asyncio.sleep(10)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())