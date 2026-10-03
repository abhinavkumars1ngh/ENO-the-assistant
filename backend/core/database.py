import os
import uuid

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from backend.core.config import DATABASE_URL
from backend.models.schema import Base

_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    # Make sure the folder for the SQLite file exists (fresh clone / fresh container).
    _db_path = DATABASE_URL.split("sqlite:///", 1)[-1]
    if _db_path and _db_path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(_db_path)), exist_ok=True)
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # pool_pre_ping survives managed-Postgres idle connection drops (Render/Supabase/Neon).
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=1800)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _migrate_users_table():
    """
    Tiny additive migration so an existing local eno.db (created before accounts had
    a plan tier) keeps working. Only ever adds columns / indexes, never drops.
    """
    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    ts_type = "DATETIME" if _is_sqlite else "TIMESTAMP WITH TIME ZONE"

    with engine.begin() as conn:
        if "plan" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN plan VARCHAR NOT NULL DEFAULT 'free'"))
        if "plan_updated_at" not in cols:
            conn.execute(text(f"ALTER TABLE users ADD COLUMN plan_updated_at {ts_type}"))
        if "public_id" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN public_id VARCHAR"))

        # Backfill opaque IDs for pre-existing accounts.
        rows = conn.execute(text("SELECT id FROM users WHERE public_id IS NULL")).fetchall()
        for (uid,) in rows:
            conn.execute(
                text("UPDATE users SET public_id = :pid WHERE id = :id"),
                {"pid": uuid.uuid4().hex, "id": uid},
            )
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_public_id ON users (public_id)"))


def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate_users_table()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
