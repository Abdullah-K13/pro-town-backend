from sqlalchemy import Column, Integer, ForeignKey
from db.init import Base

class ProfessionalPair(Base):
    __tablename__ = "professional_pairs"

    id = Column(Integer, primary_key=True, index=True)
    service_city_pair_id = Column(Integer, ForeignKey("service_city_pairs.id"), nullable=False)
    professional_id_1 = Column(Integer, ForeignKey("professionals.id"))
    professional_id_2 = Column(Integer, ForeignKey("professionals.id"))
