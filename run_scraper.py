import time
import subprocess
import sys

def run_scraping():
    while True:
        print(f"\n[{time.strftime('%H:%M:%S')}] Démarrage du cycle de scraping...")
        # Lance ton script de scrap existant
        subprocess.run([sys.executable, "scraper.py"])
        
        print("Attente de 10 minutes avant le prochain relevé...")
        time.sleep(600) # 600 secondes = 10 minutes

if __name__ == "__main__":
    run_scraping()