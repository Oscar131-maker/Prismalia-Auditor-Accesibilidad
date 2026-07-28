"""
Production start script for Railway deployment.
Runs database migrations then starts uvicorn.
"""
import os
import sys
import threading
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


def _is_transient_migration_error(exc):
    code = getattr(getattr(exc, "orig", None), "pgcode", None)
    return code in {"55P03", "57014"}


def _configure_migration_timeouts(conn):
    from sqlalchemy import text

    conn.execute(text("SET LOCAL lock_timeout = '5s'"))
    conn.execute(text("SET LOCAL statement_timeout = '30s'"))


def run_migrations():
    """Apply database schema and lightweight migrations."""
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError
    from backend.database import engine, Base
    from backend import models  # noqa: F401 — ensure models are registered

    statements = [
        "ALTER TABLE analyses ADD COLUMN IF NOT EXISTS global_summary TEXT",
        "ALTER TABLE analyses ADD COLUMN IF NOT EXISTS max_pages INTEGER DEFAULT 10",
        "ALTER TABLE page_reports ADD COLUMN IF NOT EXISTS page_title VARCHAR",
        "ALTER TABLE analyses ADD COLUMN IF NOT EXISTS wp_fingerprint JSON",
    ]

    print("Aplicando esquema de base de datos...")
    try:
        with engine.begin() as conn:
            _configure_migration_timeouts(conn)
            Base.metadata.create_all(bind=conn)
    except OperationalError as exc:
        if _is_transient_migration_error(exc):
            print("Esquema ocupado por una transacción activa; se difiere la migración para no bloquear el arranque.")
            return False
        print(f"Error en migraciones: {exc}")
        raise

    deferred = False
    for statement in statements:
        try:
            with engine.begin() as conn:
                _configure_migration_timeouts(conn)
                conn.execute(text(statement))
        except OperationalError as exc:
            if _is_transient_migration_error(exc):
                deferred = True
                print(f"Migración diferida por bloqueo transitorio: {statement}")
                continue
            print(f"Error en migraciones: {exc}")
            raise

    if deferred:
        print("Esquema parcialmente diferido; el servidor iniciará y la migración se reintentará en segundo plano.")
        return False

    print("Esquema aplicado correctamente.")
    return True


def retry_migrations():
    for attempt in range(1, 13):
        time.sleep(30)
        print(f"Reintentando migraciones diferidas ({attempt}/12)...")
        if run_migrations():
            return
    print("Las migraciones diferidas no pudieron completarse; se reintentará en el próximo deploy.")


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
    migrations_completed = run_migrations()
    if not migrations_completed:
        threading.Thread(target=retry_migrations, daemon=True).start()

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
