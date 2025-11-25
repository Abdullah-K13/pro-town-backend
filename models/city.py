from sqlalchemy import Column, Integer, String
from db.init import Base

class City(Base):
    __tablename__ = "city"

    id = Column(Integer, primary_key=True, index=True)
    city_name = Column(String(100), unique=True)
