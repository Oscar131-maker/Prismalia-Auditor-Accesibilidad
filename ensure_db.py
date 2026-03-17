import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os

def create_database():
    # Force client encoding for the environment
    os.environ["PGCLIENTENCODING"] = "utf-8"
    
    # Try to get password from environment or default
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/accessibility_db")
    
    # Simple parsing of URL
    try:
        # Expected format: postgresql://user:pass@host:port/dbname
        clean_url = db_url.replace("postgresql://", "")
        auth, rest = clean_url.split("@")
        user, password = auth.split(":")
        host_port, dbname = rest.split("/")
        host = host_port.split(":")[0]
        port = host_port.split(":")[1] if ":" in host_port else "5432"
    except Exception as e:
        print(f"Error parseando DATABASE_URL: {e}")
        return

    try:
        # Connect to 'postgres' database to create the new one
        con = psycopg2.connect(
            user=user,
            password=password,
            host=host,
            port=port,
            database="postgres",
            client_encoding='utf8'
        )
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = con.cursor()
        
        cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{dbname}'")
        exists = cur.fetchone()
        if not exists:
            print(f"Creando base de datos {dbname}...")
            cur.execute(f"CREATE DATABASE {dbname}")
        else:
            print(f"La base de datos {dbname} ya existe.")
            
        cur.close()
        con.close()
    except Exception as e:
        # Handle the pesky UnicodeDecodeError from Spanish Postgres messages
        error_msg = str(e)
        if "UnicodeDecodeError" in type(e).__name__ or "codec can't decode" in error_msg:
             error_msg = "Error de autenticación o conexión (Mensaje codificado). Verifica que PostgreSQL esté corriendo y la contraseña sea correcta."
            
        print(f"Error asegurando existencia de DB: {error_msg}")
        print(f"Sugerencia: Revisa si el usuario '{user}' y la contraseña son correctos.")

if __name__ == "__main__":
    create_database()
