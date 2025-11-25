from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, text
from db.init import Base

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    description = Column(String(900), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    state_id = Column(Integer, ForeignKey("states.id"), nullable=False)
    city_id = Column(Integer, ForeignKey("city.id"), nullable=False)
    status = Column(String(20), default="normal")  # urgent / normal
    pair_id = Column(Integer, ForeignKey("professional_pairs.id"))
    created_at = Column(TIMESTAMP, server_default=text("NOW()"))
