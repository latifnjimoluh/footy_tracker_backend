import json
import os
from datetime import datetime

# --- CONFIGURATION ---
# Seuil de la cote (1.60 comme demandé)
COTE_LIMITE = 1.60

# Chemins de fichiers (basés sur la date du jour)
DATE_STR = datetime.now().strftime("%Y-%m-%d")
BASE_DIR = os.path.join("match", DATE_STR)
INPUT_FILE = os.path.join(BASE_DIR, "matchs_details.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "favoris_1xbet.json")

def get_min_odd(match):
    """
    Récupère la cote la plus basse d'un match.
    Retourne float ou None si aucune cote valide.
    """
    odds = match.get("odds", {})
    valid_values = []
    
    # On parcourt 1, X, 2
    for key in ["1", "X", "2"]:
        val = odds.get(key)
        try:
            # Conversion en float (gère les chaines "1.45")
            # Ignore les "-", "N/A" ou vides
            f_val = float(val)
            valid_values.append(f_val)
        except (ValueError, TypeError):
            continue
            
    if valid_values:
        return min(valid_values)
    return None

def run_filter():
    print(f"📂 Dossier de travail : {BASE_DIR}")

    # 1. Vérification
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Fichier d'entrée introuvable : {INPUT_FILE}")
        return

    # 2. Chargement
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        all_matches = json.load(f)
    
    print(f"📊 Total matchs analysés : {len(all_matches)}")

    favoris = []

    # 3. Filtrage
    for match in all_matches:
        min_odd = get_min_odd(match)
        
        # Si une cote valide existe et qu'elle est <= 1.60
        if min_odd is not None and min_odd <= COTE_LIMITE:
            
            # On ajoute une petite info pratique dans le json
            match["best_odd"] = min_odd
            
            # On détermine qui est le favori pour l'affichage
            odds = match["odds"]
            try:
                if float(odds.get("1", 99)) == min_odd: match["fav_team"] = match["home"]
                elif float(odds.get("2", 99)) == min_odd: match["fav_team"] = match["away"]
                else: match["fav_team"] = "Nul"
            except: pass

            favoris.append(match)

    # 4. Tri (Optionnel : on met les plus petites cotes en premier)
    favoris.sort(key=lambda x: x["best_odd"])

    # 5. Sauvegarde
    if favoris:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(favoris, f, indent=4, ensure_ascii=False)
        
        print("\n" + "="*40)
        print(f"✅ TERMINÉ : {len(favoris)} matchs retenus (Cote <= {COTE_LIMITE})")
        print(f"📁 Sauvegardé dans : {OUTPUT_FILE}")
        print("="*40)
        
        # Aperçu des 3 premiers
        print("\n--- Top 3 des valeurs sûres ---")
        for m in favoris[:3]:
            print(f"🔥 {m['home']} vs {m['away']}")
            print(f"   👉 Favori : {m.get('fav_team')} (Cote: {m['best_odd']})")
            print(f"   🏆 Ligue : {m['league']}")
            print("-" * 20)
    else:
        print("❌ Aucun match ne correspond au critère de cote.")

if __name__ == "__main__":
    run_filter()