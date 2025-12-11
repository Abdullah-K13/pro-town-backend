"""
Independent Square Payment Testing Script
==========================================
This script provides standalone functions to test Square payment functionality:
1. Create a payment token (card nonce) from card details
2. Create a customer in Square

Usage:
    python test_square_payment.py

Requirements:
    - square (pip install squareup)
    - python-dotenv (pip install python-dotenv)
    - .env file with SQUARE_ACCESS_TOKEN and SQUARE_LOCATION_ID
"""

import os
import uuid
from dotenv import load_dotenv
from square.client import Client

# Load environment variables
load_dotenv()

SQUARE_ACCESS_TOKEN = os.getenv("SQUARE_ACCESS_TOKEN", "")
SQUARE_LOCATION_ID = os.getenv("SQUARE_LOCATION_ID", "")
SQUARE_ENVIRONMENT = os.getenv("SQUARE_ENVIRONMENT", "production") 

# Initialize Square client
client = Client(
    access_token=SQUARE_ACCESS_TOKEN,
    environment=SQUARE_ENVIRONMENT
)

def create_card_nonce(card_details: dict) -> dict:
    """
    Create a card payment token (nonce) from card details.
    
    Note: In production, card nonces should be created on the frontend using
    Square Web Payments SDK. This function is for testing purposes only.
    
    Args:
        card_details (dict): Dictionary containing:
            - card_number (str): Card number (e.g., "4111111111111111")
            - exp_month (int): Expiration month (1-12)
            - exp_year (int): Expiration year (e.g., 2025)
            - cvv (str): CVV code (e.g., "123")
            - postal_code (str): Billing postal code
            
    Returns:
        dict: Contains 'nonce', 'card_brand', 'last_4', 'exp_month', 'exp_year'
        
    Example:
        card_details = {
            "card_number": "4111111111111111",  # Test Visa card
            "exp_month": 12,
            "exp_year": 2025,
            "cvv": "123",
            "postal_code": "12345"
        }
        result = create_card_nonce(card_details)
        print(f"Card Nonce: {result['nonce']}")
    """
    try:
        # Create card nonce using Square Cards API
        # Note: This is typically done on the frontend in production
        result = client.cards.create_card(
            body={
                "idempotency_key": str(uuid.uuid4()),
                "source_id": "EXTERNAL",  # For testing
                "card": {
                    "cardholder_name": card_details.get("cardholder_name", "Test User"),
                    "billing_address": {
                        "postal_code": card_details.get("postal_code", "12345")
                    },
                    "number": card_details["card_number"],
                    "exp_month": card_details["exp_month"],
                    "exp_year": card_details["exp_year"],
                    "cvv": card_details.get("cvv", "123")
                }
            }
        )
        
        if result.is_success():
            card = result.body.get("card", {})
            return {
                "success": True,
                "nonce": card.get("id"),  # This is the card ID/token
                "card_brand": card.get("card_brand"),
                "last_4": card.get("last_4"),
                "exp_month": card.get("exp_month"),
                "exp_year": card.get("exp_year"),
                "card_id": card.get("id"),
                "message": "Card tokenized successfully"
            }
        else:
            errors = result.errors if result.errors else []
            return {
                "success": False,
                "error": "Failed to create card nonce",
                "details": errors
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Exception occurred while creating card nonce"
        }


def create_customer(customer_data: dict) -> dict:
    """
    Create a customer in Square.
    
    Args:
        customer_data (dict): Dictionary containing:
            - email (str): Customer email (required)
            - given_name (str): First name (optional)
            - family_name (str): Last name (optional)
            - phone_number (str): Phone number (optional)
            - company_name (str): Company name (optional)
            - address (dict): Address details (optional)
                - address_line_1 (str)
                - locality (str): City
                - administrative_district_level_1 (str): State
                - postal_code (str)
                - country (str): Country code (e.g., "US")
                
    Returns:
        dict: Contains 'customer_id', 'email', 'created_at', etc.
        
    Example:
        customer_data = {
            "email": "test@example.com",
            "given_name": "John",
            "family_name": "Doe",
            "phone_number": "+1234567890"
        }
        result = create_customer(customer_data)
        print(f"Customer ID: {result['customer_id']}")
    """
    try:
        # Prepare customer body
        body = {
            "idempotency_key": str(uuid.uuid4()),
            "email_address": customer_data.get("email"),
        }
        
        # Add optional fields
        if customer_data.get("given_name"):
            body["given_name"] = customer_data["given_name"]
        if customer_data.get("family_name"):
            body["family_name"] = customer_data["family_name"]
        if customer_data.get("phone_number"):
            body["phone_number"] = customer_data["phone_number"]
        if customer_data.get("company_name"):
            body["company_name"] = customer_data["company_name"]
        if customer_data.get("address"):
            body["address"] = customer_data["address"]
            
        # Create customer
        result = client.customers.create_customer(body=body)
        
        if result.is_success():
            customer = result.body.get("customer", {})
            return {
                "success": True,
                "customer_id": customer.get("id"),
                "email": customer.get("email_address"),
                "given_name": customer.get("given_name"),
                "family_name": customer.get("family_name"),
                "phone_number": customer.get("phone_number"),
                "created_at": customer.get("created_at"),
                "message": "Customer created successfully"
            }
        else:
            errors = result.errors if result.errors else []
            return {
                "success": False,
                "error": "Failed to create customer",
                "details": errors
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Exception occurred while creating customer"
        }


def attach_card_to_customer(customer_id: str, card_nonce: str) -> dict:
    """
    Attach a card to an existing customer.
    
    Args:
        customer_id (str): Square customer ID
        card_nonce (str): Card nonce/token from create_card_nonce()
        
    Returns:
        dict: Contains 'card_id', 'customer_id', 'last_4', etc.
    """
    try:
        result = client.cards.create_card(
            body={
                "idempotency_key": str(uuid.uuid4()),
                "source_id": card_nonce,
                "card": {
                    "customer_id": customer_id
                }
            }
        )
        
        if result.is_success():
            card = result.body.get("card", {})
            return {
                "success": True,
                "card_id": card.get("id"),
                "customer_id": card.get("customer_id"),
                "last_4": card.get("last_4"),
                "card_brand": card.get("card_brand"),
                "message": "Card attached to customer successfully"
            }
        else:
            errors = result.errors if result.errors else []
            return {
                "success": False,
                "error": "Failed to attach card to customer",
                "details": errors
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Exception occurred while attaching card"
        }


# ============================================================================
# MAIN TEST FUNCTION
# ============================================================================

def main():
    """
    Main test function - demonstrates usage of all functions.
    """
    print("=" * 70)
    print("SQUARE PAYMENT TESTING SCRIPT")
    print("=" * 70)
    print()
    
    # Check environment variables
    if not SQUARE_ACCESS_TOKEN:
        print("❌ ERROR: SQUARE_ACCESS_TOKEN not found in .env file")
        return
    
    if not SQUARE_LOCATION_ID:
        print("⚠️  WARNING: SQUARE_LOCATION_ID not found in .env file")
    
    print(f"✅ Environment: {SQUARE_ENVIRONMENT}")
    print(f"✅ Access Token: {SQUARE_ACCESS_TOKEN[:20]}...")
    print(f"✅ Location ID: {SQUARE_LOCATION_ID}")
    print()
    
    # Test 1: Create Customer
    print("-" * 70)
    print("TEST 1: Creating a customer")
    print("-" * 70)
    
    customer_data = {
        "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        "given_name": "John",
        "family_name": "Doe",
        "phone_number": "+12345678900"
    }
    
    print(f"Customer Data: {customer_data}")
    customer_result = create_customer(customer_data)
    print(f"\nResult: {customer_result}")
    print()
    
    if not customer_result.get("success"):
        print("❌ Customer creation failed. Stopping tests.")
        return
    
    customer_id = customer_result.get("customer_id")
    print(f"✅ Customer created with ID: {customer_id}")
    print()
    
    # Test 2: Create Card Nonce (Tokenize Card)
    print("-" * 70)
    print("TEST 2: Creating card nonce (tokenizing card)")
    print("-" * 70)
    
    # Square test card numbers:
    # Visa: 4111111111111111
    # Mastercard: 5105105105105100
    # Amex: 378282246310005
    
    card_details = {
        "card_number": "4782780004694314",  # Test Visa
        "exp_month": 2,
        "exp_year": 2027,
        "cvv": "680",
        "postal_code": "75050",
        "cardholder_name": "M ABDULLAH KHAN"
    }
    
    print(f"Card Details: {card_details}")
    card_result = create_card_nonce(card_details)
    print(f"\nResult: {card_result}")
    print()
    
    if card_result.get("success"):
        print(f"✅ Card Nonce: {card_result.get('nonce')}")
        print(f"✅ Card Brand: {card_result.get('card_brand')}")
        print(f"✅ Last 4: {card_result.get('last_4')}")
    else:
        print("❌ Card nonce creation failed")
    
    print()
    print("=" * 70)
    print("TESTS COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()
