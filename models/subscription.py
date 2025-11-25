from sqlalchemy import Column, Integer, String, DECIMAL
from db.init import Base

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    plan_name = Column(String(100))
    plan_cost = Column(DECIMAL(10, 2))
    plan_description = Column(String)
