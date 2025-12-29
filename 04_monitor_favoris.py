# monitor_favoris_with_opportunities.py - Version avec Détection d'Opportunités
import asyncio
import json
import os
import time
import random
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


# --- CONFIGURATION ---
BASE_URL = "https://1xbet.cm"
DATE_STR = datetime.now().strftime("%Y-%m-%d")
BASE_DIR = os.path.join("match", DATE_STR)
INPUT_FILE = os.path.join(BASE_DIR, "matchs_tries_favoris.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "matchs_surveillance_final.json")
ALERTS_FILE = os.path.join(BASE_DIR, "alertes_opportunites.json")



# === SYSTÈME DE NOTATION D'OPPORTUNITÉ ===
def calculate_opportunity_score(match_data):
    """
    Calcule une note d'opportunité et propose une ACTION DE PARI.
    Compatible V1 et V2.
    """
    opportunity = {
        "score": 0,
        "niveau": "AUCUNE",
        "type": None,
        "raisons": [],
        "recommandation": None,
        "action_suggeree": None, # Nouveau champ explicite
        "risque": "FAIBLE"
    }
    
    # 1. Vérifications de base
    if match_data.get("status") != "LIVE": return opportunity

    # 2. Parsing des données (Robuste)
    try:
        score = match_data.get("score", "0-0")
        if "-" not in score: return opportunity
        home_score, away_score = map(int, score.replace(" ", "").split("-"))
        
        game_time = match_data.get("game_time", "00:00")
        minutes = int(game_time.split(":")[0]) if ":" in game_time else 0
        
        cote_initiale = float(match_data.get("cote", 0))
        favori = match_data.get("favori", "Favori")
        pronostic = match_data.get("pronostic", "") # "V1" ou "V2"
        
        # Cotes Live
        live_odds = match_data.get("live_odds", {})
        try: c_v1 = float(live_odds.get("V1")) 
        except: c_v1 = None
        try: c_v2 = float(live_odds.get("V2")) 
        except: c_v2 = None

    except: return opportunity

    # 3. Définition dynamique
    if pronostic == "V1":
        score_fav = home_score
        score_adv = away_score
        cote_live_fav = c_v1
        side_fav = "home"
    elif pronostic == "V2":
        score_fav = away_score
        score_adv = home_score
        cote_live_fav = c_v2
        side_fav = "away"
    else:
        return opportunity

    # =========================================================
    # 🧠 STRATÉGIE ET RECOMMANDATION
    # =========================================================

    ecart = score_adv - score_fav
    
    # --- CAS 1 : FAVORI PERDANT (LE SCÉNARIO CLASSIQUE) ---
    if score_adv > score_fav and minutes >= 20:
        opportunity["type"] = "FAVORI_PERDANT"
        opportunity["raisons"].append(f"{favori} ({pronostic}) mené {score} (Cote init: {cote_initiale})")
        
        # A. Petit écart (1 but) + Temps > 60' -> Grosse opportunité de Nul ou Victoire
        if ecart == 1 and minutes >= 60: 
            opportunity["score"] = 90
            opportunity["niveau"] = "🔴 ALERTE ROUGE"
            opportunity["risque"] = "MOYEN"
            opportunity["recommandation"] = "Le favori n'a qu'un but de retard. Pression maximale attendue."
            
            if minutes < 80:
                opportunity["action_suggeree"] = "👉 PARIER : Prochain but équipe favori (ou '1X/X2' Double Chance)"
            else:
                opportunity["action_suggeree"] = "👉 PARIER : But dans le match (Over 0.5 fin de match)"

        # B. Gros écart (2+ buts) -> Risque élevé, on vise juste UN but
        elif ecart >= 2:
            opportunity["score"] = 75
            opportunity["niveau"] = "🟠 ALERTE ORANGE"
            opportunity["risque"] = "ÉLEVÉ"
            opportunity["recommandation"] = "Écart important. Le favori va attaquer pour l'honneur."
            opportunity["action_suggeree"] = "👉 PARIER : Total Buts +0.5 ou But du Favori (si cote > 1.60)"

        # C. Ecart 1 but mais début de match (20-60') -> Value Bet
        elif ecart == 1 and 20 <= minutes < 60:
            opportunity["score"] = 85
            opportunity["niveau"] = "🔴 ALERTE ROUGE"
            opportunity["risque"] = "MOYEN"
            opportunity["recommandation"] = "Le favori a tout le temps de revenir."
            opportunity["action_suggeree"] = f"👉 PARIER : Victoire sèche du Favori (Cote boostée : {cote_live_fav})"

    # --- CAS 2 : MATCH NUL (FAVORI ACCROCHÉ) ---
    elif score_adv == score_fav and minutes >= 65:
        opportunity["type"] = "MATCH_NUL_TARDIF"
        opportunity["raisons"].append(f"Score de parité {score} à la {minutes}'")
        
        # Si la cote a bien monté
        if cote_live_fav and cote_live_fav >= 1.80:
            opportunity["score"] = 80
            opportunity["niveau"] = "🟠 ALERTE VALUE"
            opportunity["risque"] = "MOYEN"
            opportunity["recommandation"] = "Cote du favori devenue très intéressante."
            opportunity["action_suggeree"] = "👉 PARIER : Victoire Favori (Remboursé si Nul) ou But fin de match"
        else:
            opportunity["score"] = 60
            opportunity["niveau"] = "🟡 SURVEILLANCE"
            opportunity["action_suggeree"] = "Attendre que la cote monte encore"

    # --- CAS 3 : DOMINATION STATISTIQUE (LE "XG" DU PAUVRE) ---
    # On utilise les stats pour confirmer
    stats = match_data.get("stats", {})
    try:
        def get_stat(k, s): return int(stats.get(k, {}).get(s, "0")) if stats.get(k, {}).get(s, "0").isdigit() else 0
        
        att_fav = get_stat("Attaques", side_fav)
        att_adv = get_stat("Attaques", "home" if side_fav == "away" else "away")
        
        # Si le favori domine outrageusement mais ne gagne pas
        if att_fav > att_adv * 1.5 and minutes >= 50 and score_adv >= score_fav:
            opportunity["score"] += 10 # Bonus confiance
            opportunity["raisons"].append(f"🔥 Domination : {att_fav} attaques vs {att_adv}")
            if opportunity["action_suggeree"] is None:
                 opportunity["action_suggeree"] = "👉 PARIER : Prochain but du Favori"
    except: pass

    # Ajout de l'action dans le message de raisons pour l'affichage Telegram
    if opportunity["action_suggeree"]:
        opportunity["recommandation"] = f"{opportunity.get('recommandation', '')}\n🔥 <b>{opportunity['action_suggeree']}</b>"

    return opportunity


def generate_alert_message(match_data, opportunity):
    """Génère un message d'alerte optimisé pour la prise de décision"""
    if opportunity["score"] < 50:
        return None
    
    # Barre de séparation
    sep = "=" * 65
    
    message = f"\n{sep}\n"
    message += f"{opportunity['niveau']} | {opportunity['type']}\n"
    message += f"{sep}\n"
    message += f"⚽ Match : {match_data.get('match_complet', 'N/A')}\n"
    message += f"🔢 Score : {match_data.get('score', 'N/A')} ({match_data.get('game_time', 'N/A')})\n"
    message += f"📊 Confiance : {opportunity['score']}/100  |  💣 Risque : {opportunity['risque']}\n"
    
    message += f"\n🔍 ANALYSE :\n"
    for raison in opportunity["raisons"]:
        message += f"  • {raison}\n"
    
    # --- AFFICHAGE DE L'ACTION (Le plus important) ---
    if opportunity.get("action_suggeree"):
        message += f"\n🚀 ACTION SUGGÉRÉE :\n"
        message += f"   👉 {opportunity['action_suggeree']}\n"
        
    # Affichage du conseil contextuel (s'il reste du texte)
    if opportunity.get("recommandation"):
        # On nettoie pour ne pas afficher l'action en double si elle est dans la recommandation
        conseil = opportunity['recommandation'].split('\n🔥')[0] 
        if conseil:
            message += f"\n💡 Conseil : {conseil}\n"
    
    message += f"{sep}\n"
    
    return message
# === FONCTIONS DE BASE (Identiques à la version précédente) ===

# === FONCTIONS DE BASE (Identiques à la version précédente) ===

async def check_for_popup(page):
    """Ferme le popup d'âge de manière robuste avec plusieurs tentatives"""
    try:
        popup_button = page.locator(".notification-age-restriction__actions button")
        if await popup_button.is_visible(timeout=3000):
            print("      🔞 Popup d'âge détecté. Fermeture...")
            await popup_button.click(force=True)
            await asyncio.sleep(1.5)
            return True
    except:
        pass
    return False


async def continuous_popup_checker(page, duration=15):
    """Surveille et ferme les popups en continu pendant une durée donnée"""
    end_time = time.time() + duration
    popup_closed = False
    
    while time.time() < end_time:
        try:
            popup_button = page.locator(".notification-age-restriction__actions button")
            if await popup_button.is_visible(timeout=500):
                if not popup_closed:
                    print("      🔞 Popup d'âge détecté. Fermeture...")
                    popup_closed = True
                await popup_button.click(force=True)
                await asyncio.sleep(0.5)
        except:
            pass
        await asyncio.sleep(0.5)
    
    return popup_closed


async def wait_for_page_readiness(page, timeout=20000):
    """Attend que les éléments clés du scoreboard soient visibles"""
    selectors = [
        ".scoreboard-stats__body",
        ".scoreboard-countdown",
        ".game-over-loaders-progress",
        ".scoreboard-scores",
        ".ui-game-timer"
    ]
    combined_selector = ", ".join(selectors)
    try:
        await page.wait_for_selector(combined_selector, state="visible", timeout=timeout)
        await asyncio.sleep(2)
        return True
    except:
        return False


async def determine_match_status(page):
    """Détermine le statut visuel du match"""
    try:
        if await page.locator(".game-over-loaders-progress").is_visible(timeout=500):
            return "FINISHED"
        if await page.locator(".scoreboard-countdown").is_visible(timeout=500):
            return "UPCOMING"
        if await page.locator(".ui-game-timer").is_visible(timeout=500):
            return "LIVE"
    except:
        pass
    return "UNKNOWN"


def fix_url_for_live_match(url, is_live):
    """Corrige l'URL en remplaçant 'line' par 'live' ou inversement"""
    if is_live:
        if "/line/" in url:
            url = url.replace("/line/", "/live/")
            print("      🔄 URL corrigée : line → live")
    else:
        if "/live/" in url:
            url = url.replace("/live/", "/line/")
            print("      🔄 URL corrigée : live → line")
    return url


async def extract_current_score_and_time(page):
    """Extrait le score et le temps de jeu actuel depuis le DOM"""
    score_info = {"home": "0", "away": "0", "time": "00:00"}
    try:
        score_loc = page.locator(".scoreboard-scores__score")
        if await score_loc.count() >= 2:
            scores = await score_loc.all_inner_texts()
            score_info["home"] = scores[0].strip()
            score_info["away"] = scores[1].strip()
        
        time_loc = page.locator(".ui-game-timer__time")
        if await time_loc.is_visible():
            score_info["time"] = await time_loc.inner_text()
    except:
        pass
    return score_info


async def get_half_time_score(page):
    """Récupère le score de la 1ère mi-temps"""
    ht_score = {"home": None, "away": None}
    try:
        period_rows = await page.locator(".scoreboard-table-row").all()
        for row in period_rows:
            row_text = await row.inner_text()
            if "Mi-temps 1" in row_text:
                row_html = await row.inner_html()
                row_soup = BeautifulSoup(row_html, 'html.parser')
                cells = row_soup.select(".scoreboard-table-cell")
                if len(cells) >= 6:
                    ht_score["home"] = cells[4].get_text(strip=True)
                    ht_score["away"] = cells[5].get_text(strip=True)
                break
    except:
        pass
    return ht_score


async def extract_detailed_stats(page):
    """Extrait les statistiques détaillées du match"""
    stats = {}
    try:
        if await page.locator(".scoreboard-stats__body").is_visible(timeout=1000):
            stats_html = await page.inner_html(".scoreboard-stats__body")
            soup = BeautifulSoup(stats_html, 'html.parser')
            rows = soup.select(".scoreboard-list__item")
            for row in rows:
                label_el = row.select_one(".scoreboard-stats-table-view-name__label")
                if label_el:
                    label = label_el.get_text(strip=True)
                    v1 = row.select_one(".scoreboard-stats-value--team-1")
                    v2 = row.select_one(".scoreboard-stats-value--team-2")
                    if v1 and v2:
                        val1 = v1.get_text(strip=True).replace('%', '')
                        val2 = v2.get_text(strip=True).replace('%', '')
                        stats[label] = {"home": val1, "away": val2}
    except:
        pass
    return stats


def organize_totals(raw_list):
    """Organise les totaux par seuil"""
    mapped = {}
    for item in raw_list:
        threshold = item.get("P")
        type_pari = item.get("Type")
        cote = item.get("Cote")
        if threshold is not None:
            if threshold not in mapped:
                mapped[threshold] = {"Plus": "-", "Moins": "-"}
            mapped[threshold][type_pari] = cote
    
    sorted_result = []
    for threshold in sorted(mapped.keys()):
        sorted_result.append({
            "Seuil": threshold,
            "Plus": mapped[threshold]["Plus"],
            "Moins": mapped[threshold]["Moins"]
        })
    return sorted_result


def process_event_item(item, info, raw_totals_global, raw_totals_t1, raw_totals_t2):
    """Traite un élément d'événement et extrait les cotes/totaux"""
    if not isinstance(item, dict):
        return
    
    t = item.get("T")
    c = item.get("C")
    p = item.get("P")
    
    if t is None or c is None:
        return
    
    if t == 1:
        info["live_odds"]["V1"] = c
    elif t == 2:
        info["live_odds"]["X"] = c
    elif t == 3:
        info["live_odds"]["V2"] = c
    elif t == 180:
        info["live_odds"]["BTS_Oui"] = c
    elif t == 181:
        info["live_odds"]["BTS_Non"] = c
    elif t == 9 and p is not None:
        raw_totals_global.append({"P": p, "Type": "Plus", "Cote": c})
    elif t == 10 and p is not None:
        raw_totals_global.append({"P": p, "Type": "Moins", "Cote": c})
    elif t == 11 and p is not None:
        raw_totals_t1.append({"P": p, "Type": "Plus", "Cote": c})
    elif t == 12 and p is not None:
        raw_totals_t1.append({"P": p, "Type": "Moins", "Cote": c})
    elif t == 13 and p is not None:
        raw_totals_t2.append({"P": p, "Type": "Plus", "Cote": c})
    elif t == 14 and p is not None:
        raw_totals_t2.append({"P": p, "Type": "Moins", "Cote": c})


def parse_api_data(json_data):
    """Parse les données API"""
    info = {
        "current_score": None,
        "current_time": None,
        "probabilities": {},
        "live_odds": {"V1": "N/A", "V2": "N/A", "X": "N/A", "BTS_Oui": "N/A", "BTS_Non": "N/A"},
        "totals": {"global": [], "team_1": [], "team_2": []}
    }
    
    try:
        val = json_data.get("Value", {})
        
        if "SC" in val:
            sc = val["SC"]
            if "FS" in sc:
                info["current_score"] = f"{sc['FS'].get('S1', 0)}-{sc['FS'].get('S2', 0)}"
            if "TS" in sc:
                minutes = sc['TS'] // 60
                seconds = sc['TS'] % 60
                info["current_time"] = f"{minutes}:{seconds:02d}"

        if "WP" in val:
            info["probabilities"] = {
                "P1": f"{val['WP'].get('P1', 0)*100:.0f}%",
                "PX": f"{val['WP'].get('PX', 0)*100:.0f}%",
                "P2": f"{val['WP'].get('P2', 0)*100:.0f}%"
            }

        raw_totals_global, raw_totals_t1, raw_totals_t2 = [], [], []
        game_events = val.get("GE", [])
        
        for group in game_events:
            events = group.get("E", [])
            if isinstance(events, list):
                for event_group in events:
                    if isinstance(event_group, list):
                        for item in event_group:
                            process_event_item(item, info, raw_totals_global, raw_totals_t1, raw_totals_t2)
                    elif isinstance(event_group, dict):
                        process_event_item(event_group, info, raw_totals_global, raw_totals_t1, raw_totals_t2)

        info["totals"]["global"] = organize_totals(raw_totals_global)
        info["totals"]["team_1"] = organize_totals(raw_totals_t1)
        info["totals"]["team_2"] = organize_totals(raw_totals_t2)
        
    except Exception as e:
        print(f"      ⚠️ Erreur parsing API: {e}")
    
    return info


async def extract_complete_match_data(page, match_info):
    """Extraction complète des données avec analyse d'opportunité"""
    match_url = match_info.get('url', '')
    original_url = BASE_URL + match_url if not match_url.startswith("http") else match_url
    
    print(f"\n⚽ Analyse : {match_info.get('match_complet', 'Match inconnu')}")
    
    result = {
        **match_info,
        "status": "UNKNOWN",
        "timestamp": datetime.now().isoformat(),
        "last_update": datetime.now().strftime("%H:%M:%S"),
        "score": "0-0",
        "half_time_score": {"home": None, "away": None},
        "game_time": "00:00",
        "stats": {},
        "live_odds": {},
        "probabilities": {},
        "totals": {},
        "opportunity": {}  # Nouvelle clé pour l'analyse d'opportunité
    }

    captured_data = {}
    api_captured = False

    async def handle_response(response):
        nonlocal api_captured, captured_data
        if ("GetGameZip" in response.url or "GetGame" in response.url):
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    data = await response.json()
                    if "Value" in data and ("GE" in data["Value"] or "SC" in data["Value"]):
                        captured_data = data
                        api_captured = True
                        print("      📡 Données API capturées")
                except:
                    pass

    page.on("response", handle_response)

    try:
        current_url = original_url
        print(f"      🌐 Chargement: {current_url}")
        
        await page.goto(current_url, wait_until="load", timeout=60000)
        
        print("      ⏳ Surveillance des popups et chargement...")
        popup_task = asyncio.create_task(continuous_popup_checker(page, duration=15))
        
        start_wait = time.time()
        while not api_captured and time.time() - start_wait < 10:
            await asyncio.sleep(0.5)
        
        await popup_task
        print("      ✅ Page chargée et stabilisée")

        page_ready = await wait_for_page_readiness(page, timeout=20000)
        
        if not page_ready:
            status = await determine_match_status(page)
            if status == "UNKNOWN":
                result["status"] = "NOT_READY"
                return result
        else:
            status = await determine_match_status(page)
        
        result["status"] = status
        print(f"      📊 Statut initial: {status}")

        # Vérification FINISHED
        if status == "FINISHED":
            print("      🔍 Vérification en mode LIVE...")
            live_url = original_url.replace("/line/", "/live/")
            
            if live_url != current_url:
                api_captured = False
                captured_data = {}
                
                try:
                    await page.goto(live_url, wait_until="load", timeout=60000)
                    popup_task2 = asyncio.create_task(continuous_popup_checker(page, duration=12))
                    
                    start_wait = time.time()
                    while not api_captured and time.time() - start_wait < 10:
                        await asyncio.sleep(0.5)
                    
                    await popup_task2
                    
                    page_ready_live = await wait_for_page_readiness(page, timeout=20000)
                    
                    if page_ready_live:
                        status_live = await determine_match_status(page)
                        print(f"      📊 Statut en mode live: {status_live}")
                        
                        if status_live == "LIVE":
                            status = "LIVE"
                            result["status"] = "LIVE"
                            current_url = live_url
                            print("      ✅ Match LIVE détecté")
                        elif status_live == "FINISHED":
                            print("      ✅ Match confirmé terminé")
                            score_data = await extract_current_score_and_time(page)
                            result["score"] = f"{score_data['home']}-{score_data['away']}"
                            return result
                except Exception as e:
                    print(f"      ⚠️ Erreur vérification live: {e}")
                    return result

        # Correction URL si nécessaire
        url_needs_correction = False
        if status == "LIVE" and "/line/" in current_url:
            url_needs_correction = True
        elif status == "UPCOMING" and "/live/" in current_url:
            url_needs_correction = True
        
        if url_needs_correction:
            current_url = fix_url_for_live_match(current_url, status == "LIVE")
            api_captured = False
            captured_data = {}
            
            await page.goto(current_url, wait_until="load", timeout=60000)
            popup_task3 = asyncio.create_task(continuous_popup_checker(page, duration=12))
            
            start_wait = time.time()
            while not api_captured and time.time() - start_wait < 10:
                await asyncio.sleep(0.5)
            
            await popup_task3
            await wait_for_page_readiness(page, timeout=20000)
            
            status = await determine_match_status(page)
            result["status"] = status

        # Extraction selon statut
        if status == "FINISHED":
            score_data = await extract_current_score_and_time(page)
            result["score"] = f"{score_data['home']}-{score_data['away']}"
            return result

        if status == "UPCOMING":
            if api_captured:
                api_data = parse_api_data(captured_data)
                result["live_odds"] = api_data.get("live_odds", {})
                result["probabilities"] = api_data.get("probabilities", {})
                result["totals"] = api_data.get("totals", {})
            return result

        if status == "LIVE":
            score_data = await extract_current_score_and_time(page)
            result["score"] = f"{score_data['home']}-{score_data['away']}"
            result["game_time"] = score_data["time"]

            ht_score = await get_half_time_score(page)
            result["half_time_score"] = ht_score

            result["stats"] = await extract_detailed_stats(page)

            if api_captured:
                api_data = parse_api_data(captured_data)
                
                if api_data["current_score"]:
                    result["score"] = api_data["current_score"]
                if api_data["current_time"]:
                    result["game_time"] = api_data["current_time"]
                
                result["live_odds"] = api_data.get("live_odds", {})
                result["probabilities"] = api_data.get("probabilities", {})
                result["totals"] = api_data.get("totals", {})
            
            # === ANALYSE D'OPPORTUNITÉ ===
            opportunity = calculate_opportunity_score(result)
            result["opportunity"] = opportunity
            
            # Affichage
            print(f"      ⚽ Score: {result['score']} ({result['game_time']})")
            if ht_score["home"] is not None:
                print(f"      📍 HT: {ht_score['home']}-{ht_score['away']}")
            
            if opportunity["score"] >= 50:
                print(f"      {opportunity['niveau']} - Score: {opportunity['score']}/100")
                print(f"      💡 {opportunity['type']}")

        return result

    except Exception as e:
        print(f"      ❌ Erreur : {e}")
        return result
    
    finally:
        page.remove_listener("response", handle_response)


async def monitor_matches():
    """Fonction principale avec génération d'alertes"""
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Fichier manquant : {INPUT_FILE}")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        matches_to_check = json.load(f)

    print(f"🚀 TRACKING AVEC DÉTECTION D'OPPORTUNITÉS : {len(matches_to_check)} matchs")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        monitored_data = []
        alerts = []

        for i, match in enumerate(matches_to_check):
            print(f"\n{'='*70}")
            print(f"🎯 Match {i+1}/{len(matches_to_check)}")

            # Extraction complète des données pour ce match
            match_data = await extract_complete_match_data(page, match)
            monitored_data.append(match_data)

            # Générer alerte si opportunité détectée
            opportunity = match_data.get("opportunity", {})
            if opportunity.get("score", 0) >= 50:
                alert_msg = generate_alert_message(match_data, opportunity)
                if alert_msg:
                    print(alert_msg)
                    alerts.append({
                        "match": match_data.get("match_complet"),
                        "timestamp": datetime.now().isoformat(),
                        "opportunity": opportunity
                    })

            # Sauvegarde incrémentale
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(monitored_data, f, indent=4, ensure_ascii=False)

            # Sauvegarde des alertes
            if alerts:
                with open(ALERTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(alerts, f, indent=4, ensure_ascii=False)

            print(f"      ✅ Données sauvegardées")
            await asyncio.sleep(random.uniform(2, 4))

    print(f"\n{'='*70}")
    print(f"💾 Monitoring terminé !")
    print(f"📊 Total : {len(monitored_data)} matchs surveillés")
    print(f"🚨 Alertes générées : {len(alerts)}")
    
    if alerts:
        print(f"\n🔔 Fichier d'alertes : {ALERTS_FILE}")


if __name__ == "__main__":
    asyncio.run(monitor_matches())