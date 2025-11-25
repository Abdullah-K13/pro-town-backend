from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.init import get_db
from models.lead import Lead
from utils.deps import role_required
from models.professional import Professional
from models.professional_pair import ProfessionalPair
from utils.deps import get_current_user
from sqlalchemy import or_
from models.customer import Customer
from models.state import State
from models.city import City
from models.service import Service
from typing import List, Dict, Any
import logging
from sqlalchemy import func, text
from models.service_city_pair import ServiceCityPair
from models.state_city import StateCityPair
from utils.email import send_email


logger = logging.getLogger("uvicorn")

router = APIRouter()



@router.get("/")
def get_all(db: Session = Depends(get_db), payload = Depends(get_current_user)):
    role = payload.get("role")
    email = payload.get("sub")

    # ---- 1) Figure out which leads this user can see ----
    if role == "admins":
        leads: List[Lead] = db.query(Lead).all()

    elif role == "professionals" :
        me = db.query(Professional).filter(Professional.email == email).first()
        if not me:
            raise HTTPException(status_code=403, detail="Not enough privileges")

        leads = (
            db.query(Lead)
            .join(ProfessionalPair, Lead.pair_id == ProfessionalPair.id)
            .filter(
                or_(
                    ProfessionalPair.professional_id_1 == me.id,
                    ProfessionalPair.professional_id_2 == me.id,
                )
            )
            .all()
        )

    elif role == "customers":
        me = db.query(Customer).filter(Customer.email == email).first()
        if not me:
            raise HTTPException(status_code=403, detail="Not enough privileges")

        leads = (
            db.query(Lead)
            .filter(Lead.customer_id == me.id)
            .all()
        )
    else:
        # Customers or others: forbidden
        raise HTTPException(status_code=403, detail="Not enough privileges")

    if not leads:
        return []

    # ---- 2) Batch preload all lookups to avoid N+1 ----
    customer_ids = {ld.customer_id for ld in leads if ld.customer_id is not None}
    state_ids    = {ld.state_id    for ld in leads if ld.state_id    is not None}
    city_ids     = {ld.city_id     for ld in leads if ld.city_id     is not None}
    service_ids  = {ld.service_id  for ld in leads if ld.service_id  is not None}
    pair_ids     = {ld.pair_id     for ld in leads if ld.pair_id     is not None}

    # Customers
    customers = {}
    if customer_ids:
        for cid, first, last in (
            db.query(Customer.id, Customer.first_name, Customer.last_name)
            .filter(Customer.id.in_(customer_ids))
            .all()
        ):
            customers[cid] = f"{first or ''} {last or ''}".strip()

    # States
    states = {}
    if state_ids:
        for sid, name in db.query(State.id, State.state_name).filter(State.id.in_(state_ids)).all():
            states[sid] = name

    # Cities
    cities = {}
    if city_ids:
        for cid, name in db.query(City.id, City.city_name).filter(City.id.in_(city_ids)).all():
            cities[cid] = name

    # Services
    services = {}
    if service_ids:
        for svcid, name in db.query(Service.id, Service.service_name).filter(Service.id.in_(service_ids)).all():
            services[svcid] = name

    # Professional pairs
    pairs_by_id: Dict[int, ProfessionalPair] = {}
    pro_ids: set[int] = set()
    if pair_ids:
        for pp in db.query(ProfessionalPair).filter(ProfessionalPair.id.in_(pair_ids)).all():
            pairs_by_id[pp.id] = pp
            if pp.professional_id_1:
                pro_ids.add(pp.professional_id_1)
            if pp.professional_id_2:
                pro_ids.add(pp.professional_id_2)

    # Professionals
    pros_by_id: Dict[int, Dict[str, Any]] = {}
    if pro_ids:
        # Fetch only the fields you need (id, name). Add email if desired.
        for pid, pname in db.query(Professional.id, Professional.name).filter(Professional.id.in_(pro_ids)).all():
            pros_by_id[pid] = {"id": pid, "name": pname}

    # ---- 3) Assemble enriched response ----
    result: List[Dict[str, Any]] = []
    for ld in leads:
        # professionals for this lead's pair_id
        prof_list: List[Dict[str, Any]] = []
        if ld.pair_id and ld.pair_id in pairs_by_id:
            pp = pairs_by_id[ld.pair_id]
            for pid in [pp.professional_id_1, pp.professional_id_2]:
                if pid and pid in pros_by_id:
                    prof_list.append(pros_by_id[pid])

        item = {
            "id": ld.id,
            "description": ld.description,
            "status": ld.status,
            "created_at": ld.created_at,
            "customer": {
                "id": ld.customer_id,
                "name": customers.get(ld.customer_id),
            } if ld.customer_id is not None else None,
            "service": {
                "id": ld.service_id,
                "name": services.get(ld.service_id),
            } if ld.service_id is not None else None,
            "state": {
                "id": ld.state_id,
                "name": states.get(ld.state_id),
            } if ld.state_id is not None else None,
            "city": {
                "id": ld.city_id,
                "name": cities.get(ld.city_id),
            } if ld.city_id is not None else None,
            "pair": {
                "id": ld.pair_id,
                "professionals": prof_list,
                "quantity": len(prof_list),
            } if ld.pair_id is not None else None,
        }
        result.append(item)

    return result

@router.get("/{id}")
def get_by_id_3(id: int, db: Session = Depends(get_db), payload = Depends(get_current_user)):
    role = payload.get("role")
    email = payload.get("sub")
    print("Payload:")

    # ---- 1) Figure out which leads this user can see ----
    if role == "admins":
        leads: List[Lead] = db.query(Lead).all()

    elif role == "professionals":
        me = db.query(Professional).filter(Professional.email == email).first()
        if not me:
            raise HTTPException(status_code=403, detail="Not enough privileges")

        leads = (
            db.query(Lead)
            .join(ProfessionalPair, Lead.pair_id == ProfessionalPair.id)
            .filter(
                Lead.id == id,
                or_(
                    ProfessionalPair.professional_id_1 == me.id,
                    ProfessionalPair.professional_id_2 == me.id,
                )
            )
            .all()
        )
    elif role == "customers":
        
        me = db.query(Customer).filter(Customer.email == email).first()
        if not me:
            raise HTTPException(status_code=403, detail="Not enough privileges")
        leads = (db.query(Lead)
        .filter(Lead.id == id,Lead.customer_id == me.id)
        .all()
    )
    else:
        # Customers or others: forbidden
        raise HTTPException(status_code=403, detail="Not enough privileges")

    if not leads:
        return []

    # ---- 2) Batch preload all lookups to avoid N+1 ----
    customer_ids = {ld.customer_id for ld in leads if ld.customer_id is not None}
    state_ids    = {ld.state_id    for ld in leads if ld.state_id    is not None}
    service_ids  = {ld.service_id  for ld in leads if ld.service_id  is not None}
    pair_ids     = {ld.pair_id     for ld in leads if ld.pair_id     is not None}

    # Customers
    customers = {}
    if customer_ids:
        for cid, first, last, email, address, phone_number in (
            db.query(Customer.id, Customer.first_name, Customer.last_name, Customer.email, Customer.address, Customer.phone_number)
            .filter(Customer.id.in_(customer_ids))
            .all()
        ):
            customers[cid] = {
                        "name": f"{first or ''} {last or ''}".strip(),
                        "email": email,
                        "address": address,
                        "phone_number": phone_number,
                    }
    # States
    states = {}
    if state_ids:
        for sid, name in db.query(State.id, State.state_name).filter(State.id.in_(state_ids)).all():
            states[sid] = name

    # Services
    services = {}
    if service_ids:
        for svcid, name in db.query(Service.id, Service.service_name).filter(Service.id.in_(service_ids)).all():
            services[svcid] = name

    # Professional pairs
    pairs_by_id: Dict[int, ProfessionalPair] = {}
    pro_ids: set[int] = set()
    if pair_ids:
        for pp in db.query(ProfessionalPair).filter(ProfessionalPair.id.in_(pair_ids)).all():
            pairs_by_id[pp.id] = pp
            if pp.professional_id_1:
                pro_ids.add(pp.professional_id_1)
            if pp.professional_id_2:
                pro_ids.add(pp.professional_id_2)

    # Professionals
    pros_by_id: Dict[int, Dict[str, Any]] = {}
    if pro_ids:
        # Fetch only the fields you need (id, name). Add email if desired.
        for pid, pname, email, phone_number, business_name in db.query(Professional.id, Professional.name, Professional.email, Professional.phone_number,
                                   Professional.business_name).filter(Professional.id.in_(pro_ids)).all():
            pros_by_id[pid] = {"id": pid, "name": pname, "email": email, "phone_number": phone_number, "business_name": business_name}

    # ---- 3) Assemble enriched response ----
    result: List[Dict[str, Any]] = []
    for ld in leads:
        # professionals for this lead's pair_id
        prof_list: List[Dict[str, Any]] = []
        if ld.pair_id and ld.pair_id in pairs_by_id:
            pp = pairs_by_id[ld.pair_id]
            for pid in [pp.professional_id_1, pp.professional_id_2]:
                if pid and pid in pros_by_id:
                    prof_list.append(pros_by_id[pid])

        item = {
            "id": ld.id,
            "description": ld.description,
            "status": ld.status,
            "created_at": ld.created_at,
            "customer": {
                "id": ld.customer_id,
                "name": customers.get(ld.customer_id).get("name"),
                "email": customers.get(ld.customer_id).get("email"),
                "address": customers.get(ld.customer_id).get("address"),
                "phone_number": customers.get(ld.customer_id).get("phone_number"),
            } if ld.customer_id is not None else None,
            "service": {
                "id": ld.service_id,
                "name": services.get(ld.service_id),
            } if ld.service_id is not None else None,
            "state": {
                "id": ld.state_id,
                "name": states.get(ld.state_id),
            } if ld.state_id is not None else None,
            "pair": {
                "id": ld.pair_id,
                "professionals": prof_list,
                "quantity": len(prof_list),
            } if ld.pair_id is not None else None,
        }
        result.append(item)

    return result

@router.post("/", status_code=201)
def create_lead(
    data: Dict[str, Any],
    db: Session = Depends(get_db),
    payload = Depends(get_current_user),
):
    role = payload.get("role")
    sub  = payload.get("sub")  # your JWT subject (email in your setup)

    # Only customers (and optionally admins) can create
    # if role not in ("customers", "admins"):
    #     raise HTTPException(status_code=403, detail="Not enough privileges")

    # Force customer_id from token for customers (no spoofing)
    # if role == "customers":
    me = db.query(Customer).filter(Customer.email == sub).first()
    if not me:
        raise HTTPException(status_code=403, detail="Customer not found for this token")
    data = {**data, "customer_id": me.id}

    # Require service/city so we can pick among admin-defined pairs
    svc_id = data.get("service_id")
    city_id = data.get("city_id")
    state_id = data.get("state_id")
    
    if not svc_id or not city_id:
        raise HTTPException(status_code=400, detail="service_id and city_id are required")

    # Validate service/city exist
    if not db.query(Service.id).filter(Service.id == svc_id).first():
        raise HTTPException(status_code=400, detail="Invalid service_id")
    
    city = db.query(City).filter(City.id == city_id).first()
    if not city:
        raise HTTPException(status_code=400, detail="Invalid city_id")
    
    # If state_id not provided, try to get it from the city's state association
    if not state_id:
        # Get state from StateCityPair for this city
        state_city_pair = (
            db.query(StateCityPair)
            .filter(StateCityPair.city_id == city_id)
            .first()
        )
        if state_city_pair:
            state_id = state_city_pair.state_id
        else:
            raise HTTPException(
                status_code=400,
                detail="state_id is required. City is not associated with any state. Please provide state_id in the request."
            )
    
    # Validate state exists
    if not db.query(State).filter(State.id == state_id).first():
        raise HTTPException(status_code=400, detail="Invalid state_id")
    
    # Set state_id in data (required by Lead model)
    data["state_id"] = state_id

    # Pick pair_id (ignore any incoming pair_id from client)
    data.pop("pair_id", None)
    assigned_pair_id = choose_pair_for_service_city(db, service_id=svc_id, city_id=city_id)
    data["pair_id"] = assigned_pair_id

    # Create lead
    lead = Lead(**data)
    db.add(lead)
    db.commit()
    db.refresh(lead)

    # Enriched response (same shape as your GETs)
    # --- customer ---
    cust = None
    if lead.customer_id:
        row = (
            db.query(
                Customer.first_name, Customer.last_name,
                Customer.email, Customer.address, Customer.phone_number
            )
            .filter(Customer.id == lead.customer_id)
            .first()
        )
        if row:
            first, last, cmail, caddr, cphone = row
            cust = {
                "id": lead.customer_id,
                "name": (f"{first or ''} {last or ''}").strip() or None,
                "email": cmail,
                "address": caddr,
                "phone_number": cphone,
            }

    # --- state & service ---
    state_name = db.query(State.state_name).filter(State.id == lead.state_id).scalar() if lead.state_id else None
    service_name = db.query(Service.service_name).filter(Service.id == lead.service_id).scalar() if lead.service_id else None

    # --- pair & professionals ---
    prof_list: List[Dict[str, Any]] = []
    if lead.pair_id:
        pp = db.query(ProfessionalPair).filter(ProfessionalPair.id == lead.pair_id).first()
        if pp:
            ids = [pid for pid in (pp.professional_id_1, pp.professional_id_2) if pid]
            if ids:
                for pid, pname in (
                    db.query(Professional.id, Professional.name)
                    .filter(Professional.id.in_(ids))
                    .all()
                ):
                    prof_list.append({"id": pid, "name": pname})



    # ---- 4) Send Email Notifications ----
    # Subject and Body as requested
    email_subject = "leads testing"
    email_body = "hi this is abdullah to test leads"

    # Send to Customer
    if cust and cust.get("email"):
        send_email(
            to_email=cust["email"],
            subject=email_subject,
            body=email_body,
            is_html=False
        )

    # Send to Professionals
    for prof in prof_list:
        # We need to ensure we have the email for the professional.
        # The current prof_list construction in create_lead only includes id and name.
        # We need to fetch email if it's not there, or better, fetch it when building prof_list.
        
        # Let's fetch the professional email directly here to be safe and simple
        prof_obj = db.query(Professional).filter(Professional.id == prof["id"]).first()
        if prof_obj and prof_obj.email:
             send_email(
                to_email=prof_obj.email,
                subject=email_subject,
                body=email_body,
                is_html=False
            )

    return {
        "id": lead.id,
        "description": lead.description,
        "status": lead.status,
        "created_at": lead.created_at,
        "customer": cust,
        "service": {"id": lead.service_id, "name": service_name} if lead.service_id else None,
        "state":   {"id": lead.state_id,   "name": state_name}   if lead.state_id   else None,
        "pair": (
            {"id": lead.pair_id, "professionals": prof_list, "quantity": len(prof_list)}
            if lead.pair_id else None
        ),
    }


@router.put("/{id}", dependencies=[Depends(role_required("admins"))])
def update(id: int, data: dict, db: Session = Depends(get_db)):
    lead = db.query(Lead).get(id)
    if not lead:
        raise HTTPException(404)
    for k, v in data.items():
        setattr(lead, k, v)
    db.commit()
    db.refresh(lead)
    return lead

@router.delete("/{id}", dependencies=[Depends(role_required("admins"))])
def delete(id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).get(id)
    if not lead:
        raise HTTPException(404)
    db.delete(lead)
    db.commit()
    return {"deleted": True}



# helpers/pairs.py

def choose_pair_for_service_city(
    db: Session,
    *,
    service_id: int,
    city_id: int,
    use_advisory_lock: bool = True,  # safe round-robin under concurrency (Postgres)
) -> int:
    # Resolve the service_city_pair row (admin created)
    scp = (
        db.query(ServiceCityPair)
        .filter(
            ServiceCityPair.service_id == service_id,
            ServiceCityPair.city_id  == city_id,
        )
        .first()
    )
    if not scp:
        raise HTTPException(status_code=400, detail="No service_city_pair for given service/city")

    # Fetch the 2 predefined pairs for this SCP
    pairs = (
        db.query(ProfessionalPair)
        .filter(ProfessionalPair.service_city_pair_id == scp.id)
        .order_by(ProfessionalPair.id.asc())
        .all()
    )
    if len(pairs) < 2:
        raise HTTPException(status_code=400, detail="Admin must configure two pairs for this service/city")

    pair_a, pair_b = pairs[0], pairs[1]

    # Optional: protect the round-robin from race conditions (Postgres only )
    if use_advisory_lock:
        try:
            db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": int(scp.id)})
        except Exception:
            pass  # non-Postgres env: proceed without the lock

    # Strict round-robin A,B,A,B based on total assigned so far
    total_assigned = (
        db.query(func.count(Lead.id))
        .filter(Lead.pair_id.in_([pair_a.id, pair_b.id]))
        .scalar()
    )
    return pair_a.id if (total_assigned % 2 == 0) else pair_b.id
