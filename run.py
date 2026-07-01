import os
import asyncio
import sys

# Fix for Playwright/Subprocess on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Fix for Windows encoding issues with PostgreSQL error messages
os.environ["PGCLIENTENCODING"] = "utf-8"

def load_env():
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ[key] = value

if __name__ == "__main__":
    load_env()
    
    # Imports MUST happen after load_env so the database URL is read correctly
    import uvicorn
    from backend.database import engine, Base
    from ensure_db import create_database
    
    # Only run DB setup in the main process (not in uvicorn reloader workers)
    if os.environ.get("PA11Y_DB_READY") != "1":
        # Ensure DB exists
        create_database()
        
        # Create tables if they don't exist (preserves existing data)
        print("Aplicando esquema de base de datos...")
        try:
            Base.metadata.create_all(bind=engine)

            # Apply lightweight column migrations for columns added after initial creation
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS global_summary TEXT"))
                conn.execute(text("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS max_pages INTEGER DEFAULT 10"))
                conn.execute(text("ALTER TABLE page_reports ADD COLUMN IF NOT EXISTS page_title VARCHAR"))
                conn.execute(text("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS wp_fingerprint JSON"))
                conn.commit()

            os.environ["PA11Y_DB_READY"] = "1"
            print("Esquema aplicado correctamente.")
        except Exception as e:
            error_msg = str(e)
            if "UnicodeDecodeError" in type(e).__name__ or "codec can't decode" in error_msg:
                error_msg = "Error de conexión/autenticación. Revisa tu .env y que la contraseña sea correcta."
            print(f"Error fatal al crear tablas: {error_msg}")
            exit(1)
    
    print("Iniciando servidor en http://localhost:8000")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
