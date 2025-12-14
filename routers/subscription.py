from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from db.init import get_db
from models.professional import Professional
from models.subscription import Subscription
from utils.deps import role_required

router = APIRouter()


@router.get("/")
def get_all_subscriptions_with_counts(db: Session = Depends(get_db)):
    """
    Get all subscriptions and how many professionals are subscribed
    to each one (1, 2, 3, etc.)
    """

    # 1️⃣ Fetch all subscriptions
    subscriptions = db.query(Subscription).all()

    # 2️⃣ Aggregate counts of professionals per subscription
    sub_counts = (
        db.query(
            Professional.subscription_plan_id,
            func.count(Professional.id).label("total_professionals")
        )
        .filter(Professional.subscription_plan_id.isnot(None))
        .group_by(Professional.subscription_plan_id)
        .all()
    )

    # 3️⃣ Convert counts to a dictionary {sub_id: total}
    count_map = {row.subscription_plan_id: row.total_professionals for row in sub_counts}

    # 4️⃣ Enrich subscriptions with their professional counts
    result = []
    for sub in subscriptions:
        item = {c.name: getattr(sub, c.name) for c in sub.__table__.columns}
        item["total_professionals"] = count_map.get(sub.id, 0)
        result.append(item)

    return result

@router.get("/{id}")
def get_by_id(id: int, db: Session = Depends(get_db)):
    s = db.query(Subscription).get(id)
    if not s:
        raise HTTPException(404)
    return s

@router.post("/", dependencies=[Depends(role_required("admins"))])
def create(data: dict, db: Session = Depends(get_db)):
    s = Subscription(**data)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s

@router.put("/{id}", dependencies=[Depends(role_required("admins"))])
def update(id: int, data: dict, db: Session = Depends(get_db)):
    s = db.query(Subscription).get(id)
    if not s:
        raise HTTPException(404)
    for k, v in data.items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s

@router.delete("/{id}", dependencies=[Depends(role_required("admins"))])
def delete(id: int, db: Session = Depends(get_db)):
    s = db.query(Subscription).get(id)
    if not s:
        raise HTTPException(404)
    db.delete(s)
    db.commit()
    return {"deleted": True}
