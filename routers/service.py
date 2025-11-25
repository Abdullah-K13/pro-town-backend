from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.init import get_db
from models.service import Service
from models.service_city_pair import ServiceCityPair
from models.city import City
from utils.deps import role_required
from sqlalchemy import asc
from models.service import ServiceCreate
from sqlalchemy.exc import IntegrityError

router = APIRouter()

@router.get("/")
def get_all(db: Session = Depends(get_db)):
    """
    Return services with their associated cities.
    Shape:
    [
      { "id": 1, "service_name": "Plumbing", "cities": [{ "id": 4, "name": "New York" }, ...] },
      ...
    ]
    """
    rows = (
        db.query(
            Service.id.label("service_id"),
            Service.service_name.label("service_name"),
            City.id.label("city_id"),
            City.city_name.label("city_name"),
        )
        .outerjoin(ServiceCityPair, ServiceCityPair.service_id == Service.id)
        .outerjoin(City, City.id == ServiceCityPair.city_id)
        .order_by(asc(Service.service_name), asc(City.city_name))
        .all()
    )

    by_service: dict[int, dict] = {}
    for r in rows:
        svc = by_service.setdefault(
            r.service_id,
            {"id": r.service_id, "service_name": r.service_name, "cities": []},
        )
        # With your UniqueConstraint("service_id","city_id") there shouldn't be dupes,
        # but we guard anyway in case of legacy data.
        if r.city_id is not None:
            if not any(c["id"] == r.city_id for c in svc["cities"]):
                svc["cities"].append({"id": r.city_id, "name": r.city_name})

    return list(by_service.values())

@router.get("/{id}")
def get_by_id(id: int, db: Session = Depends(get_db)):
    s = db.query(Service).get(id)
    if not s:
        raise HTTPException(404)
    return s

@router.get("/{city_id}/services")
def services_for_city(city_id: int, db: Session = Depends(get_db)):
    # validate city
    city = db.query(City).get(city_id)
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    services = (
        db.query(Service)
          .join(ServiceCityPair, ServiceCityPair.service_id == Service.id)
          .filter(ServiceCityPair.city_id == city_id)
          .distinct()
          .order_by(Service.service_name.asc())
          .all()
    )
    # return [] if none; don't 404 here—empty means "no services in this city"
    return services


@router.post(
    "/", 
    dependencies=[Depends(role_required("admins"))],
    status_code=status.HTTP_201_CREATED
)
def create(payload: ServiceCreate, db: Session = Depends(get_db)):
    """
    Create a new service and associate it with cities.
    Data is inserted into two tables:
    1. services table - the service record
    2. service_city_pairs table - the service-city associations
    """
    # 1) Validate city IDs (if provided)
    city_ids = payload.city_ids if payload.city_ids else []
    if city_ids:
        rows = db.query(City.id).filter(City.id.in_(city_ids)).all()
        existing_ids = {cid for (cid,) in rows}
        missing = set(city_ids) - existing_ids
        if missing:
            raise HTTPException(
                status_code=400,
                detail={"error": "Invalid city_ids", "missing": sorted(missing)}
            )

    # 2) Create the service in services table (flush to get its ID)
    s = Service(service_name=payload.service_name)
    db.add(s)
    db.flush()  # assigns s.id without committing

    # 3) Insert mappings into service_city_pairs table
    if city_ids:
        pairs = [
            ServiceCityPair(service_id=s.id, city_id=cid)
            for cid in city_ids
        ]
        db.add_all(pairs)

    # 4) Commit both tables (handle uniqueness/constraint issues)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        # Could be duplicate service_name or duplicate (service_id, city_id)
        raise HTTPException(
            status_code=409,
            detail="Conflict: service name already exists or duplicate (service_id, city_id) mapping."
        ) from e

    # 5) Build response (service with its cities)
    cities = []
    if city_ids:
        city_rows = (
            db.query(City.id, City.city_name)
              .join(ServiceCityPair, ServiceCityPair.city_id == City.id)
              .filter(ServiceCityPair.service_id == s.id)
              .order_by(City.city_name.asc())
              .all()
        )
        cities = [{"id": cid, "name": name} for (cid, name) in city_rows]

    return {"id": s.id, "service_name": s.service_name, "cities": cities}

@router.put("/{id}", dependencies=[Depends(role_required("admins"))])
def update(id: int, data: dict, db: Session = Depends(get_db)):
    s = db.query(Service).get(id)
    if not s:
        raise HTTPException(404)
    for k, v in data.items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s

@router.delete("/{id}", dependencies=[Depends(role_required("admins"))])
def delete(id: int, db: Session = Depends(get_db)):
    s = db.query(Service).get(id)
    if not s:
        raise HTTPException(404)
    db.delete(s)
    db.commit()
    return {"deleted": True}
