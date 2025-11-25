from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, TIMESTAMP, text
from db.init import Base

class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id = Column(Integer, primary_key=True, index=True)
    professional_id = Column(Integer, ForeignKey("professionals.id"), nullable=False)
    square_card_id = Column(String(255), nullable=False)  # Square's card ID
    last_4_digits = Column(String(4), nullable=False)
    card_brand = Column(String(50))  # VISA, MASTERCARD, etc.
    exp_month = Column(Integer)
    exp_year = Column(Integer)
    is_default = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=text("NOW()"))

