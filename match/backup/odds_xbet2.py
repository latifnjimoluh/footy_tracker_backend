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

# --- DICTIONNAIRE ALIAS ---
TEAM_ALIASES = {
    # Europe
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
    """Gère le démarrage et les popups"""
    print("   🧹 Initialisation et nettoyage...")
    try:
        # Restriction âge
        age_button = page.locator(".notification-age-restriction__actions button")
        if await age_button.is_visible(timeout=5000):
            await age_button.click()
            await asyncio.sleep(0.5)
            
        # Fermeture générique de modales (Escape est souvent efficace)
        await page.keyboard.press("Escape")
        
        # Clic spécifique sur les boutons de fermeture de modales (vfm)
        close_btns = page.locator(".vfm__container .close, .vfm__close, button[aria-label='Close']")
        if await close_btns.count() > 0:
            if await close_btns.first.is_visible():
                await close_btns.first.click(force=True)
                
    except Exception as e:
        print(f"   ⚠️ Petit souci au setup (non bloquant): {e}")

def normalize_text(text):
    """Normalise le texte pour comparaison (minuscules, sans accents)"""
    if not text: return ""
    replacements = {
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'à': 'a', 'â': 'a', 'ä': 'a',
        'ô': 'o', 'ö': 'o',
        'ù': 'u', 'û': 'u', 'ü': 'u',
        'î': 'i', 'ï': 'i',
        'ç': 'c'
    }
    # Force conversion to string to avoid AttributeValueList error
    text = str(text).lower()
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def get_team_alias(name):
    norm = normalize_text(name)
    return TEAM_ALIASES.get(norm, norm)

def is_fuzzy_match(a, b, threshold=0.65):
    if a in b or b in a: return True
    return SequenceMatcher(None, a, b).ratio() > threshold

def calculate_match_score(card, match_data):
    """ Système de scoring (Code original conservé) """
    score = 0
    details = []
    
    # Text extraction with normalization
    card_text = card.get_text()
    card_text_norm = normalize_text(card_text)
    
    exclusions = [
        'fifa', 'cyber', 'esport', 'virtual', 'simulated', 'srl',
        'vs joueur', 'equipe vs joueur', 'team vs player', 'joueur 1', 'joueur 2',
        'player 1', 'player 2', 'special', 'speciaux', 'cinema', 'tv games', 'jeux tele', 
        'paris speciaux', 'special bets', 'wrestling', 'wwe', 'catch', 'rugby', 'cricket', 'futsal',
        'tennis', 'basketball', 'hockey', 'baseball', 'politique', 'politics', 'weather', 'meteo', 'award', 'oscar',
        'ballon d\'or', 'ballon dor', 'transfert', 'manager', 'eurovision',
        'academy awards', 'most academy', 'box office', 'higher vs lower', 'coin flip', 'dice', 'roulette',
        'alternative', 'alternatif', 'matchs alternatifs',
    ]
    
    for excl in exclusions:
        if excl in card_text_norm:
            return 0, [f"❌ Exclusion: {excl}"]
    
    additional_span = card.select_one(".games-search-modal-card-info__additional")
    card_league = ""
    card_country = ""
    if additional_span:
        full_text = additional_span.get_text(strip=True)
        full_text = full_text.replace("Football", "").strip()
        parts = [p.strip() for p in full_text.split("  ") if p.strip()]
        
        if len(parts) >= 1:
            combined = parts[0]
            if "." in combined:
                country_part, league_part = combined.split(".", 1)
                card_country = normalize_text(country_part.strip())
                card_league = normalize_text(league_part.strip())
            else:
                card_league = normalize_text(combined)
    
    match_country = normalize_text(match_data.get("country", ""))
    if match_country and card_country and match_country in card_country:
        score += 30
        details.append(f"✅ Pays OK: {match_country}")
    elif match_country and card_league and match_country in card_league:
        score += 30
        details.append(f"✅ Pays OK (dans ligue): {match_country}")
    else:
        details.append(f"⚠️ Pays différent: {match_country} vs {card_country}/{card_league}")
    
    match_league = normalize_text(match_data.get("league", ""))
    league_match = False
    for main_name, variants in LEAGUE_ALIASES.items():
        if match_league in main_name or main_name in match_league:
            for variant in variants:
                if variant in card_league:
                    league_match = True
                    break
        for variant in variants:
            if variant in match_league and main_name in card_league:
                league_match = True
                break
    
    if not league_match:
        match_keywords = match_league.replace("25/26", "").replace("2025/2026", "").replace("group", "").replace("groupe", "").strip()
        card_keywords = card_league.replace("25/26", "").replace("2025/2026", "").replace("group", "").replace("groupe", "").strip()
        if len(match_keywords) > 3 and match_keywords[:4] in card_keywords:
            league_match = True
        elif len(card_keywords) > 3 and card_keywords[:4] in match_keywords:
            league_match = True
    
    if league_match:
        score += 30
        details.append(f"✅ Ligue OK: {match_league}")
    else:
        details.append(f"⚠️ Ligue différente: {match_league} vs {card_league}")
    
    home_norm = normalize_text(match_data.get("home", ""))
    away_norm = normalize_text(match_data.get("away", ""))
    
    target_home = get_team_alias(home_norm)
    target_away = get_team_alias(away_norm)

    # Clean suffixes
    for suffix in [" fc", " ac", " sc", " united", " city"]:
        target_home = target_home.replace(suffix, "")
        target_away = target_away.replace(suffix, "")
    
    main_span = card.select_one(".games-search-modal-card-info__main")
    card_match_title = normalize_text(main_span.get_text(strip=True)) if main_span else ""
    
    home_found = target_home in card_match_title
    away_found = target_away in card_match_title
    
    if home_found and away_found:
        score += 40
        details.append(f"✅ Équipes OK: {target_home} vs {target_away}")
    elif home_found or away_found:
        score += 20
        details.append(f"⚠️ Une équipe trouvée seulement")
    else:
        details.append(f"❌ Équipes non trouvées")
    
    return score, details

async def perform_search(page, query):
    try:
        # On attend activement que l'input soit prêt
        target_input = page.locator(MODAL_SEARCH_SELECTOR)
        if not await target_input.is_visible():
            target_input = page.locator(MENU_SEARCH_SELECTOR).first
        
        # Action de recherche sécurisée
        await target_input.click(force=True)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await target_input.type(query, delay=100)
        await page.keyboard.press("Enter")
        await asyncio.sleep(4) # Temps de chargement réseau
        
        if await page.locator(EMPTY_RESULT_SELECTOR).is_visible():
            return []

        # Scroll logic
        all_cards = []
        for scroll_attempt in range(3):
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            cards = soup.select(".games-search-modal-game-card")
            all_cards.extend(cards)
            
            try:
                modal_list = page.locator(".games-search-modal-results__list").first
                if await modal_list.is_visible():
                    await modal_list.evaluate("el => el.scrollBy(0, 1000)")
                    await asyncio.sleep(1.5)
            except:
                break
        
        # Deduplicate
        seen_hrefs = set()
        unique_cards = []
        for card in all_cards:
            href = card.find("a")
            if href and href.get("href"):
                if href.get("href") not in seen_hrefs:
                    seen_hrefs.add(href.get("href"))
                    unique_cards.append(card)
        
        return unique_cards

    except Exception as e:
        print(f"      ⚠️ Erreur recherche: {e}")
        return []

async def get_1xbet_odds(page, match_data):
    odds = {"1": "NaN", "X": "NaN", "2": "NaN"}
    ids = {"1xbet_id": None, "1xbet_league_id": None}
    status = "NON_TROUVE"
    
    # Stratégie Double Recherche
    queries = [
        normalize_text(match_data.get("home", "")).replace(" fc", "").replace(" ac", ""), 
        normalize_text(match_data.get("away", "")).replace(" fc", "").replace(" ac", "")
    ]
    
    best_card = None
    best_score = 0
    best_details = []
    
    for q_idx, q in enumerate(queries):
        if len(q) < 3: continue
        if q_idx > 0: print(f"      🔄 Tentative 2 avec : {q}")

        cards = await perform_search(page, q)
        if not cards: continue
        
        print(f"   🔍 {len(cards)} résultats trouvés, analyse en cours...")
        
        for card in cards:
            score, details = calculate_match_score(card, match_data)
            if score > best_score:
                best_score = score
                best_card = card
                best_details = details
        
        if best_score >= 80: break
    
    # --- Extraction finale ---
    is_found = False
    if best_card and best_score >= 60:
        is_found = True
    elif best_card and best_score >= 50:
        # Fallback logic check if teams matched
        teams_ok = False
        for detail in best_details:
            if "Équipes OK" in detail:
                teams_ok = True
                break
        if teams_ok:
            is_found = True

    if is_found:
        status = "TROUVE"
        print(f"   ✅ Match validé (Score: {best_score}/100)")
        
        # 1. Extraction IDs (League ID Extraction added here)
        try:
            href_tag = best_card.find("a")
            if href_tag and href_tag.get("href"):
                href_val = href_tag.get("href")
                # Format: /fr/line/football/ID_LIGUE-slug/ID_MATCH-slug
                parts = [p for p in href_val.split('/') if p]
                
                if len(parts) >= 2:
                    match_part = parts[-1]
                    league_part = parts[-2]
                    
                    if "-" in match_part:
                        ids["1xbet_id"] = match_part.split("-")[0]
                    else:
                        ids["1xbet_id"] = match_part
                        
                    if "-" in league_part:
                        ids["1xbet_league_id"] = league_part.split("-")[0]
                    else:
                        ids["1xbet_league_id"] = league_part
                        
                print(f"   🆔 ID Match: {ids['1xbet_id']} | ID Ligue: {ids['1xbet_league_id']}")
        except Exception as e:
            print(f"   ⚠️ Impossible d'extraire les ID : {e}")

        # 2. Extraction Cotes
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
            print(f"   ❌ Rejeté (Score insuffisant: {best_score}/100)")
            for detail in best_details:
                print(f"      {detail}")
        else:
            print(f"   ❓ Aucun match trouvé")

    return odds, ids, status

def is_valid_favorite(odds_dict, threshold=1.60):
    try:
        v1 = float(odds_dict["1"]) if odds_dict["1"] != "NaN" else 99.0
        v2 = float(odds_dict["2"]) if odds_dict["2"] != "NaN" else 99.0
        return v1 <= threshold or v2 <= threshold
    except ValueError:
        return False

async def run_1xbet_scraper(input_file, output_file):
    if not os.path.exists(input_file):
        print(f"❌ Erreur : {input_file} introuvable.")
        return

    with open(input_file, "r", encoding="utf-8") as f:
        matches = json.load(f)

    # 🔥 MODE "w" = OVERWRITE TOTAL (Overwrite Mode logic applied here)
    print(f"📁 Préparation du fichier de sortie : {output_file} (Mode Remplacement)")
    # Initialize empty file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump([], f, indent=4, ensure_ascii=False)

    async with async_playwright() as p:
        # HEADLESS MODE ACTIVATED (Headless Mode logic applied here)
        browser = await p.chromium.launch(headless=True, args=["--start-maximized"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        print("🌐 Connexion à 1xBet...")
        try:
            await page.goto(URL_1XBET, wait_until="networkidle", timeout=60000)
        except:
            print("⚠️ Timeout chargement page, on continue quand même...")
            
        await handle_initial_setup(page)

        favoris_retenus = []
        matches_to_process = [m for m in matches if m.get("start_time") != "FT"]

        for match in matches_to_process:
            home = match.get('home', "")
            away = match.get('away', "")
            
            print(f"\n🚀 Recherche : {home} vs {away}")
            print(f"   📍 {match.get('country')} - {match.get('league')}")
            
            match_odds, match_ids, status = await get_1xbet_odds(page, match)
            
            if status == "TROUVE":
                if is_valid_favorite(match_odds, 1.60):
                    updated = match.copy()
                    updated["odds_1xbet"] = match_odds
                    
                    # AJOUT DES ID DANS LE JSON
                    updated["1xbet_id"] = match_ids.get("1xbet_id")
                    updated["1xbet_league_id"] = match_ids.get("1xbet_league_id")
                    
                    favoris_retenus.append(updated)
                    print(f"   💰 Cotes : {match_odds['1']} | {match_odds['X']} | {match_odds['2']}")
                    
                    # Sauvegarde progressive (Overwrite Mode logic re-applied here)
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(favoris_retenus, f, indent=4, ensure_ascii=False)
                else:
                    print(f"   ❌ Ignoré (Cote > 1.60)")
            
            await asyncio.sleep(1.5)

        await browser.close()
        print(f"\n✨ Terminé ! {len(favoris_retenus)} matchs valides stockés dans {output_file}")

if __name__ == "__main__":
    today_str = datetime.now().strftime("%Y-%m-%d")
    # Dossier match/DATE
    base_dir = os.path.join("match", today_str)
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        
    input_file = os.path.join(base_dir, "matchs_du_jour.json")
    output_file = os.path.join(base_dir, "fav2.json")
    
    asyncio.run(run_1xbet_scraper(input_file, output_file))