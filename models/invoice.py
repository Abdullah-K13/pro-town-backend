from sqlalchemy import Column, Integer, String, ForeignKey, Date, TIMESTAMP, text
from db.init import Base

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    professional_id = Column(Integer, ForeignKey("professionals.id"), nullable=False)
    subscription_plan_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    amount = Column(Integer, nullable=False)  # Amount in cents
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    invoice_date = Column(Date, server_default=text("CURRENT_DATE"))
    due_date = Column(Date)
    status = Column(String(50), default="PENDING")  # PAID, PENDING, FAILED
    created_at = Column(TIMESTAMP, server_default=text("NOW()"))

