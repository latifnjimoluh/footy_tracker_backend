import csv
import json
import os
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup

# --- CONFIGURATION DES CHEMINS ---
BASE_DIR = "scrapped_data"
date_du_jour = datetime.now().strftime("%Y-%m-%d")
# Création du dossier principal et du sous-dossier du jour
DAILY_DIR = os.path.join(BASE_DIR, date_du_jour)
os.makedirs(DAILY_DIR, exist_ok=True)

# Noms des fichiers incluant la date
FILENAME_JSON = os.path.join(DAILY_DIR, f"{date_du_jour}_matchs_data.json")
FILENAME_CSV = os.path.join(DAILY_DIR, f"{date_du_jour}_matchs_data.csv")

URL = "https://footystats.org/"

# --- 1. CONFIGURATION DU SCRAPING ---
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={'width': 1920, 'height': 1080}
    )
    page = context.new_page()
    
    try:
        print(f"Chargement de {URL}...")
        page.goto(URL, timeout=60000, wait_until="commit")
        print("Attente de l'apparition des matchs...")
        page.wait_for_selector("a.match.row", timeout=15000)
        page.wait_for_timeout(3000)
    except PlaywrightTimeoutError:
        print("⚠️ Note: Délai dépassé, tentative avec les données reçues...")

    html = page.content()
    browser.close()

# --- 2. EXTRACTION DES DONNÉES ---
soup = BeautifulSoup(html, "lxml")
new_results = []
match_elements = soup.select("a.match.row")

if not match_elements:
    print("❌ Aucun match trouvé.")
else:
    for match in match_elements:
        time_el = match.select_one(".timezone-convert-match-regular")
        home_el = match.select_one(".team.home .hover-modal-ajax-team")
        away_el = match.select_one(".team.away .hover-modal-ajax-team")
        
        heure = time_el.text.strip() if time_el else "N/A"
        home_name = home_el.text.strip() if home_el else "Inconnu"
        away_name = away_el.text.strip() if away_el else "Inconnu"
        odds_elements = match.select(".stat.odds > span")
        odds = [o.get_text(strip=True)[:4] for o in odds_elements if o.get_text(strip=True)]

        match_id = f"{date_du_jour}_{home_name}_{away_name}".replace(" ", "_")

        match_data = {
            "id": match_id,
            "date_scrap": date_du_jour,
            "heure": heure,
            "home": home_name,
            "away": away_name,
            "cote_1": odds[0] if len(odds) > 0 else "N/A",
            "cote_X": odds[1] if len(odds) > 1 else "N/A",
            "cote_2": odds[2] if len(odds) > 2 else "N/A"
        }
        new_results.append(match_data)

# --- 3. GESTION DES DOUBLONS ET SAUVEGARDE ---
existing_data = []
if os.path.exists(FILENAME_JSON):
    with open(FILENAME_JSON, 'r', encoding='utf-8') as f:
        try:
            existing_data = json.load(f)
        except json.JSONDecodeError:
            existing_data = []

existing_ids = {m['id'] for m in existing_data if 'id' in m}

added_count = 0
for m in new_results:
    if m['id'] not in existing_ids:
        existing_data.append(m)
        added_count += 1
        try:
            if m["cote_1"] != "N/A" and 2.0 <= float(m["cote_1"]) <= 2.6:
                print(f"🎯 CRITÈRE REMPLI : {m['home']} vs {m['away']} (Cote: {m['cote_1']})")
        except: pass

# --- 4. ECRITURE FINALE ---
if added_count > 0:
    # Sauvegarde JSON
    with open(FILENAME_JSON, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=4)

    # Sauvegarde CSV
    keys = existing_data[0].keys()
    with open(FILENAME_CSV, 'w', newline='', encoding='utf-8-sig') as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(existing_data)
    
    print(f"\n✅ Fichiers mis à jour dans : {DAILY_DIR}")
    print(f"📈 Matchs ajoutés : {added_count}")
else:
    print("\nℹ️ Aucun nouveau match trouvé pour ce jour.")

print(f"📁 Total pour aujourd'hui : {len(existing_data)}")