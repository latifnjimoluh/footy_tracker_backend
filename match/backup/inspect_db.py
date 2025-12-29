import psycopg2
from psycopg2 import sql

# --- CONFIGURATION ---
DB_CONFIG = {
    "dbname": "football",
    "user": "postgres",
    "password": "Nexus2023.",
    "host": "localhost",
    "port": "5432"
}

def list_tables_and_columns():
    try:
        # Connexion à PostgreSQL
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Requête SQL pour récupérer les tables et leurs colonnes
        # On filtre par 'public' pour ne pas voir les tables systèmes internes de Postgres
        query = """
            SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position;
        """
        
        cur.execute(query)
        rows = cur.fetchall()

        if not rows:
            print("⚠️ Aucune table trouvée dans le schéma public.")
            return

        print("\n=== STRUCTURE DE LA BASE DE DONNÉES : " + DB_CONFIG['dbname'].upper() + " ===\n")

        current_table = ""
        for row in rows:
            table_name, column_name, data_type, is_nullable = row
            
            # Affichage du nom de la table quand on change de groupe
            if table_name != current_table:
                print(f"\n📦 TABLE: {table_name}")
                print("-" * 50)
                current_table = table_name
            
            # Affichage des détails de la colonne
            null_status = "NULL OK" if is_nullable == "YES" else "NOT NULL"
            print(f"  🔹 {column_name:<25} | {data_type:<15} | {null_status}")

        cur.close()
        conn.close()
        print("\n" + "="*50)

    except Exception as e:
        print(f"❌ Erreur lors de l'inspection : {e}")

if __name__ == "__main__":
    list_tables_and_columns()