from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from db.init import get_db
from models.professional import Professional
from models.professional_pair import ProfessionalPair
from models.service import Service
from utils.deps import role_required
from utils.security import hash_password
from models.state import State
from models.city import City
import boto3, os
from uuid import uuid4
import json
import io
from botocore.exceptions import ClientError
from utils.deps import get_current_user
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

class ProfessionalUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone_number: str | None = None
    business_name: str | None = None
    business_address: str | None = None
    website: str | None = None
    experience_years: int | None = None
    business_insurance: bool | None = None
    google_certified: bool | None = None
    facebook_page: str | None = None
    linkedin_profile: str | None = None
    twitter_handle: str | None = None
    instagram_profile: str | None = None
    service_id: int | None = None
    state_id: int | None = None
    verified_status: bool | None = None
    subscription_plan_id: int | None = None
    subscription_active: bool | None = None
    # NOTE: password changes should be a separate endpoint that hashes input


router = APIRouter()

S3_BUCKET = os.getenv("S3_BUCKET", "pro-town-data")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")  # adjust
s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id="AKIA46ALPOQWHEXDJJHV",
    aws_secret_access_key="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",
)

@router.get("/", dependencies=[Depends(role_required("admins"))])
def get_all_professionals(db: Session = Depends(get_db)):
    # JOIN Professional → Service, State, City (outer joins in case some FKs are null)
    rows = (
        db.query(
            Professional,
            Service.id.label("svc_id"),
            Service.service_name.label("svc_name"),
            State.id.label("st_id"),
            State.state_name.label("st_name"),
            City.id.label("city_id"),
            City.city_name.label("city_name"),
        )
        .outerjoin(Service, Service.id == Professional.service_id)
        .outerjoin(State, State.id == Professional.state_id)
        .outerjoin(City, City.id == Professional.city_id)
        .all()
    )

    def prof_to_dict(p: Professional) -> dict:
        # serialize all DB columns exactly as they are now
        return {c.name: getattr(p, c.name) for c in p.__table__.columns}

    out = []
    for p, svc_id, svc_name, st_id, st_name, city_id, city_name in rows:
        base = prof_to_dict(p)
        # add nested service + state + city objects
        base["service"] = (
            {"id": svc_id, "service_name": svc_name} if svc_id is not None else None
        )
        base["state"] = (
            {"id": st_id, "state_name": st_name} if st_id is not None else None
        )
        base["city"] = (
            {"id": city_id, "city_name": city_name} if city_id is not None else None
        )
        out.append(base)

    return out

@router.get("/me", dependencies=[Depends(role_required("professionals"))])
def get_my_professional_profile(
    db: Session = Depends(get_db),
    payload = Depends(get_current_user),
):
    """
    Return the Professional that matches the current access token.
    Tries id (uid/user_id/id) first, then falls back to email in `sub`.
    Includes nested `service` and `state` objects like your list endpoint.
    """
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    pro_id = payload.get("uid") or payload.get("user_id") or payload.get("id")
    email = payload.get("sub")

    q = (
        db.query(
            Professional,
            Service.id.label("svc_id"),
            Service.service_name.label("svc_name"),
            State.id.label("st_id"),
            State.state_name.label("st_name"),
            City.id.label("city_id"),
            City.city_name.label("city_name"),
        )
        .outerjoin(Service, Service.id == Professional.service_id)
        .outerjoin(State, State.id == Professional.state_id)
        .outerjoin(City, City.id == Professional.city_id)
    )

    row = None
    if pro_id is not None:
        row = q.filter(Professional.id == int(pro_id)).first()

    if row is None and email:
        row = q.filter(Professional.email == email).first()

    if row is None:
        raise HTTPException(status_code=404, detail="Professional not found")

    prof, svc_id, svc_name, st_id, st_name, city_id, city_name = row

    # serialize all DB columns exactly as they are now
    base = {c.name: getattr(prof, c.name) for c in prof.__table__.columns}

    # add nested service + state + city objects (same shape you used before)
    base["service"] = (
        {"id": svc_id, "service_name": svc_name} if svc_id is not None else None
    )
    base["state"] = (
        {"id": st_id, "state_name": st_name} if st_id is not None else None
    )
    base["city"] = (
        {"id": city_id, "city_name": city_name} if city_id is not None else None
    )

    return base

@router.get("/filtered", dependencies=[Depends(role_required("admins"))])
def get_filtered_professionals(
    service_id: int,
    city_id: int,
    state_id: int,  # ✅ Added state_id
    service_city_pair_id: int,   # ✅ required to check assigned pros
    verified: bool = True,
    db: Session = Depends(get_db),
):
    """
    Return only id + name for professionals that match:
    - service_id
    - city_id
    - state_id
    - verified_status
    AND are NOT already assigned in ProfessionalPair table
    """
    # ✅ Get all assigned pros for this SCP
    assigned = (
        db.query(ProfessionalPair.professional_id_1, ProfessionalPair.professional_id_2)
        .filter(ProfessionalPair.service_city_pair_id == service_city_pair_id)
        .all()
    )

    # Flatten into a single set {1,5,7,9}
    assigned_ids = set()
    for row in assigned:
        if row.professional_id_1:
            assigned_ids.add(row.professional_id_1)
        if row.professional_id_2:
            assigned_ids.add(row.professional_id_2)

    # ✅ Fetch professionals NOT in assigned list
    results = (
        db.query(Professional.id, Professional.name)
        .filter(Professional.service_id == service_id)
        .filter(Professional.city_id == city_id)
        .filter(Professional.state_id == state_id) # ✅ Filter by state
        .filter(Professional.verified_status == verified)
        .filter(~Professional.id.in_(assigned_ids))  # ✅ EXCLUDE assigned ones
        .all()
    )

    return [{"id": r.id, "name": r.name} for r in results]


@router.get("/{professional_id}")
def get_professional(professional_id: int, db: Session = Depends(get_db)):
    pro = db.query(Professional).filter(Professional.id == professional_id).first()
    if not pro:
        raise HTTPException(404)
    return pro

# @router.post("/", )
# def create_professional(data: dict, db: Session = Depends(get_db)):
#     data["password_hash"] = hash_password(data.pop("password", "pro123"))
#     p = Professional(**data)
#     db.add(p)
#     db.commit()
#     db.refresh(p)
#     return p


# ---- NEW: self-update using access token ----
@router.put("/me", dependencies=[Depends(role_required("professionals"))])
def update_my_professional_profile(
    data: ProfessionalUpdate,
    db: Session = Depends(get_db),
    payload = Depends(get_current_user),
):
    """
    Update the professional that’s authenticated by the access token.
    We try id (uid/user_id/id) first, then fall back to email (sub).
    """
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    pro_id = payload.get("uid") or payload.get("user_id") or payload.get("id")
    email = payload.get("sub")

    me = None
    if pro_id is not None:
        me = db.query(Professional).filter(Professional.id == int(pro_id)).first()
    if me is None and email:
        me = db.query(Professional).filter(Professional.email == email).first()

    if not me:
        raise HTTPException(status_code=404, detail="Professional not found")

    patch = data.model_dump(exclude_unset=True)

    # Optional: prevent self-setting of sensitive admin-only fields
    # (uncomment if you want to restrict)
    # for disallowed in ("verified_status", "subscription_active", "subscription_plan_id"):
    #     patch.pop(disallowed, None)

    for k, v in patch.items():
        setattr(me, k, v)

    db.commit()
    db.refresh(me)
    return me

@router.delete("/{professional_id}", dependencies=[Depends(role_required("admins"))])
def delete_professional(professional_id: int, db: Session = Depends(get_db)):
    p = db.query(Professional).get(professional_id)
    if not p:
        raise HTTPException(404)
    db.delete(p)
    db.commit()
    return {"deleted": True}


@router.put("/{professional_id}", dependencies=[Depends(role_required("admins"))])
def update_professional(
    professional_id: int,
    data: ProfessionalUpdate,
    db: Session = Depends(get_db),
):
    """
    Minimal update endpoint that supports your update_professional_status_api
    which sends a body like: true / false or { \"verified_status\": true }.

    If you send just a raw boolean from frontend, FastAPI will parse it
    into `verified_status`.
    
    When verified_status changes to True and professional has a pending subscription,
    the subscription will be automatically created and charged.
    """
    p = db.query(Professional).get(professional_id)
    if not p:
        raise HTTPException(status_code=404, detail="Professional not found")

    # Check if verified_status is being changed from False to True
    was_verified = p.verified_status
    update_data = data.model_dump(exclude_unset=True)
    will_be_verified = update_data.get("verified_status", was_verified)
    
    # Apply fields if provided
    for k, v in update_data.items():
        setattr(p, k, v)

    db.commit()
    db.refresh(p)
    
    # If professional is being verified and has pending subscription, activate it
    if not was_verified and will_be_verified and p.pending_subscription_plan_variation_id:
        try:
            from utils.square_client import create_subscription, get_square_customer_by_email
            from models.payment_method import PaymentMethod
            import uuid as uuid_lib
            import os
            
            # Get saved payment method
            payment_method = db.query(PaymentMethod).filter(
                PaymentMethod.professional_id == p.id,
                PaymentMethod.is_default == True
            ).first()
            
            if not payment_method:
                logger.warning(f"Professional {p.id} verified but no payment method found. Subscription not activated.")
                return p
            
            # Get or use stored Square customer ID
            square_customer_id = p.square_customer_id
            if not square_customer_id:
                # Try to find customer by email
                customer_result = get_square_customer_by_email(p.email)
                if customer_result.get("success"):
                    square_customer_id = customer_result.get("customer_id")
                    p.square_customer_id = square_customer_id
                    db.commit()
            
            if not square_customer_id:
                logger.error(f"Professional {p.id} verified but no Square customer ID found. Subscription not activated.")
                return p
            
            # Get location ID
            location_id = os.getenv("SQUARE_LOCATION_ID", "")
            if not location_id:
                logger.error(f"SQUARE_LOCATION_ID not set. Subscription not activated for professional {p.id}.")
                return p
            
            # Create subscription (THIS IS WHERE THE CHARGE HAPPENS)
            idempotency_key = str(uuid_lib.uuid4())
            subscription_result = create_subscription(
                customer_id=square_customer_id,
                location_id=location_id,
                plan_variation_id=p.pending_subscription_plan_variation_id,
                source_id=None,
                card_id=payment_method.square_card_id,
                idempotency_key=idempotency_key
            )
            
            if subscription_result.get("success"):
                # Subscription created and charged successfully
                p.subscription_active = True
                p.pending_subscription_plan_variation_id = None  # Clear pending flag
                db.commit()
                db.refresh(p)
                logger.info(f"Subscription activated for professional {p.id}: {subscription_result.get('subscription_id')}")
            else:
                logger.error(f"Failed to activate subscription for professional {p.id}: {subscription_result.get('error')}")
                # Don't fail the verification, but log the error
                # Admin can retry subscription activation later
        except Exception as e:
            logger.error(f"Error activating subscription for professional {p.id}: {str(e)}")
            # Don't fail the verification, but log the error
    
    return p

@router.post("/")
async def create_professional(
    payload: str = Form(...),  # ✅ must be Form (not Body)
    insurance_document: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    """
    Accepts multipart/form-data with:
    - payload: JSON string (can include subscription_plan_variation_id and payment_source_id)
    - insurance_document: optional file
    
    If subscription_plan_variation_id and payment_source_id are provided in payload,
    a Square subscription will be automatically created.
    """

    # Parse JSON safely
    try:
        data = json.loads(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in payload: {e}")

    # Extract subscription-related fields
    subscription_plan_variation_id = data.pop("subscription_plan_variation_id", None)
    payment_source_id = data.pop("payment_source_id", None)
    card_id = data.pop("card_id", None)  # New field for reused card
    square_customer_id = data.pop("square_customer_id", None)  # New field for reused customer
    location_id = data.pop("location_id", None) or os.getenv("SQUARE_LOCATION_ID", "")

    # Check if email already exists
    email = data.get("email")
    if email:
        existing_professional = db.query(Professional).filter(Professional.email == email).first()
        if existing_professional:
            raise HTTPException(
                status_code=400,
                detail=f"Email '{email}' is already registered. Please use a different email address."
            )

    # Extract and hash password
    password = data.pop("password", "pro123")
    password_hash = hash_password(password)
    
    # Get valid Professional model fields
    valid_professional_fields = {
        "name", "email", "phone_number", "business_name", "business_address",
        "website", "experience_years", "business_insurance", "google_certified",
        "facebook_page", "linkedin_profile", "twitter_handle", "instagram_profile",
        "service_id", "state_id", "city_id", "verified_status", "documents_uploaded",
        "insurance_doc_url", "subscription_plan_id", "subscription_active",
        "pending_subscription_plan_variation_id", "square_customer_id"
    }
    
    # Filter data to only include valid Professional fields
    professional_data = {
        k: v for k, v in data.items() 
        if k in valid_professional_fields
    }

    # Create the professional
    try:
        p = Professional(password_hash=password_hash, **professional_data, documents_uploaded=False)
        db.add(p)
        db.commit()
        db.refresh(p)
    except IntegrityError as e:
        db.rollback()
        # Check if it's a duplicate email error (fallback in case check above missed it)
        if "email" in str(e.orig).lower() or "ix_professionals_email" in str(e.orig):
            raise HTTPException(
                status_code=400,
                detail=f"Email '{email}' is already registered. Please use a different email address."
            )
        # For other integrity errors, return generic message
        raise HTTPException(
            status_code=400,
            detail=f"Database integrity error: {str(e.orig)}"
        )

    # Handle optional file upload
    if insurance_document:
        filename = insurance_document.filename or "document"
        key = f"professionals/{p.id}/insurance/{uuid4()}-{filename.replace(' ', '_')}"
        try:
            # Read file content and upload
            file_content = await insurance_document.read()
            s3.upload_fileobj(
                io.BytesIO(file_content),
                S3_BUCKET,
                key,
                ExtraArgs={"ContentType": insurance_document.content_type or "application/octet-stream",
                        #    "ACL": "public-read"
                           
                           },
            )
        except ClientError as e:
            raise HTTPException(status_code=500, detail=f"S3 upload failed: {e}")

        # Generate S3 URL
        s3_url = f"s3://{S3_BUCKET}/{key}"
        if hasattr(p, "insurance_doc_url"):
            p.insurance_doc_url = s3_url

        p.documents_uploaded = True
        db.commit()
        db.refresh(p)

    # If subscription details provided, validate card and save for later (NO CHARGE YET)
    subscription_info = None
    if subscription_plan_variation_id and (payment_source_id or card_id):
        try:
            from utils.square_client import create_square_customer, create_card_on_file, update_square_customer
            from models.payment_method import PaymentMethod
            
            # Validate subscription plan variation ID
            valid_plans = {
                "LYIAHPLNYRD3AX5FPCDDYDV3": "Pro Town Network Monthly",
                "VGMYZYBSVKPM3CJWYK35FS7N": "Pro Town Network Yearly"
            }
            
            if subscription_plan_variation_id not in valid_plans:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid subscription plan. Use 'LYIAHPLNYRD3AX5FPCDDYDV3' for Monthly or 'VGMYZYBSVKPM3CJWYK35FS7N' for Yearly"
                )
            
            if not location_id:
                raise HTTPException(
                    status_code=400,
                    detail="location_id is required. Provide it in the request or set SQUARE_LOCATION_ID in .env"
                )
            
            # Handle Square Customer
            if square_customer_id:
                # Reuse existing customer (from validation step) and update details
                update_result = update_square_customer(
                    customer_id=square_customer_id,
                    given_name=p.name.split()[0] if p.name else "Professional",
                    family_name=" ".join(p.name.split()[1:]) if p.name and len(p.name.split()) > 1 else "",
                    email=p.email,
                    phone_number=p.phone_number
                )
                if not update_result.get("success"):
                    logger.warning(f"Failed to update Square customer {square_customer_id}: {update_result.get('error')}")
                    # Continue anyway, as we have the ID
            else:
                # Create new Square customer (no charge)
                customer_result = create_square_customer(
                    given_name=p.name.split()[0] if p.name else "Professional",
                    family_name=" ".join(p.name.split()[1:]) if p.name and len(p.name.split()) > 1 else "",
                    email=p.email,
                    phone_number=p.phone_number
                )
                
                if not customer_result.get("success"):
                    logger.error(f"Failed to create Square customer: {customer_result.get('error')}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to create Square customer: {customer_result.get('error')}. Professional account created but card validation failed."
                    )
                
                square_customer_id = customer_result.get("customer_id")
            
            # Handle Card
            final_card_id = card_id
            final_last_4 = "****"
            final_brand = "UNKNOWN"
            final_exp_month = None
            final_exp_year = None

            if not final_card_id and payment_source_id:
                # Create card on file (validates card, but NO CHARGE)
                card_result = create_card_on_file(
                    source_id=payment_source_id,
                    customer_id=square_customer_id
                )
                
                if not card_result.get("success"):
                    logger.error(f"Failed to create card on file: {card_result.get('error')}")
                    error_msg = card_result.get("error", "")
                    
                    # Check for "used before" error - most common issue
                    if "used before" in error_msg.lower() or "already used" in error_msg.lower():
                        raise HTTPException(
                            status_code=400,
                            detail="Payment token has already been used. Square payment tokens are single-use only. Please tokenize the card again using Square Web Payments SDK and use the fresh token immediately."
                        )
                    # Check for expired/invalid token
                    elif "blank" in error_msg.lower() or "expired" in error_msg.lower() or "invalid" in error_msg.lower():
                        raise HTTPException(
                            status_code=400,
                            detail="Payment token is expired or invalid. Square payment tokens expire quickly (within minutes) and are single-use. Please tokenize the card again using Square Web Payments SDK."
                        )
                    else:
                        raise HTTPException(
                            status_code=500,
                            detail=f"Card validation failed: {error_msg}. Please check your card details."
                        )
                
                final_card_id = card_result.get("card_id")
                final_last_4 = card_result.get("last_4", "****")
                final_brand = card_result.get("brand", "UNKNOWN")
                final_exp_month = card_result.get("exp_month")
                final_exp_year = card_result.get("exp_year")
            
            # Save card to database (for later use when verified)
            payment_method = PaymentMethod(
                professional_id=p.id,
                square_card_id=final_card_id,
                last_4_digits=final_last_4,
                card_brand=final_brand,
                exp_month=final_exp_month,
                exp_year=final_exp_year,
                is_default=True
            )
            db.add(payment_method)
            
            # Store subscription plan and customer ID for later activation
            p.pending_subscription_plan_variation_id = subscription_plan_variation_id
            p.square_customer_id = square_customer_id
            p.subscription_active = False  # Not active until verified
            
            db.commit()
            db.refresh(p)
            
            subscription_info = {
                "subscription_created": False,
                "card_validated": True,
                "card_saved": True,
                "plan_name": valid_plans[subscription_plan_variation_id],
                "message": "Card validated and saved. Subscription will be activated when admin verifies your account. No charge has been made yet."
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error validating card during professional creation: {str(e)}")
            subscription_info = {
                "subscription_created": False,
                "card_validated": False,
                "error": str(e),
                "message": "Professional account created but card validation failed. Please contact support."
            }
            
    elif subscription_plan_variation_id or (payment_source_id or card_id):
        # If only one is provided, it's incomplete
        subscription_info = {
            "subscription_created": False,
            "card_validated": False,
            "message": "Both subscription_plan_variation_id and payment_source_id (or card_id) are required for subscription setup."
        }

    # Return a safe dict response (exclude password_hash and ensure JSON serializable)
    from datetime import datetime
    response_dict = {}
    for c in p.__table__.columns:
        if c.name == "password_hash":
            continue
        value = getattr(p, c.name)
        # Handle datetime objects
        if isinstance(value, datetime):
            response_dict[c.name] = value.isoformat() if value else None
        else:
            response_dict[c.name] = value
    
    # Add subscription info if available
    if subscription_info:
        response_dict["subscription"] = subscription_info
    
    return response_dict