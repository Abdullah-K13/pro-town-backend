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
    aws_access_key_id="AKIA46ALPOQWPLWEINMP",
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
    
    # Apply fields if provided (but don't commit verified_status yet - wait for subscription success)
    fields_to_apply = {k: v for k, v in update_data.items() if k != "verified_status"}
    for k, v in fields_to_apply.items():
        setattr(p, k, v)
    
    # If professional is being verified and has pending subscription, activate it
    # This happens BEFORE setting verified_status to ensure subscription is created first
    subscription_created = False
    subscription_error = None
    had_pending_subscription = bool(p.pending_subscription_plan_variation_id)
    
    if not was_verified and will_be_verified and p.pending_subscription_plan_variation_id:
        try:
            from utils.square_client import create_subscription, get_square_customer_by_email
            from models.payment_method import PaymentMethod
            import uuid as uuid_lib
            import os
            
            # Get saved payment method - try default first, then any payment method
            payment_method = db.query(PaymentMethod).filter(
                PaymentMethod.professional_id == p.id,
                PaymentMethod.is_default == True
            ).first()
            
            # If no default payment method, try to get any payment method
            if not payment_method:
                payment_method = db.query(PaymentMethod).filter(
                    PaymentMethod.professional_id == p.id
                ).first()
                
                # If we found a payment method but it's not default, set it as default
                if payment_method:
                    # Unset other defaults
                    db.query(PaymentMethod).filter(
                        PaymentMethod.professional_id == p.id,
                        PaymentMethod.id != payment_method.id
                    ).update({"is_default": False})
                    # Set this one as default
                    payment_method.is_default = True
                    db.commit()
                    logger.info(f"Set payment method {payment_method.id} as default for professional {p.id}")
            
            if not payment_method:
                # Check if professional has square_customer_id and try to get cards from Square
                square_customer_id = p.square_customer_id
                if not square_customer_id:
                    # Try to find customer by email
                    customer_result = get_square_customer_by_email(p.email)
                    if customer_result.get("success"):
                        square_customer_id = customer_result.get("customer_id")
                        p.square_customer_id = square_customer_id
                        db.commit()
                
                if square_customer_id:
                    # First verify the customer exists in Square
                    from utils.square_client import get_square_customer_by_id, get_customer_cards, get_square_customer_by_email
                    customer_check = get_square_customer_by_id(square_customer_id)
                    
                    # If stored customer_id doesn't exist, try to find customer by email
                    if not customer_check.get("success"):
                        http_status = customer_check.get("http_status")
                        if http_status == 404:
                            logger.warning(f"⚠️  Stored customer_id {square_customer_id} not found in Square. Searching by email: {p.email}")
                            # Try to find customer by email
                            email_search = get_square_customer_by_email(p.email)
                            if email_search.get("success"):
                                # Found customer by email - update stored ID
                                correct_customer_id = email_search.get("customer_id")
                                logger.info(f"✅ Found customer by email. Updating stored customer_id from {square_customer_id} to {correct_customer_id}")
                                p.square_customer_id = correct_customer_id
                                square_customer_id = correct_customer_id
                                db.commit()
                            else:
                                logger.error(f"❌ Professional {p.id} verified but Square customer {square_customer_id} does NOT exist in Square (404).")
                                logger.error(f"   Searched by email {p.email} but customer not found.")
                                logger.error(f"   This customer_id may be from a different environment (sandbox vs production) or was deleted.")
                                logger.error(f"   Action needed: Professional must add a payment method via /payments/save-method or re-register with card.")
                                return p
                        else:
                            logger.error(f"Professional {p.id} verified but could not verify Square customer {square_customer_id}: {customer_check.get('error')}")
                            return p
                    
                    # Customer exists, now try to get cards
                    cards_result = get_customer_cards(square_customer_id)
                    
                    if cards_result.get("success") and cards_result.get("cards"):
                        cards = cards_result.get("cards", [])
                        if cards:
                            # Use the first card
                            first_card = cards[0]
                            card_id = first_card.get("id")
                            
                            # Create payment method from Square card
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
                            logger.info(f"✅ Created payment method from Square card {card_id} for professional {p.id}")
                        else:
                            logger.error(f"❌ Professional {p.id} verified but customer {square_customer_id} has no cards in Square.")
                            logger.error(f"   Professional email: {p.email}")
                            logger.error(f"   Action needed: Professional must add a payment method via /payments/save-method endpoint.")
                            return p
                    else:
                        # Cards API returned error - try searching by email as fallback
                        http_status = cards_result.get("http_status")
                        error_msg = cards_result.get("error", "Unknown error")
                        
                        if http_status == 404:
                            # 404 from cards API - customer might exist but cards API might have issues
                            # Try to verify customer exists and search by email as fallback
                            logger.warning(f"⚠️  Cards API returned 404 for customer {square_customer_id}. Verifying customer exists...")
                            
                            # Double-check customer exists
                            customer_verify = get_square_customer_by_id(square_customer_id)
                            if not customer_verify.get("success"):
                                # Customer doesn't exist with stored ID - try email search
                                logger.warning(f"⚠️  Customer {square_customer_id} not found. Searching by email: {p.email}")
                                email_search = get_square_customer_by_email(p.email)
                                if email_search.get("success"):
                                    correct_customer_id = email_search.get("customer_id")
                                    logger.info(f"✅ Found customer by email. Updating stored customer_id from {square_customer_id} to {correct_customer_id}")
                                    p.square_customer_id = correct_customer_id
                                    square_customer_id = correct_customer_id
                                    db.commit()
                                    
                                    # Try getting cards again with correct customer ID
                                    cards_result = get_customer_cards(square_customer_id)
                                    if cards_result.get("success") and cards_result.get("cards"):
                                        cards = cards_result.get("cards", [])
                                        if cards:
                                            first_card = cards[0]
                                            card_id = first_card.get("id")
                                            
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
                                            logger.info(f"✅ Created payment method from Square card {card_id} for professional {p.id} using corrected customer_id")
                                        else:
                                            logger.error(f"❌ Professional {p.id} verified but customer {square_customer_id} has no cards in Square.")
                                            logger.error(f"   Professional email: {p.email}")
                                            logger.error(f"   Action needed: Professional must add a payment method via /payments/save-method endpoint.")
                                            return p
                                    else:
                                        logger.error(f"❌ Professional {p.id} verified but customer {square_customer_id} has no cards in Square (404 from cards API).")
                                        logger.error(f"   Professional email: {p.email}")
                                        logger.error(f"   Action needed: Professional must add a payment method via /payments/save-method endpoint.")
                                        return p
                                else:
                                    logger.error(f"❌ Professional {p.id} verified but could not find customer in Square by ID or email.")
                                    logger.error(f"   Stored customer_id: {square_customer_id}")
                                    logger.error(f"   Professional email: {p.email}")
                                    logger.error(f"   Action needed: Professional must add a payment method via /payments/save-method endpoint.")
                                    return p
                            else:
                                # Customer exists but cards API returned 404 - likely no cards
                                logger.error(f"❌ Professional {p.id} verified but customer {square_customer_id} has no cards in Square (404 from cards API).")
                                logger.error(f"   Professional email: {p.email}")
                                logger.error(f"   Customer exists in Square but has no saved cards.")
                                logger.error(f"   Action needed: Professional must add a payment method via /payments/save-method endpoint.")
                                return p
                        else:
                            logger.error(f"Professional {p.id} verified but could not retrieve cards from Square: {error_msg} (HTTP {http_status})")
                            return p
                else:
                    logger.error(f"Professional {p.id} verified but no payment method found and no Square customer ID. Subscription not activated.")
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
                    
                    # CRITICAL: When we find/create a customer, also check for cards and create payment method
                    # This ensures payment methods are created using the same logic as /payments/save-method
                    logger.info(f"Found customer {square_customer_id} by email. Checking for cards to create payment method...")
                    cards_result = get_customer_cards(square_customer_id)
                    
                    if cards_result.get("success") and cards_result.get("cards"):
                        cards = cards_result.get("cards", [])
                        if cards:
                            # Check if payment method already exists for this card
                            first_card = cards[0]
                            card_id = first_card.get("id")
                            
                            # Check if we already have this card saved
                            existing_payment_method = db.query(PaymentMethod).filter(
                                PaymentMethod.professional_id == p.id,
                                PaymentMethod.square_card_id == card_id
                            ).first()
                            
                            if not existing_payment_method:
                                # Create payment method from Square card using same logic as /payments/save-method
                                existing_methods_count = db.query(PaymentMethod).filter(
                                    PaymentMethod.professional_id == p.id
                                ).count()
                                is_default = existing_methods_count == 0
                                
                                # If setting as default, unset other defaults
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
                            else:
                                logger.info(f"Payment method already exists for card {card_id}")
                                payment_method = existing_payment_method
            
            if not square_customer_id:
                logger.error(f"Professional {p.id} verified but no Square customer ID found. Subscription not activated.")
                return p
            
            # Get location ID - try configured one first, then get available locations
            location_id = os.getenv("SQUARE_LOCATION_ID", "")
            from utils.square_client import get_square_locations
            
            # If location_id is set, verify it's accessible
            if location_id:
                locations_result = get_square_locations()
                if locations_result.get("success"):
                    available_location_ids = locations_result.get("location_ids", [])
                    if location_id not in available_location_ids:
                        logger.warning(f"Configured location ID {location_id} not accessible. Available locations: {available_location_ids}")
                        # Use first available location if configured one doesn't work
                        if available_location_ids:
                            location_id = available_location_ids[0]
                            logger.info(f"Using first available location: {location_id}")
                        else:
                            logger.error(f"No accessible locations found for professional {p.id}.")
                            return p
                else:
                    logger.warning(f"Could not verify location access: {locations_result.get('error')}")
            else:
                # No location ID configured, get first available
                locations_result = get_square_locations()
                if locations_result.get("success") and locations_result.get("location_ids"):
                    location_id = locations_result.get("location_ids")[0]
                    logger.info(f"No SQUARE_LOCATION_ID configured. Using first available location: {location_id}")
                else:
                    logger.error(f"SQUARE_LOCATION_ID not set and could not get locations. Subscription not activated for professional {p.id}.")
                    return p
            
            # CRITICAL: Ensure the card belongs to this customer
            # The stored card_id MUST belong to the current square_customer_id
            stored_card_id = payment_method.square_card_id
            
            if not stored_card_id:
                logger.error(f"Professional {p.id} has no card_id stored in payment method.")
                return p
            
            # Verify the stored card belongs to this customer
            # This prevents the INVALID_CARD error where card belongs to different customer
            from utils.square_client import get_customer_cards
            cards_result = get_customer_cards(square_customer_id)
            card_id_to_use = None
            
            if cards_result.get("success") and cards_result.get("cards"):
                cards = cards_result.get("cards", [])
                # Find the stored card in the customer's cards
                for card in cards:
                    card_id = card.get("id")
                    # Match exact ID or handle ccof: prefix
                    if card_id == stored_card_id:
                        card_id_to_use = card_id
                        break
                    # Also check if stored is ccof: and card is without prefix (or vice versa)
                    elif stored_card_id.startswith("ccof:") and card_id == stored_card_id.replace("ccof:", ""):
                        card_id_to_use = card_id
                        break
                    elif card_id.startswith("ccof:") and stored_card_id == card_id.replace("ccof:", ""):
                        card_id_to_use = card_id
                        break
                
                if card_id_to_use:
                    logger.info(f"✅ Verified card {card_id_to_use} belongs to customer {square_customer_id} for professional {p.id}")
                else:
                    # Stored card not found in customer's cards - CRITICAL ERROR
                    logger.error(f"❌ CRITICAL: Stored card_id '{stored_card_id}' does NOT belong to customer '{square_customer_id}'")
                    logger.error(f"   Professional ID: {p.id}, Email: {p.email}")
                    logger.error(f"   Customer has {len(cards)} card(s): {[c.get('id') for c in cards]}")
                    logger.error(f"   This means the card was created for a different customer or environment.")
                    logger.error(f"   Cannot create subscription - card/customer mismatch will cause INVALID_CARD error.")
                    return p
            else:
                # Card lookup failed - could be API issue or customer has no cards
                error_msg = cards_result.get("error", "Unknown error")
                http_status = cards_result.get("http_status")
                
                # If 404, it means customer has no cards, but we have a stored card_id - this is a problem!
                if http_status == 404:
                    logger.error(f"❌ CRITICAL: Customer '{square_customer_id}' has NO cards in Square (404), but we have stored card_id '{stored_card_id}'")
                    logger.error(f"   This indicates the card was created for a different customer or in a different environment.")
                    logger.error(f"   Cannot safely create subscription - would result in INVALID_CARD error.")
                    return p
                else:
                    # API error - log but try to proceed with stored card (risky but might work)
                    logger.warning(f"⚠️  Could not verify card ownership via API: {error_msg} (HTTP {http_status})")
                    logger.warning(f"   Using stored card_id '{stored_card_id}' without verification.")
                    logger.warning(f"   If this fails with INVALID_CARD error, the card belongs to a different customer.")
                    card_id_to_use = stored_card_id
            
            if not card_id_to_use:
                logger.error(f"Could not determine valid card_id for professional {p.id}")
                return p
            
            # Create subscription (THIS IS WHERE THE CHARGE HAPPENS)
            idempotency_key = str(uuid_lib.uuid4())
            logger.info(f"Creating subscription for professional {p.id} with card_id: {card_id_to_use}")
            subscription_result = create_subscription(
                customer_id=square_customer_id,
                location_id=location_id,
                plan_variation_id=p.pending_subscription_plan_variation_id,
                source_id=None,
                card_id=card_id_to_use,
                idempotency_key=idempotency_key
            )
            
            if subscription_result.get("success"):
                # Subscription created and charged successfully
                subscription_id = subscription_result.get('subscription_id')
                subscription_status = subscription_result.get('status', 'ACTIVE')
                
                # Update database with subscription info
                p.subscription_active = True
                p.pending_subscription_plan_variation_id = None  # Clear pending flag
                p.square_subscription_id = subscription_id  # Save subscription ID
                subscription_created = True
                
                logger.info(f"✅ Subscription created and charged for professional {p.id}")
                logger.info(f"   Subscription ID: {subscription_id}")
                logger.info(f"   Status: {subscription_status}")
                logger.info(f"   Customer ID: {square_customer_id}")
                logger.info(f"   Card ID: {card_id_to_use}")
                logger.info(f"   Plan: {p.pending_subscription_plan_variation_id}")
            else:
                error_msg = subscription_result.get('error', 'Unknown error')
                http_status = subscription_result.get('http_status', 'N/A')
                subscription_error = error_msg
                
                logger.error(f"❌ Failed to create subscription for professional {p.id}")
                logger.error(f"   Error: {error_msg} (HTTP {http_status})")
                logger.error(f"   Customer ID: {square_customer_id}")
                logger.error(f"   Card ID used: {card_id_to_use}")
                logger.error(f"   Plan: {p.pending_subscription_plan_variation_id}")
                
                # Check for specific error types
                error_lower = error_msg.lower()
                if "declined" in error_lower or "insufficient" in error_lower:
                    logger.error(f"   ⚠️  Payment declined - card may be declined or insufficient funds")
                elif "invalid_card" in error_lower or "card" in error_lower and "invalid" in error_lower:
                    logger.error(f"   ⚠️  Invalid card - card may not belong to customer or is invalid")
                elif "customer" in error_lower and "not found" in error_lower:
                    logger.error(f"   ⚠️  Customer not found - customer_id may be invalid")
                
                # Don't set verified_status if subscription fails
                # Admin can retry subscription activation later
                subscription_created = False
                
        except Exception as e:
            subscription_error = str(e)
            logger.error(f"❌ Exception activating subscription for professional {p.id}: {str(e)}")
            logger.error(f"   Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            subscription_created = False
    
    # Only set verified_status to True if subscription was successfully created
    # OR if there's no pending subscription to activate
    if not was_verified and will_be_verified:
        if had_pending_subscription:
            # Had pending subscription - only verify if subscription was created
            if subscription_created:
                p.verified_status = True
                logger.info(f"✅ Professional {p.id} verified and subscription activated")
            else:
                # Subscription failed - keep verified_status as False
                logger.warning(f"⚠️  Professional {p.id} verification deferred - subscription creation failed")
                if subscription_error:
                    logger.warning(f"   Error: {subscription_error}")
                logger.warning(f"   Professional will remain unverified until subscription is successfully created")
                # Revert verified_status to False
                p.verified_status = False
        else:
            # No pending subscription - just verify
            p.verified_status = True
            logger.info(f"✅ Professional {p.id} verified (no subscription to activate)")
    
    # Commit all changes
    db.commit()
    db.refresh(p)
    
    # Return response with subscription status
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
            from utils.square_client import create_square_customer, create_card_on_file, update_square_customer
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