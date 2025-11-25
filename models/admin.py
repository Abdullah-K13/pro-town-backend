from sqlalchemy import Column, Integer, String
from db.init import Base

class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150))
    phone_number = Column(String(20))
    email = Column(String(150), unique=True)
    password_hash = Column(String)
