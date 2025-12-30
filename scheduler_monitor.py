import subprocess
import time
import sys

def run_forever():
    print("🔄 Démarrage de la boucle infinie pour le Monitoring...")
    
    cycle_count = 1
    
    while True:
        print(f"\n{'='*40}")
        print(f"🎬 CYCLE N°{cycle_count}")
        print(f"{'='*40}")
        
        try:
            # 1️⃣ Exécution du monitor
            print("▶️  Lancement de 04_monitor_favoris.py ...")
            subprocess.run([sys.executable, "04_monitor_favoris.py"], check=False)
            
            # 2️⃣ Exécution du script d'extraction LIVE
            print("▶️  Lancement de 06_extract_live_matches.py ...")
            subprocess.run([sys.executable, "06_extract_live_matches.py"], check=False)
            
        except KeyboardInterrupt:
            print("\n🛑 Arrêt manuel demandé.")
            break
        except Exception as e:
            print(f"❌ Erreur système : {e}")
        
        print("\n⏳ Attente 60 secondes avant le prochain cycle...")
        time.sleep(60)  # pause 1 minute
        cycle_count += 1

if __name__ == "__main__":
    run_forever()
