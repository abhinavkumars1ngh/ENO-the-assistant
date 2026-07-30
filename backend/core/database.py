from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models.schema import Base
import os

DATABASE_URL = "sqlite:////Users/abhinavkumarsingh/ENO/storage/db/eno.db"

# Create engine
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
