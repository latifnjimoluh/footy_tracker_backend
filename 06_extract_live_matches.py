import json
import os
from datetime import datetime

# === DATE DU JOUR ===
DATE_STR = datetime.now().strftime("%Y-%m-%d")

BASE_DIR = os.path.join("match", DATE_STR)

INPUT_FILE = os.path.join(BASE_DIR, "matchs_surveillance_final.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "live_matches.json")


def extract_live_matches():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Fichier surveillance introuvable : {INPUT_FILE}")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        matches = json.load(f)

    live_matches = []

    for m in matches:
        status = m.get("status", "UNKNOWN")
        
        # === FILTRE ===
        # On garde tout SAUF ce qui est "FINISHED" ou "UNKNOWN"
        # Donc on garde : LIVE et UPCOMING
        if status not in ["FINISHED", "UNKNOWN"]:
            live_matches.append({
                "id": m.get("id"),
                "url": m.get("url"),
                "status": status
            })

    # === TRI ===
    # On met les LIVE tout en haut de la liste (True < False n'est pas intuitif, 
    # donc x["status"] != "LIVE" renvoie False(0) pour LIVE et True(1) pour le reste -> LIVE arrive en premier)
    live_matches.sort(key=lambda x: x["status"] != "LIVE")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(live_matches, f, indent=4, ensure_ascii=False)

    print(f"✅ {len(live_matches)} matchs filtrés exportés (LIVE en tête)")
    print(f"📁 Fichier généré : {OUTPUT_FILE}")


if __name__ == "__main__":
    extract_live_matches()