from sqlalchemy import Column, Integer, String, ForeignKey
from db.init import Base

class Request(Base):
    __tablename__ = "requests"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String)
    description = Column(String)
    status = Column(String, default="pending")
