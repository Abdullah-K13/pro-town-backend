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
    aws_access_key_id="AKIA46ALPOQWCY5GJ77C",
    aws_secret_access_key="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",
)

@router.get("/", dependencies=[Depends(role_required("admins"))])
def get_all_professionals(db: Session = Depends(get_db)):
    from sqlalchemy import func
    from models.customer import Customer

    # Subquery to count referrals per professional
    referral_counts = (
        db.query(
            Customer.referred_by,
            func.count(Customer.id).label("count")
        )
        .filter(Customer.referred_by != None)
        .group_by(Customer.referred_by)
        .subquery()
    )

    # JOIN Professional → Service, State, City (outer joins in case some FKs are null)
    # Also join with referral_counts subquery
    rows = (
        db.query(
            Professional,
            Service.id.label("svc_id"),
            Service.service_name.label("svc_name"),
            State.id.label("st_id"),
            State.state_name.label("st_name"),
            City.id.label("city_id"),
            City.city_name.label("city_name"),
            func.coalesce(referral_counts.c.count, 0).label("referral_count")
        )
        .outerjoin(Service, Service.id == Professional.service_id)
        .outerjoin(State, State.id == Professional.state_id)
        .outerjoin(City, City.id == Professional.city_id)
        .outerjoin(referral_counts, referral_counts.c.referred_by == Professional.id)
        .all()
    )

    def prof_to_dict(p: Professional) -> dict:
        # serialize all DB columns exactly as they are now
        return {c.name: getattr(p, c.name) for c in p.__table__.columns}

    out = []
    for p, svc_id, svc_name, st_id, st_name, city_id, city_name, ref_count in rows:
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
        base["referral_count"] = ref_count
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

    # Generate referral token
    from utils.security import create_referral_token
    base["referral_token"] = create_referral_token(prof.id)

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

@router.post("/")
def create_professional(
    payload: str = Form(...),
    insurance_document: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # 1. Validation: check email unique
    email = data.get("email")
    if db.query(Professional).filter(Professional.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # 2. Upload Insurance Document
    file_url = None
    if insurance_document:
        try:
            file_content = insurance_document.file.read()
            filename = f"insurance/{uuid4()}_{insurance_document.filename}"
            s3.upload_fileobj(
                io.BytesIO(file_content),
                S3_BUCKET,
                filename,
                ExtraArgs={"ContentType": insurance_document.content_type}
            )
            file_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{filename}"
        except ClientError as e:
            logger.error(f"S3 Upload Error: {e}")
            raise HTTPException(status_code=500, detail="Failed to upload insurance document")

    # 3. Create Professional in DB
    try:
        # Hash password
        pwd = data.get("password", "pro123")
        hashed = hash_password(pwd)
        
        # Extract fields
        new_pro = Professional(
            name=data.get("name") or data.get("fullName"),
            email=email,
            password_hash=hashed,
            phone_number=data.get("phone_number"),
            business_name=data.get("business_name"),
            business_address=data.get("business_address"),
            website=data.get("website"),
            experience_years=data.get("experience_years"),
            business_insurance=data.get("business_insurance"),
            google_certified=data.get("google_certified"),
            facebook_page=data.get("facebook_page"),
            linkedin_profile=data.get("linkedin_profile"),
            twitter_handle=data.get("twitter_handle"),
            instagram_profile=data.get("instagram_profile"),
            service_id=data.get("service_id"),
            state_id=data.get("state_id"),
            city_id=data.get("city_id"),
            insurance_doc_url=file_url,
            verified_status=False, # Always false initially
            subscription_plan_id=data.get("subscription_plan_id"),
            pending_subscription_plan_variation_id=data.get("subscription_plan_variation_id")
        )
        
        db.add(new_pro)
        db.commit()
        db.refresh(new_pro)
        
        # 4. Integrate with Square if token provided
        payment_source_id = data.get("payment_source_id")
        if payment_source_id:
            try:
                from utils.square_client import create_square_customer, create_card_on_file
                from models.payment_method import PaymentMethod

                # A. Create Square Customer
                # Split name
                full_name = new_pro.name or ""
                parts = full_name.split(" ", 1)
                given_name = parts[0]
                family_name = parts[1] if len(parts) > 1 else ""
                
                cust_res = create_square_customer(
                    given_name=given_name,
                    family_name=family_name,
                    email=new_pro.email,
                    phone_number=new_pro.phone_number
                )
                
                if not cust_res.get("success"):
                    logger.error(f"Failed to create Square Customer: {cust_res.get('error')}")
                    # Don't fail the whole request, but log error
                    # Admin can fix later
                else:
                    square_cust_id = cust_res.get("customer_id")
                    
                    # Update Pro with Square Customer ID
                    new_pro.square_customer_id = square_cust_id
                    db.commit() # Save progress
                    
                    # B. Create Card on File
                    card_res = create_card_on_file(
                        source_id=payment_source_id,
                        customer_id=square_cust_id
                    )
                    
                    if card_res.get("success"):
                        card_id = card_res.get("card_id")
                        card_data = card_res.get("card", {})
                        
                        # C. Create PaymentMethod record
                        pm = PaymentMethod(
                            professional_id=new_pro.id,
                            square_card_id=card_id,
                            last_4_digits=card_data.get("last_4", "****"),
                            card_brand=card_data.get("card_brand", "UNKNOWN"),
                            exp_month=card_data.get("exp_month"),
                            exp_year=card_data.get("exp_year"),
                            is_default=True
                        )
                        db.add(pm)
                        db.commit()
                        logger.info(f"Successfully created Square Customer {square_cust_id} and Card {card_id} for Pro {new_pro.id}")
                    else:
                        logger.error(f"Failed to create card on file: {card_res.get('error')}")

            except Exception as sq_err:
                logger.error(f"Square Integration Error: {sq_err}")
                # Continue without failing request
        
        return new_pro

    except Exception as e:
        logger.error(f"Create Professional Error: {e}")
        db.rollback() # Rollback DB transaction on error
        raise HTTPException(status_code=500, detail=str(e))


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

@router.post("/me/document", dependencies=[Depends(role_required("professionals"))])
def upload_professional_document(
    insurance_document: UploadFile = File(...),
    db: Session = Depends(get_db),
    payload = Depends(get_current_user),
):
    """
    Upload or replace the business insurance document for the authenticated professional.
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

    # Upload to S3
    file_url = None
    try:
        file_content = insurance_document.file.read()
        filename = f"insurance/{uuid4()}_{insurance_document.filename}"
        s3.upload_fileobj(
            io.BytesIO(file_content),
            S3_BUCKET,
            filename,
            ExtraArgs={"ContentType": insurance_document.content_type}
        )
        file_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{filename}"
    except ClientError as e:
        logger.error(f"S3 Upload Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload document")

    # Update Professional
    me.insurance_doc_url = file_url
    me.documents_uploaded = True
    
    db.commit()
    db.refresh(me)
    
    return {"url": file_url, "message": "Document uploaded successfully"}

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
    
    # Apply fields if provided (but don't commit verified_status yet - wait for subscription success)
    fields_to_apply = {k: v for k, v in update_data.items() if k != "verified_status"}
    for k, v in fields_to_apply.items():
        setattr(p, k, v)
    
    # If professional is being verified and has pending subscription, activate it
    subscription_created = False
    subscription_error = None
    had_pending_subscription = bool(p.pending_subscription_plan_variation_id)

    if not was_verified and will_be_verified and p.pending_subscription_plan_variation_id:
        success, error = _activate_subscription_for_professional(db, p)
        if success:
            p.verified_status = True
            subscription_created = True
        else:
            subscription_error = error
            # Revert verified status if subscription fails
            p.verified_status = False
    
    db.commit()
    db.refresh(p)
    
    response_data = {
        "id": p.id,
        "name": p.name,
        "email": p.email,
        "verified_status": p.verified_status,
        "subscription_active": p.subscription_active,
        "square_subscription_id": p.square_subscription_id
    }
    
    if subscription_error:
        response_data["subscription_error"] = subscription_error
        response_data["subscription_created"] = False
    elif subscription_created:
        response_data["subscription_created"] = True
        response_data["message"] = "Professional verified and subscription activated successfully"
    
    return response_data

@router.post("/{professional_id}/verify", dependencies=[Depends(role_required("admins"))])
def verify_professional(
    professional_id: int,
    data: dict = Body(..., example={"verify": True}), 
    db: Session = Depends(get_db)
):
    """
    Verify or Reject a Professional.
    Payload: {"verify": true} or {"verify": false}
    
    - true: Sets verified_status=True. If pending subscription exists, activates it.
    - false: Sets verified_status=False.
    """
    p = db.query(Professional).get(professional_id)
    if not p:
        raise HTTPException(status_code=404, detail="Professional not found")

    verify = data.get("verify")
    if verify is None:
        raise HTTPException(status_code=400, detail="Missing 'verify' boolean in body")

    if verify:
        # VERIFY
        # 1. Activate Subscription if pending
        if p.pending_subscription_plan_variation_id and not p.subscription_active:
             success, error = _activate_subscription_for_professional(db, p)
             if success:
                 p.verified_status = True
                 logger.info(f"✅ Professional {p.id} verified and subscription activated")
             else:
                 # Subscription failed, do not verify
                 logger.warning(f"⚠️ Professional {p.id} verification deferred - subscription failed: {error}")
                 return {
                     "success": False, 
                     "message": f"Verification failed. Subscription could not be activated: {error}",
                     "professional": {"id": p.id, "verified_status": False}
                }
        else:
            # No pending subscription or already active
             p.verified_status = True
             logger.info(f"✅ Professional {p.id} verified (no pending subscription)")

    else:
        # REJECT / UNVERIFY
        p.verified_status = False
        logger.info(f"ℹ️ Professional {p.id} unverified/rejected by admin")
    
    db.commit()
    db.refresh(p)
    return {
        "success": True, 
        "professional": {
            "id": p.id, 
            "name": p.name, 
            "verified_status": p.verified_status,
            "subscription_active": p.subscription_active
        }
    }

def _activate_subscription_for_professional(db: Session, p: Professional) -> tuple[bool, str | None]:
    """
    Helper to activate pending subscription for a professional.
    Returns (success, error_message).
    """
    try:
        from utils.square_client import create_subscription, get_square_customer_by_email, get_square_customer_by_id, get_customer_cards, get_square_locations
        from models.payment_method import PaymentMethod
        import uuid as uuid_lib
        import os
        
        # Get location ID
        location_id = os.getenv("SQUARE_LOCATION_ID", "")
        if not location_id:
             locations_result = get_square_locations()
             if locations_result.get("success") and locations_result.get("location_ids"):
                 location_id = locations_result.get("location_ids")[0]
             else:
                 return False, "SQUARE_LOCATION_ID not set and could not fetch available locations."

        # Get saved payment method
        payment_method = db.query(PaymentMethod).filter(
            PaymentMethod.professional_id == p.id,
            PaymentMethod.is_default == True
        ).first()

        if not payment_method:
             # Try any method
             payment_method = db.query(PaymentMethod).filter(PaymentMethod.professional_id == p.id).first()

        # If still no payment method, try to find one from Square cards
        if not payment_method:
            square_customer_id = p.square_customer_id
            if not square_customer_id:
                 # Try finding by email
                 cust_res = get_square_customer_by_email(p.email)
                 if cust_res.get("success"):
                     square_customer_id = cust_res.get("customer_id")
                     p.square_customer_id = square_customer_id
                     db.commit()
            
            if square_customer_id:
                # Check for cards in Square
                cards_res = get_customer_cards(square_customer_id)
                if cards_res.get("success") and cards_res.get("cards"):
                    first_card = cards_res.get("cards")[0]
                    card_id = first_card.get("id")
                    
                    # Create local PaymentMethod
                    payment_method = PaymentMethod(
                        professional_id=p.id,
                        square_card_id=card_id,
                        last_4_digits=first_card.get("last_4", "****"),
                        card_brand=first_card.get("card_brand", "UNKNOWN"),
                        exp_month=first_card.get("exp_month"),
                        exp_year=first_card.get("exp_year"),
                        is_default=True
                    )
                    db.add(payment_method)
                    db.commit()
                    db.refresh(payment_method)
                else:
                    return False, "No payment method found locally or in Square."
            else:
                return False, "No Customer ID and no Payment Method found."
        
        # Validate Card ID
        card_id_to_use = payment_method.square_card_id
        if not card_id_to_use:
            return False, "Payment Method has no card_id."

        # Create Subscription
        idempotency_key = str(uuid_lib.uuid4())
        subscription_result = create_subscription(
            customer_id=p.square_customer_id, # Must use stored ID
            location_id=location_id,
            plan_variation_id=p.pending_subscription_plan_variation_id,
            card_id=card_id_to_use,
            idempotency_key=idempotency_key
        )

        if subscription_result.get("success"):
            subscription_id = subscription_result.get('subscription_id')
            p.subscription_active = True
            p.pending_subscription_plan_variation_id = None
            p.square_subscription_id = subscription_id
            db.commit()
            return True, None
        else:
             return False, subscription_result.get("error", "Unknown Square error")

    except Exception as e:
        logger.error(f"Error activating subscription: {e}")
        return False, str(e)


@router.put("/{professional_id}/subscription", dependencies=[Depends(get_current_user)])
def update_professional_subscription(
    professional_id: int,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_current_user)
):
    """
    Update subscription information for a professional.
    Allows professionals to update their pending subscription plan before verification.
    Professionals can only update their own subscription. Admins can update any professional's subscription.
    """
    # Get professional from database
    p = db.query(Professional).filter(Professional.id == professional_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Professional not found")
    
    # Check user role
    user_role = payload.get("role")
    is_admin = user_role == "admins"
    
    # If not admin, verify the professional is updating their own subscription
    if not is_admin:
        # Verify the professional is updating their own subscription
        # Check by ID or email from token
        token_pro_id = payload.get("uid") or payload.get("user_id") or payload.get("id")
        token_email = payload.get("sub")
        
        is_own_profile = False
        if token_pro_id and str(token_pro_id) == str(professional_id):
            is_own_profile = True
        elif token_email and token_email == p.email:
            is_own_profile = True
        
        if not is_own_profile:
            raise HTTPException(
                status_code=403,
                detail="You can only update your own subscription"
            )
    
    # Extract subscription plan variation ID from request
    subscription_plan_variation_id = data.get("subscription_plan_variation_id")
    
    if subscription_plan_variation_id is None:
        raise HTTPException(
            status_code=400,
            detail="subscription_plan_variation_id is required"
        )
    
    # Validate subscription plan variation ID
    valid_plans = {
        "LYIAHPLNYRD3AX5FPCDDYDV3": "Pro Town Network Monthly",
        "VGMYZYBSVKPM3CJWYK35FS7N": "Pro Town Network Yearly",
        "JDCZJQKUQOYZQI73XOMDOH3H": "ProTown Testing"
    }
    
    if subscription_plan_variation_id not in valid_plans:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid subscription plan. Use 'LYIAHPLNYRD3AX5FPCDDYDV3' for Monthly or 'VGMYZYBSVKPM3CJWYK35FS7N' for Yearly"
        )
    
    # Only allow updating pending subscription if professional is not verified yet
    # If already verified and has active subscription, they should use the payment subscription update endpoint
    if p.verified_status and p.subscription_active:
        raise HTTPException(
            status_code=400,
            detail="Cannot update subscription plan. You already have an active subscription. Please use the subscription update endpoint to change your plan."
        )
    
    # Update pending subscription plan variation ID
    p.pending_subscription_plan_variation_id = subscription_plan_variation_id
    db.commit()
    db.refresh(p)
    
    logger.info(f"Updated subscription plan for professional {p.id} to {valid_plans[subscription_plan_variation_id]}")
    
    return {
        "success": True,
        "message": f"Subscription plan updated to {valid_plans[subscription_plan_variation_id]}. The subscription will be activated when your account is verified.",
        "professional_id": p.id,
        "pending_subscription_plan_variation_id": p.pending_subscription_plan_variation_id,
        "plan_name": valid_plans[subscription_plan_variation_id],
        "verified_status": p.verified_status,
        "subscription_active": p.subscription_active
    }

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

    logger.info(f"DEBUG: create_professional payload extracted: sub_plan={subscription_plan_variation_id}, source={payment_source_id}, card={card_id}, cust={square_customer_id}")

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

    # ✅ Explicitly add Square fields if they were popped or missing from data
    if subscription_plan_variation_id:
        professional_data["pending_subscription_plan_variation_id"] = subscription_plan_variation_id
    
    if square_customer_id:
        professional_data["square_customer_id"] = square_customer_id

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
    logger.info(f"DEBUG: Checking subscription condition: plan={subscription_plan_variation_id}, source={payment_source_id}, card={card_id}")
    
    if subscription_plan_variation_id and (payment_source_id or card_id):
        logger.info("DEBUG: Entering subscription setup block")
        try:
            from utils.square_client import create_square_customer, create_card_on_file, update_square_customer, search_subscriptions
            from models.payment_method import PaymentMethod
            
            # Validate subscription plan variation ID
            valid_plans = {
                "LYIAHPLNYRD3AX5FPCDDYDV3": "Pro Town Network Monthly",
                "VGMYZYBSVKPM3CJWYK35FS7N": "Pro Town Network Yearly",
                "JDCZJQKUQOYZQI73XOMDOH3H": "ProTown Testing"
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
                # Reuse existing customer (from validation step or provided)
                # Update customer details with actual professional information
                logger.info(f"Reusing existing Square customer {square_customer_id} for professional {p.id}")
                update_result = update_square_customer(
                    customer_id=square_customer_id,
                    given_name=p.name.split()[0] if p.name else "Professional",
                    family_name=" ".join(p.name.split()[1:]) if p.name and len(p.name.split()) > 1 else "",
                    email=p.email,
                    phone_number=p.phone_number
                )
                if not update_result.get("success"):
                    logger.warning(f"Failed to update Square customer {square_customer_id}: {update_result.get('error')}")
                    # Continue anyway, as we have the ID - customer exists even if update fails
            else:
                # Create new Square customer (no charge)
                logger.info(f"Creating new Square customer for professional {p.id}")
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
                logger.info(f"Created Square customer {square_customer_id} for professional {p.id}")
                
                # CRITICAL: After creating customer, check for any existing cards and create payment method
                # This uses the same logic as /payments/save-method endpoint
                from utils.square_client import get_customer_cards
                cards_result = get_customer_cards(square_customer_id)
                
                if cards_result.get("success") and cards_result.get("cards"):
                    cards = cards_result.get("cards", [])
                    if cards:
                        # Use the first card to create payment method
                        first_card = cards[0]
                        card_id = first_card.get("id")
                        
                        # Check if payment method already exists
                        existing_payment_method = db.query(PaymentMethod).filter(
                            PaymentMethod.professional_id == p.id,
                            PaymentMethod.square_card_id == card_id
                        ).first()
                        
                        if not existing_payment_method:
                            # Create payment method using same logic as /payments/save-method
                            existing_methods_count = db.query(PaymentMethod).filter(
                                PaymentMethod.professional_id == p.id
                            ).count()
                            is_default = existing_methods_count == 0
                            
                            if is_default:
                                db.query(PaymentMethod).filter(
                                    PaymentMethod.professional_id == p.id
                                ).update({"is_default": False})
                            
                            payment_method = PaymentMethod(
                                professional_id=p.id,
                                square_card_id=card_id,
                                last_4_digits=first_card.get("last_4", "****")[-4:] if len(first_card.get("last_4", "")) >= 4 else "****",
                                card_brand=first_card.get("card_brand", "UNKNOWN"),
                                exp_month=first_card.get("exp_month"),
                                exp_year=first_card.get("exp_year"),
                                is_default=is_default
                            )
                            db.add(payment_method)
                            db.commit()
                            db.refresh(payment_method)
                            logger.info(f"✅ Created payment method from Square card {card_id} for professional {p.id} (using /payments/save-method logic)")
            
            # Handle Card
            # If card_id is provided (from validation step), reuse it
            # Otherwise, create new card from payment_source_id
            final_card_id = card_id
            final_last_4 = "****"
            final_brand = "UNKNOWN"
            final_exp_month = None
            final_exp_year = None

            if card_id:
                # Card was already created during validation - reuse it
                logger.info(f"Reusing existing card {card_id} from validation step for professional {p.id}")
                # Note: We don't have card details from validation, so we'll use defaults
                # The card is already associated with the customer from validation
            elif payment_source_id:
                # CRITICAL: Create card on file with the correct customer_id
                # This MUST use the square_customer_id to ensure card belongs to this customer
                logger.info(f"Creating card for customer {square_customer_id} (professional {p.id}, email: {p.email})")
                card_result = create_card_on_file(
                    source_id=payment_source_id,
                    customer_id=square_customer_id  # CRITICAL: Must match the customer
                )
                
                if not card_result.get("success"):
                    logger.error(f"Failed to create card on file for customer {square_customer_id}: {card_result.get('error')}")
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
                
                # CRITICAL: Immediately verify the card was created for the correct customer
                if not final_card_id:
                    raise HTTPException(
                        status_code=500,
                        detail="Card creation succeeded but no card_id returned from Square. Please try again."
                    )
                
                # CRITICAL: Verify the card response from Square includes customer_id
                card_response_customer_id = card_result.get("customer_id")
                if not card_response_customer_id:
                    # Card was created but not associated with customer - this is the problem!
                    logger.error(f"❌ CRITICAL: Card {final_card_id} was created but Square response shows NO customer_id!")
                    logger.error(f"   This means the card was NOT associated with customer {square_customer_id}")
                    logger.error(f"   Card creation may have succeeded but card is orphaned (not linked to customer)")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Card was created but not associated with customer. Square API did not return customer_id in card response. Card ID: {final_card_id}, Expected customer: {square_customer_id}. Please check Square dashboard - the card may exist but not be linked to the customer."
                    )
                
                if card_response_customer_id != square_customer_id:
                    logger.error(f"❌ CRITICAL: Card {final_card_id} was created for customer {card_response_customer_id}, but we requested {square_customer_id}!")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Card created for wrong customer. Expected {square_customer_id}, got {card_response_customer_id}"
                    )
                
                logger.info(f"✅ Card {final_card_id} response confirms it belongs to customer {square_customer_id}")
                
                # Additional verification: Fetch customer's cards to double-check
                logger.info(f"Double-checking: Fetching all cards for customer {square_customer_id}")
                from utils.square_client import get_customer_cards
                verify_result = get_customer_cards(square_customer_id)
                
                if verify_result.get("success"):
                    cards = verify_result.get("cards", [])
                    card_found = any(
                        card.get("id") == final_card_id or 
                        (final_card_id.startswith("ccof:") and card.get("id") == final_card_id.replace("ccof:", "")) or
                        (card.get("id").startswith("ccof:") and final_card_id == card.get("id").replace("ccof:", ""))
                        for card in cards
                    )
                    if card_found:
                        logger.info(f"✅ DOUBLE-VERIFIED: Card {final_card_id} found in customer {square_customer_id}'s card list")
                    else:
                        # Card not in customer's list - might be timing issue, but log warning
                        logger.warning(f"⚠️  Card {final_card_id} not immediately found in customer's card list (timing issue?)")
                        logger.warning(f"   Customer has {len(cards)} card(s): {[c.get('id') for c in cards]}")
                        logger.warning(f"   Card response confirmed customer_id={card_response_customer_id}, so card should be linked")
                        # Don't fail here since card response confirmed customer_id - might be API timing
                else:
                    # Verification API call failed - but card response confirmed customer_id, so proceed
                    error_msg = verify_result.get("error", "Unknown error")
                    http_status = verify_result.get("http_status")
                    logger.warning(f"⚠️  Could not fetch customer cards list: {error_msg} (HTTP {http_status})")
                    logger.warning(f"   However, card creation response confirmed customer_id={card_response_customer_id}, so proceeding")
                    # Don't fail - card response already confirmed customer association
            
            # Save card to database (for later use when verified)
            logger.info(f"DEBUG: Saving payment method: pro_id={p.id}, card_id={final_card_id}, customer_id={square_customer_id}, last4={final_last_4}")
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
            # CRITICAL: Always store the customer_id that was used to create the card
            p.pending_subscription_plan_variation_id = subscription_plan_variation_id
            p.square_customer_id = square_customer_id  # This MUST match the customer_id used in create_card_on_file
            p.subscription_active = False  # Not active until verified
            
            db.commit()
            db.refresh(p)
            logger.info("DEBUG: Payment method saved and professional updated")
            
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

@router.get("/me/subscription")
def get_my_subscription(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Get the professional's current subscription details from Square with plan information
    """
    # Get professional from token (current_user is a dict)
    pro_id = current_user.get("uid") or current_user.get("user_id") or current_user.get("id")
    email = current_user.get("sub")
    
    prof = None
    if pro_id:
        prof = db.query(Professional).filter(Professional.id == int(pro_id)).first()
    if not prof and email:
        prof = db.query(Professional).filter(Professional.email == email).first()
        
    if not prof:
        raise HTTPException(status_code=404, detail="Professional not found")
    
    if not prof.square_customer_id:
        return {"active": False, "message": "No Square customer ID found"}

    from utils.square_client import search_subscriptions, get_subscription_plans
    from models.subscription import Subscription
    import requests

    # Search for subscriptions for this customer
    result = search_subscriptions([prof.square_customer_id])
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))

    subscriptions = result.get("subscriptions", [])
    
    # Filter for active or paused subscriptions
    active_subs = [s for s in subscriptions if s.get("status") in ["ACTIVE", "PAUSED"]]

    if not active_subs:
        return {"active": False, "message": "No active subscriptions found"}

    # Get the first active subscription
    sub = active_subs[0]
    plan_variation_id = sub.get("plan_variation_id")
    square_status = sub.get("status")
    
    # Update local database with current status from Square
    if square_status:
        prof.subscription_status = square_status
        if square_status == "ACTIVE":
            prof.subscription_active = True
        elif square_status in ["PAUSED", "CANCELED"]:
            prof.subscription_active = False
        db.commit()
        logger.info(f"Synced professional {prof.id} subscription_status to {square_status}")
    
    # Fetch plan details - try local DB first, then Square catalog
    plan_name = "Subscription Plan"
    price = "$0.00"
    billing_period = "monthly"
    plan_description = None
    
    # Try to get plan details from local database first
    if plan_variation_id:
        db_plan = db.query(Subscription).filter(
            Subscription.plan_variation_id == plan_variation_id
        ).first()
        
        if db_plan:
            plan_name = db_plan.plan_name or "Subscription Plan"
            if db_plan.plan_cost:
                price = f"${float(db_plan.plan_cost):.2f}"
            plan_description = db_plan.plan_description
            logger.info(f"Found plan details in local DB: {plan_name}")
    
    # If not found in DB or need more details, fetch from Square catalog
    if plan_variation_id and (not plan_description or price == "$0.00"):
        try:
            # Get all subscription plans from Square
            plans_result = get_subscription_plans()
            
            if plans_result.get("success"):
                plans = plans_result.get("plans", [])
                
                # Find the matching plan variation
                for plan in plans:
                    for variation in plan.get("variations", []):
                        if variation.get("id") == plan_variation_id:
                            # Found the matching variation
                            if not db_plan or not db_plan.plan_name:
                                plan_name = variation.get("name") or plan.get("name", "Subscription Plan")
                            
                            # Get price from phases
                            phases = variation.get("phases", [])
                            if phases and len(phases) > 0:
                                phase = phases[0]
                                price_money = phase.get("recurring_price_money", {})
                                amount = price_money.get("amount", 0)
                                currency = price_money.get("currency", "USD")
                                
                                # Convert cents to dollars
                                if amount > 0:
                                    price = f"${amount / 100:.2f}"
                                
                                # Determine billing period
                                cadence = phase.get("cadence", "MONTHLY")
                                if cadence == "MONTHLY":
                                    billing_period = "month"
                                elif cadence == "ANNUAL":
                                    billing_period = "year"
                                elif cadence == "WEEKLY":
                                    billing_period = "week"
                                elif cadence == "DAILY":
                                    billing_period = "day"
                            
                            break
                    else:
                        continue
                    break
        except Exception as e:
            logger.error(f"Error fetching plan details from Square: {e}")
            # Continue with DB values or defaults
    
    return {
        "active": True,
        "subscription": sub,
        "plan_name": plan_name,
        "plan_variation_id": plan_variation_id,
        "price": price,
        "billing_period": billing_period,
        "plan_description": plan_description,
        "status": square_status,
        "subscription_status": prof.subscription_status,  # Include DB status
        "renewal_date": sub.get("charged_through_date"),
        "start_date": sub.get("start_date"),
        "square_subscription_id": sub.get("id")
    }