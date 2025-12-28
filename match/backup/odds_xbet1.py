import asyncio
import json
import os
import re
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

# --- CONFIGURATION ---
URL_1XBET = "https://1xbet.cm/fr/line/football/"
MENU_SEARCH_SELECTOR = "input.ui-search-default__input"
MODAL_SEARCH_SELECTOR = "input.games-search-modal__input"
EMPTY_RESULT_SELECTOR = ".games-search-modal-empty-block"

# ... (Le reste du DICTIONNAIRE ALIAS et des FONCTIONS DE RECHERCHE reste identique) ...
# ... (Je ne les répète pas ici pour ne pas encombrer, mais elles doivent être présentes) ...
# ... (TEAM_ALIASES, LEAGUE_ALIASES, EXCLUDED, handle_initial_setup, normalize_text, get_team_alias, is_fuzzy_match, calculate_match_score, perform_search, get_1xbet_odds, is_valid_favorite) ...

# ⚠️ Insère ici toutes les fonctions précédentes (handle_initial_setup, normalize_text, etc.) ⚠️
# ⚠️ Je remets juste les fonctions modifiées pour le dossier ci-dessous ⚠️

# --- DICTIONNAIRE ALIAS (Rappel pour contexte) ---
TEAM_ALIASES = {
    "naples": "napoli", "ssc naples": "napoli",
    "milan ac": "milan", "ac milan": "milan", "inter milan": "inter", "internazionale": "inter",
    "hellas verone": "hellas verona", "verone": "verona",
    "leeds": "leeds united", "crystal palace fc": "crystal palace", "tottenham hotspur fc": "tottenham hotspur",
    "us cremonese": "cremonese", "bologna fc": "bologna1909", "sassuolo": "sassuolo calcio",
    "atalanta bergame": "atalanta", "sporting cp": "sporting clube de portugal",
    "casa pia ac": "casa pia", "fc arouca": "arouca", "braga": "braga", "benfica lisbonne": "benfica",
    "sl benfica b": "s.l. benficaii", "academico de viseu fc": "academico de viseu",
    "pacos ferreira": "pacos de ferreira", "sc farense": "farense", "serik belediyespor": "serikspor",
    "erbaaspor": "erbaaspor", "iskenderun fk": "iskenderun fk", "1928 bucaspor": "bucaspor",
    "24erzincanspor": "24erzincanspor", "beykoz anadolu": "beykoz anadoluspor", "muglaspor": "muglaspor",
    "fc nagaworld": "nagaworld", "al-ahli sc manama": "al-ahli club manama", "sunderland afc": "sunderland",
    
    # Afrique / Asie / Amériques
    "cote d'ivoire": "ivory coast", "cameroun": "cameroon", "guinee equatoriale": "equatorial guinea",
    "soudan": "sudan", "algerie": "algeria", "maroc": "morocco", "tunisie": "tunisia", "egypte": "egypt",
    "afrique du sud": "south africa", "fc visakha": "visakha", "national police commissary": "kompong dewa",
    "haras el hodoud": "haras el hodoud", "smouha sc": "smouha", "malut united": "malut united",
    "borneo samarinda": "pusamania borneo", "persebaya surabaya": "persebaya 1927",
    "persijap": "persijap jepara", "pss sleman": "pss sleman", "persipal (babel united)": "persipal palu bu",
    "persiba": "persiba balikpapan", "esteghlal fc": "esteghlal", "gol gohar sirjan fc": "gol gohar",
    "sanat naft abadan": "sanat naft abadan", "niroye zamini tehran": "niroye zamini",
    "hapoel raanana": "hapoel raanana u19", "maccabi herzliya": "maccabi herzliya u19",
    "montego bay": "montego bay united", "mount pleasant fc": "mount pleasant academy",
    "portmore united": "portmore united", "dunbeholden fc": "dunbeholden",
    "seoul phoenix": "seoul phoenix", "kedah fa": "kedah", "fc mali coura": "mali coura",
    "usfas bamako": "usfas bamako", "as korofina": "korofina", "as uam": "as uam",
    "espoir": "espoir zinder", "enyimba fc": "enyimba international", "kun khalifat": "kun khalifat",
    "katsina united fc": "katsina united", "niger tornadoes": "niger tornadoes",
    "bahla club": "bahla club", "sur sc": "sur club", "al-shabab oman": "al-shabab barka",
    "dhofar club": "dhofar", "al-sailiya": "al-sailiya", "al wakrah": "al-wakrah", "musanze": "musanze",
    "gorilla fc": "gorilla", "as dakar sacre coeur": "dakar sacre-coeur", "sonacos": "sonacos",
    "al wahda (eau)": "al-wahda abu dhabi", "khor fakkan club": "khor fakkan", "al-nasr dubai csc": "al nasr dubai",
    "fatih vatan spor": "fatih vatan spor (femmes)", "1207 antalyaspor kadin fk": "1207 antalyaspor (femmes)",
    "prolift giresun sanayspor": "giresun sanayispor (femmes)", "trabzonspor as": "trabzonspor (femmes)",
    "cekmekoy bilgidoga sportif": "cekmekoy bilgidoga (femmes)", "besiktas": "besiktas (femmes)",
    "galatasaray istanbul": "galatasaray"
}

LEAGUE_ALIASES = {
    "primeira liga": ["primeira liga", "liga portugal"], "premier league": ["premier league"],
    "serie a": ["serie a", "italie. serie a"], "coupe d'afrique": ["coupe d'afrique", "africa cup", "can"],
    "championship": ["championship"], "super coupe": ["super cup", "super ligue"], "cup": ["cup", "coupe"]
}

EXCLUDED = ['fifa', 'cyber', 'esport', 'virtual', 'vs joueur', 'equipe vs', 'srl', 'simulated', 'special', 'spéciaux']

async def handle_initial_setup(page):
    try:
        await page.wait_for_selector("div.main-content", timeout=15000)
        age_btn = page.locator(".notification-age-restriction__actions button")
        if await age_btn.is_visible(timeout=3000):
            await age_btn.click()
        close_btn = page.locator(".ico--times, .vfm__close").first
        if await close_btn.is_visible(timeout=2000):
            await close_btn.click()
    except: pass

def normalize_text(text):
    if not text: return ""
    replacements = {'é':'e', 'è':'e', 'ê':'e', 'ë':'e', 'à':'a', 'â':'a', 'î':'i', 'ï':'i', 'ç':'c'}
    text = str(text).lower() 
    for old, new in replacements.items(): text = text.replace(old, new)
    return text.strip()

def get_team_alias(name):
    norm = normalize_text(name)
    return TEAM_ALIASES.get(norm, norm)

def is_fuzzy_match(a, b, threshold=0.65):
    if a in b or b in a: return True
    return SequenceMatcher(None, a, b).ratio() > threshold

def calculate_match_score(card, match_data):
    score = 0
    details = []
    
    info_div = card.select_one(".games-search-modal-card-info__additional")
    raw_card_info = normalize_text(info_div.get_text(strip=True)) if info_div else ""
    
    main_div = card.select_one(".games-search-modal-card-info__main")
    raw_card_title = normalize_text(main_div.get_text(strip=True)) if main_div else ""
    
    link_tag = card.select_one("a.games-search-modal-card__link")
    if link_tag:
        href = link_tag.get("href", "").lower()
        if "/football/" not in href or any(x in href for x in ["tv-games", "special", "cyber"]):
            return 0, ["❌ Hors Sujet/Spécial"], raw_card_title, raw_card_info
    
    for excl in EXCLUDED:
        if excl in raw_card_title:
            return 0, [f"❌ Exclusion: {excl}"], raw_card_title, raw_card_info

    if " - " in raw_card_title: parts = raw_card_title.split(" - ")
    elif " vs " in raw_card_title: parts = raw_card_title.split(" vs ")
    else: return 0, ["❌ Format Titre Inconnu"], raw_card_title, raw_card_info
    
    if len(parts) >= 2:
        card_home, card_away = parts[0].strip(), parts[1].strip()
        target_home = get_team_alias(match_data.get("home", ""))
        target_away = get_team_alias(match_data.get("away", ""))
        
        home_match = is_fuzzy_match(target_home, card_home)
        away_match = is_fuzzy_match(target_away, card_away)
        
        inverted = False
        if not home_match and not away_match:
            home_match = is_fuzzy_match(target_home, card_away)
            away_match = is_fuzzy_match(target_away, card_home)
            if home_match or away_match: inverted = True

        if home_match and away_match:
            score += 70
            details.append(f"✅ Équipes OK ({'Inversé' if inverted else 'Direct'})")
        elif home_match:
            score += 30
            details.append(f"⚠️ 1 Équipe OK: {target_home}")
        elif away_match:
            score += 30
            details.append(f"⚠️ 1 Équipe OK: {target_away}")
        else:
            details.append(f"❌ Équipes KO ({card_home}/{card_away})")
            return 0, details, raw_card_title, raw_card_info

    target_league = normalize_text(match_data.get("league", ""))
    target_country = normalize_text(match_data.get("country", ""))
    
    league_found = False
    for key, variants in LEAGUE_ALIASES.items():
        if key in target_league:
            for v in variants:
                if normalize_text(v) in raw_card_info:
                    league_found = True
                    break
    if not league_found and target_league in raw_card_info: league_found = True
    
    if league_found: score += 30; details.append("✅ Ligue OK")
    elif target_country in raw_card_info: score += 20; details.append("✅ Pays OK")
    
    return score, details, raw_card_title, raw_card_info

async def perform_search(page, query):
    try:
        target_input = page.locator(MODAL_SEARCH_SELECTOR)
        if not await target_input.is_visible():
            target_input = page.locator(MENU_SEARCH_SELECTOR).first
        
        await target_input.click(force=True)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await target_input.type(query, delay=50)
        await page.keyboard.press("Enter")
        await asyncio.sleep(3.5)
        
        if await page.locator(EMPTY_RESULT_SELECTOR).is_visible():
            return []

        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        return soup.select(".games-search-modal-game-card")
    except: return []

async def get_1xbet_odds(page, match_data):
    odds = {"1": "NaN", "X": "NaN", "2": "NaN"}
    xbet_match_id = None
    xbet_league_id = None
    
    queries = [
        normalize_text(match_data.get("home", "")).replace(" fc", ""), 
        normalize_text(match_data.get("away", "")).replace(" fc", "")
    ]
    
    best_card, best_score, best_title, best_info = None, 0, "", ""
    
    for q_idx, q in enumerate(queries):
        if len(q) < 3: continue
        if q_idx > 0: print(f"      🔄 Tentative 2 avec : {q}")

        cards = await perform_search(page, q)
        if not cards: continue
        
        for card in cards:
            score, details, r_title, r_info = calculate_match_score(card, match_data)
            if score > best_score:
                best_score = score
                best_card = card
                best_title = r_title
                best_info = r_info
        
        if best_score >= 80: break
    
    if best_card:
        print(f"      🔎 Comparaison :")
        print(f"         Cible : {match_data.get('home')} vs {match_data.get('away')} ({match_data.get('league')})")
        print(f"         Trouvé : {best_title}")
        print(f"         Contexte : {best_info}")
    
    final_status = "NON_TROUVE"
    
    if best_card and best_score >= 60:
        final_status = "TROUVE"
        print(f"   ✅ Match validé (Score: {best_score}/100)")
        
        link_tag = best_card.select_one("a.games-search-modal-card__link")
        if link_tag:
            href = link_tag.get("href", "")
            try:
                parts = href.strip("/").split("/")
                if len(parts) >= 2:
                    match_part = parts[-1]
                    match_id_match = re.match(r'^(\d+)', match_part)
                    if match_id_match:
                        xbet_match_id = match_id_match.group(1)
                    
                    league_part = parts[-2]
                    league_id_match = re.match(r'^(\d+)', league_part)
                    if league_id_match:
                        xbet_league_id = league_id_match.group(1)
            except Exception as e:
                print(f"      ⚠️ Erreur extraction ID: {e}")

        market_items = best_card.select(".games-search-modal-game-card-markets__item")
        for item in market_items:
            n = item.select_one(".ui-market__name")
            v = item.select_one(".ui-market__value")
            if n and v:
                name = n.get_text(strip=True)
                val = v.get_text(strip=True).replace(',', '.')
                if name in odds: odds[name] = val
    else:
        if best_score > 0:
            print(f"   ❌ Rejeté (Score: {best_score})")
        else:
            print(f"   ❓ Aucun match trouvé")

    return odds, final_status, xbet_match_id, xbet_league_id

def is_valid_favorite(odds_dict, threshold=1.60):
    try:
        v1 = float(odds_dict["1"]) if odds_dict["1"] != "NaN" else 99.0
        v2 = float(odds_dict["2"]) if odds_dict["2"] != "NaN" else 99.0
        return v1 <= threshold or v2 <= threshold
    except: return False

async def run_1xbet_scraper(input_file, output_file):
    if not os.path.exists(input_file): 
        print(f"❌ Fichier source introuvable: {input_file}")
        return

    with open(input_file, "r", encoding="utf-8") as f: matches = json.load(f)
    
    # Chargement existant
    favoris_dict = {}
    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                existing_list = json.load(f)
                for item in existing_list:
                    favoris_dict[item['match_id']] = item
        except: pass

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True) 
        page = await browser.new_page()
        print("🌐 Connexion à 1xBet (Mode Silencieux)...")
        try:
            await page.goto(URL_1XBET, wait_until="domcontentloaded", timeout=60000)
            await handle_initial_setup(page)
        except: print("⚠️ Timeout initial, on continue...")

        to_process = [m for m in matches if m.get("start_time") != "FT"]
        
        for i, match in enumerate(to_process):
            m_id = match.get('match_id')
            
            # Skip si déjà complet
            if m_id in favoris_dict and "odds_1xbet" in favoris_dict[m_id]:
                continue

            print(f"\n🚀 ({i+1}/{len(to_process)}) Recherche : {match.get('home')}")
            
            match_odds, status, xb_mid, xb_lid = await get_1xbet_odds(page, match)
            
            if status == "TROUVE":
                if is_valid_favorite(match_odds, 1.60):
                    match["odds_1xbet"] = match_odds
                    match["1xbet_id"] = xb_mid
                    match["1xbet_league_id"] = xb_lid
                    
                    favoris_dict[m_id] = match 
                    
                    print(f"   💰 Cotes OK: {match_odds['1']} | {match_odds['2']} (MatchID: {xb_mid}, LeagueID: {xb_lid})")
                    
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(list(favoris_dict.values()), f, indent=4, ensure_ascii=False)
                    print(f"   💾 Sauvegardé.")
                else:
                    print(f"   ❌ Cotes trop hautes")
            
            await asyncio.sleep(1)

        await browser.close()

if __name__ == "__main__":
    # --- GESTION DES DOSSIERS ---
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Chemin vers le dossier "match/AAAA-MM-JJ"
    base_dir = os.path.join("match", today_str)
    
    # Chemins des fichiers
    input_file = os.path.join(base_dir, "matchs_du_jour.json")
    output_file = os.path.join(base_dir, "fav1.json")
    
    print(f"📂 Dossier de travail : {base_dir}")
    asyncio.run(run_1xbet_scraper(input_file, output_file))