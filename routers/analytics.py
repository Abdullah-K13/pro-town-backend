# routes/analytics.py
from datetime import date, datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, case, and_, cast, Date
from sqlalchemy.orm import Session

from db.init import get_db
from utils.deps import role_required

from models.admin import Admin
from models.customer import Customer
from models.lead import Lead
from models.professional import Professional
from models.subscription import Subscription
from models.state import State
from models.professional_pair import ProfessionalPair
from models.service_city_pair import ServiceCityPair
# you likely have a Services model; importing as Services here:
from models.service import Service  # adjust import path to your project

router = APIRouter()

# ---------------------------
# 1) High-level KPIs (cards)
# ---------------------------
@router.get("/overview")
def analytics_overview(db: Session = Depends(get_db)):
    total_customers = db.query(func.count(Customer.id)).scalar() or 0
    total_pros = db.query(func.count(Professional.id)).scalar() or 0
    verified_pros = db.query(func.count(Professional.id)).filter(Professional.verified_status == True).scalar() or 0
    active_subscribed_pros = (
        db.query(func.count(Professional.id))
        .filter(Professional.subscription_active == True)
        .scalar() or 0
    )
    total_leads = db.query(func.count(Lead.id)).scalar() or 0
    urgent_leads = db.query(func.count(Lead.id)).filter(Lead.status == "urgent").scalar() or 0
    states_count = db.query(func.count(State.id)).scalar() or 0
    avg_experience = db.query(func.avg(Professional.experience_years)).scalar()
    avg_experience = float(avg_experience) if avg_experience is not None else 0.0

    # “new this month” quickies (UTC by created_at)
    first_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_customers_month = db.query(func.count(Customer.id)).filter(Customer.created_at >= first_of_month).scalar() or 0
    new_pros_month = db.query(func.count(Professional.id)).filter(Professional.created_at >= first_of_month).scalar() or 0
    new_leads_month = db.query(func.count(Lead.id)).filter(Lead.created_at >= first_of_month).scalar() or 0

    return {
        "totals": {
            "customers": total_customers,
            "professionals": total_pros,
            "verified_professionals": verified_pros,
            "active_subscribed_professionals": active_subscribed_pros,
            "leads": total_leads,
            "urgent_leads": urgent_leads,
            "states": states_count,
        },
        "quality": {
            "avg_professional_experience_years": round(avg_experience, 2),
        },
        "month_to_date": {
            "new_customers": new_customers_month,
            "new_professionals": new_pros_month,
            "new_leads": new_leads_month,
        },
    }


# ------------------------------------------------
# 2) Leads: time series for charts (day or week)
# ------------------------------------------------
@router.get("/leads/time-series")
def leads_time_series(
    db: Session = Depends(get_db),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    service_id: Optional[int] = Query(None),
    state_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),  # 'urgent' | 'normal'
    bucket: str = Query("day", regex="^(day|week)$"),
):
    q = db.query(
        cast(Lead.created_at, Date).label("day"),
        func.count(Lead.id).label("count")
    )

    if service_id:
        q = q.filter(Lead.service_id == service_id)
    if state_id:
        q = q.filter(Lead.state_id == state_id)
    if status:
        q = q.filter(Lead.status == status)
    if date_from:
        q = q.filter(cast(Lead.created_at, Date) >= date_from)
    if date_to:
        q = q.filter(cast(Lead.created_at, Date) <= date_to)

    if bucket == "day":
        q = q.group_by(cast(Lead.created_at, Date)).order_by("day")
        rows = q.all()
        return [{"date": d.isoformat(), "count": c} for d, c in rows]

    # weekly buckets (week starting Monday)
    q = (
        db.query(
            func.date_trunc("week", Lead.created_at).label("week"),
            func.count(Lead.id).label("count"),
        )
    )
    if service_id:
        q = q.filter(Lead.service_id == service_id)
    if state_id:
        q = q.filter(Lead.state_id == state_id)
    if status:
        q = q.filter(Lead.status == status)
    if date_from:
        q = q.filter(Lead.created_at >= date_from)
    if date_to:
        q = q.filter(Lead.created_at <= date_to)

    q = q.group_by(func.date_trunc("week", Lead.created_at)).order_by("week")
    rows = q.all()
    return [{"week_start": w.date().isoformat(), "count": c} for w, c in rows]


# ---------------------------------------------------------
# 3) Leads breakdowns (status, by service, by state)
# ---------------------------------------------------------
@router.get("/leads/status-breakdown")
def leads_status_breakdown(
    db: Session = Depends(get_db),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
):
    q = db.query(
        Lead.status,
        func.count(Lead.id)
    )
    if date_from:
        q = q.filter(cast(Lead.created_at, Date) >= date_from)
    if date_to:
        q = q.filter(cast(Lead.created_at, Date) <= date_to)
    q = q.group_by(Lead.status)
    rows = q.all()
    return [{"status": s or "unknown", "count": c} for s, c in rows]


@router.get("/leads/by-service")
def leads_by_service(
    db: Session = Depends(get_db),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    state_id: Optional[int] = Query(None),
):
    q = (
        db.query(
            Service.id.label("service_id"),
            Service.service_name.label("service_name"),
            func.count(Lead.id).label("count"),
        )
        .outerjoin(Lead, Lead.service_id == Service.id)
    )
    if state_id:
        q = q.filter(Lead.state_id == state_id)
    if date_from:
        q = q.filter(cast(Lead.created_at, Date) >= date_from)
    if date_to:
        q = q.filter(cast(Lead.created_at, Date) <= date_to)

    q = q.group_by(Service.id, Service.service_name).order_by(func.count(Lead.id).desc())
    rows = q.all()
    return [{"service_id": sid, "service": sname, "count": cnt or 0} for sid, sname, cnt in rows]


@router.get("/leads/by-state")
def leads_by_state(
    db: Session = Depends(get_db),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    service_id: Optional[int] = Query(None),
):
    q = (
        db.query(
            State.id.label("state_id"),
            State.state_name,
            func.count(Lead.id).label("count"),
        )
        .outerjoin(Lead, Lead.state_id == State.id)
    )

    if service_id:
        q = q.filter(Lead.service_id == service_id)
    if date_from:
        q = q.filter(cast(Lead.created_at, Date) >= date_from)
    if date_to:
        q = q.filter(cast(Lead.created_at, Date) <= date_to)

    q = q.group_by(State.id, State.state_name).order_by(func.count(Lead.id).desc())
    rows = q.all()
    return [{"state_id": sid, "state": sname, "count": cnt or 0} for sid, sname, cnt in rows]


# ---------------------------------------------------------
# 4) Subscriptions: plan breakdown and revenue summary
# ---------------------------------------------------------
@router.get("/subscriptions/plan-breakdown")
def subscriptions_plan_breakdown(db: Session = Depends(get_db)):
    """
    Count how many professionals are on each subscription plan, and sum revenue if active.
    """
    # professionals joined to subscription plan
    q = (
        db.query(
            Subscription.id.label("plan_id"),
            Subscription.plan_name,
            Subscription.plan_cost,
            func.count(Professional.id).label("professionals_on_plan"),
            func.sum(
                case(
                    (Professional.subscription_active == True, Subscription.plan_cost),
                    else_=0,
                )
            ).label("active_mrr")  # monthly recurring revenue (if your costs are monthly)
        )
        .outerjoin(Professional, Professional.subscription_plan_id == Subscription.id)
        .group_by(Subscription.id, Subscription.plan_name, Subscription.plan_cost)
        .order_by(Subscription.id)
    )
    rows = q.all()

    return [
        {
            "plan_id": pid,
            "plan_name": pname,
            "plan_cost": float(pcost) if pcost is not None else None,
            "professionals_on_plan": int(pros or 0),
            "active_mrr": float(mrr or 0.0),
        }
        for pid, pname, pcost, pros, mrr in rows
    ]


# ---------------------------------------------------------
# 5) Professionals: distribution by state & service
# ---------------------------------------------------------
@router.get("/professionals/by-state")
def professionals_by_state(db: Session = Depends(get_db)):
    q = (
        db.query(
            State.id.label("state_id"),
            State.state_name,
            func.count(Professional.id).label("count"),
            func.sum(case((Professional.verified_status == True, 1), else_=0)).label("verified"),
            func.sum(case((Professional.subscription_active == True, 1), else_=0)).label("active_subscribed"),
        )
        .outerjoin(Professional, Professional.state_id == State.id)
        .group_by(State.id, State.state_name)
        .order_by(func.count(Professional.id).desc())
    )
    rows = q.all()
    return [
        {
            "state_id": sid,
            "state": sname,
            "professionals": int(cnt or 0),
            "verified": int(ver or 0),
            "active_subscribed": int(active or 0),
        }
        for sid, sname, cnt, ver, active in rows
    ]


@router.get("/professionals/by-service")
def professionals_by_service(db: Session = Depends(get_db)):
    q = (
        db.query(
            Service.id.label("service_id"),
            Service.service_name,
            func.count(Professional.id).label("count"),
            func.sum(case((Professional.verified_status == True, 1), else_=0)).label("verified"),
        )
        .outerjoin(Professional, Professional.service_id == Service.id)
        .group_by(Service.id, Service.service_name)
        .order_by(func.count(Professional.id).desc())
    )
    rows = q.all()
    return [
        {
            "service_id": sid,
            "service": sname,
            "professionals": int(cnt or 0),
            "verified": int(ver or 0),
        }
        for sid, sname, cnt, ver in rows
    ]


# ---------------------------------------------------------
# 6) Pair utilization: how many leads each pair got
# ---------------------------------------------------------
@router.get("/pairs/utilization")
def pair_utilization(
    db: Session = Depends(get_db),
    service_id: Optional[int] = Query(None),
    state_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
):
    q = (
        db.query(
            ProfessionalPair.id.label("pair_id"),
            ProfessionalPair.professional_id_1,
            ProfessionalPair.professional_id_2,
            func.count(Lead.id).label("leads_assigned"),
        )
        .outerjoin(Lead, Lead.pair_id == ProfessionalPair.id)
    )

    if service_id or state_id:
        # join through service_city_pairs to filter pairs
        q = q.join(ServiceCityPair, ServiceCityPair.id == ProfessionalPair.service_city_pair_id)
        if service_id:
            q = q.filter(ServiceCityPair.service_id == service_id)
        # Note: state_id parameter kept for backward compatibility but not used with city-based pairs

    if date_from:
        q = q.filter(cast(Lead.created_at, Date) >= date_from)
    if date_to:
        q = q.filter(cast(Lead.created_at, Date) <= date_to)

    q = q.group_by(
        ProfessionalPair.id,
        ProfessionalPair.professional_id_1,
        ProfessionalPair.professional_id_2,
    ).order_by(func.count(Lead.id).desc())

    rows = q.all()
    return [
        {
            "pair_id": pid,
            "professional_id_1": p1,
            "professional_id_2": p2,
            "leads_assigned": int(cnt or 0),
        }
        for pid, p1, p2, cnt in rows
    ]


# ---------------------------------------------------------
# 7) Growth charts: new customers, pros by day
# ---------------------------------------------------------
@router.get("/growth/new-customers")
def new_customers_series(
    db: Session = Depends(get_db),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
):
    q = (
        db.query(
            cast(Customer.created_at, Date).label("day"),
            func.count(Customer.id).label("count"),
        )
    )
    if date_from:
        q = q.filter(cast(Customer.created_at, Date) >= date_from)
    if date_to:
        q = q.filter(cast(Customer.created_at, Date) <= date_to)
    q = q.group_by(cast(Customer.created_at, Date)).order_by("day")
    rows = q.all()
    return [{"date": d.isoformat(), "count": c} for d, c in rows]


@router.get("/growth/new-professionals")
def new_professionals_series(
    db: Session = Depends(get_db),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
):
    q = (
        db.query(
            cast(Professional.created_at, Date).label("day"),
            func.count(Professional.id).label("count"),
        )
    )
    if date_from:
        q = q.filter(cast(Professional.created_at, Date) >= date_from)
    if date_to:
        q = q.filter(cast(Professional.created_at, Date) <= date_to)
    q = q.group_by(cast(Professional.created_at, Date)).order_by("day")
    rows = q.all()
    return [{"date": d.isoformat(), "count": c} for d, c in rows]
