from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from db.init import Base

class StateCityPair(Base):
    __tablename__ = "state_city_pairs"

    id = Column(Integer, primary_key=True, index=True)
    state_id = Column(Integer, ForeignKey("states.id"), nullable=False)
    city_id = Column(Integer, ForeignKey("city.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("state_id", "city_id", name="unique_state_city"),
    )
