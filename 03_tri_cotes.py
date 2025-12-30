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

    print(f"📂 Lecture du fichier source : {INPUT_FILE}")
    
    matchs_source = []
    
    # 2. Lecture sécurisée du fichier source
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                print("⚠️ Le fichier d'entrée est vide.")
                return
            matchs_source = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"❌ Erreur critique : Le fichier JSON source est corrompu.")
        return

    matchs_candidats = []
    print(f"   🔍 Analyse de {len(matchs_source)} matchs pour trouver les favoris (< {SEUIL_COTE})...")

    # 3. Boucle de filtrage (Identification des favoris)
    for m in matchs_source:
        odds = m.get("odds", {})
        str_v1 = odds.get("1", "-")
        str_v2 = odds.get("2", "-")

        cote_retenue = None
        pronostic = None
        equipe_favorite = None

        # --- TEST VICTOIRE DOMICILE (1) ---
        try:
            if isinstance(str_v1, str): str_v1 = str_v1.replace(',', '.')
            val_v1 = float(str_v1)
            if 1.0 < val_v1 < SEUIL_COTE:
                cote_retenue = val_v1
                pronostic = "V1"
                equipe_favorite = m['home']
        except ValueError: pass 

        # --- TEST VICTOIRE EXTÉRIEUR (2) ---
        try:
            if isinstance(str_v2, str): str_v2 = str_v2.replace(',', '.')
            val_v2 = float(str_v2)
            if 1.0 < val_v2 < SEUIL_COTE:
                # Si V2 est encore plus sûr que V1 (cas rare mais possible)
                if cote_retenue is None or val_v2 < cote_retenue:
                    cote_retenue = val_v2
                    pronostic = "V2"
                    equipe_favorite = m['away']
        except ValueError: pass

        # Si c'est un favori, on prépare l'objet
        if pronostic:
            match_trie = {
                "id": m.get("id", "N/A"),
                "league": m.get("league", "Inconnue"),
                "heure": m.get("time", "N/A"),
                "favori": equipe_favorite,
                "pronostic": pronostic,   
                "cote": cote_retenue,    
                "match_complet": f"{m['home']} vs {m['away']}",
                "url": f"https://1xbet.cm{m['url']}" if m.get('url') else "#"
            }
            matchs_candidats.append(match_trie)

    # 4. LOGIQUE DE FUSION (MERGE)
    # On ne veut pas écraser, on veut ajouter.
    
    favoris_existants = []
    
    # a) Charger les favoris déjà sauvegardés s'ils existent
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    favoris_existants = json.loads(content)
        except:
            favoris_existants = []

    # b) Créer un set des IDs existants pour éviter les doublons
    ids_existants = {m['id'] for m in favoris_existants}
    
    matchs_final = favoris_existants # On commence avec la liste existante
    nouveaux_ajoutes = 0

    # c) Ajouter seulement les nouveaux
    for cand in matchs_candidats:
        if cand['id'] not in ids_existants:
            matchs_final.append(cand)
            ids_existants.add(cand['id']) # On l'ajoute au set pour le tour suivant
            nouveaux_ajoutes += 1

    # 5. Sauvegarde finale
    if matchs_final:
        # On trie TOUT le fichier par heure (anciens + nouveaux mélangés correctement)
        matchs_final.sort(key=lambda x: x['heure'])

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(matchs_final, f, indent=4, ensure_ascii=False)
        
        print(f"\n✅ SUCCÈS ! Mise à jour terminée.")
        print(f"   ➕ Nouveaux favoris ajoutés : {nouveaux_ajoutes}")
        print(f"   📂 Total dans le fichier : {len(matchs_final)}")
        print(f"   📁 Chemin : {OUTPUT_FILE}")
        
        # Aperçu des 3 premiers matchs de la liste globale
        if matchs_final:
            print("\n--- Aperçu (3 premiers matchs) ---")
            for mm in matchs_final[:3]:
                print(f"⏰ {mm['heure']} | 🏆 {mm['pronostic']} ({mm['cote']}) : {mm['match_complet']}")
    else:
        print(f"\n⚠️ Aucun favori trouvé (ni ancien, ni nouveau).")
        # On crée un fichier vide si nécessaire
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)

if __name__ == "__main__":
    filtrer_matchs()