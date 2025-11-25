from sqlalchemy import Column, Integer, String
from db.init import Base

class Catalog(Base):
    __tablename__ = "catalog"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String)
    description = Column(String)
