from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.init import get_db
from models.admin import Admin
from models.professional import Professional
from models.customer import Customer
from utils.security import hash_password, verify_password, create_access_token
from models.login import LoginRequest
from utils.square_client import create_square_customer, create_subscription
import os
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/signup")
def signup(role: str, data: dict, db: Session = Depends(get_db)):
    """
    Signup endpoint for creating new users.
    
    For professionals, you can optionally include:
    - subscription_plan_variation_id: "LYIAHPLNYRD3AX5FPCDDYDV3" (Monthly) or "VGMYZYBSVKPM3CJWYK35FS7N" (Yearly)
    - payment_source_id: Payment token from Square Web Payments SDK
    
    If both are provided, a subscription will be automatically created.
    """
    if role == "admin":
        data["password_hash"] = hash_password(data.pop("password"))
        user = Admin(**data)
    elif role == "professional":
        # Extract subscription-related fields before creating professional
        subscription_plan_variation_id = data.pop("subscription_plan_variation_id", None)
        payment_source_id = data.pop("payment_source_id", None)
        location_id = data.pop("location_id", None) or os.getenv("SQUARE_LOCATION_ID", "")
        
        # Hash password
        data["password_hash"] = hash_password(data.pop("password"))
        
        # Create professional first
        user = Professional(**data)
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # If subscription details provided, validate card and save for later (NO CHARGE YET)
        if subscription_plan_variation_id and payment_source_id:
            try:
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
                
                # Create Square customer (no charge)
                customer_result = create_square_customer(
                    given_name=user.name.split()[0] if user.name else "Professional",
                    family_name=" ".join(user.name.split()[1:]) if user.name and len(user.name.split()) > 1 else "",
                    email=user.email,
                    phone_number=user.phone_number
                )
                
                if not customer_result.get("success"):
                    logger.error(f"Failed to create Square customer: {customer_result.get('error')}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to create Square customer: {customer_result.get('error')}. Professional account created but card validation failed."
                    )
                
                square_customer_id = customer_result.get("customer_id")
                
                # Create card on file (validates card, but NO CHARGE)
                from utils.square_client import create_card_on_file
                from models.payment_method import PaymentMethod
                
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
                
                # Save card to database (for later use when verified)
                payment_method = PaymentMethod(
                    professional_id=user.id,
                    square_card_id=card_result.get("card_id"),
                    last_4_digits=card_result.get("last_4", "****"),
                    card_brand=card_result.get("brand", "UNKNOWN"),
                    exp_month=card_result.get("exp_month"),
                    exp_year=card_result.get("exp_year"),
                    is_default=True
                )
                db.add(payment_method)
                
                # Store subscription plan and customer ID for later activation
                user.pending_subscription_plan_variation_id = subscription_plan_variation_id
                user.square_customer_id = square_customer_id
                user.subscription_active = False  # Not active until verified
                
                db.commit()
                db.refresh(user)
                
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
                logger.error(f"Error validating card during signup: {str(e)}")
                subscription_info = {
                    "subscription_created": False,
                    "card_validated": False,
                    "error": str(e),
                    "message": "Professional account created but card validation failed. Please contact support."
                }
        else:
            subscription_info = {
                "subscription_created": False,
                "card_validated": False,
                "message": "No subscription plan provided. You can add a subscription plan later."
            }
    elif role == "customer":
        data["password_hash"] = hash_password(data.pop("password"))
        user = Customer(**data)
    else:
        raise HTTPException(400, "Invalid role")
    
    # For non-professional roles, add user normally
    if role != "professional":
        db.add(user)
        db.commit()
        db.refresh(user)
    
    access_token = create_access_token({"sub": user.email, "role": role})
    
    response = {
        "message": f"{role.capitalize()} created successfully",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "role": role,
            "email": getattr(user, "email", None),
            "name": getattr(user, "name", None),
        },
    }
    
    # Add subscription info for professionals
    if role == "professional" and "subscription_info" in locals():
        response["subscription"] = subscription_info
    
    return response

@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    email = body.email
    password = body.password

    user = db.query(Admin).filter(Admin.email == email).first()
    role = "admins"
    if not user:
        user = db.query(Professional).filter(Professional.email == email).first()
        role = "professionals"
    if not user:
        user = db.query(Customer).filter(Customer.email == email).first()
        role = "customers"

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": user.email, "role": role})
    return {"access_token": token, "token_type": "bearer", "role": role}