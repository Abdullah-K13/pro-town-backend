# Payment Endpoints Documentation

This document outlines all endpoints available in `routers/payment.py` and their functionality.

## Table of Contents
- [Public Endpoints](#public-endpoints-no-authentication-required)
- [Protected Endpoints](#protected-endpoints-professional-role-required)
- [Request/Response Models](#requestresponse-models)

---

## Public Endpoints (No Authentication Required)

### `GET /payments/square-config`
**Purpose**: Provide Square Application ID and Location ID to the frontend for Square Web Payments SDK initialization.

**Returns**:
```json
{
  "application_id": "sandbox-sq0idb-...",
  "location_id": "L...XXXX"
}
```

**Notes**: These values are safe to expose publicly and are required for frontend Square SDK initialization.

---

### `GET /payments/subscription-plans`
**Purpose**: Fetch all subscription plans from Square Catalog.

**Returns**:
```json
{
  "success": true,
  "plans": [...],
  "cursor": "...",
  "errors": [],
  "raw_objects": [...]
}
```

**Error Handling**: Returns helpful message if no plans exist (404 is handled gracefully).

---

### `GET /payments/subscriptions`
**Purpose**: Fetch active subscription instances from Square Subscriptions API.

**Query Parameters**:
- `customer_id` (optional): Filter by Square customer ID
- `status` (optional): Filter by status (ACTIVE, CANCELED, etc.)
- `cursor` (optional): Pagination cursor

**Returns**:
```json
{
  "success": true,
  "subscriptions": [...],
  "count": 1,
  "cursor": "...",
  "errors": []
}
```

**Notes**: 
- Returns 404 with helpful message if no subscriptions exist (this is normal for new accounts)
- This endpoint returns subscription **instances**, not subscription **plans**

---

### `GET /payments/catalog/debug`
**Purpose**: Debug endpoint to see ALL catalog objects in Square. Useful for troubleshooting.

**Returns**:
```json
{
  "success": true,
  "total_objects": 10,
  "types_found": ["ITEM", "SUBSCRIPTION_PLAN"],
  "objects_by_type": {...},
  "sample_objects": {...},
  "all_objects": [...]
}
```

---

### `GET /payments/catalog/items`
**Purpose**: Fetch catalog items from Square.

**Query Parameters**:
- `types` (optional): Comma-separated list of types (e.g., "ITEM,ITEM_VARIATION")
- `cursor` (optional): Pagination cursor

**Returns**:
```json
{
  "success": true,
  "objects": [...],
  "cursor": "...",
  "count": 5
}
```

---

### `GET /payments/catalog/items-formatted`
**Purpose**: Fetch catalog items in a formatted, easy-to-use structure with items grouped with their variations.

**Returns**:
```json
{
  "success": true,
  "items": [...],
  "item_variations": [...],
  "count": 5
}
```

---

### `POST /payments/process-application`
**Purpose**: Process payment for new user application (no authentication required). Used when a new professional is applying and needs to pay before their account is fully created.

**Request Body**:
```json
{
  "source_id": "cnon:card-token-from-square",
  "amount": 9900,
  "subscription_plan_id": 1,
  "professional_id": 123,
  "email": "user@example.com"
}
```

**Returns**:
```json
{
  "success": true,
  "transaction_id": "...",
  "payment_id": 456,
  "message": "Payment processed successfully",
  "professional_id": 123,
  "subscription_activated": true
}
```

**Notes**: 
- If `professional_id` or `email` is not provided, payment is created without professional association
- Payment can be linked to professional later when account is created
- Validates amount matches subscription cost (if subscription_plan_id provided)

---

### `GET /payments/test-connection`
**Purpose**: Test if Square API connection is working. Helps debug authentication and permission issues.

**Returns**:
```json
{
  "success": true,
  "message": "Connection successful"
}
```

---

### `POST /payments/validate-card`
**Purpose**: Validate a credit card without saving it or charging it. Only checks if the card is valid.

**Request Body**:
```json
{
  "source_id": "cnon:card-token-from-square",
  "customer_id": "optional-square-customer-id"
}
```

**Returns**:
```json
{
  "valid": true,
  "card_details": {
    "last_4": "1234",
    "brand": "VISA",
    "exp_month": 12,
    "exp_year": 2025,
    "card_id": "..."
  },
  "customer_id": "...",
  "message": "Card is valid"
}
```

**Notes**: 
- Creates temporary customer if `customer_id` not provided
- Square payment tokens are single-use and expire quickly
- No charge is made

---

### `POST /payments/subscription-plans/create`
**Purpose**: Create a subscription plan in Square Catalog. Creates a subscription plan template that can be used to create subscriptions.

**Request Body**:
```json
{
  "name": "Pro Plan",
  "phases": [
    {
      "cadence": "MONTHLY",
      "periods": 1,
      "recurring_price_money": {
        "amount": 9900,
        "currency": "USD"
      }
    }
  ],
  "location_id": "optional-location-id",
  "idempotency_key": "optional-unique-key"
}
```

**Returns**:
```json
{
  "success": true,
  "subscription_plan": {...},
  "plan_id": "...",
  "message": "Subscription plan created successfully"
}
```

**Phase Cadence Options**: `DAILY`, `WEEKLY`, `MONTHLY`, `QUARTERLY`, `YEARLY`

---

## Protected Endpoints (Professional Role Required)

### `POST /payments/subscriptions/create`
**Purpose**: Create a subscription using Square Subscriptions API. Charges the user initially and sets up automatic recurring charges.

**Request Body**:
```json
{
  "plan_variation_id": "LYIAHPLNYRD3AX5FPCDDYDV3",
  "source_id": "cnon:card-token-from-square",
  "location_id": "optional-location-id",
  "professional_id": 123,
  "idempotency_key": "optional-unique-key"
}
```

**Plan Variation IDs**:
- Monthly: `"LYIAHPLNYRD3AX5FPCDDYDV3"`
- Yearly: `"VGMYZYBSVKPM3CJWYK35FS7N"`

**Returns**:
```json
{
  "success": true,
  "subscription": {...},
  "subscription_id": "...",
  "status": "ACTIVE",
  "plan_name": "Pro Town Network Monthly",
  "plan_variation_id": "...",
  "customer_id": "...",
  "message": "Subscription created successfully..."
}
```

**Side Effects**:
- Creates or finds Square customer for the professional
- Updates `professional.subscription_active = True`
- **Stores `subscription_id` in `professional.square_subscription_id`**

**Authentication**: Required (Professional login)

---

### `POST /payments/process`
**Purpose**: Process a one-time payment using Square Payments API. If `subscription_plan_id` is provided, activates subscription on success.

**Request Body**:
```json
{
  "source_id": "cnon:card-token-from-square",
  "amount": 9900,
  "subscription_plan_id": 1
}
```

**Returns**:
```json
{
  "success": true,
  "transaction_id": "...",
  "payment_id": 456,
  "message": "Payment processed successfully"
}
```

**Notes**: 
- Amount should be in cents (e.g., $99.00 = 9900)
- Validates amount matches subscription cost if `subscription_plan_id` provided
- Creates invoice if subscription payment is successful

---

### `POST /payments/save-method`
**Purpose**: Save a payment method for future use (recurring billing).

**Request Body**:
```json
{
  "source_id": "cnon:card-token-from-square"
}
```

**Returns**:
```json
{
  "success": true,
  "payment_method_id": 789,
  "last_4_digits": "1234",
  "card_brand": "VISA",
  "exp_month": 12,
  "exp_year": 2025,
  "is_default": true
}
```

**Notes**: 
- First saved method is automatically set as default
- Square's source_id tokens are single-use; proper implementation should use Square Cards API for reusable card IDs

---

### `GET /payments/methods/{id}`
**Purpose**: Get saved payment methods for a professional.

**Path Parameters**:
- `id`: Professional ID (must match authenticated user)

**Returns**:
```json
{
  "data": [
    {
      "id": 789,
      "professional_id": 123,
      "square_card_id": "...",
      "last_4_digits": "1234",
      "card_brand": "VISA",
      "exp_month": 12,
      "exp_year": 2025,
      "is_default": true,
      "created_at": "2024-01-01T00:00:00"
    }
  ]
}
```

**Notes**: Professionals can only access their own payment methods.

---

### `POST /payments/set-default-method`
**Purpose**: Set a payment method as default for a professional.

**Request Body**:
```json
{
  "payment_method_id": 789
}
```

**Returns**:
```json
{
  "success": true,
  "message": "Default payment method updated",
  "payment_method_id": 789
}
```

---

### `POST /payments/renew-subscription`
**Purpose**: Process a recurring subscription payment using a saved payment method.

**Request Body**:
```json
{
  "professional_id": 123,
  "payment_method_id": 789,
  "amount": 9900
}
```

**Returns**:
```json
{
  "success": true,
  "transaction_id": "...",
  "payment_id": 456,
  "renewal_date": "2024-02-01",
  "message": "Subscription renewed successfully"
}
```

**Notes**: 
- Validates amount matches subscription cost
- Creates invoice on success
- Updates subscription renewal date

---

### `DELETE /payments/methods/{payment_method_id}`
**Purpose**: Delete a saved payment method.

**Path Parameters**:
- `payment_method_id`: ID of payment method to delete

**Returns**:
```json
{
  "success": true,
  "message": "Payment method deleted"
}
```

**Notes**: If deleted method was default, automatically sets another method as default (if any exist).

---

### `POST /payments/subscriptions/{subscription_id}/cancel`
**Purpose**: Cancel an active subscription.

**Path Parameters**:
- `subscription_id`: Square subscription ID (or uses stored `professional.square_subscription_id` if available)

**Returns**:
```json
{
  "success": true,
  "message": "Subscription canceled successfully",
  "subscription": {...}
}
```

**Side Effects**:
- Calls Square API to cancel subscription
- Updates `professional.subscription_active = False`
- Updates `professional.subscription_plan_id = None`

**Notes**: 
- **Uses `professional.square_subscription_id` if available** (preferred)
- Falls back to path parameter `subscription_id` if stored ID not available
- Verifies professional has active subscription before canceling

---

### `POST /payments/subscriptions/{subscription_id}/update`
**Purpose**: Update an active subscription (upgrade/downgrade plan).

**Path Parameters**:
- `subscription_id`: Square subscription ID

**Request Body**:
```json
{
  "plan_variation_id": "VGMYZYBSVKPM3CJWYK35FS7N"
}
```

**Returns**:
```json
{
  "success": true,
  "message": "Subscription updated successfully",
  "subscription": {...}
}
```

**Side Effects**:
- Updates subscription plan in Square
- Keeps `professional.subscription_active = True`

---

## Request/Response Models

### `ProcessPaymentRequest`
```python
{
  "source_id": str,  # Payment token from Square Web Payments SDK
  "amount": int,  # Amount in cents
  "subscription_plan_id": Optional[int]
}
```

### `ProcessApplicationPaymentRequest`
```python
{
  "source_id": str,
  "amount": int,
  "subscription_plan_id": Optional[int],
  "professional_id": Optional[int],
  "email": Optional[str]
}
```

### `CreateSubscriptionRequest`
```python
{
  "plan_variation_id": str,  # e.g., "LYIAHPLNYRD3AX5FPCDDYDV3"
  "source_id": str,  # Payment token from Square Web Payments SDK
  "location_id": Optional[str],
  "professional_id": Optional[int],
  "idempotency_key": Optional[str]
}
```

### `UpdateSubscriptionRequest`
```python
{
  "plan_variation_id": str  # New plan variation ID
}
```

---

## Important Notes

1. **Square Subscription ID Storage**: The `create_square_subscription` endpoint now stores the Square subscription ID in `professional.square_subscription_id` for future reference.

2. **Subscription Cancellation**: The `cancel_subscription_endpoint` prefers using the stored `professional.square_subscription_id` if available, falling back to the path parameter.

3. **Payment Tokens**: Square's `source_id` tokens are single-use and expire quickly. They should be generated immediately before use.

4. **Database Migration**: Run `migrations/add_square_subscription_id.sql` to add the `square_subscription_id` column to the `professionals` table if not already applied.
