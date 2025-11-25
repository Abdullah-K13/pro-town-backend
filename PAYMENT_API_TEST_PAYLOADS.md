# Payment API Test Payloads

This document provides example payloads for testing all payment endpoints.

## Prerequisites

1. **Authentication Token**: For endpoints requiring auth, you need a JWT token from `/auth/login` as a professional user.
2. **Square Test Card**: Use Square's test card for sandbox: `4111 1111 1111 1111`
3. **Environment**: Make sure `SQUARE_ENVIRONMENT=sandbox` in your `.env` file

---

## 1. GET `/payments/square-config` (No Auth Required)

**Request:**{
  "detail": "Payment processing failed: (psycopg2.errors.NotNullViolation) null value in column \"professional_id\" of relation \"payments\" violates not-null constraint\nDETAIL:  Failing row contains (2, null, 2, 1687, nXCi7txgTlCTKmbJN6XjLSzx1tdZY, SUCCESS, null, 2025-11-21 07:57:51.937266).\n\n[SQL: INSERT INTO payments (professional_id, subscription_plan_id, amount, square_transaction_id, status, payment_method_id) VALUES (%(professional_id)s, %(subscription_plan_id)s, %(amount)s, %(square_transaction_id)s, %(status)s, %(payment_method_id)s) RETURNING payments.id, payments.created_at]\n[parameters: {'professional_id': None, 'subscription_plan_id': 2, 'amount': 1687, 'square_transaction_id': 'nXCi7txgTlCTKmbJN6XjLSzx1tdZY', 'status': 'SUCCESS', 'payment_method_id': None}]\n(Background on this error at: https://sqlalche.me/e/20/gkpj)"
}
```http
GET /payments/square-config
```

**Response:**
```json
{
  "application_id": "sandbox-sq0idb-...",
  "location_id": "LOCATION_ID"
}
```

---

## 2. POST `/payments/process-application` (No Auth Required)

**Use Case:** New user application payment (before account is fully created)

**Request:**
```http
POST /payments/process-application
Content-Type: application/json
```

**Payload Examples:**

### Example 1: Payment with subscription plan (professional exists)
```json
{
  "source_id": "cnon:card-nonce-ok",
  "amount": 9900,
  "subscription_plan_id": 2,
  "professional_id": 1
}
```

### Example 2: Payment with subscription plan (by email)
```json
{
  "source_id": "cnon:card-nonce-ok",
  "amount": 1500,
  "subscription_plan_id": 1,
  "email": "newpro@example.com"
}
```

### Example 3: Payment without subscription (general payment)
```json
{
  "source_id": "cnon:card-nonce-ok",
  "amount": 5000
}
```

### Example 4: Free plan (amount can be 0 or any positive)
```json
{
  "source_id": "cnon:card-nonce-ok",
  "amount": 0,
  "subscription_plan_id": 1
}
```

**Response (Success):**
```json
{
  "success": true,
  "transaction_id": "square-transaction-id-123",
  "payment_id": 456,
  "message": "Payment processed successfully",
  "professional_id": 1,
  "subscription_activated": true
}
```

**Response (Failed):**
```json
{
  "success": false,
  "transaction_id": null,
  "payment_id": 457,
  "message": "Payment failed",
  "professional_id": null,
  "subscription_activated": false
}
```

---

## 3. POST `/payments/process` (Auth Required)

**Use Case:** Authenticated user payments

**Request:**
```http
POST /payments/process
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
```

**Payload Examples:**

### Example 1: Subscription payment
```json
{
  "source_id": "cnon:card-nonce-ok",
  "amount": 9900,
  "subscription_plan_id": 2
}
```

### Example 2: One-time payment (no subscription)
```json
{
  "source_id": "cnon:card-nonce-ok",
  "amount": 2500
}
```

**Response (Success):**
```json
{
  "success": true,
  "transaction_id": "square-transaction-id-123",
  "payment_id": 789,
  "message": "Payment processed successfully"
}
```

---

## 4. POST `/payments/save-method` (Auth Required)

**Use Case:** Save payment method for recurring billing

**Request:**
```http
POST /payments/save-method
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
```

**Payload:**
```json
{
  "source_id": "cnon:card-nonce-ok"
}
```

**Response (Success):**
```json
{
  "success": true,
  "payment_method_id": 123,
  "last_4_digits": "4242",
  "card_brand": "VISA",
  "exp_month": 12,
  "exp_year": 2026,
  "is_default": true
}
```

**Response (Error):**
```json
{
  "detail": "Failed to save payment method: Card creation failed: ..."
}
```

---

## 5. GET `/payments/methods/{id}` (Auth Required)

**Use Case:** Get saved payment methods for a professional

**Request:**
```http
GET /payments/methods/1
Authorization: Bearer <JWT_TOKEN>
```

**Note:** The `{id}` is the `professional_id`. The endpoint validates that the authenticated professional matches this ID.

**Response:**
```json
{
  "data": [
    {
      "id": 123,
      "professional_id": 1,
      "square_card_id": "card-id-from-square",
      "last_4_digits": "4242",
      "card_brand": "VISA",
      "exp_month": 12,
      "exp_year": 2026,
      "is_default": true,
      "created_at": "2025-01-15T10:30:00Z"
    },
    {
      "id": 124,
      "professional_id": 1,
      "square_card_id": "card-id-2",
      "last_4_digits": "8888",
      "card_brand": "MASTERCARD",
      "exp_month": 6,
      "exp_year": 2027,
      "is_default": false,
      "created_at": "2025-01-20T14:20:00Z"
    }
  ]
}
```

**Response (No methods):**
```json
{
  "data": []
}
```

---

## 6. POST `/payments/set-default-method` (Auth Required)

**Use Case:** Set a payment method as default

**Request:**
```http
POST /payments/set-default-method
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
```

**Payload:**
```json
{
  "payment_method_id": 124
}
```

**Response:**
```json
{
  "success": true,
  "message": "Default payment method updated",
  "payment_method_id": 124
}
```

---

## 7. POST `/payments/renew-subscription` (Auth Required)

**Use Case:** Process recurring subscription payment using saved payment method

**Request:**
```http
POST /payments/renew-subscription
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
```

**Payload:**
```json
{
  "professional_id": 1,
  "payment_method_id": 123,
  "amount": 9900
}
```

**Response (Success):**
```json
{
  "success": true,
  "transaction_id": "square-transaction-id-456",
  "payment_id": 790,
  "renewal_date": "2025-02-15",
  "message": "Subscription renewed successfully"
}
```

**Response (Error - No default method):**
```json
{
  "detail": "No default payment method found. Please add a payment method first."
}
```

**Note:** This endpoint currently requires Square Customer/Card API implementation for true recurring payments. It may return a 501 error if the stored `square_card_id` is a source_id (single-use) rather than a reusable Card ID.

---

## 8. DELETE `/payments/methods/{payment_method_id}` (Auth Required)

**Use Case:** Delete a saved payment method

**Request:**
```http
DELETE /payments/methods/123
Authorization: Bearer <JWT_TOKEN>
```

**Response:**
```json
{
  "success": true,
  "message": "Payment method deleted"
}
```

**Response (Not Found):**
```json
{
  "detail": "Payment method not found"
}
```

---

## Square Test Cards (Sandbox)

Use these test card numbers in Square's sandbox environment:

### Successful Payment
- **Card Number:** `4111 1111 1111 1111`
- **CVV:** Any 3 digits (e.g., `123`)
- **Expiry:** Any future date (e.g., `12/26`)
- **ZIP:** Any 5 digits (e.g., `12345`)

### Declined Payment
- **Card Number:** `4000 0000 0000 0002`
- **CVV:** Any 3 digits
- **Expiry:** Any future date
- **ZIP:** Any 5 digits

### Insufficient Funds
- **Card Number:** `4000 0000 0000 9995`
- **CVV:** Any 3 digits
- **Expiry:** Any future date
- **ZIP:** Any 5 digits

---

## Testing Workflow

### Complete Payment Flow Test:

1. **Get Square Config** (Optional)
   ```bash
   GET /payments/square-config
   ```

2. **Process Application Payment** (New user)
   ```bash
   POST /payments/process-application
   {
     "source_id": "cnon:card-nonce-ok",
     "amount": 9900,
     "subscription_plan_id": 2,
     "email": "test@example.com"
   }
   ```

3. **Login as Professional** (Get JWT token)
   ```bash
   POST /auth/login
   {
     "email": "test@example.com",
     "password": "password"
   }
   ```

4. **Save Payment Method**
   ```bash
   POST /payments/save-method
   Authorization: Bearer <token>
   {
     "source_id": "cnon:card-nonce-ok"
   }
   ```

5. **Get Payment Methods**
   ```bash
   GET /payments/methods/1
   Authorization: Bearer <token>
   ```

6. **Process Payment** (Authenticated)
   ```bash
   POST /payments/process
   Authorization: Bearer <token>
   {
     "source_id": "cnon:card-nonce-ok",
     "amount": 9900,
     "subscription_plan_id": 2
   }
   ```

---

## Common Error Responses

### 400 Bad Request
```json
{
  "detail": "Amount must match subscription cost: 9900 cents ($99.00)"
}
```

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

### 403 Forbidden
```json
{
  "detail": "Not authorized to access these payment methods"
}
```

### 404 Not Found
```json
{
  "detail": "Subscription plan not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Payment processing failed: Square API error..."
}
```

---

## Notes

1. **Amount Format**: All amounts are in **cents** (e.g., $99.00 = 9900 cents)
2. **source_id**: This is the payment token from Square Web Payments SDK (frontend)
3. **Subscription Plans**: Make sure subscription plans exist in your database with correct costs
4. **Free Plans**: If a subscription plan has cost = $0.00, amount can be 0 or any positive value
5. **Authentication**: Use JWT tokens from `/auth/login` for protected endpoints
6. **Idempotency**: Square requires unique idempotency keys (automatically generated if not provided)

