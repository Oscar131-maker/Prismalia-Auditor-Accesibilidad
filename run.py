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
    
    # Ensure DB exists
    create_database()
    
    # Ensure tables are created
    print("Iniciando esquemas...")
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        error_msg = str(e)
        if "UnicodeDecodeError" in type(e).__name__ or "codec can't decode" in error_msg:
             error_msg = "Error de conexión/autenticación. Revisa tu .env y que la contraseña sea correcta."
        print(f"Error fatal al crear tablas: {error_msg}")
        exit(1)
    
    print("Asegurando navegadores de Playwright...")
    os.system("python -m playwright install chromium")
    
    print("Iniciando servidor en http://localhost:8000")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
