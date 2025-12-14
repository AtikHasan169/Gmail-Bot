from fastapi import APIRouter
from app.db.session import SessionLocal
from app.db.models import User

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/users")
def users():
    db = SessionLocal()
    users = db.query(User).all()
    db.close()

    return [
        {
            "telegram_id": u.telegram_id,
            "email": u.email,
            "banned": u.banned,
        }
        for u in users
    ]