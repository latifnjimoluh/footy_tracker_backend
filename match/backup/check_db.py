import psycopg2
from datetime import datetime

# --- CONFIGURATION DB ---
DB_CONFIG = {
    "dbname": "football",
    "user": "postgres",
    "password": "Nexus2023.",
    "host": "localhost",
    "port": "5432"
}

def check_data():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        print("\n🔍 --- VÉRIFICATION DE LA BASE DE DONNÉES ---\n")

        # 1. Compter les données
        cur.execute("SELECT COUNT(*) FROM leagues;")
        nb_leagues = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM matches;")
        nb_matches = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM favorites;")
        nb_favoris = cur.fetchone()[0]

        print(f"📊 Statistiques actuelles :")
        print(f"   🏆 Championnats : {nb_leagues}")
        print(f"   ⚽ Matchs stockés : {nb_matches}")
        print(f"   🔥 Opportunités (Favoris) : {nb_favoris}")
        print("-" * 40)

        # 2. Afficher les Top Favoris (Cote la plus basse)
        print("\n🔥 TOP 5 DES FAVORIS (Cote < 1.60) :\n")
        
        query = """
        SELECT m.start_time, m.home_team, m.away_team, f.initial_odd, f.bet_type, l.name
        FROM favorites f
        JOIN matches m ON f.match_id = m.id
        JOIN leagues l ON m.league_id = l.id
        ORDER BY f.initial_odd ASC
        LIMIT 5;
        """
        
        cur.execute(query)
        rows = cur.fetchall()

        if rows:
            print(f"{'HEURE':<18} | {'MATCH':<40} | {'PARI':<10} | {'COTE':<5} | {'LIGUE'}")
            print("-" * 100)
            for row in rows:
                date_str = row[0].strftime("%d/%m %H:%M") if row[0] else "N/A"
                match_str = f"{row[1]} vs {row[2]}"
                bet_str = f"Victoire {row[4]}" # 1 ou 2
                odd_str = str(row[3])
                league_str = row[5][:20] # Tronquer si trop long

                print(f"{date_str:<18} | {match_str:<40} | {bet_str:<10} | {odd_str:<5} | {league_str}")
        else:
            print("Aucun favori trouvé dans la table.")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"❌ Erreur de lecture : {e}")

if __name__ == "__main__":
    check_data()