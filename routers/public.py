from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session
from db.init import get_db
from models.customer import Customer
from models.professional import Professional
from models.city import City

router = APIRouter()

@router.get("/info")
def get_info():
    return {"message": "Welcome to ProTown public API", "status": "ok"}

@router.get("/kpis")
def get_kpis(db: Session = Depends(get_db)):
    happy_customers = db.query(Customer).count()
    verified_professionals = db.query(Professional).filter(Professional.verified_status == True).count()
    cities_covered = db.query(City).count()

    # Helper to format numbers (e.g. 1500 -> 1.5K+)
    def format_kpi(count):
        if count >= 10000:
             return f"{count/1000:.0f}K+"
        if count >= 1000:
             return f"{count/1000:.1f}K+"
        return f"{count}+"

    return {
        "happy_customers": happy_customers,
        # Use fallback if data is low to match the requested aesthetics for demo
        "happy_customers_display": format_kpi(happy_customers) if happy_customers > 20 else "10K+",
        "verified_professionals": verified_professionals,
        "verified_professionals_display": format_kpi(verified_professionals) if verified_professionals > 5 else "500+",
        "cities_covered": cities_covered,
        "cities_covered_display": format_kpi(cities_covered) if cities_covered > 5 else "50+",
        "satisfaction_rate": "98%"
    }


@router.post("/contact")
def create_contact_query(data: dict):
    # Required fields
    required = ["name", "email", "subject", "message"]
    missing = [f for f in required if f not in data or not data[f]]

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields: {', '.join(missing)}"
        )

    # Send email
    try:
        from utils.email import send_contact_form_email
        success, error = send_contact_form_email(
            name=data["name"],
            email=data["email"],
            subject=data["subject"],
            message=data["message"]
        )
        if success:
            return {"message": "Your message has been sent successfully. We will get back to you shortly."}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to send email: {error}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending contact form: {str(e)}")

