import subprocess
import sys

# Liste des fichiers à exécuter dans l'ordre
scripts = ["live_tracker.py", "update_live_db.py"]

print("--- Démarrage de la boucle de scraping CONTINUE ---")

while True:
    for script in scripts:
        print(f"\n[DÉBUT] : {script}")
        
        # subprocess.run attend la fin du script avant de passer à la ligne suivante
        result = subprocess.run([sys.executable, script])
        
        if result.returncode == 0:
            print(f"[OK] : {script} terminé.")
        else:
            print(f"[ERREUR] : {script} a échoué. Relance du cycle...")
            break  # Sort de la liste des scripts pour recommencer au premier immédiatement