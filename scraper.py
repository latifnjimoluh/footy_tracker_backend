import csv
import json
import os
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup

# --- CONFIGURATION DES CHEMINS ---
BASE_DIR = "scrapped_data"
date_du_jour = datetime.now().strftime("%Y-%m-%d")
DAILY_DIR = os.path.join(BASE_DIR, date_du_jour)
os.makedirs(DAILY_DIR, exist_ok=True)

FILENAME_JSON = os.path.join(DAILY_DIR, f"{date_du_jour}_matchs_complet.json")
ULTRA_FAV_JSON = os.path.join(DAILY_DIR, f"{date_du_jour}_ultra_favoris_1_25.json")
SECOND_FAV_JSON = os.path.join(DAILY_DIR, f"{date_du_jour}_favoris_1_50.json")

URL = "https://footystats.org/"

# --- 1. SCRAPING ---
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...")
    page = context.new_page()
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Scraping de FootyStats...")
        page.goto(URL, timeout=60000, wait_until="commit")
        page.wait_for_selector("a.match.row", timeout=20000)
        page.wait_for_timeout(3000) 
        html = page.content()
    except:
        html = page.content()
    finally:
        browser.close()

# --- 2. EXTRACTION DES DONNÉES ---
soup = BeautifulSoup(html, "lxml")
current_scraped_data = {}

# On itère sur chaque ligne de match
for match in soup.select("a.match.row"):
    try:
        # Championnat (souvent dans l'attribut data-league ou via le parent/contexte)
        # Sur FootyStats, les matchs sont groupés sous des en-têtes de ligue
        league_el = match.find_previous("div", class_="league-title")
        league_name = league_el.get_text(strip=True) if league_el else "Inconnu"

        # Heure, Équipes, Score
        heure_el = match.select_one(".timezone-convert-match-regular")
        heure = heure_el.get_text(strip=True) if heure_el else "En cours"
        
        home = match.select_one(".team.home .hover-modal-ajax-team").get_text(strip=True)
        away = match.select_one(".team.away .hover-modal-ajax-team").get_text(strip=True)
        
        score = match.select_one(".status .score").get_text(strip=True) if match.select_one(".status .score") else "0-0"
        minute = match.select_one(".status .time").get_text(strip=True) if match.select_one(".status .time") else "Pas commencé"

        # FORME (Récupère les lettres W, D, L ou les points de couleur)
        # Souvent représenté par des spans dans la colonne 'form'
        form_elements = match.select(".stat.form .form-icon")
        forme_brute = [f.get_text(strip=True) for f in form_elements if f.get_text(strip=True)]
        forme_texte = "-".join(forme_brute) if forme_brute else "N/A"

        # COTES
        odds = [o.get_text(strip=True)[:4] for o in match.select(".stat.odds > span") if o.get_text(strip=True)]
        c1 = odds[0] if len(odds) >= 1 else "N/A"
        c2 = odds[2] if len(odds) >= 3 else "N/A"

        m_id = f"{date_du_jour}_{home}_{away}".replace(" ", "_")
        
        current_scraped_data[m_id] = {
            "id": m_id,
            "championnat": league_name,
            "heure_match": heure,
            "minute": minute,
            "home": home,
            "away": away,
            "score": score,
            "forme": forme_texte,
            "cote_1": c1,
            "cote_2": c2,
            "last_update": datetime.now().strftime("%H:%M:%S")
        }
    except Exception as e:
        continue

# --- 3. SYNCHRONISATION ET CLASSEMENT ---
def sync_and_classify(file_path, data_dict, category=None):
    stored_data = {}
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                content = json.load(f)
                stored_data = {m['id']: m for m in content}
            except: pass

    for m_id, m_info in data_dict.items():
        try:
            c1 = float(m_info["cote_1"]) if m_info["cote_1"] != "N/A" else 99
            c2 = float(m_info["cote_2"]) if m_info["cote_2"] != "N/A" else 99
            min_cote = min(c1, c2)

            if category == "ULTRA":
                if min_cote >= 1.25: continue
            elif category == "SECOND":
                if not (1.25 <= min_cote <= 1.50): continue
            
            # Mise à jour (Score, Minute, Forme actualisée)
            stored_data[m_id] = m_info
        except: continue

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(list(stored_data.values()), f, ensure_ascii=False, indent=4)
    return len(stored_data)

# Sauvegardes
total_g = sync_and_classify(FILENAME_JSON, current_scraped_data)
total_u = sync_and_classify(ULTRA_FAV_JSON, current_scraped_data, category="ULTRA")
total_s = sync_and_classify(SECOND_FAV_JSON, current_scraped_data, category="SECOND")

print(f"\n✅ MISE À JOUR TERMINÉE")
print(f"🌍 Total matchs : {total_g}")
print(f"🔥 Ultra-Favoris (<1.25) : {total_u}")
print(f"⭐ Favoris Secondaires (1.25-1.50) : {total_s}")