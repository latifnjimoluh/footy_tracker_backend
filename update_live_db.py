import psycopg2
import json
import os
from datetime import datetime

# --- CONFIGURATION ---
DB_CONFIG = {
    "dbname": "football",
    "user": "postgres",
    "password": "Nexus2023.",
    "host": "localhost",
    "port": "5432"
}

DATE_STR = datetime.now().strftime("%Y-%m-%d")
TRACKING_FILE = os.path.join("match", DATE_STR, "live_tracking_results.json")
FAVORITES_FILE = os.path.join("match", DATE_STR, "favoris_1xbet.json")

def init_live_tables():
    """Ajoute les colonnes manquantes sans supprimer les données existantes"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # 1. S'assurer que la table de base existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS match_live_stats (
                id SERIAL PRIMARY KEY,
                match_id TEXT NOT NULL,
                status TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (match_id) REFERENCES matches (id)
            );
        """)

        # 2. Liste des colonnes à ajouter si elles n'existent pas
        # Type, Nom
        columns_to_add = [
            ("INTEGER DEFAULT 0", "score_home"),
            ("INTEGER DEFAULT 0", "score_away"),
            ("TEXT", "ht_score"),
            ("TEXT", "game_clock"),
            ("INTEGER DEFAULT 0", "attacks_home"),
            ("INTEGER DEFAULT 0", "attacks_away"),
            ("INTEGER DEFAULT 0", "dangerous_attacks_home"),
            ("INTEGER DEFAULT 0", "dangerous_attacks_away"),
            ("INTEGER DEFAULT 0", "possession_home"),
            ("INTEGER DEFAULT 0", "possession_away"),
            ("INTEGER DEFAULT 0", "shots_on_target_home"),
            ("INTEGER DEFAULT 0", "shots_on_target_away"),
            ("INTEGER DEFAULT 0", "corners_home"),
            ("INTEGER DEFAULT 0", "corners_away"),
            ("TEXT", "probabilities")
        ]

        for col_type, col_name in columns_to_add:
            cur.execute(f"""
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name='match_live_stats' AND column_name='{col_name}') THEN
                        ALTER TABLE match_live_stats ADD COLUMN {col_name} {col_type};
                    END IF;
                END $$;
            """)
        
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Structure de la base de données vérifiée et mise à jour (sans perte).")
    except Exception as e:
        print(f"❌ Erreur Migration : {e}")

def clean_int(val):
    if val is None or val == "" or val == "-": return 0
    try:
        return int(str(val).replace('%', '').strip())
    except: return 0

def update_all():
    if not os.path.exists(TRACKING_FILE) or not os.path.exists(FAVORITES_FILE):
        print(f"❌ Fichiers JSON manquants.")
        return

    try:
        with open(TRACKING_FILE, "r", encoding="utf-8") as f:
            tracking_results = json.load(f)
        with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
            favorites_data = json.load(f)

        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        status_map = {str(item['id']): item['status'] for item in tracking_results}

        print(f"🔄 Insertion de {len(tracking_results)} nouveaux points d'historique...")

        for entry in tracking_results:
            m_id = str(entry['id'])
            status = entry['status']
            data = entry.get('data', {})
            
            score = entry.get('score', {"home": 0, "away": 0})
            ht_data = entry.get('half_time_score', {"home": None, "away": None})
            game_time = entry.get('game_time', "00:00")
            
            ht_score_str = f"{ht_data['home']}-{ht_data['away']}" if ht_data.get('home') is not None else None

            # 1. Update Table principale (Statut actuel du match)
            cur.execute("UPDATE matches SET status = %s WHERE id = %s", (status, m_id))

            # 2. Insertion d'une NOUVELLE ligne d'historique (Snapshot)
            # On insère une nouvelle ligne à chaque fois, l'ID auto-incrémenté gère l'ordre
            if status == "LIVE":
                cur.execute("""
                    INSERT INTO match_live_stats 
                    (match_id, status, score_home, score_away, ht_score, game_clock,
                     attacks_home, attacks_away, dangerous_attacks_home, 
                     dangerous_attacks_away, possession_home, possession_away, 
                     shots_on_target_home, shots_on_target_away, corners_home, corners_away)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    m_id, status, 
                    clean_int(score.get('home')), clean_int(score.get('away')),
                    ht_score_str, game_time,
                    clean_int(data.get("Attaques", {}).get("home")),
                    clean_int(data.get("Attaques", {}).get("away")),
                    clean_int(data.get("Attaques dangereuses", {}).get("home")),
                    clean_int(data.get("Attaques dangereuses", {}).get("away")),
                    clean_int(data.get("% de possession de balle", {}).get("home")),
                    clean_int(data.get("% de possession de balle", {}).get("away")),
                    clean_int(data.get("Tirs cadrés", {}).get("home")),
                    clean_int(data.get("Tirs cadrés", {}).get("away")),
                    clean_int(data.get("Corners", {}).get("home")),
                    clean_int(data.get("Corners", {}).get("away"))
                ))
            elif status == "UPCOMING" and "probabilities" in data:
                cur.execute("INSERT INTO match_live_stats (match_id, status, probabilities) VALUES (%s, %s, %s)", 
                            (m_id, status, json.dumps(data["probabilities"])))

        # 3. Update Favoris JSON
        updated_favorites = []
        for fav in favorites_data:
            fid = str(fav['id'])
            if fid in status_map:
                fav['status'] = status_map[fid]
            updated_favorites.append(fav)

        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(updated_favorites, f, indent=4, ensure_ascii=False)

        conn.commit()
        cur.close()
        conn.close()
        print(f"🚀 Synchro terminée !")

    except Exception as e:
        print(f"❌ Erreur : {e}")

if __name__ == "__main__":
    init_live_tables()
    update_all()