import json
import os
from datetime import datetime

# --- CONFIGURATION ---
SEUIL_COTE = 1.60  # On cherche les cotes strictement inférieures à ce chiffre

# Récupération automatique du dossier d'aujourd'hui
DATE_STR = datetime.now().strftime("%Y-%m-%d")
BASE_DIR = os.path.join("match", DATE_STR)
INPUT_FILE = os.path.join(BASE_DIR, "matchs_details.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "matchs_tries_favoris.json")

def filtrer_matchs():
    # 1. Vérification de l'existence du fichier source
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Erreur : Le fichier {INPUT_FILE} n'existe pas.")
        print("   👉 Lance d'abord le scraper pour récupérer les matchs.")
        return

    print(f"📂 Lecture du fichier : {INPUT_FILE}")
    
    matchs = []
    
    # 2. Lecture sécurisée (évite le crash si le fichier est vide ou mal formé)
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                print("⚠️ Le fichier d'entrée est vide.")
                return
            matchs = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"❌ Erreur critique : Le fichier JSON est corrompu (Erreur de syntaxe).")
        print(f"   Détail : {e}")
        return

    matchs_selectionnes = []
    total_matchs = len(matchs)
    
    print(f"   🔍 Analyse de {total_matchs} matchs...")

    # 3. Boucle de filtrage
    for m in matchs:
        odds = m.get("odds", {})
        
        # On récupère les cotes en format texte
        str_v1 = odds.get("1", "-")
        str_v2 = odds.get("2", "-")

        cote_retenue = None
        pronostic = None
        equipe_favorite = None

        # --- TEST VICTOIRE DOMICILE (1) ---
        try:
            # On remplace la virgule par un point au cas où (ex: "1,20" -> "1.20")
            if isinstance(str_v1, str): str_v1 = str_v1.replace(',', '.')
            val_v1 = float(str_v1)
            
            # On vérifie si la cote est valide (> 1.0) et inférieure au seuil
            if 1.0 < val_v1 < SEUIL_COTE:
                cote_retenue = val_v1
                pronostic = "V1" # Victoire Domicile
                equipe_favorite = m['home']
        except ValueError: pass 

        # --- TEST VICTOIRE EXTÉRIEUR (2) ---
        try:
            if isinstance(str_v2, str): str_v2 = str_v2.replace(',', '.')
            val_v2 = float(str_v2)
            
            if 1.0 < val_v2 < SEUIL_COTE:
                # Si on avait déjà retenu V1, on regarde si V2 est encore plus "sûr"
                if cote_retenue is None or val_v2 < cote_retenue:
                    cote_retenue = val_v2
                    pronostic = "V2" # Victoire Extérieur
                    equipe_favorite = m['away']
        except ValueError: pass

        # 4. Si une condition est remplie, on ajoute à la liste
        if pronostic:
            match_trie = {
                "id": m.get("id", "N/A"),
                "league": m.get("league", "Inconnue"),
                "heure": m.get("time", "N/A"),
                "favori": equipe_favorite,
                "pronostic": pronostic,   # V1 ou V2
                "cote": cote_retenue,     # La valeur (ex: 1.2)
                "match_complet": f"{m['home']} vs {m['away']}",
                "url": f"https://1xbet.cm{m['url']}" if m.get('url') else "#"
            }
            matchs_selectionnes.append(match_trie)

    # 5. Sauvegarde propre
    if matchs_selectionnes:
        # Tri par heure
        matchs_selectionnes.sort(key=lambda x: x['heure'])

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            # indent=4 assure que le fichier est lisible par un humain
            # ensure_ascii=False permet d'afficher les accents correctement
            json.dump(matchs_selectionnes, f, indent=4, ensure_ascii=False)
        
        print(f"\n✅ SUCCÈS ! {len(matchs_selectionnes)} matchs trouvés avec une cote < {SEUIL_COTE}")
        print(f"📁 Sauvegardé dans : {OUTPUT_FILE}")
        
        # Aperçu
        print("\n--- Aperçu des 3 premiers matchs ---")
        for mm in matchs_selectionnes[:3]:
            print(f"⏰ {mm['heure']} | 🏆 {mm['pronostic']} ({mm['cote']}) : {mm['match_complet']}")
    else:
        print(f"\n⚠️ Aucun match trouvé avec une cote inférieure à {SEUIL_COTE} aujourd'hui.")
        # On crée quand même un fichier vide (liste vide) pour ne pas faire planter le script suivant
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)

if __name__ == "__main__":
    filtrer_matchs()