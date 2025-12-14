from sqlalchemy import Column, Integer, String, Boolean
from app.db.session import Base, engine

class User(Base):
    __tablename__ = "users"

    telegram_id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    banned = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)