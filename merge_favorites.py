import json
import os
from datetime import datetime

# --- CONFIGURATION ---
# Liste des fichiers à chercher dans le dossier du jour
INPUT_FILENAMES = ["fav1.json", "fav2.json", "fav3.json"] 
OUTPUT_FILENAME = "fav.json"

def load_json(filepath):
    """Charge un fichier JSON en toute sécurité"""
    if not os.path.exists(filepath):
        # On ne crie pas au loup, c'est normal si fav2 n'existe pas encore par exemple
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"❌ Erreur lecture {filepath} : {e}")
        return []

def merge_data():
    # 1. Définir le dossier de travail (Date du jour)
    today_str = datetime.now().strftime("%Y-%m-%d")
    base_dir = os.path.join("match", today_str)
    
    if not os.path.exists(base_dir):
        print(f"❌ Le dossier {base_dir} n'existe pas. Lance d'abord le collectionneur.")
        return

    output_path = os.path.join(base_dir, OUTPUT_FILENAME)
    print(f"🔄 DÉBUT DE LA FUSION dans {base_dir}...")
    
    # Dictionnaire maître : { "match_id": { ...données complètes... } }
    master_dict = {}
    
    files_processed = 0
    total_entries_read = 0

    # 2. Parcours des fichiers sources
    for filename in INPUT_FILENAMES:
        filepath = os.path.join(base_dir, filename)
        matches = load_json(filepath)
        
        if not matches: 
            continue
        
        print(f"   📂 Lecture de {filename} ({len(matches)} matchs)")
        files_processed += 1
        total_entries_read += len(matches)

        for match in matches:
            m_id = match.get("match_id")
            if not m_id: continue

            # 3. Logique de Fusion
            if m_id not in master_dict:
                # Cas A : Nouveau match, on l'ajoute au dictionnaire maître
                master_dict[m_id] = match
            else:
                # Cas B : Match déjà présent -> on enrichit !
                # .update() va ajouter les clés manquantes (ex: cotes BetPawa) à l'objet existant (ex: cotes 1xBet)
                master_dict[m_id].update(match)

    # 3. Statistiques
    matches_with_both = 0
    matches_1xbet_only = 0
    matches_betpawa_only = 0

    final_list = list(master_dict.values())

    for m in final_list:
        has_1xbet = "odds_1xbet" in m
        has_betpawa = "odds_betpawa" in m
        
        if has_1xbet and has_betpawa:
            matches_with_both += 1
        elif has_1xbet:
            matches_1xbet_only += 1
        elif has_betpawa:
            matches_betpawa_only += 1

    # 4. Sauvegarde
    if not final_list:
        print("⚠️ Aucun favori trouvé à fusionner.")
        return

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_list, f, indent=4, ensure_ascii=False)
        
        print("\n✅ FUSION TERMINÉE !")
        print(f"   📊 Total matchs uniques : {len(final_list)}")
        print(f"   💎 Matchs Complets (1xBet + BetPawa) : {matches_with_both}")
        print(f"   🔵 Matchs 1xBet seulement : {matches_1xbet_only}")
        print(f"   🟢 Matchs BetPawa seulement : {matches_betpawa_only}")
        print(f"   💾 Sauvegardé dans : {output_path}")

    except Exception as e:
        print(f"❌ Erreur écriture finale : {e}")

if __name__ == "__main__":
    merge_data()