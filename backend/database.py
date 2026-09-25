import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Handle Railway/Heroku style postgres:// vs postgresql://
DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    # Local development fallback — Railway MUST set DATABASE_URL env var
    DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/accessibility_db"
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,        # detect stale connections before use
    pool_recycle=300,           # recycle connections every 5 min
    connect_args={"connect_timeout": 10},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
