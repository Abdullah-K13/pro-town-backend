from fastapi import FastAPI
from db.init import init_db
from dotenv import load_dotenv

load_dotenv()

from routers import (
    auth, customer, professional, admin, subscription,
    service, state, city, service_city_pair, professional_pair, lead, analytics, newsletter, payment, public  # adjust path
)
from fastapi.middleware.cors import CORSMiddleware


origins = [
    "http://localhost:8080",   # your frontend
    "http://127.0.0.1:8080",
    "https://protownnetwork.com",
    "https://www.protownnetwork.com",
    "https://api.protownnetwork.com",
    # add others if you use them:
    # "http://localhost:5173",  # Vite default
    # "http://localhost:3000",  # Next.js/CRA
]


app = FastAPI(title="ProTown Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # cannot be ["*"] if allow_credentials=True
    allow_credentials=True,         # set True if you use cookies/auth headers
    allow_methods=["*"],            # or list specific methods ["GET","POST","OPTIONS"]
    allow_headers=["*"],            # or list specific headers
)
@app.on_event("startup")
def startup():
    init_db()

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Routers
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(customer.router, prefix="/customers", tags=["Customers"])
app.include_router(professional.router, prefix="/professionals", tags=["Professionals"])
app.include_router(admin.router, prefix="/admins", tags=["Admins"])
app.include_router(subscription.router, prefix="/subscriptions", tags=["Subscriptions"])
app.include_router(service.router, prefix="/services", tags=["Services"])
app.include_router(state.router, prefix="/states", tags=["States"])
app.include_router(city.router, prefix="/cities", tags=["Cities"])
app.include_router(service_city_pair.router, prefix="/service_city_pairs", tags=["Service-City Pairs"])
app.include_router(professional_pair.router, prefix="/professional_pairs", tags=["Professional Pairs"])
app.include_router(lead.router, prefix="/leads", tags=["Leads"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(newsletter.router, prefix="/newsletter", tags=["Newsletter"])
app.include_router(payment.router, prefix="/payments", tags=["Payments"])
app.include_router(public.router, prefix="/public", tags=["Public"])


@app.get("/")
def root():
    return {"message": "ProTown Backend running successfully"}
