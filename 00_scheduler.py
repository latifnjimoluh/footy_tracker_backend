import subprocess
import time
import sys
from datetime import datetime, timedelta

# Liste des scripts à exécuter dans l'ordre
SCRIPTS = [
    "01_ids_league.py",
    "02_scrape.py",
    "03_tri_cotes.py"
]

def run_script(script_name):
    """Exécute un script python et attend qu'il finisse"""
    print(f"🔹 Lancement de {script_name}...")
    try:
        # On utilise sys.executable pour s'assurer qu'on utilise le même python (venv)
        result = subprocess.run([sys.executable, script_name], check=True)
        print(f"✅ {script_name} terminé avec succès.")
    except subprocess.CalledProcessError:
        print(f"❌ ERREUR CRITIQUE lors de l'exécution de {script_name}")
        # On ne quitte pas forcément, on veut peut-être essayer les suivants ou attendre l'heure prochaine
    except Exception as e:
        print(f"❌ Erreur inattendue : {e}")

def get_seconds_until_next_hour():
    """Calcule le nombre de secondes à attendre jusqu'à la prochaine heure pile"""
    now = datetime.now()
    # Prochaine heure : on prend l'heure actuelle + 1, et on met minutes/secondes à 0
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    seconds = (next_hour - now).total_seconds()
    return seconds

def main():
    print("🚀 DÉMARRAGE DU PLANIFICATEUR (SCHEDULER)")
    print("   Les scripts seront lancés séquentiellement chaque heure.")
    
    while True:
        start_time = datetime.now()
        print(f"\n==================================================")
        print(f"⏰ Début du cycle : {start_time.strftime('%H:%M:%S')}")
        print(f"==================================================")

        # 1. Exécution de la chaîne de scripts
        for script in SCRIPTS:
            run_script(script)
            # Petite pause de sécurité entre les scripts
            time.sleep(2)

        # 2. Calcul du temps d'attente
        wait_seconds = get_seconds_until_next_hour()
        next_run = datetime.now() + timedelta(seconds=wait_seconds)
        
        print(f"\n💤 Cycle terminé. Pause de {int(wait_seconds/60)} minutes.")
        print(f"📅 Prochain lancement prévu à : {next_run.strftime('%H:%M:%S')}")
        
        # 3. Dodo jusqu'à la prochaine heure
        time.sleep(wait_seconds)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Arrêt du planificateur.")