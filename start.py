"""
Production start script for Railway deployment.
Runs database migrations then starts uvicorn.
"""
import os
import sys

# Production doesn't need Windows event loop policy
if sys.platform == 'win32':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


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
        # Don't exit — Railway will show the error in logs
        raise


def main():
    port = int(os.environ.get("PORT", 8080))

    # Run migrations before starting
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
