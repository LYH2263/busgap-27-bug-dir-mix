from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def ensure_direction_columns() -> None:
    """为既有库补齐 lines/trips.direction 列（幂等）。历史数据保持 NULL，按上行兼容。"""
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in ("lines", "trips"):
            if table not in insp.get_table_names():
                continue
            cols = {c["name"] for c in insp.get_columns(table)}
            if "direction" not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN direction VARCHAR(8)"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
