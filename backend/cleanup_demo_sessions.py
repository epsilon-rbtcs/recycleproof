"""Remove expired/revoked demo database namespaces; never deletes shared seed files."""
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from sqlalchemy import or_
from app.db import Base, engine, SessionLocal
from app.models import DemoSession


def cleanup() -> int:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        rows = db.query(DemoSession).filter(or_(DemoSession.expires_at < now,
                                                 DemoSession.revoked_at.isnot(None))).limit(1000).all()
        count = len(rows)
        for session in rows:
            db.delete(session)
        db.commit()
        return count
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    removed = cleanup()
    print(f"Removed {removed} expired/revoked demo session(s) and their isolated database records.")
    print("Shared demo-assets/seed/ files were not deleted.")
