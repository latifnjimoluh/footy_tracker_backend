import time
import json
import os
import requests
from datetime import datetime
from dotenv import load_dotenv


# 1. Chargement du fichier .env
load_dotenv()

# 2. Récupération des variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
recipients_str = os.getenv("TELEGRAM_RECIPIENTS", "")

# 3. Conversion de la chaîne "id1,id2" en liste ["id1", "id2"]
# On coupe à chaque virgule et on nettoie les espaces
TELEGRAM_RECIPIENTS = [x.strip() for x in recipients_str.split(",") if x.strip()]

# 4. Vérification de sécurité
if not TELEGRAM_TOKEN or not TELEGRAM_RECIPIENTS:
    print("❌ ERREUR CRITIQUE : Le fichier .env est mal configuré ou introuvable.")
    print("   Vérifie que TELEGRAM_TOKEN et TELEGRAM_RECIPIENTS sont bien définis.")
    exit()
    
    

# Dossiers et Fichiers
DATE_STR = datetime.now().strftime("%Y-%m-%d")
BASE_DIR = os.path.join("match", DATE_STR)
ALERTS_FILE = os.path.join(BASE_DIR, "alertes_opportunites.json")

# ==========================================
# 📨 FONCTIONS TELEGRAM MULTI-DESTINATAIRES
# ==========================================

def send_telegram_alert(message):
    """Envoie le message à TOUS les destinataires de la liste"""
    if "TON_TOKEN" in TELEGRAM_TOKEN:
        print("⚠️ ERREUR : Token manquant dans le script !")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    # Boucle sur chaque destinataire (Toi, le Canal, etc.)
    for chat_id in TELEGRAM_RECIPIENTS:
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                print(f"      📲 Envoyé avec succès à {chat_id} !")
            else:
                print(f"      ❌ Échec vers {chat_id} ({response.status_code}): {response.text}")
        
        except Exception as e:
            print(f"      ❌ Erreur connexion vers {chat_id}: {e}")
        
        # Petite pause pour respecter les limites de l'API Telegram
        time.sleep(0.5)

def format_message(alert_data):
    """Transforme les données JSON en un message Telegram percutant"""
    match = alert_data.get("match", "Match Inconnu")
    opp = alert_data.get("opportunity", {})
    
    # Icônes selon le niveau
    level = opp.get("niveau", "")
    icon = "🚨" if "ROUGE" in level else "⚠️" if "ORANGE" in level else "ℹ️"
    
    # En-tête
    msg = f"{icon} <b>{level}</b>\n"
    msg += f"<i>{opp.get('type')}</i>\n\n"
    
    # Infos Match
    msg += f"⚽ <b>{match}</b>\n"
    msg += f"📊 Score : <b>{alert_data.get('score', 'N/A')}</b>\n" # Si dispo dans le json, sinon voir note plus bas
    
    # Analyse
    msg += "\n📋 <b>Analyse :</b>\n"
    for raison in opp.get("raisons", []):
        msg += f"• {raison}\n"
    
    # --- ACTION (Zone Critique) ---
    action = opp.get("action_suggeree")
    if action:
        # On enlève le "👉 PARIER :" pour garder l'essentiel si besoin, ou on le laisse
        msg += f"\n🚀 <b>{action}</b>\n"
    
    # Conseil supplémentaire
    rec = opp.get("recommandation", "").split('\n🔥')[0] # Nettoyage doublon
    if rec:
        msg += f"\n💡 <i>{rec}</i>\n"
        
    msg += f"\n🎯 Confiance: {opp.get('score')}/100 | 🕒 {alert_data.get('timestamp', '').split('T')[1][:5]}"
    
    return msg

# ==========================================
# 🚀 BOUCLE PRINCIPALE (SURVEILLANCE)
# ==========================================

def run_alert_system():
    print(f"📡 Démarrage du SYSTEME D'ALERTE TELEGRAM (Multi-Diffusion)")
    print(f"📂 Surveillance du fichier : {ALERTS_FILE}")
    print(f"👥 Destinataires : {len(TELEGRAM_RECIPIENTS)}")
    print("------------------------------------------------")

    sent_alerts_cache = set()

    # Initialisation du cache avec l'existant (pour ne pas spammer au lancement)
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
                for item in existing:
                    opp_type = item.get('opportunity', {}).get('type', 'UNKNOWN')
                    unique_key = f"{item['match']}_{opp_type}_{item.get('timestamp')}"
                    sent_alerts_cache.add(unique_key)
            print(f"ℹ️ {len(sent_alerts_cache)} anciennes alertes ignorées.")
        except: pass

    while True:
        if os.path.exists(ALERTS_FILE):
            try:
                with open(ALERTS_FILE, "r", encoding="utf-8") as f:
                    alerts = json.load(f)
                
                for alert in alerts:
                    opp = alert.get("opportunity", {})
                    timestamp = alert.get("timestamp")
                    match_name = alert.get("match")
                    
                    unique_key = f"{match_name}_{opp.get('type')}_{timestamp}"
                    
                    if unique_key not in sent_alerts_cache:
                        print(f"\n🔔 NOUVELLE ALERTE : {match_name}")
                        
                        message_text = format_message(alert)
                        send_telegram_alert(message_text)
                        
                        sent_alerts_cache.add(unique_key)
            
            except json.JSONDecodeError:
                pass 
            except Exception as e:
                print(f"❌ Erreur lecture : {e}")
        
        time.sleep(5)

if __name__ == "__main__":
    run_alert_system()