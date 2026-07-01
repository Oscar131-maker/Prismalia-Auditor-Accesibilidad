"""
Production start script for Railway deployment.
Runs database migrations then starts uvicorn.
"""
import os
import sys
import time

# Production doesn't need Windows event loop policy
if sys.platform == 'win32':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def check_database_url():
    """Verify DATABASE_URL is configured. Fail fast with a clear message if not."""
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("=" * 60)
        print("ERROR FATAL: DATABASE_URL no está configurada.")
        print("")
        print("En Railway, debes:")
        print("  1. Agregar un servicio PostgreSQL al proyecto")
        print("  2. En Variables del servicio web, agregar:")
        print("     DATABASE_URL = ${{Postgres.DATABASE_URL}}")
        print("=" * 60)
        sys.exit(1)

    # Show sanitized URL for debugging (hide password)
    safe_url = db_url
    if "@" in safe_url:
        prefix = safe_url.split("@")[0]
        if ":" in prefix:
            parts = prefix.rsplit(":", 1)
            safe_url = parts[0] + ":****@" + db_url.split("@", 1)[1]
    print(f"DATABASE_URL detectada: {safe_url}")

    if "localhost" in db_url or "127.0.0.1" in db_url:
        print("ADVERTENCIA: DATABASE_URL apunta a localhost. Esto NO funcionará en Railway.")
        print("Asegúrate de vincular el servicio PostgreSQL correctamente.")


def wait_for_db(max_retries=15, delay=5):
    """Wait until the database is reachable."""
    from backend.database import engine
    from sqlalchemy import text

    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"Base de datos disponible (intento {attempt}).")
            return True
        except Exception as e:
            print(f"Esperando base de datos (intento {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(delay)
    return False


def run_migrations():
    """Apply database schema and lightweight migrations."""
    from backend.database import engine, Base
    from backend import models  # noqa: F401 — ensure models are registered

    print("Aplicando esquema de base de datos...")
    try:
        Base.metadata.create_all(bind=engine)

        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS global_summary TEXT"))
            conn.execute(text("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS max_pages INTEGER DEFAULT 10"))
            conn.execute(text("ALTER TABLE page_reports ADD COLUMN IF NOT EXISTS page_title VARCHAR"))
            conn.execute(text("ALTER TABLE analyses ADD COLUMN IF NOT EXISTS wp_fingerprint JSON"))
            conn.commit()

        print("Esquema aplicado correctamente.")
    except Exception as e:
        print(f"Error en migraciones: {e}")
        raise


def main():
    port = int(os.environ.get("PORT", 8080))

    # 1. Validate DATABASE_URL exists
    check_database_url()

    # 2. Wait for DB to be ready
    if not wait_for_db():
        print("ERROR: No se pudo conectar a la base de datos después de 15 intentos.")
        print("Verifica que el servicio PostgreSQL esté corriendo en Railway.")
        sys.exit(1)

    # 3. Run migrations
    run_migrations()

    # 4. Start uvicorn (no reload in production)
    import uvicorn
    print(f"Iniciando servidor en puerto {port}")
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        workers=1,  # Single worker for Railway (shared browser instances)
        log_level="info",
    )


if __name__ == "__main__":
    main()
