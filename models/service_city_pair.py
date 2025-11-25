from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from db.init import Base

class ServiceCityPair(Base):
    __tablename__ = "service_city_pairs"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    city_id = Column(Integer, ForeignKey("city.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("service_id", "city_id", name="unique_service_city"),
    )
