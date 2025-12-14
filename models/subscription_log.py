from sqlalchemy import Column, Integer, String, Date, ForeignKey, TIMESTAMP, text
from db.init import Base

class SubscriptionLog(Base):
    __tablename__ = "subscription_logs"

    id = Column(Integer, primary_key=True, index=True)
    professional_id = Column(Integer, ForeignKey("professionals.id"), nullable=False)
    subscription_id = Column(String(255), nullable=False)
    action = Column(String(50), nullable=False)  # "PAUSE", "RESUME", "CANCEL"
    effective_date = Column(Date, nullable=True) # The date the action takes/took effect
    created_at = Column(TIMESTAMP, server_default=text("NOW()"))
