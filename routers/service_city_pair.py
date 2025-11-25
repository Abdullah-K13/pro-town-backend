from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.init import get_db
from models.service import Service
from models.service_city_pair import ServiceCityPair
from models.city import City
from models.state import State
from models.state_city import StateCityPair
from utils.deps import role_required
from sqlalchemy import asc

router = APIRouter()


@router.get("/", dependencies=[Depends(role_required("admins"))])
def get_all(db: Session = Depends(get_db)):
    rows = (
        db.query(
            ServiceCityPair.id.label("pair_id"),
            ServiceCityPair.service_id.label("service_id"),
            Service.service_name.label("service_name"),
            ServiceCityPair.city_id.label("city_id"),
            City.city_name.label("city_name"),
            State.id.label("state_id"),
            State.state_name.label("state_name"),
        )
        .join(Service, Service.id == ServiceCityPair.service_id)
        .join(City, City.id == ServiceCityPair.city_id)
        .outerjoin(StateCityPair, StateCityPair.city_id == City.id)
        .outerjoin(State, State.id == StateCityPair.state_id)
        .order_by(asc(Service.service_name), asc(City.city_name))
        .all()
    )

    # Return as plain dicts (FastAPI will JSONify)
    return [
        {
            "pair_id": r.pair_id,
            "service_id": r.service_id,
            "service_name": r.service_name,
            "city_id": r.city_id,
            "city_name": r.city_name,
            "state_id": r.state_id,
            "state_name": r.state_name,
        }
        for r in rows
    ]

@router.get("/{id}", dependencies=[Depends(role_required("admins"))])
def get_by_id(id: int, db: Session = Depends(get_db)):
    pair = db.query(ServiceCityPair).get(id)
    if not pair:
        raise HTTPException(404)
    return pair

@router.post("/", dependencies=[Depends(role_required("admins"))])
def create(data: dict, db: Session = Depends(get_db)):
    pair = ServiceCityPair(**data)
    db.add(pair)
    db.commit()
    db.refresh(pair)
    return pair

@router.put("/{id}", dependencies=[Depends(role_required("admins"))])
def update(id: int, data: dict, db: Session = Depends(get_db)):
    pair = db.query(ServiceCityPair).get(id)
    if not pair:
        raise HTTPException(404)
    for k, v in data.items():
        setattr(pair, k, v)
    db.commit()
    db.refresh(pair)
    return pair

@router.delete("/{id}", dependencies=[Depends(role_required("admins"))])
def delete(id: int, db: Session = Depends(get_db)):
    pair = db.query(ServiceCityPair).get(id)
    if not pair:
        raise HTTPException(404)
    db.delete(pair)
    db.commit()
    return {"deleted": True}
