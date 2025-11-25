from sqlalchemy import Column, Integer, String
from db.init import Base

class Audit(Base):
    __tablename__ = "audit"
    id = Column(Integer, primary_key=True, index=True)
    action = Column(String)
    actor = Column(String)
