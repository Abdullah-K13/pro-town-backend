from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, TIMESTAMP, text
from db.init import Base

class Professional(Base):
    __tablename__ = "professionals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150))
    email = Column(String(150), unique=True, index=True)
    password_hash = Column(String)
    phone_number = Column(String(20))
    business_name = Column(String(150))
    business_address = Column(String(250))
    website = Column(String(150))
    experience_years = Column(Integer)
    business_insurance = Column(Boolean, default=False)
    google_certified = Column(Boolean, default=False)
    facebook_page = Column(String(150))
    linkedin_profile = Column(String(150))
    twitter_handle = Column(String(100))
    instagram_profile = Column(String(150))
    service_id = Column(Integer, ForeignKey("services.id"))
    state_id = Column(Integer, ForeignKey("states.id"))
    city_id = Column(Integer, ForeignKey("city.id"))
    verified_status = Column(Boolean, default=False)
    documents_uploaded = Column(Boolean, default=False)
    insurance_doc_url = Column(String(512), nullable=True)
    subscription_plan_id = Column(Integer, ForeignKey("subscriptions.id"))
    subscription_active = Column(Boolean, default=False)
    pending_subscription_plan_variation_id = Column(String(255), nullable=True)  # Store Square plan variation ID for later activation
    square_customer_id = Column(String(255), nullable=True)  # Store Square customer ID
    created_at = Column(TIMESTAMP, server_default=text("NOW()"))
