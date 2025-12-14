from square.client import squareclient
from datetime import date

# =============================
# CONFIG (UPDATE THESE)
# =============================
SQUARE_ACCESS_TOKEN = "EAAAl4Q9pRT9LMPrVJM2IM8ck6C0m6g9gG3jt02Nz5P8hsh8PdumSOFnSf8_44ym"
LOCATION_ID = "LTC83GFNXBNE6"
PLAN_ID = "JDCZJQKUQOYZQI73XOMDOH3H"

# Card nonce from frontend (PASTE HERE)
CARD_NONCE = "cnon:CA4SEDeFvqlc-xcZ9p2xSOhpN6QYASgB"

USER_EMAIL = "abdullahapperal@gmail.com"
USER_NAME = "Abdullah Khan"

# =============================
# INIT CLIENT
# =============================
client = squareclient(
    access_token=SQUARE_ACCESS_TOKEN,
    environment="production"
)

# =============================
# 1️⃣ CREATE CUSTOMER
# =============================
print("\n🔹 Creating customer...")
customer_result = client.customers.create_customer(
    body={
        "email_address": USER_EMAIL,
        "given_name": USER_NAME
    }
)

if customer_result.is_error():
    print("❌ Customer Error:", customer_result.errors)
    exit()

customer_id = customer_result.body["customer"]["id"]
print("✅ Customer ID:", customer_id)

# =============================
# 2️⃣ SAVE CARD (GET CARD ID)
# =============================
print("\n🔹 Saving card...")
card_result = client.cards.create_card(
    body={
        "source_id": CARD_NONCE,
        "card": {
            "customer_id": customer_id
        }
    }
)

if card_result.is_error():
    print("❌ Card Error:", card_result.errors)
    exit()

card = card_result.body["card"]
card_id = card["id"]

print("✅ Card saved")
print("   Card ID:", card_id)
print("   Brand:", card["card_brand"])
print("   Last 4:", card["last_4"])

# =============================
# 3️⃣ CREATE SUBSCRIPTION
# =============================
print("\n🔹 Creating subscription...")
subscription_result = client.subscriptions.create_subscription(
    body={
        "location_id": LOCATION_ID,
        "customer_id": customer_id,
        "plan_id": PLAN_ID,
        "card_id": card_id,
        "start_date": date.today().isoformat()
    }
)

if subscription_result.is_error():
    print("❌ Subscription Error:", subscription_result.errors)
    exit()

subscription = subscription_result.body["subscription"]
subscription_id = subscription["id"]

print("✅ Subscription created")
print("   Subscription ID:", subscription_id)
print("   Status:", subscription["status"])

# =============================
# 4️⃣ FETCH USER SUBSCRIPTIONS
# =============================
print("\n🔹 Fetching subscriptions...")
search_result = client.subscriptions.search_subscriptions(
    body={
        "query": {
            "filter": {
                "customer_ids": [customer_id]
            }
        }
    }
)

if search_result.is_error():
    print("❌ Fetch Error:", search_result.errors)
    exit()

subscriptions = search_result.body.get("subscriptions", [])

print(f"✅ Found {len(subscriptions)} subscription(s)")
for sub in subscriptions:
    print(
        f"   • ID: {sub['id']} | "
        f"Status: {sub['status']} | "
        f"Plan: {sub['plan_id']}"
    )


print("\n🎉 FLOW COMPLETED SUCCESSFULLY")

# =============================
# 5️⃣ FETCH CUSTOMER DETAILS (NEW FUNCTION)
# =============================
print("\n🔹 Fetching customer details (New Function)...")
# Import dynamically or assume it's available if running from root
try:
    from utils.square_client import get_customer_details
    
    details = get_customer_details(customer_id)
    print("✅ Customer Details Result:")
    import json
    print(json.dumps(details, indent=4))
    
    if details.get("success"):
        print(f"   Is Card Attached: {details.get('is_card_attached')}")
        print(f"   Subscription Status: {details.get('subscription_status')}")
    else:
        print("❌ Failed to get details")
        
except ImportError:
    print("⚠️  Could not import utils.square_client. Make sure you are running from the backend root directory.")
except Exception as e:
    print(f"❌ Error testing new function: {e}")

