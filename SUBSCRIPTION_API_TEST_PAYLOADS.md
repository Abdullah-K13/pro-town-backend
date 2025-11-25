# Subscription API Test Payloads

This document provides test payloads for the subscription endpoints.

## Available Subscription Plans

Based on your Square Catalog, you have 2 subscription plans:

### 1. Pro Town Network Monthly
- **Plan ID**: `D3B2LOI6VSAH3DMYD6GLPYV6`
- **Variation ID**: `LYIAHPLNYRD3AX5FPCDDYDV3`
- **Price**: $100.00 (10000 cents) per month
- **Cadence**: MONTHLY

### 2. Pro Town Network Yearly
- **Plan ID**: `AXNTHZYDCKVCL6NXGXF3CLVY`
- **Variation ID**: `VGMYZYBSVKPM3CJWYK35FS7N`
- **Price**: $1,200.00 (120000 cents) per year
- **Cadence**: ANNUAL

---

## Endpoints

### 1. GET `/payments/subscription-plans`
**Purpose**: Fetch all available subscription plans from Square

**Authentication**: ❌ No

**Request**:
```bash
GET /payments/subscription-plans
```

**Response Example**:
```json
{
  "success": true,
  "plans": [
    {
      "id": "D3B2LOI6VSAH3DMYD6GLPYV6",
      "name": "Pro Town Network Monthly",
      "variations": [
        {
          "id": "LYIAHPLNYRD3AX5FPCDDYDV3",
          "name": "Pro Town Network Monthly",
          "phases": [
            {
              "uid": "LJCJXGZNDOKQ2Y5CDHEY3P7Z",
              "cadence": "MONTHLY",
              "ordinal": 0,
              "pricing": {
                "type": "RELATIVE"
              }
            }
          ],
          "subscription_plan_id": "D3B2LOI6VSAH3DMYD6GLPYV6",
          "item_id": null,
          "item_variation_id": null
        }
      ],
      "eligible_item_ids": ["WZ46V4MTESLQ6AJG7SX34F53"],
      "all_items": false
    },
    {
      "id": "AXNTHZYDCKVCL6NXGXF3CLVY",
      "name": "Pro Town Network Yearly",
      "variations": [
        {
          "id": "VGMYZYBSVKPM3CJWYK35FS7N",
          "name": "Pro Town Network Yearly",
          "phases": [
            {
              "uid": "OR73OQN2U64Y2JD6OLTKMVK6",
              "cadence": "ANNUAL",
              "ordinal": 0,
              "pricing": {
                "type": "RELATIVE"
              }
            }
          ],
          "subscription_plan_id": "AXNTHZYDCKVCL6NXGXF3CLVY",
          "item_id": null,
          "item_variation_id": null
        }
      ],
      "eligible_item_ids": ["Z7JC2BUN2LN34A5IJSDUL3QL"],
      "all_items": false
    }
  ],
  "cursor": null
}
```

---

### 2. POST `/payments/subscriptions/create`
**Purpose**: Create a subscription (charges user immediately and sets up automatic recurring charges)

**Authentication**: ✅ Yes (Professional login required)

**Request Body**:
```json
{
  "plan_variation_id": "LYIAHPLNYRD3AX5FPCDDYDV3",
  "source_id": "cnon:card-nonce-ok",
  "location_id": "L630MQ9S2T49X"
}
```

**Field Descriptions**:
- `plan_variation_id` (required): The variation ID of the subscription plan
  - Monthly: `"LYIAHPLNYRD3AX5FPCDDYDV3"`
  - Yearly: `"VGMYZYBSVKPM3CJWYK35FS7N"`
- `source_id` (required): Payment token from Square Web Payments SDK (frontend)
- `location_id` (optional): Square location ID (uses env var if not provided)
- `idempotency_key` (optional): Unique key to prevent duplicate subscriptions

**Response Example (Success)**:
```json
{
  "success": true,
  "subscription": {
    "id": "subscription-id-from-square",
    "location_id": "L630MQ9S2T49X",
    "plan_variation_id": "LYIAHPLNYRD3AX5FPCDDYDV3",
    "customer_id": "customer-id-from-square",
    "status": "ACTIVE",
    "start_date": "2025-11-21",
    "charged_through_date": "2025-12-21",
    "created_at": "2025-11-21T21:00:00Z"
  },
  "subscription_id": "subscription-id-from-square",
  "status": "ACTIVE",
  "plan_name": "Pro Town Network Monthly",
  "plan_variation_id": "LYIAHPLNYRD3AX5FPCDDYDV3",
  "customer_id": "customer-id-from-square",
  "message": "Subscription created successfully. You will be charged automatically on each billing cycle."
}
```

**Response Example (Error)**:
```json
{
  "detail": "Invalid request: Payment declined"
}
```

---

## Test Payloads

### Test Payload 1: Subscribe to Monthly Plan
```json
{
  "plan_variation_id": "LYIAHPLNYRD3AX5FPCDDYDV3",
  "source_id": "cnon:card-nonce-ok",
  "location_id": "L630MQ9S2T49X"
}
```

**cURL Command**:
```bash
curl -X POST "http://localhost:8000/payments/subscriptions/create" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_PROFESSIONAL_JWT_TOKEN" \
  -d '{
    "plan_variation_id": "LYIAHPLNYRD3AX5FPCDDYDV3",
    "source_id": "cnon:card-nonce-ok",
    "location_id": "L630MQ9S2T49X"
  }'
```

---

### Test Payload 2: Subscribe to Yearly Plan
```json
{
  "plan_variation_id": "VGMYZYBSVKPM3CJWYK35FS7N",
  "source_id": "cnon:card-nonce-ok",
  "location_id": "L630MQ9S2T49X"
}
```

**cURL Command**:
```bash
curl -X POST "http://localhost:8000/payments/subscriptions/create" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_PROFESSIONAL_JWT_TOKEN" \
  -d '{
    "plan_variation_id": "VGMYZYBSVKPM3CJWYK35FS7N",
    "source_id": "cnon:card-nonce-ok",
    "location_id": "L630MQ9S2T49X"
  }'
```

---

### Test Payload 3: Subscribe with Idempotency Key
```json
{
  "plan_variation_id": "LYIAHPLNYRD3AX5FPCDDYDV3",
  "source_id": "cnon:card-nonce-ok",
  "location_id": "L630MQ9S2T49X",
  "idempotency_key": "unique-key-12345"
}
```

**cURL Command**:
```bash
curl -X POST "http://localhost:8000/payments/subscriptions/create" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_PROFESSIONAL_JWT_TOKEN" \
  -d '{
    "plan_variation_id": "LYIAHPLNYRD3AX5FPCDDYDV3",
    "source_id": "cnon:card-nonce-ok",
    "location_id": "L630MQ9S2T49X",
    "idempotency_key": "unique-key-12345"
  }'
```

---

## Frontend Integration Notes

### Step 1: Get Square Application ID
```javascript
// Call GET /payments/square-config
const config = await fetch('/payments/square-config').then(r => r.json());
const applicationId = config.application_id;
```

### Step 2: Initialize Square Payment Form
```javascript
import { payments } from '@square/web-payments-sdk';

const paymentsClient = await payments(applicationId, locationId).then(client => {
  return client;
});

const card = await paymentsClient.card();
await card.attach('#card-container');
```

### Step 3: Tokenize Card and Create Subscription
```javascript
const tokenResult = await card.tokenize();
if (tokenResult.status === 'OK') {
  const sourceId = tokenResult.token;
  
  // Call subscription creation endpoint
  const response = await fetch('/payments/subscriptions/create', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${userToken}`
    },
    body: JSON.stringify({
      plan_variation_id: 'LYIAHPLNYRD3AX5FPCDDYDV3', // or yearly variation ID
      source_id: sourceId,
      location_id: locationId
    })
  });
  
  const result = await response.json();
  if (result.success) {
    console.log('Subscription created!', result);
  }
}
```

---

## Square Test Cards (Sandbox)

If you're testing in sandbox mode, use these test cards:

### Successful Payment
- **Card Number**: `4111 1111 1111 1111`
- **CVV**: Any 3 digits (e.g., `123`)
- **Expiry**: Any future date (e.g., `12/26`)
- **ZIP**: Any 5 digits (e.g., `12345`)

### Declined Payment
- **Card Number**: `4000 0000 0000 0002`
- **CVV**: Any 3 digits
- **Expiry**: Any future date
- **ZIP**: Any 5 digits

---

## Important Notes

1. **Authentication Required**: The subscription creation endpoint requires a professional to be logged in. The JWT token must be included in the `Authorization` header.

2. **Automatic Customer Creation**: The endpoint automatically creates a Square customer if one doesn't exist for the authenticated professional.

3. **Immediate Charge**: When a subscription is created, Square will charge the customer immediately for the first billing period.

4. **Automatic Recurring Charges**: Square will automatically charge the customer on each billing cycle (monthly or yearly) based on the plan.

5. **Payment Token**: The `source_id` must be a valid payment token from Square Web Payments SDK. These tokens are single-use and expire quickly.

6. **Location ID**: Make sure your `SQUARE_LOCATION_ID` is set in your `.env` file, or provide it in the request.

7. **Production vs Sandbox**: 
   - Make sure `SQUARE_ENVIRONMENT` is set correctly in `.env`
   - Production: `SQUARE_ENVIRONMENT=production`
   - Sandbox: `SQUARE_ENVIRONMENT=sandbox`

---

## Error Handling

### Common Errors:

1. **401 Unauthorized**: 
   - Missing or invalid JWT token
   - Solution: Login as a professional first

2. **400 Bad Request**: 
   - Missing required fields
   - Invalid `plan_variation_id`
   - Invalid `source_id`
   - Solution: Check request payload

3. **404 Not Found**: 
   - Invalid `location_id`
   - Invalid `plan_variation_id`
   - Solution: Verify Square location and plan IDs

4. **500 Internal Server Error**: 
   - Square API error
   - Database error
   - Solution: Check server logs

---

## Testing Checklist

- [ ] Get subscription plans: `GET /payments/subscription-plans`
- [ ] Login as professional: `POST /auth/login`
- [ ] Create monthly subscription: `POST /payments/subscriptions/create`
- [ ] Create yearly subscription: `POST /payments/subscriptions/create`
- [ ] Verify subscription in Square Dashboard
- [ ] Check automatic recurring charges are set up

---

## Next Steps

1. **Webhook Integration**: Set up Square webhooks to receive subscription status updates
2. **Subscription Management**: Add endpoints to:
   - Cancel subscriptions
   - Update payment method
   - View subscription history
   - Pause/resume subscriptions
3. **Database Tracking**: Store Square subscription IDs in your database for easier management

