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


def wait_for_db(max_retries=10, delay=3):
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

    # Wait for DB to be ready, then run migrations
    if not wait_for_db():
        print("ERROR: No se pudo conectar a la base de datos después de varios intentos.")
        print(f"DATABASE_URL configurada: {'Sí' if os.environ.get('DATABASE_URL') else 'NO — FALTA CONFIGURAR'}")
        sys.exit(1)

    run_migrations()

    # Start uvicorn (no reload in production)
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
