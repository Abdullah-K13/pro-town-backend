from sqlalchemy import Column, Integer, String
from db.init import Base
from pydantic import BaseModel, Field


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(100), unique=True)

class ServiceCreate(BaseModel):
    service_name: str = Field(..., min_length=2, max_length=200)
    city_ids: list[int] = Field(default_factory=list)