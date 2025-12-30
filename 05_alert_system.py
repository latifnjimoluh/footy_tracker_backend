"""
05_telegram_notifier.py
Script autonome qui surveille le fichier d'alertes et envoie les notifs Telegram.
CORRECTIF ANTI-SPAM : N'envoie qu'une seule fois par niveau d'alerte.
"""

import time
import json
import os
import requests
import sys
from datetime import datetime
from dotenv import load_dotenv

# 1. Chargement du fichier .env
load_dotenv()

# 2. Récupération des variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
recipients_str = os.getenv("TELEGRAM_RECIPIENTS", "")
TELEGRAM_RECIPIENTS = [x.strip() for x in recipients_str.split(",") if x.strip()]

# 4. Vérification de sécurité
if not TELEGRAM_TOKEN or not TELEGRAM_RECIPIENTS:
    print("❌ ERREUR CRITIQUE : Le fichier .env est mal configuré.")
    sys.exit()

# Dossiers et Fichiers
DATE_STR = datetime.now().strftime("%Y-%m-%d")
BASE_DIR = os.path.join("match", DATE_STR)
ALERTS_FILE = os.path.join(BASE_DIR, "alertes_opportunites.json")

# ==========================================
# 📨 FONCTIONS TELEGRAM
# ==========================================

def send_telegram_alert(message):
    """Envoie le message à TOUS les destinataires"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for chat_id in TELEGRAM_RECIPIENTS:
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        try:
            requests.post(url, json=payload, timeout=10)
            sys.stdout.write(f"      📲 Envoyé à {chat_id}\n")
        except Exception as e:
            print(f"      ❌ Erreur envoi ({chat_id}): {e}")
        time.sleep(0.2)

def format_message(alert_data):
    """Transforme les données JSON en message HTML riche"""
    match_name = alert_data.get("match", "Match Inconnu")
    score = alert_data.get("score", "N/A")
    time_game = alert_data.get("game_time", "N/A")
    
    opp = alert_data.get("opportunity", {})
    cotes = opp.get("cotes_extra", {})
    level = opp.get("niveau", "INFO")
    
    # Icônes selon le niveau
    if "ROUGE" in level or "FORT" in level: icon = "🚨"
    elif "ORANGE" in level: icon = "🔥"
    else: icon = "👀"
    
    msg = f"{icon} <b>{level}</b>\n"
    msg += f"<i>{opp.get('type', 'Opportunité')}</i>\n\n"
    msg += f"⚽ <b>{match_name}</b>\n"
    msg += f"⏱️ <b>{time_game}</b>  |  📊 Score : <b>{score}</b>\n"
    
    msg += "\n📋 <b>Analyse :</b>\n"
    for raison in opp.get("raisons", []):
        msg += f"• {raison}\n"
    
    # Cotes
    odds_msg = "\n💰 <b>Cotes Live :</b>\n"
    has_odds = False
    if cotes.get('but_match') and cotes['but_match'] != "N/A":
        odds_msg += f"• But Match : <b>@{cotes['but_match']}</b>\n"
        has_odds = True
    if cotes.get('but_favori') and cotes['but_favori'] != "N/A":
        odds_msg += f"• But Favori : <b>@{cotes['but_favori']}</b>\n"
        has_odds = True
    if has_odds: msg += odds_msg
        
    # Action
    action = opp.get("action_suggeree")
    if action:
        clean_action = action.replace("👉 PARIER :", "").strip()
        msg += f"\n🚀 <b>{clean_action}</b>\n"
    
    # Footer
    alert_time = alert_data.get('timestamp', '').split('T')[-1][:5]
    msg += f"\n🎯 Confiance: {opp.get('score')}/100 | 🕒 {alert_time}"
    return msg

# ==========================================
# 🚀 GÉNÉRATEUR DE CLÉ UNIQUE (LE CŒUR DU CORRECTIF)
# ==========================================
def generate_unique_key(alert):
    """
    Crée une signature unique pour l'alerte.
    On retire le TIMESTAMP pour éviter les doublons si le match stagne.
    """
    match = alert.get("match")
    opp = alert.get("opportunity", {})
    
    opp_type = opp.get("type", "UNKNOWN")
    niveau = opp.get("niveau", "UNKNOWN")
    action = opp.get("action_suggeree", "UNKNOWN")
    
    # La clé est composée de : MATCH + TYPE + NIVEAU + ACTION
    # Si l'un de ces éléments change, on renvoie une alerte.
    # Si tout est pareil (même si le temps passe), on ne renvoie rien.
    return f"{match}|{opp_type}|{niveau}|{action}"

# ==========================================
# 📡 BOUCLE PRINCIPALE
# ==========================================

def run_alert_system():
    print(f"\n📡 BOT TELEGRAM ACTIF (ANTI-SPAM ACTIVÉ)")
    print(f"📂 Fichier surveillé : {ALERTS_FILE}")
    print("------------------------------------------------")

    # Cache des alertes déjà envoyées (Mémoire vive)
    sent_alerts_cache = set()

    # 1. Chargement initial : On remplit le cache avec ce qui existe déjà pour ne pas spammer au démarrage
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    existing = json.loads(content)
                    for item in existing:
                        key = generate_unique_key(item)
                        sent_alerts_cache.add(key)
            print(f"ℹ️ {len(sent_alerts_cache)} anciennes alertes ignorées.")
        except: pass

    # 2. Boucle
    while True:
        if os.path.exists(ALERTS_FILE):
            try:
                # Lecture
                with open(ALERTS_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if not content:
                        time.sleep(2)
                        continue
                    alerts = json.loads(content)
                
                # Traitement
                new_alerts_count = 0
                
                # On parcourt les alertes (les plus récentes sont souvent à la fin)
                for alert in alerts:
                    # On génère la clé SANS le timestamp
                    unique_key = generate_unique_key(alert)
                    
                    # Si cette configuration exacte n'a jamais été envoyée
                    if unique_key not in sent_alerts_cache:
                        match_name = alert.get("match")
                        print(f"\n🔔 NOUVELLE ALERTE VALIDÉE : {match_name}")
                        
                        # Envoi
                        msg = format_message(alert)
                        send_telegram_alert(msg)
                        
                        # Ajout au cache pour ne plus la renvoyer
                        sent_alerts_cache.add(unique_key)
                        new_alerts_count += 1
                
                if new_alerts_count == 0:
                    # Petit print de debug optionnel pour dire "je suis vivant"
                    # sys.stdout.write(".") 
                    # sys.stdout.flush()
                    pass

            except json.JSONDecodeError:
                pass # Conflit lecture/écriture, on ignore
            except Exception as e:
                print(f"❌ Erreur : {e}")
        
        time.sleep(5)

if __name__ == "__main__":
    try:
        run_alert_system()
    except KeyboardInterrupt:
        print("\n👋 Arrêt du bot.")