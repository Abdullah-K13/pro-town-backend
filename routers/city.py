from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from db.init import get_db
from models.city import City
from models.state import State
from models.state_city import StateCityPair
from utils.deps import role_required

router = APIRouter()

@router.get("/")
def get_all(db: Session = Depends(get_db)):
    """
    Get all cities with their associated state information.
    Returns cities with state id and state name.
    """
    rows = (
        db.query(
            City.id.label("city_id"),
            City.city_name,
            State.id.label("state_id"),
            State.state_name,
        )
        .outerjoin(StateCityPair, StateCityPair.city_id == City.id)
        .outerjoin(State, State.id == StateCityPair.state_id)
        .order_by(City.city_name.asc())
        .all()
    )
    
    # Build response with state information
    result = []
    for city_id, city_name, state_id, state_name in rows:
        city_data = {
            "id": city_id,
            "city_name": city_name,
            "state": {
                "id": state_id,
                "state_name": state_name
            } if state_id is not None else None
        }
        result.append(city_data)
    
    return result

@router.get("/state/{state_id}")
def get_cities_by_state(state_id: int, db: Session = Depends(get_db)):
    """
    Get all cities for a specific state.
    Returns empty list if state has no cities or state doesn't exist.
    """
    # Validate state exists
    state = db.query(State).get(state_id)
    if not state:
        raise HTTPException(status_code=404, detail="State not found")
    
    # Get cities for this state through StateCityPair
    cities = (
        db.query(City)
        .join(StateCityPair, StateCityPair.city_id == City.id)
        .filter(StateCityPair.state_id == state_id)
        .distinct()
        .order_by(City.city_name.asc())
        .all()
    )
    
    # Return empty list if no cities (don't 404 - empty is valid)
    return cities

@router.get("/{id}")
def get_by_id(id: int, db: Session = Depends(get_db)):
    city = db.query(City).get(id)
    if not city:
        raise HTTPException(status_code=404, detail="City not found")
    return city

@router.post("/", dependencies=[Depends(role_required("admins"))])
def create(data: dict, db: Session = Depends(get_db)):
    """
    Create a new city and associate it with a state.
    Data is inserted into two tables:
    1. city table - the city record
    2. state_city_pairs table - the state-city association
    
    Payload:
    {
        "city_name": "New York",
        "state_id": 1
    }
    """
    # Extract and validate required fields
    city_name = data.get("city_name")
    state_id = data.get("state_id")
    
    if not city_name:
        raise HTTPException(status_code=400, detail="city_name is required")
    if not state_id:
        raise HTTPException(status_code=400, detail="state_id is required")
    
    # Validate state exists
    state = db.query(State).get(state_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"State with id {state_id} not found")
    
    # Create the city in city table (flush to get its ID)
    city = City(city_name=city_name)
    db.add(city)
    db.flush()  # assigns city.id without committing
    
    # Create the state-city pair in state_city_pairs table
    state_city_pair = StateCityPair(state_id=state_id, city_id=city.id)
    db.add(state_city_pair)
    
    # Commit both tables (handle uniqueness/constraint issues)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        # Could be duplicate city_name or duplicate (state_id, city_id)
        if "city_name" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail="Conflict: city name already exists or duplicate (state_id, city_id) mapping."
            ) from e
        raise HTTPException(
            status_code=500,
            detail="Database error occurred"
        ) from e
    
    db.refresh(city)
    
    # Return city with state information
    return {
        "id": city.id,
        "city_name": city.city_name,
        "state": {
            "id": state.id,
            "state_name": state.state_name
        }
    }

@router.put("/{id}", dependencies=[Depends(role_required("admins"))])
def update(id: int, data: dict, db: Session = Depends(get_db)):
    city = db.query(City).get(id)
    if not city:
        raise HTTPException(status_code=404, detail="City not found")
    for k, v in data.items():
        setattr(city, k, v)
    db.commit()
    db.refresh(city)
    return city

@router.delete("/{id}", dependencies=[Depends(role_required("admins"))])
def delete(id: int, db: Session = Depends(get_db)):
    city = db.query(City).get(id)
    if not city:
        raise HTTPException(status_code=404, detail="City not found")
    db.delete(city)
    db.commit()
    return {"deleted": True}

