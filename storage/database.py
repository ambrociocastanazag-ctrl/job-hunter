import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from storage.models import Base
from utils.logger import get_logger

logger = get_logger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_DEFAULT_DB = f"sqlite:///{os.path.join(_BASE_DIR, 'data', 'jobs.db')}"

DATABASE_URL = os.getenv("DATABASE_URL", _DEFAULT_DB)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    os.makedirs(os.path.join(_BASE_DIR, "data"), exist_ok=True)
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized.")


def get_session() -> Session:
    return SessionLocal()
