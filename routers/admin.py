from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.init import get_db
from models.admin import Admin
from utils.deps import role_required
from utils.security import hash_password

router = APIRouter()

@router.get("/", dependencies=[Depends(role_required("admins"))])
def get_all_admins(db: Session = Depends(get_db)):
    return db.query(Admin).all()

@router.get("/{admin_id}", dependencies=[Depends(role_required("admins"))])
def get_admin(admin_id: int, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(404, "Admin not found")
    return admin

@router.post("/", dependencies=[Depends(role_required("admins"))])
def create_admin(data: dict, db: Session = Depends(get_db)):
    data["password_hash"] = hash_password(data.pop("password", "admin123"))
    admin = Admin(**data)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin

@router.put("/{admin_id}", dependencies=[Depends(role_required("admins"))])
def update_admin(admin_id: int, data: dict, db: Session = Depends(get_db)):
    admin = db.query(Admin).get(admin_id)
    if not admin:
        raise HTTPException(404)
    for k, v in data.items():
        setattr(admin, k, v)
    db.commit()
    db.refresh(admin)
    return admin

@router.delete("/{admin_id}", dependencies=[Depends(role_required("admins"))])
def delete_admin(admin_id: int, db: Session = Depends(get_db)):
    admin = db.query(Admin).get(admin_id)
    if not admin:
        raise HTTPException(404)
    db.delete(admin)
    db.commit()
    return {"deleted": True}
