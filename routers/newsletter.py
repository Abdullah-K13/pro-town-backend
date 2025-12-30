from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.init import get_db
from models.customer import Customer
from models.state import State
from models.city import City
from models.state_city import StateCityPair
from utils.deps import role_required, get_current_user
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr
import os
import logging
import time
import requests

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models for request/response
class NewsletterFilters(BaseModel):
    state: Optional[str] = None
    city: Optional[str] = None


class NewsletterRequest(BaseModel):
    subject: str
    body: str  # HTML or plain text
    recipient_emails: Optional[List[EmailStr]] = None  # Optional: specific emails
    filters: Optional[NewsletterFilters] = None  # Optional: filter by state/city


class SMSRequest(BaseModel):
    recipient_number: str
    message: str


class NewsletterResponse(BaseModel):
    success: bool
    message: str
    sent_count: int = 0
    failed_count: int = 0
    errors: Optional[List[str]] = None


from utils.email import send_email, BREVO_API_KEY, BREVO_FROM_EMAIL


def get_recipient_emails(
    db: Session,
    recipient_emails: Optional[List[str]] = None,
    filters: Optional[NewsletterFilters] = None
) -> List[str]:
    """
    Get list of recipient emails based on filters or provided list.
    If recipient_emails are provided, use them directly (no database validation required).
    """
    emails = []

    # If specific emails provided, use those directly (no need to check database)
    if recipient_emails:
        emails = recipient_emails
    else:
        # Query customers based on filters
        query = db.query(Customer.email)

        if filters:
            # Filter by state
            if filters.state:
                state = db.query(State).filter(State.state_name == filters.state).first()
                if state:
                    # Get cities in this state
                    city_ids = (
                        db.query(StateCityPair.city_id)
                        .filter(StateCityPair.state_id == state.id)
                        .all()
                    )
                    city_id_list = [cid[0] for cid in city_ids]

                    # Filter customers by state (using the state field in Customer model)
                    # OR by city_id if we have city filtering
                    if filters.city:
                        city = db.query(City).filter(City.city_name == filters.city).first()
                        if city and city.id in city_id_list:
                            # Filter by both state and city
                            query = query.filter(
                                Customer.state == filters.state,
                                Customer.city == filters.city
                            )
                        else:
                            # City not in state, return empty
                            return []
                    else:
                        # Filter by state only
                        query = query.filter(Customer.state == filters.state)

            # Filter by city only (if no state filter)
            elif filters.city:
                query = query.filter(Customer.city == filters.city)

        # Get emails where notifications are enabled
        query = query.filter(Customer.email_notifications == True)

        # Execute query and extract emails
        results = query.all()
        emails = [email[0] for email in results if email[0]]

    return emails


@router.post("/send")
def send_newsletter(
    request: NewsletterRequest,
    db: Session = Depends(get_db)
) -> NewsletterResponse:
    """
    Send newsletter emails to customers.
    
    Can send to:
    1. Specific emails (via recipient_emails)
    2. Filtered customers (via filters - state/city)
    3. All customers with email notifications enabled (if no filters/recipients)
    """
    # Validate Brevo configuration
    if not BREVO_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Brevo API key is missing. Please set BREVO_API_KEY environment variable."
        )
    if not BREVO_FROM_EMAIL:
        raise HTTPException(
            status_code=500,
            detail="Brevo sender email is missing. Please set BREVO_FROM_EMAIL environment variable."
        )

    # Get recipient emails
    try:
        recipient_emails = get_recipient_emails(
            db,
            [str(email) for email in request.recipient_emails] if request.recipient_emails else None,
            request.filters
        )
    except Exception as e:
        logger.error(f"Error getting recipient emails: {str(e)}")
        return NewsletterResponse(
            success=False,
            message="Failed to retrieve recipient emails",
            errors=[str(e)]
        )

    if not recipient_emails:
        return NewsletterResponse(
            success=False,
            message="No recipients found matching the criteria",
            errors=["No customers found with the specified filters or email addresses"]
        )

    # Send emails
    sent_count = 0
    failed_count = 0
    errors = []

    # Detect if body is HTML (simple check)
    is_html = "<" in request.body and ">" in request.body

    logger.info(f"Starting newsletter send to {len(recipient_emails)} recipients")

    for email in recipient_emails:
        success, error = send_email(
            to_email=email,
            subject=request.subject,
            body=request.body,
            is_html=is_html
        )

        if success:
            sent_count += 1
        else:
            failed_count += 1
            errors.append(error)

        # Rate limiting: small delay to avoid overwhelming SMTP server
        # (You can adjust this or use a proper queue for large batches)
        if len(recipient_emails) > 10:
            time.sleep(0.1)  # 100ms delay for batches > 10

    # Prepare response
    if failed_count == 0:
        return NewsletterResponse(
            success=True,
            message=f"Newsletter sent successfully to {sent_count} recipients",
            sent_count=sent_count,
            failed_count=0
        )
    elif sent_count > 0:
        return NewsletterResponse(
            success=True,
            message=f"Newsletter sent to {sent_count} recipients, {failed_count} failed",
            sent_count=sent_count,
            failed_count=failed_count,
            errors=errors[:10]  # Limit errors in response
        )
    else:
        return NewsletterResponse(
            success=False,
            message="Failed to send newsletter to any recipients",
            sent_count=0,
            failed_count=failed_count,
            errors=errors[:10]
        )

@router.post("/send-sms")
def send_sms_endpoint(request: SMSRequest):
    """
    Send an SMS using Brevo's Transactional SMS API.
    """
    if not BREVO_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Brevo API key is missing. Please set BREVO_API_KEY environment variable."
        )

    sender = os.getenv("BREVO_SMS_SENDER", "ProTown")
    url = "https://api.brevo.com/v3/transactionalSMS/sms"

    payload = {
        "sender": sender,
        "recipient": request.recipient_number,
        "content": request.message,
        "type": "transactional",
    }

    headers = {
        "api-key": BREVO_API_KEY,
        "accept": "application/json",
        "content-type": "application/json",
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return {"success": True, "message": "SMS sent successfully", "data": response.json()}

    except requests.exceptions.RequestException as e:
        error_detail = str(e)
        if hasattr(e, 'response') and e.response is not None:
             try:
                 error_detail = e.response.json()
             except:
                 pass
        
        logger.error(f"Error sending SMS: {error_detail}")
        raise HTTPException(status_code=400, detail=f"Failed to send SMS: {error_detail}")
