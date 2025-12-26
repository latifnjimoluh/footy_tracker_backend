import os
import json
import subprocess
import sys
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS
from flask_apscheduler import APScheduler
from dotenv import load_dotenv; load_dotenv()

# --- INITIALISATION ---
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "https://footytracker.movie-in-the-park.com"}}, supports_credentials=True, methods=["GET", "POST", "OPTIONS"])
scheduler = APScheduler()

BASE_DIR = "scrapped_data"

# --- FONCTIONS UTILITAIRES ---

def get_latest_data(filename_pattern):
    """Lit le fichier JSON du jour selon la catégorie demandée."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(BASE_DIR, date_str, f"{date_str}_{filename_pattern}.json")
    
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Erreur de lecture JSON : {e}")
            return []
    return []

def run_scraping_task():
    """Lance le script de scraping."""
    print(f"\n🚀 [SCHEDULER] Démarrage du cycle de scraping : {datetime.now().strftime('%H:%M:%S')}")
    try:
        # Exécute scrap.py situé dans le même dossier
        subprocess.run([sys.executable, "scrap.py"])
        print(f"✅ [SCHEDULER] Cycle terminé à {datetime.now().strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution du scraping : {e}")

# --- CONFIGURATION DU SCHEDULER & AUTO-RELOAD ---

class Config:
    SCHEDULER_API_ENABLED = True

app.config.from_object(Config())

# Protection cruciale pour le mode debug (Hot Reload)
# Werkzeug lance un processus "parent" et un "enfant". 
# On ne lance le scheduler que dans l'enfant (RUN_MAIN).
if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
    scheduler.init_app(app)
    scheduler.start()
    
    # Évite d'ajouter le job plusieurs fois lors des actualisations de code
    if not scheduler.get_job('scrap_sync_job'):
        scheduler.add_job(
            id='scrap_sync_job', 
            func=run_scraping_task, 
            trigger='interval', 
            minutes=10
        )
    
    # Lancement immédiat au démarrage du serveur
    run_scraping_task()

# --- ENDPOINTS API ---

@app.route('/api/matchs/all', methods=['GET'])
def get_all_matchs():
    return jsonify(get_latest_data("matchs_complet"))

@app.route('/api/matchs/ultra', methods=['GET'])
def get_ultra_favoris():
    return jsonify(get_latest_data("ultra_favoris_1_25"))

@app.route('/api/matchs/second', methods=['GET'])
def get_second_favoris():
    return jsonify(get_latest_data("favoris_1_50"))

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({
        "status": "online",
        "time": datetime.now().strftime("%H:%M:%S"),
        "date": datetime.now().strftime("%Y-%m-%d")
    })

# --- LANCEMENT DU SERVEUR ---

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🔥 BACKEND DÉMARRÉ AVEC AUTO-RELOAD")
    print("📍 URL: http://127.0.0.1:5000")
    print("="*50 + "\n")
    
    # On active debug=True et use_reloader=True (par défaut)
    app.run(debug=True, port=5000)