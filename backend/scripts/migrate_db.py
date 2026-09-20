import sys
import os
from sqlalchemy import text

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.database import SessionLocal, engine
from backend.models import schema
import bcrypt

def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password=pwd_bytes, salt=salt)
    return hashed_password.decode('utf-8')

def migrate():
    print("Running database migrations...")
    
    # 1. Update schema with new columns (SQLite ALTER TABLE workaround)
    db = SessionLocal()
    
    try:
        db.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR;"))
    except Exception as e:
        print("Column email might already exist:", e)

    try:
        db.execute(text("ALTER TABLE users ADD COLUMN hashed_password VARCHAR;"))
    except Exception as e:
        print("Column hashed_password might already exist:", e)

    try:
        db.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR DEFAULT 'user';"))
    except Exception as e:
        print("Column role might already exist:", e)

    try:
        db.execute(text("ALTER TABLE conversations ADD COLUMN user_id INTEGER REFERENCES users(id);"))
    except Exception as e:
        print("Column user_id in conversations might already exist:", e)
        
    db.commit()

    # 2. Create or find admin user
    admin_user = db.query(schema.User).filter(schema.User.username == "admin").first()
    if not admin_user:
        print("Creating admin user with password 'adminisghei'...")
        admin_user = schema.User(
            username="admin",
            hashed_password=get_password_hash("adminisghei"),
            role="admin"
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
    else:
        print("Admin user already exists. Updating password...")
        admin_user.hashed_password = get_password_hash("adminisghei")
        db.commit()

    print(f"Admin user ID: {admin_user.id}")

    # 3. Assign all conversations to the admin user
    conversations = db.query(schema.Conversation).filter(schema.Conversation.user_id == None).all()
    count = 0
    for conv in conversations:
        conv.user_id = admin_user.id
        count += 1
    
    db.commit()
    print(f"Migrated {count} orphaned conversations to admin user.")

    db.close()
    print("Migration complete!")

if __name__ == "__main__":
    schema.Base.metadata.create_all(bind=engine)
    migrate()
