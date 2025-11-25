from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, text
from db.init import Base

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    professional_id = Column(Integer, ForeignKey("professionals.id"), nullable=True)  # Nullable for application payments
    subscription_plan_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    amount = Column(Integer, nullable=False)  # Amount in cents
    square_transaction_id = Column(String(255), unique=True, nullable=True)
    status = Column(String(50), default="PENDING")  # SUCCESS, FAILED, PENDING
    payment_method_id = Column(Integer, ForeignKey("payment_methods.id"), nullable=True)
    created_at = Column(TIMESTAMP, server_default=text("NOW()"))

