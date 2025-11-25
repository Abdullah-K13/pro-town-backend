from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, aliased
from db.init import get_db
from models.professional import Professional
from models.professional_pair import ProfessionalPair
from models.service_city_pair import ServiceCityPair
from models.state_city import StateCityPair
from models.state import State
from utils.deps import role_required
from sqlalchemy import asc

router = APIRouter()

@router.get("/", dependencies=[Depends(role_required("admins"))])
def get_all(db: Session = Depends(get_db)):
    return db.query(ProfessionalPair).all()

@router.get("/{id}", dependencies=[Depends(role_required("admins"))])
def get_by_id(id: int, db: Session = Depends(get_db)):
    pair = db.query(ProfessionalPair).get(id)
    if not pair:
        raise HTTPException(404)
    return pair

@router.post("/", dependencies=[Depends(role_required("admins"))])
def create(data: dict, db: Session = Depends(get_db)):
    """
    Create a new professional pair.
    Required fields:
    - service_city_pair_id: ID of the service-city pair
    - professional_id_1: ID of first professional
    - professional_id_2: ID of second professional
    
    Note: If 'service_state_pair_id' is provided, it will be converted to 'service_city_pair_id'
    """
    # Handle legacy field name conversion
    if "service_state_pair_id" in data and "service_city_pair_id" not in data:
        data["service_city_pair_id"] = data.pop("service_state_pair_id")
    
    # Validate required fields
    if "service_city_pair_id" not in data:
        raise HTTPException(
            status_code=400,
            detail="service_city_pair_id is required"
        )
    
    # Validate service_city_pair exists
    scp = db.query(ServiceCityPair).get(data["service_city_pair_id"])
    if not scp:
        raise HTTPException(
            status_code=404,
            detail=f"ServiceCityPair with id {data['service_city_pair_id']} not found"
        )
    
    pair = ProfessionalPair(**data)
    db.add(pair)
    db.commit()
    db.refresh(pair)
    return pair

@router.put("/{id}", dependencies=[Depends(role_required("admins"))])
def update(id: int, data: dict, db: Session = Depends(get_db)):
    pair = db.query(ProfessionalPair).get(id)
    if not pair:
        raise HTTPException(404)
    
    # Handle legacy field name conversion
    if "service_state_pair_id" in data and "service_city_pair_id" not in data:
        data["service_city_pair_id"] = data.pop("service_state_pair_id")
    
    # Validate service_city_pair exists if being updated
    if "service_city_pair_id" in data:
        scp = db.query(ServiceCityPair).get(data["service_city_pair_id"])
        if not scp:
            raise HTTPException(
                status_code=404,
                detail=f"ServiceCityPair with id {data['service_city_pair_id']} not found"
            )
    
    for k, v in data.items():
        setattr(pair, k, v)
    db.commit()
    db.refresh(pair)
    return pair

@router.delete("/{id}", dependencies=[Depends(role_required("admins"))])
def delete(id: int, db: Session = Depends(get_db)):
    pair = db.query(ProfessionalPair).get(id)
    if not pair:
        raise HTTPException(404)
    db.delete(pair)
    db.commit()
    return {"deleted": True}


@router.get("/{id}/pairs", dependencies=[Depends(role_required("admins"))])
def get_pairs_for_service_city_pair(id: int, db: Session = Depends(get_db)):
    # 1) Validate SCP exists
    scp = db.query(ServiceCityPair).get(id)
    if not scp:
        raise HTTPException(status_code=404, detail="ServiceCityPair not found")

    # 2) Join each pair to the two professional records (outer joins allow nulls)
    #    Also join to get State info for the SCP's city
    P1 = aliased(Professional)
    P2 = aliased(Professional)

    # We need to fetch state_id associated with this SCP's city
    # SCP -> City -> StateCityPair -> State
    # But here we just need to return the state_id for the frontend to use.
    # We can do a separate query or join. Since we are returning a dict, let's just fetch the state_id.
    
    state_id = (
        db.query(State.id)
        .join(StateCityPair, StateCityPair.state_id == State.id)
        .filter(StateCityPair.city_id == scp.city_id)
        .scalar()
    )

    rows = (
        db.query(
            ProfessionalPair.id.label("pair_id"),
            ProfessionalPair.professional_id_1,
            ProfessionalPair.professional_id_2,
            P1.id.label("p1_id"),
            P1.name.label("p1_name"),
            P2.id.label("p2_id"),
            P2.name.label("p2_name"),
        )
        .outerjoin(P1, P1.id == ProfessionalPair.professional_id_1)
        .outerjoin(P2, P2.id == ProfessionalPair.professional_id_2)
        .filter(ProfessionalPair.service_city_pair_id == id)
        .order_by(asc(ProfessionalPair.id))
        .all()
    )

    # 3) Build payload
    def prof_dict(pid, pname):
        if pid is None:
            return None
        return {"id": pid, "name": pname}

    pairs_payload = []
    for r in rows:
        pros = [prof_dict(r.p1_id, r.p1_name), prof_dict(r.p2_id, r.p2_name)]
        # remove Nones (in case a slot is unfilled)
        pros = [p for p in pros if p is not None]
        pairs_payload.append({
            "id": r.pair_id,
            "professionals": pros
        })

    return {
        "service_city_pair_id": scp.id,
        "service_id": getattr(scp, "service_id", None),
        "city_id": getattr(scp, "city_id", None),
        "state_id": state_id,
        "pairs": pairs_payload,   # zero, one, or two items depending on what exists
    }