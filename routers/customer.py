from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.init import get_db
from models.customer import Customer
from utils.deps import role_required
from utils.deps import get_current_user
from utils.security import hash_password, create_access_token

router = APIRouter()

@router.get("/", dependencies=[Depends(role_required("admins"))])
def get_all_customers(db: Session = Depends(get_db)):
    return db.query(Customer).all()

@router.get("/me", dependencies=[Depends(role_required("customers"))])
def get_my_customer_profile(
    db: Session = Depends(get_db),
    payload = Depends(get_current_user),
):
    """
    Return the customer that matches the current access token.
    We try user id from the token first, then email (sub) as a fallback.
    """
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Common JWT claims you’ve used before:
    #   role = payload.get("role")
    #   email = payload.get("sub")
    # You might also have a dedicated id claim:
    customer_id = payload.get("uid") or payload.get("user_id") or payload.get("id")
    email = payload.get("sub")

    customer = None
    if customer_id is not None:
        customer = db.query(Customer).filter(Customer.id == int(customer_id)).first()

    if customer is None and email:
        customer = db.query(Customer).filter(Customer.email == email).first()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    return customer


@router.get("/{customer_id}")
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Not found")
    return customer

@router.post("/")
def create_customer(data: dict, db: Session = Depends(get_db)):
    # Required fields
    required = ["first_name", "last_name", "email", "password", "phone_number"]
    missing = [f for f in required if f not in data or not data[f]]

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields: {', '.join(missing)}"
        )

    # Check if email already exists
    exists = db.query(Customer).filter(Customer.email == data["email"]).first()
    if exists:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    # Hash password
    password_hash = hash_password(data.pop("password"))

    # Create customer
    new_c = Customer(
        first_name=data["first_name"],
        last_name=data["last_name"],
        email=data["email"],
        password_hash=password_hash,
        phone_number=data.get("phone_number"),
    )
    access_token = create_access_token({"sub": new_c.email, "role": "customers"})
    db.add(new_c)
    db.commit()
    db.refresh(new_c)

    return {"message": "Customer created successfully", "access_token": access_token, "token_type": "bearer", "customer": new_c}


@router.put("/me", dependencies=[Depends(role_required("customers"))])
def update_my_customer_profile(
    data: dict,
    db: Session = Depends(get_db),
    payload = Depends(get_current_user),
):
    """
    Update the currently authenticated customer's profile
    using the access token. No need to send customer_id.
    """
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Try to resolve user by ID or email
    customer_id = payload.get("uid") or payload.get("user_id") or payload.get("id")
    email = payload.get("sub")

    customer = None
    if customer_id:
        customer = db.query(Customer).filter(Customer.id == int(customer_id)).first()
    if not customer and email:
        customer = db.query(Customer).filter(Customer.email == email).first()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Apply incoming updates dynamically
    for k, v in data.items():
        if hasattr(customer, k):
            setattr(customer, k, v)

    db.commit()
    db.refresh(customer)
    return customer

@router.delete("/{customer_id}", dependencies=[Depends(role_required("admins"))])
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    c = db.query(Customer).get(customer_id)
    if not c:
        raise HTTPException(404)
    db.delete(c)
    db.commit()
    return {"deleted": True}

