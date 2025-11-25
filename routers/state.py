from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.init import get_db
from models.state import State
from utils.deps import role_required

router = APIRouter()

@router.get("/")
def get_all(db: Session = Depends(get_db)):
    return db.query(State).all()

@router.get("/{id}")
def get_by_id(id: int, db: Session = Depends(get_db)):
    s = db.query(State).get(id)
    if not s:
        raise HTTPException(404)
    return s

@router.post("/", dependencies=[Depends(role_required("admins"))])
def create(data: dict, db: Session = Depends(get_db)):
    s = State(**data)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s

@router.put("/{id}", dependencies=[Depends(role_required("admins"))])
def update(id: int, data: dict, db: Session = Depends(get_db)):
    s = db.query(State).get(id)
    if not s:
        raise HTTPException(404)
    for k, v in data.items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s

@router.delete("/{id}", dependencies=[Depends(role_required("admins"))])
def delete(id: int, db: Session = Depends(get_db)):
    s = db.query(State).get(id)
    if not s:
        raise HTTPException(404)
    db.delete(s)
    db.commit()
    return {"deleted": True}
