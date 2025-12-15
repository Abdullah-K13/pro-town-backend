"""
Square API Client Wrapper
Handles all Square API interactions for payment processing using REST API
"""
import os
import logging
import requests
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Square Configuration
SQUARE_ACCESS_TOKEN = os.getenv("SQUARE_ACCESS_TOKEN", "")
SQUARE_ENVIRONMENT = os.getenv("SQUARE_ENVIRONMENT", "production")
SQUARE_LOCATION_ID = os.getenv("SQUARE_LOCATION_ID", "")

# Square API Base URLs
SQUARE_API_BASE_URL = {
    "sandbox": "https://connect.squareupsandbox.com",
    "production": "https://connect.squareup.com"
}

def get_square_base_url() -> str:
    """Get the base URL for Square API based on environment"""
    return SQUARE_API_BASE_URL.get(SQUARE_ENVIRONMENT, SQUARE_API_BASE_URL["sandbox"])

def get_square_headers() -> Dict[str, str]:
    """Get headers for Square API requests"""
    if not SQUARE_ACCESS_TOKEN:
        raise ValueError("SQUARE_ACCESS_TOKEN is not set in environment variables")
    
    return {
        "Square-Version": "2024-01-18",  # Latest API version
        "Authorization": f"Bearer EAAAl4Q9pRT9LMPrVJM2IM8ck6C0m6g9gG3jt02Nz5P8hsh8PdumSOFnSf8_44ym",
        "Content-Type": "application/json"
    }


def process_payment(
    source_id: str,
    amount: float,
    idempotency_key: str,
    location_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process a payment using Square Payments API.
    
    Args:
        source_id: Payment token from frontend (Square Web Payments SDK)
        amount: Payment amount in dollars
        idempotency_key: Unique key to prevent duplicate payments
        location_id: Square location ID (uses env var if not provided)
    
    Returns:
        Dict with payment status and transaction details
    
    Raises:
        Exception: If payment processing fails
    """
    location = location_id or SQUARE_LOCATION_ID
    if not location:
        raise ValueError("SQUARE_LOCATION_ID is required for payment processing")
    
    # Convert amount to cents (Square uses smallest currency unit)
    amount_cents = int(amount * 100)
    
    # Prepare payment request
    url = f"{get_square_base_url()}/v2/payments"
    headers = get_square_headers()
    
    payload = {
        "source_id": source_id,
        "idempotency_key": idempotency_key,
        "amount_money": {
            "amount": amount_cents,
            "currency": "USD"
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if "payment" in data:
            payment = data["payment"]
            return {
                "success": True,
                "transaction_id": payment.get("id"),
                "status": payment.get("status"),
                "amount": payment.get("amount_money", {}).get("amount", 0) / 100,
                "currency": payment.get("amount_money", {}).get("currency", "USD")
            }
        else:
            errors = data.get("errors", [])
            error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
            logger.error(f"Square payment failed: {error_messages}")
            raise Exception(f"Payment failed: {', '.join(error_messages)}")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error processing Square payment: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                raise Exception(f"Payment failed: {', '.join(error_messages)}")
            except:
                raise Exception(f"Payment failed: {e.response.text}")
        raise Exception(f"Payment failed: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing Square payment: {str(e)}")
        raise


def create_card_on_file(source_id: str, customer_id: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a card on file using Square Cards API.
    This saves a payment method for future use and returns a card_id that can be used for subscriptions.
    
    Args:
        source_id: Payment token from Square Web Payments SDK
        customer_id: Square customer ID (required)
        idempotency_key: Optional unique key to prevent duplicate card creation
    
    Returns:
        Dict with card details (card_id, last_4, brand, etc.)
    
    Raises:
        Exception: If card creation fails
    """
    try:
        if not customer_id:
            raise ValueError("customer_id is required to create a card on file")
        
        if not source_id or not source_id.strip():
            raise ValueError("source_id is required and cannot be blank")
        
        url = f"{get_square_base_url()}/v2/cards"
        headers = get_square_headers()
        
        # Generate idempotency key if not provided
        if not idempotency_key:
            import uuid
            idempotency_key = str(uuid.uuid4())
        
        # Square Cards API format
        # CRITICAL: customer_id MUST be provided to associate card with customer
        # According to Square API v2, the format is:
        # {
        #   "idempotency_key": "...",
        #   "source_id": "...",
        #   "card": {
        #     "customer_id": "..."
        #   }
        # }
        payload = {
            "idempotency_key": idempotency_key,
            "source_id": source_id,
            "card": {
                "customer_id": customer_id  # This associates the card with the customer
            }
        }
        
        logger.info(f"Creating card for customer {customer_id} via Square Cards API")
        logger.debug(f"Card creation payload: {payload}")
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code not in [200, 201]:
            error_text = response.text
            logger.error(f"Square Create Card API error: {response.status_code} - {error_text}")
            try:
                error_data = response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "card_id": None,
                    "http_status": response.status_code,
                    "errors": errors
                }
            except:
                return {
                    "success": False,
                    "error": error_text,
                    "card_id": None,
                    "http_status": response.status_code
                }
        
        data = response.json()
        
        if data.get("errors"):
            errors = data.get("errors", [])
            error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
            logger.error(f"Square API returned errors: {error_messages}")
            return {
                "success": False,
                "error": ', '.join(error_messages),
                "card_id": None,
                "errors": errors
            }
        
        if "card" in data:
            card = data["card"]
            card_id = card.get("id")
            # CRITICAL: Verify the card response includes customer_id to confirm it was associated
            card_customer_id = card.get("customer_id")
            
            logger.info(f"Card creation response - card_id: {card_id}, customer_id in response: {card_customer_id}, expected: {customer_id}")
            
            # Check if customer_id is missing or wrong
            if not card_customer_id:
                logger.error(f"❌ CRITICAL: Card {card_id} was created but has NO customer_id in response!")
                logger.error(f"   This means the card was NOT associated with customer {customer_id}")
                logger.error(f"   Full card response: {card}")
                return {
                    "success": False,
                    "error": f"Card created but not associated with customer. Card has no customer_id. Expected customer_id: {customer_id}",
                    "card_id": None,
                    "http_status": 200  # API call succeeded but card not associated
                }
            
            if card_customer_id != customer_id:
                logger.error(f"❌ CRITICAL: Card {card_id} was created for customer {card_customer_id}, but we requested customer {customer_id}!")
                return {
                    "success": False,
                    "error": f"Card created for wrong customer. Expected {customer_id}, got {card_customer_id}",
                    "card_id": None
                }
            
            logger.info(f"✅ Card {card_id} created and VERIFIED for customer {customer_id}")
            logger.info(f"   Card details: last_4={card.get('last_4')}, brand={card.get('card_brand')}, customer_id={card_customer_id}")
            return {
                "success": True,
                "card_id": card_id,
                "last_4": card.get("last_4"),
                "brand": card.get("card_brand"),
                "exp_month": card.get("exp_month"),
                "exp_year": card.get("exp_year"),
                "customer_id": card_customer_id,  # Include in response for verification
                "card": card
            }
        else:
            return {
                "success": False,
                "error": "No card data in response",
                "card_id": None
            }
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating card on file: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "card_id": None
                }
            except:
                return {
                    "success": False,
                    "error": e.response.text,
                    "card_id": None
                }
        return {
            "success": False,
            "error": str(e),
            "card_id": None
        }
    except Exception as e:
        logger.error(f"Error creating card on file: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "card_id": None
        }


def get_payment_status(transaction_id: str) -> Dict[str, Any]:
    """
    Get payment status from Square.
    
    Args:
        transaction_id: Square transaction ID
    
    Returns:
        Dict with payment status and details
    """
    try:
        url = f"{get_square_base_url()}/v2/payments/{transaction_id}"
        headers = get_square_headers()
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if "payment" in data:
            payment = data["payment"]
            return {
                "success": True,
                "status": payment.get("status"),
                "amount": payment.get("amount_money", {}).get("amount", 0) / 100,
                "currency": payment.get("amount_money", {}).get("currency", "USD")
            }
        else:
            errors = data.get("errors", [])
            error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
            logger.error(f"Square payment status check failed: {error_messages}")
            return {
                "success": False,
                "error": ', '.join(error_messages)
            }
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting payment status: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages)
                }
            except:
                return {
                    "success": False,
                    "error": e.response.text
                }
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        logger.error(f"Error getting payment status: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


def get_catalog_objects(types: Optional[List[str]] = None, cursor: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch catalog objects from Square Catalog API.
    
    Args:
        types: List of catalog object types to filter (e.g., ['ITEM', 'SUBSCRIPTION_PLAN', 'SUBSCRIPTION_PLAN_VARIATION'])
        cursor: Pagination cursor for next page
    
    Returns:
        Dict with catalog objects and pagination info
    """
    try:
        url = f"{get_square_base_url()}/v2/catalog/list"
        headers = get_square_headers()
        
        payload = {}
        if types:
            payload["object_types"] = types  # Square API uses "object_types" not "types"
        if cursor:
            payload["cursor"] = cursor
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        return {
            "success": True,
            "objects": data.get("objects", []),
            "cursor": data.get("cursor"),
            "errors": data.get("errors", [])
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching catalog objects: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "objects": [],
                    "cursor": None
                }
            except:
                return {
                    "success": False,
                    "error": e.response.text,
                    "objects": [],
                    "cursor": None
                }
        return {
            "success": False,
            "error": str(e),
            "objects": [],
            "cursor": None
        }
    except Exception as e:
        logger.error(f"Error fetching catalog objects: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "objects": [],
            "cursor": None
        }


def get_all_catalog_objects() -> Dict[str, Any]:
    """
    Fetch ALL catalog objects from Square (no filters).
    Useful for debugging to see what's actually in the catalog.
    """
    try:
        url = f"{get_square_base_url()}/v2/catalog/list"
        headers = get_square_headers()
        payload = {}  # No filters - get everything

        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"Square API error: {response.status_code} - {error_text}")
            try:
                error_data = response.json()
                return {
                    "success": False,
                    "error": error_data,
                    "objects": [],
                    "http_status": response.status_code
                }
            except:
                return {
                    "success": False,
                    "error": error_text,
                    "objects": [],
                    "http_status": response.status_code
                }
        
        data = response.json()
        
        # Group objects by type
        objects_by_type = {}
        for obj in data.get("objects", []):
            obj_type = obj.get("type")
            if obj_type:
                if obj_type not in objects_by_type:
                    objects_by_type[obj_type] = []
                objects_by_type[obj_type].append(obj)
        
        return {
            "success": True,
            "objects": data.get("objects", []),
            "objects_by_type": objects_by_type,
            "types_found": list(objects_by_type.keys()),
            "cursor": data.get("cursor"),
            "errors": data.get("errors", [])
        }
        
    except Exception as e:
        logger.error(f"Error fetching all catalog objects: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "objects": [],
            "objects_by_type": {},
            "types_found": []
        }


def get_subscription_plans() -> Dict[str, Any]:
    """
    Fetch all subscription plans from Square Catalog.
    Returns the raw Square API response with subscription plans and their variations.
    """
    try:
        # url = f"https://connect.squareup.com/v2/catalog/list"
        # headers = get_square_headers()

        # print(headers)
        # print(url)
        # print(payload)

        url = "https://connect.squareup.com/v2/catalog/list"
        headers = {
            "Square-Version": "2025-10-16",
            "Authorization": "Bearer EAAAl4Q9pRT9LMPrVJM2IM8ck6C0m6g9gG3jt02Nz5P8hsh8PdumSOFnSf8_44ym",
            "Content-Type": "application/json"
        }
        
        # Fetch both plans and variations
        # Note: Square Catalog API uses POST for list endpoint
        payload = {
            "object_types": ["SUBSCRIPTION_PLAN", "SUBSCRIPTION_PLAN_VARIATION"]
        }
        print(payload)
        print(headers)
        print(url)

        response = requests.get(url, headers=headers, timeout=10)
        print("--------------------------------")
        print(response)
        print("--------------------------------")
        
        # Check for errors before processing
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"Square API error: {response.status_code} - {error_text}")
            try:
                error_data = response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "plans": [],
                    "raw_objects": [],
                    "http_status": response.status_code
                }
            except:
                return {
                    "success": False,
                    "error": error_text,
                    "plans": [],
                    "raw_objects": [],
                    "http_status": response.status_code
                }
        
        data = response.json()
        
        # Check for API-level errors in response
        if data.get("errors"):
            errors = data.get("errors", [])
            error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
            logger.error(f"Square API returned errors: {error_messages}")
            return {
                "success": False,
                "error": ', '.join(error_messages),
                "plans": [],
                "raw_objects": [],
                "errors": errors
            }
        
        # Process and organize the data
        plans = []
        
        # First, collect standalone variations (if any exist as separate objects)
        variations_by_plan = {}  # plan_id -> list of variations
        for obj in data.get("objects", []):
            if "subscription_plan_variation_data" in obj:
                var_data = obj.get("subscription_plan_variation_data", {})
                var_id = obj.get("id")
                plan_id = var_data.get("subscription_plan_id")
                
                variation_info = {
                    "id": var_id,
                    "name": var_data.get("name"),
                    "phases": var_data.get("phases", []),
                    "subscription_plan_id": plan_id,
                    "item_id": var_data.get("item_id"),
                    "item_variation_id": var_data.get("item_variation_id")
                }
                
                # Group variations by plan
                if plan_id:
                    if plan_id not in variations_by_plan:
                        variations_by_plan[plan_id] = []
                    variations_by_plan[plan_id].append(variation_info)
        
        # Then, process subscription plans
        # Square returns variations nested inside subscription_plan_data.subscription_plan_variations
        for obj in data.get("objects", []):
            if "subscription_plan_data" in obj:
                plan_data = obj.get("subscription_plan_data", {})
                plan_id = obj.get("id")
                plan_variations = []
                
                # Get variations from nested structure (Square's actual format)
                # Variations are nested inside subscription_plan_variations array
                nested_variations = plan_data.get("subscription_plan_variations", [])
                
                # Process nested variations
                for nested_var in nested_variations:
                    if isinstance(nested_var, dict):
                        var_data = nested_var.get("subscription_plan_variation_data", {})
                        var_id = nested_var.get("id")
                        
                        variation_info = {
                            "id": var_id,
                            "name": var_data.get("name"),
                            "phases": var_data.get("phases", []),
                            "subscription_plan_id": var_data.get("subscription_plan_id", plan_id),
                            "item_id": var_data.get("item_id"),
                            "item_variation_id": var_data.get("item_variation_id")
                        }
                        plan_variations.append(variation_info)
                
                # Also check standalone variations for this plan (if any)
                if plan_id in variations_by_plan:
                    for var in variations_by_plan[plan_id]:
                        # Avoid duplicates
                        if var["id"] not in [v["id"] for v in plan_variations]:
                            plan_variations.append(var)
                
                plans.append({
                    "id": plan_id,
                    "name": plan_data.get("name"),
                    "variations": plan_variations,
                    "eligible_item_ids": plan_data.get("eligible_item_ids", []),
                    "all_items": plan_data.get("all_items", False)
                })
        
        return {
            "success": True,
            "plans": plans,
            "raw_objects": data.get("objects", []),  # Include raw objects for debugging
            "cursor": data.get("cursor"),
            "errors": data.get("errors", [])
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching subscription plans: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "plans": [],
                    "raw_objects": []
                }
            except:
                return {
                    "success": False,
                    "error": e.response.text,
                    "plans": [],
                    "raw_objects": []
                }
        return {
            "success": False,
            "error": str(e),
            "plans": [],
            "raw_objects": []
        }
    except Exception as e:
        logger.error(f"Error fetching subscription plans: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "plans": [],
            "raw_objects": []
        }


def get_square_locations() -> Dict[str, Any]:
    """
    Get all locations available to the authorized merchant.
    Returns list of locations with their IDs.
    """
    try:
        url = f"{get_square_base_url()}/v2/locations"
        headers = get_square_headers()
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            locations = data.get("locations", [])
            return {
                "success": True,
                "locations": locations,
                "location_ids": [loc.get("id") for loc in locations],
                "count": len(locations)
            }
        else:
            error_data = response.json() if response.content else {}
            errors = error_data.get("errors", [])
            return {
                "success": False,
                "error": ', '.join([e.get("detail", e.get("code", "Unknown error")) for e in errors]),
                "locations": [],
                "http_status": response.status_code,
                "errors": errors
            }
            
    except Exception as e:
        logger.error(f"Error getting Square locations: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "locations": []
        }


def test_square_connection() -> Dict[str, Any]:
    """
    Test if Square API connection is working by calling a simple endpoint.
    Returns connection status and any errors.
    """
    try:
        # Try to get locations - this is a simple endpoint that should work if auth is correct
        result = get_square_locations()
        
        if result.get("success"):
            return {
                "success": True,
                "message": "Square API connection successful",
                "locations_count": result.get("count", 0),
                "location_ids": result.get("location_ids", []),
                "environment": SQUARE_ENVIRONMENT
            }
        else:
            return {
                "success": False,
                "message": "Square API connection failed",
                "http_status": result.get("http_status", 500),
                "errors": result.get("errors", []),
                "error": result.get("error")
            }
            
    except Exception as e:
        logger.error(f"Error testing Square connection: {str(e)}")
        return {
            "success": False,
            "message": f"Connection test failed: {str(e)}",
            "error": str(e)
        }


def get_subscriptions(customer_id: Optional[str] = None, status: Optional[str] = None, cursor: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch active subscriptions from Square Subscriptions API.
    
    Args:
        customer_id: Optional customer ID to filter subscriptions
        status: Optional status filter (ACTIVE, CANCELED, etc.)
        cursor: Pagination cursor
    
    Returns:
        Dict with subscriptions data
    """
    try:
        url = f"{get_square_base_url()}/v2/subscriptions"
        headers = get_square_headers()
        
        # Build query parameters
        params = {}
        if customer_id:
            params["customer_id"] = customer_id
        if status:
            params["status"] = status
        if cursor:
            params["cursor"] = cursor
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"Square Subscriptions API error: {response.status_code} - {error_text}")
            try:
                error_data = response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "subscriptions": [],
                    "http_status": response.status_code
                }
            except:
                return {
                    "success": False,
                    "error": error_text,
                    "subscriptions": [],
                    "http_status": response.status_code
                }
        
        data = response.json()
        
        # Check for API-level errors
        errors = data.get("errors", [])
        
        subscriptions = []
        if "subscriptions" in data:
            subscriptions = data["subscriptions"]
            
        return {
            "success": True,
            "subscriptions": subscriptions,
            "cursor": data.get("cursor"),
            "count": len(subscriptions)
        }
    except Exception as e:
        logger.error(f"Error fetching subscriptions: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "subscriptions": []
        }


def get_customer_cards(customer_id: str) -> Dict[str, Any]:
    """
    Fetch all cards on file for a customer.
    """
    try:
        url = f"{get_square_base_url()}/v2/cards"
        headers = get_square_headers()
        params = {"customer_id": customer_id}
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return {
                "success": False,
                "error": response.text,
                "cards": []
            }
            
        data = response.json()
        return {
            "success": True,
            "cards": data.get("cards", [])
        }
    except Exception as e:
        logger.error(f"Error fetching customer cards: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "cards": []
        }


def get_customer_details(customer_id: str) -> Dict[str, Any]:
    """
    Fetch customer details including attached cards and active subscription plan.
    
    Args:
        customer_id: Square customer ID
        
    Returns:
        Dict with keys:
        - is_card_attached: bool
        - card_details: Dict (if attached)
        - subscription_plan: Dict (if active)
        - subscription_status: str
    """
    try:
        # 1. Fetch Cards
        cards_result = get_customer_cards(customer_id)
        cards = cards_result.get("cards", [])
        is_card_attached = len(cards) > 0
        card_details = cards[0] if is_card_attached else None
        
        # 2. Fetch Subscriptions
        # We want active subscriptions usually
        subs_result = get_subscriptions(customer_id=customer_id)
        subscriptions = subs_result.get("subscriptions", [])
        
        # Determine primary/latest active subscription
        # Sort by start_date desc to get latest? Or just take the first active one.
        active_sub = None
        sub_status = "NONE"
        
        active_subs = [s for s in subscriptions if s.get("status") == "ACTIVE"]
        
        if active_subs:
            active_sub = active_subs[0]
            sub_status = "ACTIVE"
        elif subscriptions:
            # If no active, maybe take the most recent one pending or canceled
            active_sub = subscriptions[0] 
            sub_status = active_sub.get("status")
            
        return {
            "success": True,
            "customer_id": customer_id,
            "is_card_attached": is_card_attached,
            "card_details": {
                "id": card_details.get("id"),
                "brand": card_details.get("card_brand"),
                "last_4": card_details.get("last_4"),
                "exp_month": card_details.get("exp_month"),
                "exp_year": card_details.get("exp_year")
            } if card_details else None,
            "subscription_plan": {
                "id": active_sub.get("id"),
                "plan_id": active_sub.get("plan_id"),
                "start_date": active_sub.get("start_date"),
                "charged_through_date": active_sub.get("charged_through_date")
            } if active_sub else None,
            "subscription_status": sub_status
        }
        
    except Exception as e:
        logger.error(f"Error getting customer details: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

        
        subscriptions = data.get("subscriptions", [])
        
        return {
            "success": True,
            "subscriptions": subscriptions,
            "cursor": data.get("cursor"),
            "errors": data.get("errors", [])
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching subscriptions: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "subscriptions": [],
                    "http_status": e.response.status_code
                }
            except:
                return {
                    "success": False,
                    "error": e.response.text,
                    "subscriptions": [],
                    "http_status": e.response.status_code
                }
        return {
            "success": False,
            "error": str(e),
            "subscriptions": []
        }
    except Exception as e:
        logger.error(f"Error fetching subscriptions: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "subscriptions": []
        }


def create_square_customer(
    given_name: str,
    family_name: str,
    email: str,
    phone_number: Optional[str] = None,
    address: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a customer in Square.
    
    Args:
        given_name: Customer's first name
        family_name: Customer's last name
        email: Customer's email address
        phone_number: Optional phone number
        address: Optional address dict
    
    Returns:
        Dict with customer data including customer_id
    """
    try:
        url = f"{get_square_base_url()}/v2/customers"
        headers = get_square_headers()
        
        payload = {
            "given_name": given_name,
            "family_name": family_name,
            "email_address": email
        }
        
        if phone_number:
            payload["phone_number"] = phone_number
        
        if address:
            payload["address"] = address
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code not in [200, 201]:
            error_text = response.text
            logger.error(f"Square Create Customer API error: {response.status_code} - {error_text}")
            try:
                error_data = response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "customer": None,
                    "http_status": response.status_code
                }
            except:
                return {
                    "success": False,
                    "error": error_text,
                    "customer": None,
                    "http_status": response.status_code
                }
        
        data = response.json()
        
        if data.get("errors"):
            errors = data.get("errors", [])
            error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
            return {
                "success": False,
                "error": ', '.join(error_messages),
                "customer": None,
                "errors": errors
            }
        
        customer = data.get("customer", {})
        
        return {
            "success": True,
            "customer": customer,
            "customer_id": customer.get("id"),
            "errors": data.get("errors", [])
        }
        
    except Exception as e:
        logger.error(f"Error creating Square customer: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "customer": None
        }


def get_square_customer_by_id(customer_id: str) -> Dict[str, Any]:
    """
    Get a Square customer by customer ID.
    
    Args:
        customer_id: Square customer ID
    
    Returns:
        Dict with customer data if found
    """
    try:
        url = f"{get_square_base_url()}/v2/customers/{customer_id}"
        headers = get_square_headers()
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            customer = data.get("customer", {})
            if customer:
                return {
                    "success": True,
                    "customer": customer,
                    "customer_id": customer.get("id")
                }
            return {
                "success": False,
                "error": "Customer not found",
                "customer": None
            }
        else:
            error_text = response.text
            logger.error(f"Square Get Customer API error: {response.status_code} - {error_text}")
            try:
                error_data = response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "customer": None,
                    "http_status": response.status_code
                }
            except:
                return {
                    "success": False,
                    "error": error_text,
                    "customer": None,
                    "http_status": response.status_code
                }
            
    except Exception as e:
        logger.error(f"Error getting Square customer: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "customer": None
        }


def get_square_customer_by_email(email: str) -> Dict[str, Any]:
    """
    Search for a Square customer by email.
    
    Args:
        email: Customer email address
    
    Returns:
        Dict with customer data if found
    """
    try:
        url = f"{get_square_base_url()}/v2/customers/search"
        headers = get_square_headers()
        
        payload = {
            "query": {
                "filter": {
                    "email_address": {
                        "exact": email
                    }
                }
            }
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            customers = data.get("customers", [])
            if customers:
                return {
                    "success": True,
                    "customer": customers[0],
                    "customer_id": customers[0].get("id")
                }
            return {
                "success": False,
                "error": "Customer not found",
                "customer": None
            }
        else:
            error_text = response.text
            logger.error(f"Square Search Customer API error: {response.status_code} - {error_text}")
            return {
                "success": False,
                "error": error_text,
                "customer": None,
                "http_status": response.status_code
            }
            
    except Exception as e:
        logger.error(f"Error searching Square customer: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "customer": None
        }


def get_customer_cards(customer_id: str) -> Dict[str, Any]:
    """
    Get all cards associated with a Square customer.
    Uses the Search API to find cards by customer ID.
    
    Args:
        customer_id: Square customer ID
    
    Returns:
        Dict with list of cards
    """
    try:
        # Try the newer Cards Search API first
        url = f"{get_square_base_url()}/v2/cards/search"
        headers = get_square_headers()
        
        # Square Cards Search API format
        payload = {
            "query": {
                "filter": {
                    "customer_id": {
                        "exact": customer_id
                    }
                }
            }
        }
        
        logger.info(f"Searching for cards for customer {customer_id}")
        logger.debug(f"Cards search payload: {payload}")
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code not in [200, 201]:
            error_text = response.text
            logger.error(f"Square Get Customer Cards API error: {response.status_code} - {error_text}")
            try:
                error_data = response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "cards": [],
                    "http_status": response.status_code
                }
            except:
                return {
                    "success": False,
                    "error": error_text,
                    "cards": [],
                    "http_status": response.status_code
                }
        
        data = response.json()
        
        if data.get("errors"):
            errors = data.get("errors", [])
            error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
            return {
                "success": False,
                "error": ', '.join(error_messages),
                "cards": [],
                "errors": errors
            }
        
        # Cards Search API returns cards in the response
        cards = data.get("cards", [])
        
        return {
            "success": True,
            "cards": cards,
            "count": len(cards),
            "errors": data.get("errors", [])
        }
        
    except Exception as e:
        logger.error(f"Error getting customer cards: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "cards": []
        }


def update_square_customer(
    customer_id: str,
    given_name: Optional[str] = None,
    family_name: Optional[str] = None,
    email: Optional[str] = None,
    phone_number: Optional[str] = None,
    address: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Update a customer in Square.
    
    Args:
        customer_id: Square customer ID to update
        given_name: Customer's first name
        family_name: Customer's last name
        email: Customer's email address
        phone_number: Optional phone number
        address: Optional address dict
    
    Returns:
        Dict with updated customer data
    """
    try:
        url = f"{get_square_base_url()}/v2/customers/{customer_id}"
        headers = get_square_headers()
        
        payload = {}
        
        if given_name is not None:
            payload["given_name"] = given_name
        if family_name is not None:
            payload["family_name"] = family_name
        if email is not None:
            payload["email_address"] = email
        if phone_number is not None:
            payload["phone_number"] = phone_number
        if address is not None:
            payload["address"] = address
        
        response = requests.put(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code not in [200, 201]:
            error_text = response.text
            logger.error(f"Square Update Customer API error: {response.status_code} - {error_text}")
            try:
                error_data = response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "customer": None,
                    "http_status": response.status_code
                }
            except:
                return {
                    "success": False,
                    "error": error_text,
                    "customer": None,
                    "http_status": response.status_code
                }
        
        data = response.json()
        
        if data.get("errors"):
            errors = data.get("errors", [])
            error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
            return {
                "success": False,
                "error": ', '.join(error_messages),
                "customer": None,
                "errors": errors
            }
        
        customer = data.get("customer", {})
        
        return {
            "success": True,
            "customer": customer,
            "customer_id": customer.get("id"),
            "errors": data.get("errors", [])
        }
        
    except Exception as e:
        logger.error(f"Error updating Square customer: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "customer": None
        }


def create_subscription(
    customer_id: str,
    location_id: str,
    plan_variation_id: str,
    source_id: Optional[str] = None,
    card_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    start_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a subscription using Square Subscriptions API.
    
    Args:
        customer_id: Square customer ID
        location_id: Square location ID
        plan_variation_id: Subscription plan variation ID from catalog
        source_id: Payment token from Square Web Payments SDK (for new card)
        card_id: Square card ID (for saved card)
        idempotency_key: Optional unique key to prevent duplicate creation
        start_date: Optional start date in YYYY-MM-DD format (defaults to immediate)
    
    Returns:
        Dict with created subscription data
    """
    try:
        url = f"{get_square_base_url()}/v2/subscriptions"
        headers = get_square_headers()
        
        # Generate idempotency key if not provided
        if not idempotency_key:
            import uuid
            idempotency_key = str(uuid.uuid4())
        
        # Determine card_id to use
        final_card_id = card_id
        
        # If no card_id provided but we have source_id, we need to create a card first
        # Square Subscriptions API requires a card_id on the customer profile
        if not final_card_id and source_id:
            logger.info("Creating card from source_id for subscription")
            card_res = create_card_on_file(source_id, customer_id)
            if card_res.get("success"):
                final_card_id = card_res.get("card_id")
            else:
                return {
                    "success": False,
                    "error": f"Failed to create card for subscription: {card_res.get('error')}",
                    "subscription": None,
                    "http_status": card_res.get("http_status", 500) # Added http_status for consistency
                }
        
        if not final_card_id:
            return {
                "success": False,
                "error": "No card_id provided and could not create one from source_id",
                "subscription": None
            }
            
        payload = {
            "idempotency_key": idempotency_key,
            "location_id": location_id,
            "plan_variation_id": plan_variation_id,
            "customer_id": customer_id,
            "card_id": final_card_id
        }
        
        if start_date:
            payload["start_date"] = start_date
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            # check for errors
            if data.get("errors"):
                errors = data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "subscription": None,
                    "errors": errors
                }
                
            subscription = data.get("subscription", {})
            return {
                "success": True,
                "subscription": subscription,
                "subscription_id": subscription.get("id"),
                "status": subscription.get("status"),
                "errors": []
            }
        else:
            error_text = response.text
            logger.error(f"Square API error (create_subscription): {response.status_code} - {error_text}")
            try:
                error_data = response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "subscription": None,
                    "http_status": response.status_code,
                    "errors": errors
                }
            except:
                return {
                    "success": False,
                    "error": error_text,
                    "subscription": None,
                    "http_status": response.status_code
                }
        
    except ValueError as e:
        logger.error(f"Validation error creating subscription: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "subscription": None
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Request exception creating subscription: {str(e)}")
        return {
            "success": False,
            "error": "Failed to connect to Square API",
            "subscription": None
        }

def search_subscriptions(customer_ids: list[str]) -> dict[str, Any]:
    """
    Search for subscriptions by customer IDs.
    
    Args:
        customer_ids: List of Square customer IDs to filter by
        
    Returns:
        Dict with search results including subscriptions list
    """
    try:
        url = f"{get_square_base_url()}/v2/subscriptions/search"
        headers = get_square_headers()
        
        payload = {
            "query": {
                "filter": {
                    "customer_ids": customer_ids
                }
            }
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "subscriptions": data.get("subscriptions", []),
                "errors": []
            }
        else:
            logger.error(f"Square API error (search_subscriptions): {response.status_code} - {response.text}")
            return {
                "success": False,
                "error": f"Square API Error: {response.status_code}",
                "subscriptions": [],
                "http_status": response.status_code
            }
            
    except Exception as e:
        logger.error(f"Error searching subscriptions: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "subscriptions": []
        }
        logger.error(f"Error creating subscription: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "subscription": None,
                    "http_status": e.response.status_code
                }
            except:
                return {
                    "success": False,
                    "error": e.response.text,
                    "subscription": None,
                    "http_status": e.response.status_code
                }
        return {
            "success": False,
            "error": str(e),
            "subscription": None
        }
    except Exception as e:
        logger.error(f"Error creating subscription: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "subscription": None
        }


def create_subscription_plan(
    name: str,
    phases: List[Dict[str, Any]],
    location_id: Optional[str] = None,
    idempotency_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a subscription plan in Square Catalog.
    
    Args:
        name: Name of the subscription plan
        phases: List of subscription phases (billing periods)
        location_id: Square location ID (uses env var if not provided)
        idempotency_key: Unique key to prevent duplicates
    
    Returns:
        Dict with created subscription plan data
    
    Example phases:
    [
        {
            "cadence": "MONTHLY",
            "periods": 1,
            "recurring_price_money": {
                "amount": 9900,  # $99.00 in cents
                "currency": "USD"
            }
        }
    ]
    """
    try:
        url = f"{get_square_base_url()}/v2/catalog/object"
        headers = get_square_headers()
        
        # Use location_id from parameter or environment
        loc_id = location_id or SQUARE_LOCATION_ID
        
        # Generate idempotency key if not provided
        if not idempotency_key:
            import uuid
            idempotency_key = str(uuid.uuid4())
        
        # Build subscription plan object
        # Square requires an id field for catalog objects (can be a temporary ID)
        import uuid
        temp_id = f"#temp-{uuid.uuid4().hex[:8]}"
        
        # Ensure phases have all required fields
        formatted_phases = []
        for i, phase in enumerate(phases):
            # Validate required fields
            if "cadence" not in phase:
                raise ValueError(f"Phase {i} is missing required field 'cadence'")
            
            if "recurring_price_money" not in phase:
                raise ValueError(f"Phase {i} is missing required field 'recurring_price_money'")
            
            formatted_phase = {
                "ordinal": phase.get("ordinal", i),  # Required: order of phase
                "cadence": phase["cadence"],  # Required: MONTHLY, YEARLY, etc.
                "recurring_price_money": phase["recurring_price_money"]  # Required
            }
            
            # Add periods if provided (null means indefinite)
            if "periods" in phase:
                formatted_phase["periods"] = phase["periods"]
            
            # Add other optional fields
            if "order_template_id" in phase:
                formatted_phase["order_template_id"] = phase["order_template_id"]
            
            formatted_phases.append(formatted_phase)
        
        # Validate we have at least one phase
        if not formatted_phases:
            raise ValueError("At least one phase is required")
        
        # Step 1: Create the subscription plan (without phases - phases go in variations)
        plan_payload = {
            "idempotency_key": idempotency_key,
            "object": {
                "type": "SUBSCRIPTION_PLAN",
                "id": temp_id,  # Required: temporary ID for new object
                "subscription_plan_data": {
                    "name": name  # Required
                }
            }
        }
        
        response = requests.post(url, json=plan_payload, headers=headers, timeout=10)
        
        if response.status_code not in [200, 201]:
            error_text = response.text
            logger.error(f"Square Create Subscription Plan API error: {response.status_code} - {error_text}")
            try:
                error_data = response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "subscription_plan": None,
                    "http_status": response.status_code,
                    "errors": errors
                }
            except:
                return {
                    "success": False,
                    "error": error_text,
                    "subscription_plan": None,
                    "http_status": response.status_code
                }
        
        data = response.json()
        
        # Check for API-level errors
        if data.get("errors"):
            errors = data.get("errors", [])
            error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
            logger.error(f"Square API returned errors: {error_messages}")
            return {
                "success": False,
                "error": ', '.join(error_messages),
                "subscription_plan": None,
                "errors": errors
            }
        
        catalog_object = data.get("catalog_object", {})
        plan_id = catalog_object.get("id")
        
        # Step 2: Create a subscription plan variation with the phases
        # The phases belong in the variation, not the plan
        variation_temp_id = f"#temp-var-{uuid.uuid4().hex[:8]}"
        variation_payload = {
            "idempotency_key": f"{idempotency_key}-variation",
            "object": {
                "type": "SUBSCRIPTION_PLAN_VARIATION",
                "id": variation_temp_id,
                "subscription_plan_variation_data": {
                    "name": f"{name} - Variation",  # Variation name
                    "subscription_plan_id": plan_id,  # Link to the plan we just created
                    "phases": formatted_phases  # Phases go in the variation
                }
            }
        }
        
        # Create the variation
        var_response = requests.post(url, json=variation_payload, headers=headers, timeout=10)
        
        variation_data = None
        if var_response.status_code in [200, 201]:
            variation_data = var_response.json().get("catalog_object", {})
        else:
            logger.warning(f"Failed to create variation: {var_response.text}")
            # Plan was created but variation failed - return plan anyway
        
        return {
            "success": True,
            "subscription_plan": catalog_object,
            "plan_id": plan_id,
            "variation": variation_data,
            "variation_id": variation_data.get("id") if variation_data else None,
            "errors": data.get("errors", [])
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating subscription plan: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "subscription_plan": None,
                    "http_status": e.response.status_code
                }
            except:
                return {
                    "success": False,
                    "error": e.response.text,
                    "subscription_plan": None,
                    "http_status": e.response.status_code
                }
        return {
            "success": False,
            "error": str(e),
            "subscription_plan": None
        }
    except Exception as e:
        logger.error(f"Error creating subscription plan: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "subscription_plan": None
        }


def get_catalog_items() -> Dict[str, Any]:
    """
    Fetch all items from Square Catalog.
    
    Returns:
        Dict with catalog items
    """
    try:
        result = get_catalog_objects(types=["ITEM", "ITEM_VARIATION"])
        
        if not result.get("success"):
            return result
        
        items = []
        item_variations = []
        
        # Separate items and variations
        for obj in result.get("objects", []):
            if "item_data" in obj:
                item_data = obj.get("item_data", {})
                items.append({
                    "id": obj.get("id"),
                    "name": item_data.get("name"),
                    "description": item_data.get("description"),
                    "category_id": item_data.get("category_id"),
                    "variations": item_data.get("variations", []),
                    "product_type": item_data.get("product_type"),
                    "tax_ids": item_data.get("tax_ids", [])
                })
            elif "item_variation_data" in obj:
                var_data = obj.get("item_variation_data", {})
                item_variations.append({
                    "id": obj.get("id"),
                    "item_id": var_data.get("item_id"),
                    "name": var_data.get("name"),
                    "pricing_type": var_data.get("pricing_type"),
                    "price_money": var_data.get("price_money"),
                    "sku": var_data.get("sku")
                })
        
        return {
            "success": True,
            "items": items,
            "item_variations": item_variations,
            "cursor": result.get("cursor")
        }
        
    except Exception as e:
        logger.error(f"Error fetching catalog items: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "items": [],
            "item_variations": []
        }


def cancel_subscription(subscription_id: str) -> Dict[str, Any]:
    """
    Cancel a subscription in Square.
    """
    try:
        url = f"{get_square_base_url()}/v2/subscriptions/{subscription_id}/cancel"
        headers = get_square_headers()
        
        response = requests.post(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"Square Cancel Subscription API error: {response.status_code} - {error_text}")
            try:
                error_data = response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "http_status": response.status_code
                }
            except:
                return {
                    "success": False,
                    "error": error_text,
                    "http_status": response.status_code
                }
        
        data = response.json()
        
        if "subscription" in data:
            subscription = data["subscription"]
            return {
                "success": True,
                "subscription": subscription,
                "status": subscription.get("status")
            }
        else:
            errors = data.get("errors", [])
            error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
            return {
                "success": False,
                "error": ', '.join(error_messages)
            }
            
    except Exception as e:
        logger.error(f"Error canceling subscription: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


def update_subscription(subscription_id: str, plan_variation_id: str) -> Dict[str, Any]:
    """
    Swap subscription plan using Square's swap plan action.
    This is the correct way to change a subscription plan in Square.
    """
    try:
        # Use Square's swap plan action endpoint
        url = f"{get_square_base_url()}/v2/subscriptions/{subscription_id}/swap-plan"
        headers = get_square_headers()
        
        payload = {
            "new_plan_variation_id": plan_variation_id
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"Square Swap Plan API error: {response.status_code} - {error_text}")
            try:
                error_data = response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "http_status": response.status_code
                }
            except:
                return {
                    "success": False,
                    "error": error_text,
                    "http_status": response.status_code
                }
        
        data = response.json()
        
        if "subscription" in data:
            subscription = data["subscription"]
            logger.info(f"Successfully swapped subscription {subscription_id} to plan {plan_variation_id}")
            return {
                "success": True,
                "subscription": subscription,
                "status": subscription.get("status"),
                "new_plan_variation_id": plan_variation_id
            }
        else:
            errors = data.get("errors", [])
            error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
            return {
                "success": False,
                "error": ', '.join(error_messages)
            }
            
    except Exception as e:
        logger.error(f"Error swapping subscription plan: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


def pause_subscription(subscription_id: str) -> Dict[str, Any]:
    """
    Pause a subscription in Square.
    """
    try:
        url = f"{get_square_base_url()}/v2/subscriptions/{subscription_id}/pause"
        headers = get_square_headers()
        
        response = requests.post(url, json={}, headers=headers, timeout=10)
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"Square Pause Subscription API error: {response.status_code} - {error_text}")
            try:
                error_data = response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "http_status": response.status_code
                }
            except:
                return {
                    "success": False,
                    "error": error_text,
                    "http_status": response.status_code
                }
        
        data = response.json()
        
        if "subscription" in data:
            subscription = data["subscription"]
            return {
                "success": True,
                "subscription": subscription,
                "status": subscription.get("status")
            }
        else:
             return {
                "success": False,
                "error": "Unknown error"
            }
            
    except Exception as e:
        logger.error(f"Error pausing subscription: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


def resume_subscription(subscription_id: str, resume_effective_date: Optional[str] = None, resume_change_timing: Optional[str] = None) -> Dict[str, Any]:
    """
    Resume a paused subscription in Square.
    
    Args:
        subscription_id: ID of subscription to resume
        resume_effective_date: Optional specific date to resume (YYYY-MM-DD). 
        resume_change_timing: Optional timing for resume (e.g., "IMMEDIATE").
                              Use "IMMEDIATE" to cancel a scheduled pause.
    """
    try:
        url = f"{get_square_base_url()}/v2/subscriptions/{subscription_id}/resume"
        headers = get_square_headers()
        
        payload = {}
        if resume_effective_date:
            payload["resume_effective_date"] = resume_effective_date
            
        if resume_change_timing:
            payload["resume_change_timing"] = resume_change_timing
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"Square Resume Subscription API error: {response.status_code} - {error_text}")
            try:
                error_data = response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "http_status": response.status_code
                }
            except:
                return {
                    "success": False,
                    "error": error_text,
                    "http_status": response.status_code
                }
        
        data = response.json()
        
        if "subscription" in data:
            subscription = data["subscription"]
            return {
                "success": True,
                "subscription": subscription,
                "status": subscription.get("status")
            }
        else:
             return {
                "success": False,
                "error": "Unknown error"
            }
            
    except Exception as e:
        logger.error(f"Error resuming subscription: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


def retrieve_subscription(subscription_id: str) -> Dict[str, Any]:
    """
    Retrieve a single subscription by ID.
    """
    try:
        url = f"{get_square_base_url()}/v2/subscriptions/{subscription_id}"
        headers = get_square_headers()
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "subscription": data.get("subscription", {}),
                "errors": []
            }
        else:
            error_text = response.text
            return {
                "success": False,
                "error": f"Square API Error: {response.status_code}",
                "http_status": response.status_code,
                "details": error_text
            }
            
    except Exception as e:
        logger.error(f"Error retrieving subscription: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


def update_subscription(subscription_id: str, plan_variation_id: str = None, card_id: str = None) -> Dict[str, Any]:
    """
    Update a subscription (e.g. change plan or card).
    """
    try:
        url = f"{get_square_base_url()}/v2/subscriptions/{subscription_id}"
        headers = get_square_headers()
        
        subscription_obj = {}
        if plan_variation_id:
            subscription_obj["plan_variation_id"] = plan_variation_id
        if card_id:
            subscription_obj["card_id"] = card_id
            
        payload = {
            "subscription": subscription_obj
        }
        
        response = requests.put(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "subscription": data.get("subscription", {}),
                "status": data.get("subscription", {}).get("status")
            }
        else:
            error_text = response.text
            logger.error(f"Square Update Subscription API error: {response.status_code} - {error_text}")
            return {
                "success": False,
                "error": f"Square API Error: {response.status_code}",
                "details": error_text
            }
            
    except Exception as e:
        logger.error(f"Error updating subscription: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def get_customer_invoices(customer_id: str, location_id: Optional[str] = None, limit: Optional[int] = None, cursor: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch invoices for a specific customer from Square API.
    
    Args:
        customer_id: Square customer ID
        location_id: Square location ID (optional, defaults to env var)
        limit: Max number of results
        cursor: Pagination cursor
    
    Returns:
        Dict with invoices data
    """
    try:
        url = f"{get_square_base_url()}/v2/invoices/search"
        headers = get_square_headers()
        
        loc_id = location_id or SQUARE_LOCATION_ID
        
        # Build search query
        payload = {
            "query": {
                "filter": {
                    "customer_ids": [customer_id]
                },
                "sort": {
                    "field": "INVOICE_SORT_DATE",
                    "order": "DESC"
                }
            }
        }
        
        if loc_id:
             payload["query"]["filter"]["location_ids"] = [loc_id]
             
        if limit:
            payload["limit"] = limit
        if cursor:
            payload["cursor"] = cursor
            
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"Square Invoices API error: {response.status_code} - {error_text}")
            try:
                error_data = response.json()
                errors = error_data.get("errors", [])
                error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
                return {
                    "success": False,
                    "error": ', '.join(error_messages),
                    "invoices": [],
                    "http_status": response.status_code
                }
            except:
                return {
                    "success": False,
                    "error": error_text,
                    "invoices": [],
                    "http_status": response.status_code
                }
        
        data = response.json()
        return {
            "success": True,
            "invoices": data.get("invoices", []),
            "cursor": data.get("cursor"),
            "errors": data.get("errors", [])
        }
            
    except Exception as e:
        logger.error(f"Error fetching invoices: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "invoices": []
        }
