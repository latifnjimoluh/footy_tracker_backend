import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import json
import os
from datetime import datetime

# --- CONFIGURATION FICHIERS ---
DATE_STR = datetime.now().strftime("%Y-%m-%d")
BASE_DIR = os.path.join("match", DATE_STR)

FILE_LEAGUES = os.path.join(BASE_DIR, "ids_championnats_24h.json")
FILE_MATCHES = os.path.join(BASE_DIR, "matchs_details.json")
FILE_FAVORITES = os.path.join(BASE_DIR, "favoris_1xbet.json")

# --- CONFIGURATION DB ---
DB_USER = "postgres"
DB_PASS = "Nexus2023."
DB_HOST = "localhost"
DB_PORT = "5432"
TARGET_DB = "football"

def create_database_if_missing():
    """
    Se connecte à la base par défaut 'postgres' pour créer 'football'
    si elle n'existe pas.
    """
    print("🔍 Vérification de la base de données...")
    try:
        # Connexion à la base système 'postgres'
        con = psycopg2.connect(
            dbname="postgres", 
            user=DB_USER, 
            password=DB_PASS, 
            host=DB_HOST, 
            port=DB_PORT,
            # Option pour forcer l'encodage client et éviter l'erreur 0xe9
            options="-c client_encoding=utf8" 
        )
        
        # Nécessaire pour créer une DB (pas de transaction)
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT) 
        cur = con.cursor()

        # Vérifier si la base existe
        cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (TARGET_DB,))
        exists = cur.fetchone()

        if not exists:
            print(f"   ⚠️ La base '{TARGET_DB}' n'existe pas. Création en cours...")
            cur.execute(sql.SQL("CREATE DATABASE {}").format(
                sql.Identifier(TARGET_DB))
            )
            print(f"   ✅ Base '{TARGET_DB}' créée avec succès !")
        else:
            print(f"   ✅ La base '{TARGET_DB}' existe déjà.")

        cur.close()
        con.close()
        return True

    except Exception as e:
        print(f"❌ Erreur lors de la création de la BD : {e}")
        return False

def get_db_connection():
    """Connexion à la base cible 'football'"""
    try:
        conn = psycopg2.connect(
            dbname=TARGET_DB,
            user=DB_USER,
            password=DB_PASS,
            host=DB_HOST,
            port=DB_PORT,
            options="-c client_encoding=utf8"
        )
        return conn
    except Exception as e:
        print(f"❌ Erreur connexion finale : {e}")
        return None

def init_tables():
    conn = get_db_connection()
    if not conn: return
    cur = conn.cursor()

    # 1. Tables
    queries = [
        """
        CREATE TABLE IF NOT EXISTS leagues (
            id TEXT PRIMARY KEY,
            name TEXT,
            url TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS matches (
            id TEXT PRIMARY KEY,
            league_id TEXT,
            home_team TEXT,
            away_team TEXT,
            start_time TIMESTAMP,
            match_url TEXT,
            status TEXT DEFAULT 'SCHEDULED',
            score_home INTEGER,
            score_away INTEGER,
            FOREIGN KEY (league_id) REFERENCES leagues (id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS odds_history (
            id SERIAL PRIMARY KEY,
            match_id TEXT,
            odd_1 REAL,
            odd_x REAL,
            odd_2 REAL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (match_id) REFERENCES matches (id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS favorites (
            match_id TEXT PRIMARY KEY,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            initial_odd REAL,
            bet_type TEXT,
            FOREIGN KEY (match_id) REFERENCES matches (id)
        );
        """
    ]

    for q in queries:
        cur.execute(q)

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Tables initialisées.")

def format_date(date_str, time_str):
    if not date_str or date_str == "N/A": return None
    try:
        year = datetime.now().year
        dt = datetime.strptime(f"{date_str}/{year} {time_str}", "%d/%m/%Y %H:%M")
        if datetime.now().month == 12 and dt.month == 1:
            dt = dt.replace(year=year + 1)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except: return None

def insert_data():
    conn = get_db_connection()
    if not conn: return
    cur = conn.cursor()

    # 1. Ligues
    if os.path.exists(FILE_LEAGUES):
        with open(FILE_LEAGUES, "r", encoding="utf-8") as f:
            leagues = json.load(f)
            print(f"📥 Insertion de {len(leagues)} championnats...")
            for l in leagues:
                cur.execute("""
                    INSERT INTO leagues (id, name, url) VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO NOTHING;
                """, (l['id'], l['name'], l['url']))

    # 2. Matchs
    if os.path.exists(FILE_MATCHES):
        with open(FILE_MATCHES, "r", encoding="utf-8") as f:
            matches = json.load(f)
            print(f"📥 Insertion de {len(matches)} matchs...")
            for m in matches:
                m_date = format_date(m.get('date'), m.get('time'))
                
                # Chercher ID Ligue
                cur.execute("SELECT id FROM leagues WHERE name = %s", (m['league'],))
                res = cur.fetchone()
                l_id = res[0] if res else None

                # Match
                cur.execute("""
                    INSERT INTO matches (id, league_id, home_team, away_team, start_time, match_url)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING;
                """, (m['id'], l_id, m['home'], m['away'], m_date, m['url']))

                # Cotes
                odds = m.get('odds', {})
                o1 = float(odds['1']) if odds.get('1') not in ['-', None] else None
                ox = float(odds['X']) if odds.get('X') not in ['-', None] else None
                o2 = float(odds['2']) if odds.get('2') not in ['-', None] else None
                
                if o1 or o2:
                    cur.execute("""
                        INSERT INTO odds_history (match_id, odd_1, odd_x, odd_2)
                        VALUES (%s, %s, %s, %s);
                    """, (m['id'], o1, ox, o2))

    # 3. Favoris
    if os.path.exists(FILE_FAVORITES):
        with open(FILE_FAVORITES, "r", encoding="utf-8") as f:
            favs = json.load(f)
            print(f"📥 Insertion de {len(favs)} favoris...")
            for fav in favs:
                bet = "1" if fav.get('fav_team') == fav.get('home') else "2"
                cur.execute("""
                    INSERT INTO favorites (match_id, initial_odd, bet_type)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (match_id) 
                    DO UPDATE SET initial_odd = EXCLUDED.initial_odd, detected_at = CURRENT_TIMESTAMP;
                """, (fav['id'], fav.get('best_odd'), bet))

    conn.commit()
    cur.close()
    conn.close()
    print("🚀 Synchronisation terminée !")

if __name__ == "__main__":
    # Étape 1 : Créer la BD si besoin
    if create_database_if_missing():
        # Étape 2 : Créer les tables
        init_tables()
        # Étape 3 : Insérer les données
        insert_data()