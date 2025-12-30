"""
04_monitor_favoris.py
Script principal de surveillance des matchs avec détection d'opportunités.
VERSION FINALE : Avec Priorisation LIVE + Dashboard + Historique.
"""

import asyncio
import json
import os
import random
from datetime import datetime

# Import des modules du dossier monitor
from monitor.betting_logic import BettingAnalyzer
from monitor.scraper_engine import MatchScraper


# === CONFIGURATION ===
BASE_URL = "https://1xbet.cm"
DATE_STR = datetime.now().strftime("%Y-%m-%d")
BASE_DIR = os.path.join("match", DATE_STR)

# Fichiers d'entrée/sortie
INPUT_FILE = os.path.join(BASE_DIR, "matchs_tries_favoris.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "matchs_surveillance_final.json")
HISTORY_FILE = os.path.join(BASE_DIR, "matchs_history_log.jsonl")
ALERTS_FILE = os.path.join(BASE_DIR, "alertes_opportunites.json")
LIVE_FILE = os.path.join(BASE_DIR, "live_matches.json")


# Paramètres de scraping
HEADLESS_MODE = True  # True pour VPS (False pour voir sur PC)
DELAY_BETWEEN_MATCHES = (2, 4)
RESTART_BROWSER_EVERY = 120
LONG_PAUSE_EVERY = 30
LONG_PAUSE_RANGE = (60, 120)  # pause longue 1–2 min


def append_to_history(match_data):
    """Ajoute une capture (snapshot) du match dans le fichier d'historique."""
    snapshot = {
        "scan_timestamp": datetime.now().isoformat(),
        **match_data
    }
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")

def get_match_priority(match):
    """
    Calcule la priorité de scan d'un match.
    Plus le chiffre retourné est petit, plus le match sera scanné tôt.
    """
    try:
        heure_str = match.get('heure', '00:00')
        # Gestion simple des formats H:M
        if ':' in heure_str:
            h, m = map(int, heure_str.split(':'))
            now = datetime.now()
            # On crée une date match avec l'heure du json et la date d'aujourd'hui
            match_start = now.replace(hour=h, minute=m, second=0, microsecond=0)
            
            # Différence en minutes (Positif = Passé/En cours, Négatif = Futur)
            diff_minutes = (now - match_start).total_seconds() / 60
            
            # --- LOGIQUE DE TRI ---
            # 1. LIVE (Commencé entre 0 et 115 min) -> Top Priorité
            if 0 <= diff_minutes <= 115:
                return 0 
            
            # 2. IMMINENT (Commence dans moins de 15 min)
            elif -15 <= diff_minutes < 0:
                return 1
            
            # 3. FUTUR (Pas encore commencé)
            elif diff_minutes < -15:
                return 2
            
            # 4. FINI (Commencé il y a plus de 115 min)
            else:
                return 3
    except:
        return 4 # En cas d'erreur de format, on met à la fin
    
    return 4

async def monitor_matches():
    """Fonction principale de surveillance."""
    
    # === VÉRIFICATION ===
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Fichier manquant : {INPUT_FILE}")
        return
    
    # === CHARGEMENT MATCHS LIVE PRIORITAIRES ===
    live_matches = []
    if os.path.exists(LIVE_FILE):
        try:
            with open(LIVE_FILE, "r", encoding="utf-8") as f:
                live_matches = json.load(f)
                print(f"🔥 {len(live_matches)} matchs LIVE détectés (priorité absolue)")
        except:
            pass

    # === CHARGEMENT DES MATCHS CIBLES ===
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        matches_to_check = json.load(f)
    
    # === TRI INTELLIGENT (MODIFICATION DEMANDÉE) ===
    print("🔄 Réorganisation des matchs (Priorité au LIVE)...")
    matches_to_check.sort(key=get_match_priority)
    
    # === INDEX DES MATCHS NORMAUX PAR ID ===
    normal_matches_map = {
        m.get("id"): m for m in matches_to_check if m.get("id")
    }

    final_scan_queue = []

    # 1️⃣ LIVE D'ABORD
    for lm in live_matches:
        mid = lm.get("id")
        if mid and mid in normal_matches_map:
            final_scan_queue.append(normal_matches_map[mid])

    # 2️⃣ ENSUITE LE RESTE (sans doublons)
    already_added_ids = {m.get("id") for m in final_scan_queue}

    for m in matches_to_check:
        mid = m.get("id")
        if mid and mid not in already_added_ids:
            final_scan_queue.append(m)
            already_added_ids.add(mid)


        matches_to_check = final_scan_queue

    
    # === CHARGEMENT DASHBOARD EXISTANT ===
    dashboard_data_map = {}
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    old_data = json.loads(content)
                    for m in old_data:
                        if m.get('id'): dashboard_data_map[m.get('id')] = m
        except: pass

    # === AFFICHAGE INFOS ===
    print(f"\n{'='*70}")
    print(f"🚀 TRACKING INTELLIGENT (LIVE FIRST)")
    print(f"{'='*70}")
    print(f"📅 Date : {DATE_STR}")
    print(f"📊 Matchs à scanner : {len(matches_to_check)}")
    print(f"👀 Dashboard : {OUTPUT_FILE}")
    print(f"{'='*70}\n")
    
    # === INITIALISATION ===
    scraper = MatchScraper(base_url=BASE_URL, headless=HEADLESS_MODE)
    analyzer = BettingAnalyzer()
    
    # Récupération alertes existantes
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, "r", encoding="utf-8") as f:
                analyzer.alerts = json.load(f)
        except: pass
    
    monitored_data = [] 
    
    try:
        # === DÉMARRAGE NAVIGATEUR (IP STICKY GÉRÉE PAR SCRAPER) ===
        # Initialiser explicitement le navigateur via le scraper
        await scraper.start()
        print("🌐 Scraper démarré")
        
        # === BOUCLE PRINCIPALE ===
        for i, match in enumerate(matches_to_check):
            # === RESTART COMPLET DU BROWSER ===
            if i > 0 and i % RESTART_BROWSER_EVERY == 0:
                print("♻️  Restart complet du navigateur (stabilité long run)")
                if hasattr(scraper, "close_session"):
                    await scraper.close_session()
                else:
                    await scraper.stop()

                await asyncio.sleep(5)  # respiration réseau
                await scraper.start()
                print("🌐 Scraper redémarré")

            # Petit indicateur visuel de priorité
            prio = get_match_priority(match)
            icon = "🔥" if prio == 0 else "⚠️" if prio == 1 else "💤" if prio == 2 else "🏁"
            
            print(f"\n{'='*70}")
            print(f"{icon} Match {i+1}/{len(matches_to_check)} : {match.get('match', 'Inconnu')} ({match.get('heure')})")
            
            # 1. SCRAPING (Avec Retry Logic du Scraper Engine)
            match_data = await scraper.extract_match_data(match)
            monitored_data.append(match_data)
            
            # 2. ANALYSE (Seulement si LIVE)
            if match_data.get("status") == "LIVE":
                opportunity = analyzer.calculate_opportunity_score(match_data)
                match_data["opportunity"] = opportunity
                
                # Gestion Alertes
                if opportunity.get("score", 0) >= 50:
                    alert_msg = analyzer.generate_alert_message(match_data, opportunity)
                    if alert_msg:
                        print(alert_msg) # Affiche en console
                        analyzer.add_alert(match_data, opportunity) # Ajoute au JSON
            else:
                match_data["opportunity"] = {}
            
            # 3. HISTORIQUE
            if match_data.get("status") != "NOT_READY":
                append_to_history(match_data)
                print(f"      📚 Historisé")

            # 4. DASHBOARD (Sauvegarde continue)
            m_id = match_data.get('id')
            if m_id:
                dashboard_data_map[m_id] = match_data
            
            final_dashboard_list = list(dashboard_data_map.values())
            # On garde le tri LIVE en premier pour le fichier de sortie aussi
            final_dashboard_list.sort(key=lambda x: (x.get("status") != "LIVE", x.get("game_time", "")))

            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(final_dashboard_list, f, indent=4, ensure_ascii=False)
            
            # Sauvegarde Alertes
            alerts = analyzer.get_alerts()
            if alerts:
                with open(ALERTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(alerts, f, indent=4, ensure_ascii=False)
            
            print(f"      ✅ Données sauvegardées")
            
            # === PAUSE LONGUE ALÉATOIRE ===
            if i > 0 and i % LONG_PAUSE_EVERY == 0:
                long_delay = random.uniform(*LONG_PAUSE_RANGE)
                print(f"🛑 Pause longue {long_delay:.0f}s (anti-blocage)")
                await asyncio.sleep(long_delay)

            # === PAUSE NORMALE ===
            if i < len(matches_to_check) - 1:
                delay = random.uniform(*DELAY_BETWEEN_MATCHES)
                await asyncio.sleep(delay)

    
    except KeyboardInterrupt:
        print("\n\n⚠️  Arrêt demandé.")
    
    except Exception as e:
        print(f"\n❌ Erreur monitor : {e}")
    
    finally:
        # Fermeture propre via la méthode du scraper
        # Si tu utilises le scraper "Sticky/Fixe", utilise close_session()
        # Sinon utilise stop()
        if hasattr(scraper, "close_session"):
            await scraper.close_session()
        else:
            await scraper.stop()
    
    # === RÉSUMÉ ===
    print(f"\n{'='*70}")
    print(f"💾 CYCLE TERMINÉ")
    
    status_counts = {}
    for m in monitored_data:
        s = m.get("status", "UNKNOWN")
        status_counts[s] = status_counts.get(s, 0) + 1
        
    print(f"📈 Stats : {status_counts}")
    print(f"🚨 Alertes : {len(analyzer.get_alerts())}")
    print(f"{'='*70}\n")


def main():
    try:
        asyncio.run(monitor_matches())
    except KeyboardInterrupt:
        print("\n👋 Bye !")

if __name__ == "__main__":
    main()