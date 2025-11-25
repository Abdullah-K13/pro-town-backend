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
        payload = {
            "idempotency_key": idempotency_key,
            "source_id": source_id,
            "card": {
                "customer_id": customer_id
            }
        }
        
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
            return {
                "success": True,
                "card_id": card.get("id"),
                "last_4": card.get("last_4"),
                "brand": card.get("card_brand"),
                "exp_month": card.get("exp_month"),
                "exp_year": card.get("exp_year"),
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


def test_square_connection() -> Dict[str, Any]:
    """
    Test if Square API connection is working by calling a simple endpoint.
    Returns connection status and any errors.
    """
    try:
        # Try to get locations - this is a simple endpoint that should work if auth is correct
        url = f"{get_square_base_url()}/v2/locations"
        headers = get_square_headers()
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            locations = data.get("locations", [])
            return {
                "success": True,
                "message": "Square API connection successful",
                "locations_count": len(locations),
                "location_ids": [loc.get("id") for loc in locations],
                "environment": SQUARE_ENVIRONMENT
            }
        else:
            error_data = response.json() if response.content else {}
            errors = error_data.get("errors", [])
            return {
                "success": False,
                "message": "Square API connection failed",
                "http_status": response.status_code,
                "errors": errors
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
        if data.get("errors"):
            errors = data.get("errors", [])
            error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
            logger.error(f"Square API returned errors: {error_messages}")
            return {
                "success": False,
                "error": ', '.join(error_messages),
                "subscriptions": [],
                "errors": errors
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


def update_square_customer(
    customer_id: str,
    given_name: Optional[str] = None,
    family_name: Optional[str] = None,
    email: Optional[str] = None,
    phone_number: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update an existing Square customer.
    
    Args:
        customer_id: Square customer ID
        given_name: Customer's first name
        family_name: Customer's last name
        email: Customer's email address
        phone_number: Optional phone number
    
    Returns:
        Dict with updated customer data
    """
    try:
        url = f"{get_square_base_url()}/v2/customers/{customer_id}"
        headers = get_square_headers()
        
        payload = {}
        if given_name:
            payload["given_name"] = given_name
        if family_name:
            payload["family_name"] = family_name
        if email:
            payload["email_address"] = email
        if phone_number:
            payload["phone_number"] = phone_number
            
        if not payload:
            return {"success": True, "message": "No updates provided"}
        
        response = requests.put(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code != 200:
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
            "errors": []
        }
        
    except Exception as e:
        logger.error(f"Error updating Square customer: {str(e)}")
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


def create_subscription(
    customer_id: str,
    location_id: str,
    plan_variation_id: str,
    source_id: Optional[str] = None,
    card_id: Optional[str] = None,
    idempotency_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a subscription using Square Subscriptions API.
    
    Args:
        customer_id: Square customer ID
        location_id: Square location ID
        plan_variation_id: Subscription plan variation ID from catalog
        source_id: Payment token from Square Web Payments SDK (for new card)
        card_id: Square card ID (for saved card)
        idempotency_key: Unique key to prevent duplicate subscriptions
    
    Returns:
        Dict with subscription data
    
    Note: Either source_id OR card_id must be provided, not both.
    """
    try:
        if not source_id and not card_id:
            raise ValueError("Either source_id or card_id must be provided")
        
        if source_id and card_id:
            raise ValueError("Provide either source_id OR card_id, not both")
        
        url = f"{get_square_base_url()}/v2/subscriptions"
        headers = get_square_headers()
        
        # Generate idempotency key if not provided
        if not idempotency_key:
            import uuid
            idempotency_key = str(uuid.uuid4())
        
        # If source_id is provided, we need to create a card on file first
        # Square Subscriptions API only accepts card_id, not source_id directly
        if source_id and not card_id:
            # Create card on file first
            card_result = create_card_on_file(source_id=source_id, customer_id=customer_id)
            if not card_result.get("success"):
                return {
                    "success": False,
                    "error": f"Failed to create card on file: {card_result.get('error')}",
                    "subscription": None,
                    "http_status": card_result.get("http_status", 500)
                }
            card_id = card_result.get("card_id")
        
        # Build subscription request according to Square API format
        # Square Subscriptions API only accepts card_id, not source_id
        if not card_id:
            raise ValueError("card_id is required. If you provided source_id, card creation may have failed.")
        
        payload = {
            "idempotency_key": idempotency_key,
            "location_id": location_id,
            "plan_variation_id": plan_variation_id,
            "customer_id": customer_id,
            "card_id": card_id
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code not in [200, 201]:
            error_text = response.text
            logger.error(f"Square Create Subscription API error: {response.status_code} - {error_text}")
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
        
        data = response.json()
        
        # Check for API-level errors
        if data.get("errors"):
            errors = data.get("errors", [])
            error_messages = [error.get("detail", error.get("code", "Unknown error")) for error in errors]
            logger.error(f"Square API returned errors: {error_messages}")
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
            "errors": data.get("errors", [])
        }
        
    except ValueError as e:
        logger.error(f"Validation error creating subscription: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "subscription": None
        }
    except requests.exceptions.RequestException as e:
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

