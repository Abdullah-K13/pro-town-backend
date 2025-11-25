# dataingest.py
"""
Faker-based Data Ingestion for ProTown Backend

Usage:
  # (optional) tune volumes and seed via env
  export FAKER_SEED=42
  export NUM_SERVICES=8
  export NUM_STATES=10
  export NUM_SUBSCRIPTIONS=3
  export NUM_ADMINS=3
  export NUM_CUSTOMERS=50
  export NUM_PROFESSIONALS=60
  export NUM_LEADS=200

  python dataingest.py

Notes:
- Passwords are hashed via utils.security.hash_password
  - Admins    -> "admin123"    (unless changed here)
  - Customers -> "customer123"
  - Pros      -> "pro123"
- ProfessionalPairs are created only where we have ≥2 professionals
  with the same (service_id, city_id).
"""

import os
import random
from decimal import Decimal
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

from faker import Faker
from sqlalchemy.orm import Session

from db.init import init_db, SessionLocal
from utils.security import hash_password

from models.service import Service
from models.state import State
from models.subscription import Subscription

from models.admin import Admin
from models.customer import Customer
from models.professional import Professional

from models.service_city_pair import ServiceCityPair
from models.professional_pair import ProfessionalPair
from models.lead import Lead
from models.city import City
from models.state_city import StateCityPair


# ----------------------- Config -----------------------
FAKER_SEED = int(os.getenv("FAKER_SEED", "42"))

NUM_SERVICES = int(os.getenv("NUM_SERVICES", "8"))
NUM_STATES = int(os.getenv("NUM_STATES", "10"))
NUM_CITIES = int(os.getenv("NUM_CITIES", "15"))
NUM_SUBSCRIPTIONS = int(os.getenv("NUM_SUBSCRIPTIONS", "3"))

NUM_ADMINS = int(os.getenv("NUM_ADMINS", "3"))
NUM_CUSTOMERS = int(os.getenv("NUM_CUSTOMERS", "50"))
NUM_PROFESSIONALS = int(os.getenv("NUM_PROFESSIONALS", "60"))

NUM_LEADS = int(os.getenv("NUM_LEADS", "200"))

# Controls the fraction of possible (service,city) combos to materialize as pairs
PAIR_COVERAGE = float(os.getenv("PAIR_COVERAGE", "0.7"))  # 70% of combos

DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
DEFAULT_CUSTOMER_PASSWORD = os.getenv("DEFAULT_CUSTOMER_PASSWORD", "customer123")
DEFAULT_PRO_PASSWORD = os.getenv("DEFAULT_PRO_PASSWORD", "pro123")

# Sample values for enums/flags
LEAD_STATUSES = ["normal", "priority", "closed"]


# ----------------------- Faker setup -----------------------
faker = Faker(["en_US", "en_GB"])
random.seed(FAKER_SEED)
Faker.seed(FAKER_SEED)


def _bool_biased(true_prob: float = 0.5) -> bool:
    return random.random() < true_prob


def _money(lo=10, hi=150) -> Decimal:
    return Decimal(f"{random.uniform(lo, hi):.2f}")


# ----------------------- Seeders -----------------------
def seed_services(db: Session) -> List[Service]:
    # Generate unique, reasonably realistic service names
    # If you already have a canonical list, replace this generator with it.
    base = [
        "Plumbing", "Electrical", "Carpentry", "House Cleaning", "Landscaping",
        "Painting", "HVAC", "Appliance Repair", "Pest Control", "Roofing",
        "Locksmith", "IT Support", "Auto Mechanic", "Moving Services",
    ]
    random.shuffle(base)
    names = base[:max(1, NUM_SERVICES)]

    services: List[Service] = []
    for name in names:
        exists = db.query(Service).filter(Service.service_name == name).first()
        if exists:
            services.append(exists)
        else:
            svc = Service(service_name=name)
            db.add(svc)
            services.append(svc)
    db.commit()
    print(f"[seed] services: {len(services)}")
    return services


def seed_states(db: Session) -> List[State]:
    # Make state names look like US states or regions
    # Faker doesn't have a direct "state name" in all locales, so blend.
    states: List[State] = []
    seen = set()
    while len(states) < max(1, NUM_STATES):
        name = faker.state()
        if name in seen:
            continue
        seen.add(name)
        exists = db.query(State).filter(State.state_name == name).first()
        if exists:
            states.append(exists)
        else:
            st = State(state_name=name)
            db.add(st)
            states.append(st)
    db.commit()
    print(f"[seed] states: {len(states)}")
    return states

def seed_state_city_pairs(
    db: Session,
    states: List[State],
    cities: List[City],
) -> List[StateCityPair]:
    state_city_pairs: List[StateCityPair] = []
    for city in cities:
        # Check if pair already exists for this city (ensure 1 state per city)
        exists = (
            db.query(StateCityPair)
            .filter(StateCityPair.city_id == city.id)
            .first()
        )
        if exists:
            state_city_pairs.append(exists)
        else:
            state = random.choice(states)
            scp = StateCityPair(state_id=state.id, city_id=city.id)
            db.add(scp)
            state_city_pairs.append(scp)
    db.commit()
    print(f"[seed] state_city_pairs: {len(state_city_pairs)}")
    return state_city_pairs


def seed_cities(db: Session) -> List[City]:
    # Generate city names using Faker
    cities: List[City] = []
    seen = set()
    while len(cities) < max(1, NUM_CITIES):
        name = faker.city()
        if name in seen:
            continue
        seen.add(name)
        exists = db.query(City).filter(City.city_name == name).first()
        if exists:
            cities.append(exists)
        else:
            city = City(city_name=name)
            db.add(city)
            cities.append(city)
    db.commit()
    print(f"[seed] cities: {len(cities)}")
    return cities

def seed_subscriptions(db: Session) -> List[Subscription]:
    # Make simple plan tiers
    plan_templates = [
        ("Free", _money(0, 0), "Starter plan with limited features."),
        ("Standard", _money(15, 35), "Good for growing professionals."),
        ("Pro", _money(40, 99), "Advanced tools and priority leads."),
        ("Enterprise", _money(100, 299), "For agencies and large teams."),
    ]
    # Trim/expand to NUM_SUBSCRIPTIONS
    if NUM_SUBSCRIPTIONS <= 0:
        return []
    if NUM_SUBSCRIPTIONS < len(plan_templates):
        plan_templates = plan_templates[:NUM_SUBSCRIPTIONS]
    else:
        # add synthetic extra tiers if requested
        while len(plan_templates) < NUM_SUBSCRIPTIONS:
            tier_n = len(plan_templates) + 1
            plan_templates.append((
                f"Plan {tier_n}", _money(20, 200), f"Custom tier {tier_n}."
            ))

    subs: List[Subscription] = []
    for name, cost, desc in plan_templates:
        exists = db.query(Subscription).filter(Subscription.plan_name == name).first()
        if exists:
            exists.plan_cost = cost
            exists.plan_description = desc
            subs.append(exists)
        else:
            sub = Subscription(plan_name=name, plan_cost=cost, plan_description=desc)
            db.add(sub)
            subs.append(sub)
    db.commit()
    print(f"[seed] subscriptions: {len(subs)}")
    return subs


def seed_admins(db: Session, n=NUM_ADMINS) -> List[Admin]:
    admins: List[Admin] = []
    for _ in range(max(0, n)):
        name = faker.name()
        email = faker.unique.company_email()
        phone = faker.msisdn()[:12]
        exists = db.query(Admin).filter(Admin.email == email).first()
        if exists:
            # update a couple of fields if desired
            exists.name = exists.name or name
            exists.phone_number = exists.phone_number or phone
            admins.append(exists)
        else:
            adm = Admin(
                name=name,
                phone_number=phone,
                email=email,
                password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
            )
            db.add(adm)
            admins.append(adm)
    db.commit()
    print(f"[seed] admins: {len(admins)}")
    return admins


def seed_customers(db: Session, n=NUM_CUSTOMERS) -> List[Customer]:
    customers: List[Customer] = []
    for _ in range(max(0, n)):
        first = faker.first_name()
        last = faker.last_name()
        email = faker.unique.free_email()
        exists = db.query(Customer).filter(Customer.email == email).first()
        addr = faker.street_address()
        phone = faker.msisdn()[:12]
        city = faker.city()
        state = faker.state_abbr()  # NOTE: this is the textual 'state' field in your Customer model
        zipc = faker.postcode()

        # Notification prefs
        email_n = _bool_biased(0.85)
        sms_n = _bool_biased(0.7)

        if exists:
            exists.first_name = exists.first_name or first
            exists.last_name = exists.last_name or last
            exists.address = exists.address or addr
            exists.phone_number = exists.phone_number or phone
            exists.city = exists.city or city
            exists.state = exists.state or state
            exists.zip_code = exists.zip_code or zipc
            # don't forcibly override user preferences if already set
            if exists.email_notifications is None:
                exists.email_notifications = email_n
            if exists.sms_notifications is None:
                exists.sms_notifications = sms_n
            if not exists.password_hash:
                exists.password_hash = hash_password(DEFAULT_CUSTOMER_PASSWORD)
            customers.append(exists)
        else:
            c = Customer(
                first_name=first,
                last_name=last,
                address=addr,
                phone_number=phone,
                email=email,
                password_hash=hash_password(DEFAULT_CUSTOMER_PASSWORD),
                city=city,
                state=state,
                zip_code=zipc,
                email_notifications=email_n,
                sms_notifications=sms_n,
            )
            db.add(c)
            customers.append(c)
    db.commit()
    print(f"[seed] customers: {len(customers)}")
    return customers


def seed_professionals(
    db: Session,
    services: List[Service],
    states: List[State],
    cities: List[City],
    subs: List[Subscription],
    n=NUM_PROFESSIONALS,
) -> List[Professional]:
    # Build city -> state map
    city_to_state = {}
    all_scps = db.query(StateCityPair).all()
    for scp in all_scps:
        city_to_state[scp.city_id] = scp.state_id

    pros: List[Professional] = []
    for _ in range(max(0, n)):
        name = f"{faker.first_name()} {faker.last_name()}"
        email = faker.unique.safe_email()
        phone = faker.msisdn()[:12]

        service = random.choice(services) if services else None
        sub = random.choice(subs) if subs else None
        
        city = random.choice(cities) if cities else None
        state_id = city_to_state.get(city.id) if city else None

        verified = _bool_biased(0.35)
        docs_up = verified or _bool_biased(0.5)
        sub_active = bool(sub) and _bool_biased(0.6)

        exists = db.query(Professional).filter(Professional.email == email).first()
        payload = dict(
            name=name,
            email=email,
            password_hash=hash_password(DEFAULT_PRO_PASSWORD),
            phone_number=phone,
            service_id=service.id if service else None,
            state_id=state_id,
            city_id=city.id if city else None,
            business_name=faker.company(),
            business_address=faker.address(),
            verified_status=verified,
            documents_uploaded=docs_up,
            subscription_plan_id=sub.id if sub else None,
            subscription_active=sub_active,
        )
        if exists:
            for k, v in payload.items():
                if getattr(exists, k, None) in (None, "", False):
                    setattr(exists, k, v)
            pros.append(exists)
        else:
            p = Professional(**payload)
            db.add(p)
            pros.append(p)
    db.commit()
    print(f"[seed] professionals: {len(pros)}")
    return pros


def seed_service_city_pairs(
    db: Session,
    services: List[Service],
    cities: List[City],
    coverage: float = PAIR_COVERAGE,
) -> List[ServiceCityPair]:
    scps: List[ServiceCityPair] = []
    for svc in services:
        for city in cities:
            if random.random() > coverage:
                continue
            exists = (
                db.query(ServiceCityPair)
                .filter(
                    ServiceCityPair.service_id == svc.id,
                    ServiceCityPair.city_id == city.id,
                )
                .first()
            )
            if exists:
                scps.append(exists)
            else:
                scp = ServiceCityPair(service_id=svc.id, city_id=city.id)
                db.add(scp)
                scps.append(scp)
    db.commit()
    print(f"[seed] service_city_pairs: {len(scps)}")
    return scps


def seed_professional_pairs(
    db: Session,
    scps: List[ServiceCityPair],
) -> List[ProfessionalPair]:
    """
    For each ServiceCityPair, if there are >= 2 professionals sharing that (service_id, city_id),
    create one ProfessionalPair with two random pros from that bucket.
    """
    # Build buckets of professionals by (service_id, city_id)
    buckets: Dict[Tuple[int, int], List[Professional]] = defaultdict(list)
    pros = db.query(Professional).all()
    for p in pros:
        if p.service_id and p.city_id:
            buckets[(p.service_id, p.city_id)].append(p)

    pairs: List[ProfessionalPair] = []
    for scp in scps:
        key = (scp.service_id, scp.city_id)
        candidates = buckets.get(key, [])
        if len(candidates) < 2:
            continue

        # Randomly pick 2 unique pros
        pro1, pro2 = random.sample(candidates, 2)

        # Avoid duplicates if one already exists with same scp & members
        exists = (
            db.query(ProfessionalPair)
            .filter(
                ProfessionalPair.service_city_pair_id == scp.id,
                ProfessionalPair.professional_id_1 == pro1.id,
                ProfessionalPair.professional_id_2 == pro2.id,
            )
            .first()
        )
        if exists:
            pairs.append(exists)
        else:
            pair = ProfessionalPair(
                service_city_pair_id=scp.id,
                professional_id_1=pro1.id,
                professional_id_2=pro2.id,
            )
            db.add(pair)
            pairs.append(pair)

    db.commit()
    print(f"[seed] professional_pairs: {len(pairs)}")
    return pairs


def seed_leads(db: Session, n: int = 100) -> List[Lead]:
    """
    Strict: create leads only for (service_id, city_id) that have >= 1 ProfessionalPair.
    Guarantees pair_id is never NULL and satisfies the Lead schema:
      - customer_id: required (picked from existing customers)
      - description: required (<= 900 chars)
      - service_id, state_id, city_id: from eligible ServiceCityPair
      - status: random from allowed set
      - pair_id: chosen from matching ProfessionalPair
      - created_at: DB default (NOW())
    """
    leads: List[Lead] = []

    # ---- Preload lookups ----
    customers = db.query(Customer.id).all()
    if not customers:
        print("[seed] leads: 0 (no customers available)")
        return leads
    customer_ids = [c.id for c in customers]

    scps = list(db.query(ServiceCityPair).all())
    if not scps:
        print("[seed] leads: 0 (no service_city_pairs)")
        return leads

    # Map SCP.id -> list[ProfessionalPair] to ensure pair exists
    pairs_by_scp = defaultdict(list)
    for pp in db.query(ProfessionalPair).all():
        pairs_by_scp[pp.service_city_pair_id].append(pp)

    # Get states for leads (we still need state_id for Lead model)
    states = db.query(State).all()
    if not states:
        print("[seed] leads: 0 (no states available)")
        return leads

    # Keep only (service_id, city_id, scp_id) that actually have at least one pair
    # We'll assign a random state_id for each lead
    eligible = [
        (scp.service_id, scp.city_id, scp.id)
        for scp in scps
        if pairs_by_scp.get(scp.id)
    ]

    if not eligible:
        print("[seed] leads: 0 (no eligible service/city combos with pairs)")
        return leads

    # Build city -> state map
    city_to_state = {}
    all_scps = db.query(StateCityPair).all()
    for scp in all_scps:
        city_to_state[scp.city_id] = scp.state_id

    LEAD_STATUSES = ["normal", "urgent"]

    for _ in range(max(0, n)):
        svc_id, city_id, scp_id = random.choice(eligible)
        
        # Get correct state for this city
        st_id = city_to_state.get(city_id)
        if not st_id:
            # Fallback if something is wrong, though shouldn't happen if seeded correctly
            state = random.choice(states)
            st_id = state.id

        pair_list = pairs_by_scp[scp_id]          # guaranteed non-empty
        chosen_pair = random.choice(pair_list)

        customer_id = random.choice(customer_ids)

        # <= 900 chars per schema
        description = (
            f"Customer #{customer_id} requested service {svc_id} "
            f"in city {city_id}."
        )[:900]

        ld = Lead(
            customer_id=customer_id,
            description=description,
            service_id=svc_id,
            state_id=st_id,
            city_id=city_id,
            status=random.choice(LEAD_STATUSES),  # "normal" or "urgent"
            pair_id=chosen_pair.id,               # guaranteed non-NULL
            # created_at uses DB default NOW()
        )
        db.add(ld)
        leads.append(ld)

    db.commit()
    print(f"[seed] leads: {len(leads)} (strict, no NULL pair_id)")
    return leads# ----------------------- Main -----------------------
def main():
    # Initialize DB schema only; no legacy seeding
    init_db(seed=False)

    db = SessionLocal()
    try:
        services = seed_services(db)
        states = seed_states(db)
        cities = seed_cities(db)
        state_city_pairs = seed_state_city_pairs(db, states, cities)
        subs = seed_subscriptions(db)

        seed_admins(db, NUM_ADMINS)
        seed_customers(db, NUM_CUSTOMERS)
        seed_professionals(db, services, states, cities, subs, NUM_PROFESSIONALS)

        scps = seed_service_city_pairs(db, services, cities, PAIR_COVERAGE)
        seed_professional_pairs(db, scps)

        seed_leads(db, NUM_LEADS)

        print("\n✅ Faker ingestion completed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
