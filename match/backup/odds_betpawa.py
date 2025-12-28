import asyncio
import json
import os
import urllib.parse
import re
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

# --- CONFIGURATION ---
BASE_URL = "https://www.betpawa.cm/search?searchQuery="
EVENT_SELECTOR = "div[data-test-id='bpEvent']" 
EMPTY_SELECTOR = "div.no-results"

# --- MOTS VIDES (STOP WORDS) ---
STOP_WORDS = {
    "fc", "ac", "sc", "afc", "sk", "united", "city", "club", "sports", "sport", 
    "fk", "as", "cd", "us", "women", "femmes", "u19", "u20", "u21", "u23", 
    "wanderers", "rovers", "county", "athletic", "spor", "belediye", "belediyespor"
}

# --- ALIAS ---
TEAM_ALIASES = {
    "milan ac": "milan", "inter milan": "inter", "ac milan": "milan",
    "manchester city": "man city", "manchester united": "man utd",
    "leeds": "leeds united", "tottenham hotspur fc": "tottenham",
    "sporting cp": "sporting", "academico de viseu fc": "academico viseu",
    "cote d'ivoire": "ivory coast", "cameroun": "cameroon",
    "guinee equatoriale": "equatorial guinea", "atalanta bergame": "atalanta",
    "hellas verone": "hellas verona", "verone": "verona",
    "naples": "napoli", "ssc naples": "napoli", "real betis": "betis"
}

# --- LISTE NOIRE ---
EXCLUDED_SPORTS = [
    'efootball', 'virtual', 'simulated', 'cyber', 'esport', 
    'srl', 'basketball', 'tennis', 'table tennis', 'ice hockey', 'vr'
]

def normalize_text(text):
    if not text: return ""
    replacements = {'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e', 'à': 'a', 'â': 'a', 'î': 'i', 'ï': 'i', 'ç': 'c', 'ñ': 'n'}
    text = str(text).lower()
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r'\(.*?\)', '', text)
    for suffix in [" fc", " ac", " afc", " sc", " united", " city", " wanderers", " sk"]:
        text = text.replace(suffix, "")
    return text.strip()

def get_team_alias(name):
    norm = normalize_text(name)
    return TEAM_ALIASES.get(norm, norm)

def is_fuzzy_match(a, b, threshold=0.70):
    if a in b or b in a: return True
    return SequenceMatcher(None, a, b).ratio() > threshold

def extract_id_from_url(url):
    """Extrait l'ID numérique d'une URL BetPawa"""
    if not url: return ""
    match = re.search(r'\/(\d+)', url)
    if match:
        return match.group(1)
    parts = url.split('/')
    for part in reversed(parts):
        if part.isdigit(): return part
    return ""

def calculate_match_score(card, match_data):
    score = 0
    details = []
    
    # 1. ANALYSE DU FIL D'ARIANE & ID LIGUE
    breadcrumbs_div = card.select_one("[data-test-id='eventPath']")
    
    card_info_text = ""
    league_name = "Inconnu"
    league_id = "Non trouvé"
    
    if breadcrumbs_div:
        card_info_text = normalize_text(breadcrumbs_div.get_text(strip=True))
        
        # Extraction de l'ID Ligue via les liens <a>
        links = breadcrumbs_div.select("a")
        if links:
            # Le dernier lien est généralement la ligue spécifique
            last_link = links[-1]
            league_name = last_link.get_text(strip=True)
            league_id = extract_id_from_url(last_link.get('href', ''))
            
            # Si l'ID est vide, on tente l'avant-dernier
            if not league_id and len(links) > 1:
                league_id = extract_id_from_url(links[-2].get('href', ''))
        else:
            league_name = breadcrumbs_div.get_text(strip=True)

    # 2. FILTRE SPORT
    if "football" not in card_info_text:
        if any(ex in card_info_text for ex in EXCLUDED_SPORTS):
            return 0, [f"❌ Sport exclu: {card_info_text}"], "", "", "", ""
    else:
        if any(ex in card_info_text for ex in EXCLUDED_SPORTS):
            return 0, [f"❌ eSport/Virtuel détecté: {card_info_text}"], "", "", "", ""

    # 3. NOMS EQUIPES
    team_spans = card.select(".scoreboard-period-participant-name")
    if len(team_spans) < 2:
        return 0, ["❌ Pas assez d'équipes"], "", card_info_text, "", ""
        
    card_home = normalize_text(team_spans[0].get_text(strip=True))
    card_away = normalize_text(team_spans[1].get_text(strip=True))
    
    if "(" in card_home or "(" in card_away:
        return 0, ["❌ Nom suspect"], f"{card_home} vs {card_away}", card_info_text, "", ""

    # 4. EXTRACTION ID MATCH
    match_id = "Non trouvé"
    link_elem = card.select_one("a[href*='/event/']") or card.select_one("a.event-link")
    if not link_elem:
         all_links = card.select("a")
         for l in all_links:
             if extract_id_from_url(l.get('href')):
                 link_elem = l
                 break
                 
    if link_elem:
        match_id = extract_id_from_url(link_elem.get('href'))

    # 5. COMPARAISON
    target_home = get_team_alias(match_data.get("home", ""))
    target_away = get_team_alias(match_data.get("away", ""))
    
    home_match = is_fuzzy_match(target_home, card_home)
    away_match = is_fuzzy_match(target_away, card_away)
    
    inverted = False
    if not home_match and not away_match:
        home_match = is_fuzzy_match(target_home, card_away)
        away_match = is_fuzzy_match(target_away, card_home)
        if home_match or away_match: inverted = True

    title_found = f"{card_home} vs {card_away}"

    if home_match and away_match:
        score += 70
        details.append(f"✅ Équipes OK ({'Inversé' if inverted else 'Direct'})")
    elif home_match:
        score += 30
        details.append(f"⚠️ Domicile OK ({card_home})")
    elif away_match:
        score += 30
        details.append(f"⚠️ Extérieur OK ({card_away})")
    else:
        details.append(f"❌ Équipes KO ({card_home}/{card_away})")
        return 0, details, title_found, league_name, match_id, league_id

    # 6. BONUS PAYS
    target_country = normalize_text(match_data.get("country", ""))
    if target_country in card_info_text:
        score += 30
        details.append("✅ Pays trouvé")
    
    return score, details, title_found, league_name, match_id, league_id

def generate_search_queries(home_team, away_team):
    queries = []
    h_clean = re.sub(r'\(.*?\)', '', home_team).replace(" FC", "").replace(" AC", "").strip()
    a_clean = re.sub(r'\(.*?\)', '', away_team).replace(" FC", "").replace(" AC", "").strip()
    
    queries.append(h_clean) 
    queries.append(a_clean) 
    
    if " " in h_clean:
        parts = h_clean.split(" ")
        for p in parts:
            p_clean = normalize_text(p)
            if len(p) > 2 and p_clean not in STOP_WORDS:
                queries.append(p)
                
    if " " in a_clean:
        parts = a_clean.split(" ")
        for p in parts:
            p_clean = normalize_text(p)
            if len(p) > 2 and p_clean not in STOP_WORDS:
                queries.append(p)
                
    seen = set()
    unique_queries = []
    for q in queries:
        if q not in seen and len(q) > 1:
            unique_queries.append(q)
            seen.add(q)
            
    return unique_queries

async def get_betpawa_odds(page, match_data):
    odds = {"1": "NaN", "X": "NaN", "2": "NaN"}
    queries = generate_search_queries(match_data.get("home", ""), match_data.get("away", ""))
    
    best_card = None
    best_score = 0
    best_title = ""
    best_league_name = ""
    best_league_id = ""
    best_match_id = ""
    
    for q_idx, query in enumerate(queries):
        if best_score >= 80: break 
        if q_idx > 0: print(f"      🔄 Tentative {q_idx+1}: {query}")
        
        encoded_query = urllib.parse.quote_plus(query)
        search_url = f"{BASE_URL}{encoded_query}"
        
        try:
            await page.goto(search_url, wait_until="networkidle", timeout=20000)
            try:
                await page.wait_for_selector(EVENT_SELECTOR, timeout=3000)
            except:
                continue 
            
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            cards = soup.select(EVENT_SELECTOR)
            
            for card in cards:
                score, details, r_title, r_l_name, r_m_id, r_l_id = calculate_match_score(card, match_data)
                
                if score > best_score:
                    best_score = score
                    best_card = card
                    best_title = r_title
                    best_league_name = r_l_name
                    best_league_id = r_l_id
                    best_match_id = r_m_id
                    
        except Exception as e:
            print(f"      ⚠️ Erreur réseau (Skipped): {e}")
            continue

    status = "NON_TROUVE"
    
    if best_card and best_score >= 70:
        status = "TROUVE"
        print(f"   ✅ Trouvé (Score: {best_score})")
        print(f"      Match ID: {best_match_id} | League ID: {best_league_id} ({best_league_name})")
        
        bet_wrappers = best_card.select(".event-bet-wrapper")
        for bet in bet_wrappers:
            sel_span = bet.select_one(".event-selection")
            val_span = bet.select_one(".event-odds")
            if sel_span and val_span:
                selection = sel_span.get_text(strip=True)
                value = val_span.get_text(strip=True)
                if selection in odds: odds[selection] = value
    else:
        if best_score > 0:
            print(f"   ❌ Rejeté (Score: {best_score}/100)")
        else:
            print("   ❓ Aucun match pertinent trouvé")

    return odds, status, best_match_id, best_league_id, best_league_name

def is_valid_favorite(odds_dict, threshold=1.60):
    try:
        v1 = float(odds_dict["1"]) if odds_dict["1"] != "NaN" else 99.0
        v2 = float(odds_dict["2"]) if odds_dict["2"] != "NaN" else 99.0
        return v1 <= threshold or v2 <= threshold
    except: return False

async def run_betpawa_scraper(input_file, output_file):
    if not os.path.exists(input_file):
        print(f"❌ Fichier source introuvable: {input_file}")
        return

    # Chargement existant pour mise à jour
    favoris_dict = {}
    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                existing_list = json.load(f)
                for item in existing_list:
                    favoris_dict[item['match_id']] = item
        except: pass

    with open(input_file, "r", encoding="utf-8") as f: matches = json.load(f)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-gpu", "--no-sandbox"])
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()
        page.set_default_timeout(20000)
        
        print("🌐 Démarrage du scraper BetPawa...")
        
        to_process = [m for m in matches if m.get("start_time") != "FT"]
        
        for i, match in enumerate(to_process):
            m_id = match.get('match_id')
            
            # Skip si déjà traité avec succès
            if m_id in favoris_dict and "odds_betpawa" in favoris_dict[m_id]:
                continue

            print(f"\n🚀 ({i+1}/{len(to_process)}) Recherche : {match.get('home')}")
            
            match_odds, status, bp_match_id, bp_league_id, bp_league_name = await get_betpawa_odds(page, match)
            
            if status == "TROUVE":
                if is_valid_favorite(match_odds, 1.60):
                    match["odds_betpawa"] = match_odds
                    match["betpawa_id"] = bp_match_id
                    match["betpawa_league_id"] = bp_league_id
                    match["betpawa_league_name"] = bp_league_name
                    
                    favoris_dict[m_id] = match
                    
                    print(f"   💰 Cotes: {match_odds['1']} | {match_odds['X']} | {match_odds['2']}")
                    
                    # Sauvegarde avec écrasement de la liste complète
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(list(favoris_dict.values()), f, indent=4, ensure_ascii=False)
                    print(f"   💾 Sauvegardé.")
                else:
                    print("   ❌ Cotes trop hautes (> 1.60)")
            
            await asyncio.sleep(0.5)

        await browser.close()
        print("\n✨ Terminé !")

if __name__ == "__main__":
    today_str = datetime.now().strftime("%Y-%m-%d")
    base_dir = os.path.join("match", today_str)
    
    if os.path.exists(base_dir):
        input_file = os.path.join(base_dir, "matchs_du_jour2.json")
        output_file = os.path.join(base_dir, "fav3.json")
        
        print(f"📂 Dossier de travail : {base_dir}")
        asyncio.run(run_betpawa_scraper(input_file, output_file))
    else:
        print(f"❌ Le dossier du jour {base_dir} n'existe pas. Lancez d'abord le collectionneur.")