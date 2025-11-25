# db/init.py
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

# ---- Database engine & Session ----
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in environment (.env)")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ---- Base for ORM models ----
Base = declarative_base()


# ---- DB session dependency ----
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---- Initialization & optional seeding ----
def init_db(seed: bool = True):
    """
    Imports all model modules to register tables, creates them,
    and (optionally) seeds default admin/pro/customer users if none exist.
    """
    # Import models so their metadata is registered on Base
    from models import (  # noqa: F401
        customer,
        professional,
        admin,
        subscription,
        service,
        state,
        city,
        professional_pair,
        lead,
        service_city_pair,
        state_city,
        payment_method,
        payment,
        invoice,
    )

    # Create tables
    Base.metadata.create_all(bind=engine)

    if seed:
        _seed_default_users()


def _seed_default_users():
    """
    Insert one admin, one professional, and one customer if their emails
    do not already exist. Uses utils.security.hash_password.
    """
    from sqlalchemy.orm import Session
    from models.admin import Admin
    from models.professional import Professional
    from models.customer import Customer
    from utils.security import hash_password

    db: Session = SessionLocal()
    try:
        # Admin
        if not db.query(Admin).filter(Admin.email == "admin@protown.com").first():
            db.add(
                Admin(
                    name="Super Admin",
                    phone_number="0000000000",
                    email="admin@protown.com",
                    password_hash=hash_password("admin123"),
                )
            )

        # Professional (note: service_id/state_id can be filled later after you create catalog rows)
        if not db.query(Professional).filter(Professional.email == "pro@protown.com").first():
            db.add(
                Professional(
                    name="Pro User",
                    email="pro@protown.com",
                    password_hash=hash_password("pro123"),
                    phone_number="1112223333",
                    service_id=None,   # set after you insert into services
                    state_id=None,     # set after you insert into states
                    verified_status=True,
                    documents_uploaded=True,
                    subscription_plan_id=None,
                    subscription_active=False,
                )
            )

        # Customer
        if not db.query(Customer).filter(Customer.email == "customer@protown.com").first():
            db.add(
                Customer(
                    first_name="Jane",
                    last_name="Doe",
                    address="123 Main St",
                    phone_number="7778889999",
                    email="customer@protown.com",
                    password_hash=hash_password("customer123"),
                    city="Brooklyn",
                    state="NY",
                    zip_code="11201",
                    email_notifications=True,
                    sms_notifications=True,
                )
            )

        db.commit()
    finally:
        db.close()
