from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, text
from db.init import Base

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    address = Column(String)
    phone_number = Column(String)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    city = Column(String)
    state = Column(String)
    zip_code = Column(String)
    email_notifications = Column(Boolean, default=True)
    sms_notifications = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=text("NOW()"))
