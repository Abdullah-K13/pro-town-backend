# Professional Signup with Automatic Subscription - Test Payloads

This document provides test payloads for professional signup with automatic subscription creation.

## Overview

When a professional signs up, they can now automatically create a subscription by providing:
- `subscription_plan_variation_id`: The subscription plan variation ID (Monthly or Yearly)
- `payment_source_id`: Payment token from Square Web Payments SDK

The system will:
1. Create the professional account
2. Create a Square customer
3. Create a Square subscription (charges immediately)
4. Set up automatic recurring payments
5. Set `subscription_active = True` in the database

---

## Available Subscription Plans

### 1. Monthly Plan
- **Variation ID**: `LYIAHPLNYRD3AX5FPCDDYDV3`
- **Price**: $100.00/month (10000 cents)
- **Plan Name**: "Pro Town Network Monthly"

### 2. Yearly Plan
- **Variation ID**: `VGMYZYBSVKPM3CJWYK35FS7N`
- **Price**: $1,200.00/year (120000 cents)
- **Plan Name**: "Pro Town Network Yearly"

---

## Endpoints

### 1. POST `/auth/signup?role=professional`

**Purpose**: Create a new professional account with automatic subscription

**Authentication**: ❌ No

**Request Body**:
```json
{
  "name": "John Doe",
  "email": "john.doe@example.com",
  "password": "securepassword123",
  "phone_number": "1234567890",
  "business_name": "John's Plumbing",
  "business_address": "123 Main St",
  "service_id": 1,
  "state_id": 1,
  "city_id": 1,
  "subscription_plan_variation_id": "LYIAHPLNYRD3AX5FPCDDYDV3",
  "payment_source_id": "cnon:card-nonce-ok",
  "location_id": "L630MQ9S2T49X"
}
```

**Required Fields**:
- `name`: Professional's name
- `email`: Professional's email (must be unique)
- `password`: Password for the account
- `subscription_plan_variation_id`: Either `"LYIAHPLNYRD3AX5FPCDDYDV3"` (Monthly) or `"VGMYZYBSVKPM3CJWYK35FS7N"` (Yearly)
- `payment_source_id`: Payment token from Square Web Payments SDK

**Optional Fields**:
- `phone_number`: Phone number
- `business_name`: Business name
- `business_address`: Business address
- `service_id`: Service ID
- `state_id`: State ID
- `city_id`: City ID
- `location_id`: Square location ID (uses env var if not provided)

**Response Example (Success with Subscription)**:
```json
{
  "message": "Professional created successfully",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 123,
    "role": "professional",
    "email": "john.doe@example.com",
    "name": "John Doe"
  },
  "subscription": {
    "subscription_created": true,
    "subscription_id": "subscription-id-from-square",
    "plan_name": "Pro Town Network Monthly",
    "status": "ACTIVE"
  }
}
```

**Response Example (Success without Subscription)**:
```json
{
  "message": "Professional created successfully",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 123,
    "role": "professional",
    "email": "john.doe@example.com",
    "name": "John Doe"
  },
  "subscription": {
    "subscription_created": false,
    "message": "No subscription created. Provide subscription_plan_variation_id and payment_source_id to create subscription."
  }
}
```

**Response Example (Subscription Failed)**:
```json
{
  "message": "Professional created successfully",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 123,
    "role": "professional",
    "email": "john.doe@example.com",
    "name": "John Doe"
  },
  "subscription": {
    "subscription_created": false,
    "error": "Payment declined",
    "message": "Professional account created but subscription setup failed. Please contact support."
  }
}
```

---

### 2. POST `/professional/`

**Purpose**: Create a professional with file upload support (multipart/form-data)

**Authentication**: ❌ No

**Request Format**: `multipart/form-data`

**Form Fields**:
- `payload`: JSON string containing professional data and subscription info
- `insurance_document`: (Optional) File upload

**Payload JSON Example**:
```json
{
  "name": "Jane Smith",
  "email": "jane.smith@example.com",
  "password": "securepassword123",
  "phone_number": "9876543210",
  "business_name": "Jane's Electrical",
  "business_address": "456 Oak Ave",
  "service_id": 2,
  "state_id": 2,
  "city_id": 2,
  "subscription_plan_variation_id": "VGMYZYBSVKPM3CJWYK35FS7N",
  "payment_source_id": "cnon:card-nonce-ok",
  "location_id": "L630MQ9S2T49X"
}
```

---

## Test Payloads

### Test Payload 1: Signup with Monthly Subscription

```json
{
  "name": "John Doe",
  "email": "john.doe@example.com",
  "password": "password123",
  "phone_number": "1234567890",
  "business_name": "John's Plumbing Services",
  "business_address": "123 Main Street, City, State 12345",
  "service_id": 1,
  "state_id": 1,
  "city_id": 1,
  "subscription_plan_variation_id": "LYIAHPLNYRD3AX5FPCDDYDV3",
  "payment_source_id": "cnon:card-nonce-ok",
  "location_id": "L630MQ9S2T49X"
}
```

**cURL Command**:
```bash
curl -X POST "http://localhost:8000/auth/signup?role=professional" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john.doe@example.com",
    "password": "password123",
    "phone_number": "1234567890",
    "business_name": "John'\''s Plumbing Services",
    "business_address": "123 Main Street, City, State 12345",
    "service_id": 1,
    "state_id": 1,
    "city_id": 1,
    "subscription_plan_variation_id": "LYIAHPLNYRD3AX5FPCDDYDV3",
    "payment_source_id": "cnon:card-nonce-ok",
    "location_id": "L630MQ9S2T49X"
  }'
```

---

### Test Payload 2: Signup with Yearly Subscription

```json
{
  "name": "Jane Smith",
  "email": "jane.smith@example.com",
  "password": "password123",
  "phone_number": "9876543210",
  "business_name": "Jane'\''s Electrical Services",
  "business_address": "456 Oak Avenue, City, State 54321",
  "service_id": 2,
  "state_id": 2,
  "city_id": 2,
  "subscription_plan_variation_id": "VGMYZYBSVKPM3CJWYK35FS7N",
  "payment_source_id": "cnon:card-nonce-ok",
  "location_id": "L630MQ9S2T49X"
}
```

**cURL Command**:
```bash
curl -X POST "http://localhost:8000/auth/signup?role=professional" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jane Smith",
    "email": "jane.smith@example.com",
    "password": "password123",
    "phone_number": "9876543210",
    "business_name": "Jane'\''s Electrical Services",
    "business_address": "456 Oak Avenue, City, State 54321",
    "service_id": 2,
    "state_id": 2,
    "city_id": 2,
    "subscription_plan_variation_id": "VGMYZYBSVKPM3CJWYK35FS7N",
    "payment_source_id": "cnon:card-nonce-ok",
    "location_id": "L630MQ9S2T49X"
  }'
```

---

### Test Payload 3: Signup without Subscription

```json
{
  "name": "Bob Wilson",
  "email": "bob.wilson@example.com",
  "password": "password123",
  "phone_number": "5551234567",
  "business_name": "Bob'\''s HVAC",
  "business_address": "789 Pine Road, City, State 67890",
  "service_id": 3,
  "state_id": 1,
  "city_id": 1
}
```

**Note**: If `subscription_plan_variation_id` and `payment_source_id` are not provided, the professional account will be created but no subscription will be set up. They can subscribe later using the `/payments/subscriptions/create` endpoint.

---

## Frontend Integration

### Step 1: Collect Professional Information
```javascript
const professionalData = {
  name: "John Doe",
  email: "john.doe@example.com",
  password: "securepassword123",
  phone_number: "1234567890",
  business_name: "John's Plumbing",
  business_address: "123 Main St",
  service_id: 1,
  state_id: 1,
  city_id: 1
};
```

### Step 2: Initialize Square Payment Form
```javascript
import { payments } from '@square/web-payments-sdk';

// Get Square config
const config = await fetch('/payments/square-config').then(r => r.json());
const applicationId = config.application_id;
const locationId = config.location_id;

// Initialize Square
const paymentsClient = await payments(applicationId, locationId);
const card = await paymentsClient.card();
await card.attach('#card-container');
```

### Step 3: Collect Subscription Plan Selection
```javascript
// User selects subscription plan
const selectedPlan = "monthly"; // or "yearly"
const planVariationId = selectedPlan === "monthly" 
  ? "LYIAHPLNYRD3AX5FPCDDYDV3" 
  : "VGMYZYBSVKPM3CJWYK35FS7N";
```

### Step 4: Tokenize Card and Signup
```javascript
// Tokenize card
const tokenResult = await card.tokenize();
if (tokenResult.status === 'OK') {
  const sourceId = tokenResult.token;
  
  // Add subscription info to professional data
  professionalData.subscription_plan_variation_id = planVariationId;
  professionalData.payment_source_id = sourceId;
  professionalData.location_id = locationId;
  
  // Signup with subscription
  const response = await fetch('/auth/signup?role=professional', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(professionalData)
  });
  
  const result = await response.json();
  
  if (result.subscription?.subscription_created) {
    console.log('Account and subscription created!', result);
    // Store access token
    localStorage.setItem('access_token', result.access_token);
    // Redirect to dashboard
  } else {
    console.error('Subscription failed:', result.subscription?.error);
  }
}
```

---

## Error Handling

### Common Errors:

1. **Invalid Subscription Plan**:
   ```json
   {
     "detail": "Invalid subscription plan. Use 'LYIAHPLNYRD3AX5FPCDDYDV3' for Monthly or 'VGMYZYBSVKPM3CJWYK35FS7N' for Yearly"
   }
   ```

2. **Missing Location ID**:
   ```json
   {
     "detail": "location_id is required for subscription. Provide it in the request or set SQUARE_LOCATION_ID in .env"
   }
   ```

3. **Square Customer Creation Failed**:
   ```json
   {
     "detail": "Failed to create Square customer: [error message]. Professional account created but subscription setup failed."
   }
   ```

4. **Payment Declined**:
   ```json
   {
     "message": "Professional created successfully",
     "subscription": {
       "subscription_created": false,
       "error": "Payment declined",
       "message": "Professional account created but subscription setup failed. Please contact support."
     }
   }
   ```

---

## Important Notes

1. **Payment Token**: The `payment_source_id` must be a valid payment token from Square Web Payments SDK. These tokens are single-use and expire quickly.

2. **Immediate Charge**: When a subscription is created, Square will charge the customer immediately for the first billing period.

3. **Automatic Recurring Charges**: Square will automatically charge the customer on each billing cycle (monthly or yearly) based on the plan.

4. **Account Creation vs Subscription**: The professional account is always created, even if subscription setup fails. The user can try subscribing again later.

5. **Location ID**: Make sure your `SQUARE_LOCATION_ID` is set in your `.env` file, or provide it in the request.

6. **Square Test Cards** (Sandbox):
   - **Success**: `4111 1111 1111 1111`
   - **Decline**: `4000 0000 0000 0002`
   - **CVV**: Any 3 digits
   - **Expiry**: Any future date
   - **ZIP**: Any 5 digits

---

## Testing Checklist

- [ ] Signup with Monthly subscription
- [ ] Signup with Yearly subscription
- [ ] Signup without subscription (optional fields)
- [ ] Verify Square customer is created
- [ ] Verify Square subscription is created
- [ ] Verify `subscription_active = True` in database
- [ ] Test with invalid subscription plan ID
- [ ] Test with declined payment card
- [ ] Test with missing location_id
- [ ] Verify automatic recurring charges are set up in Square Dashboard

---

## Next Steps

1. **Webhook Integration**: Set up Square webhooks to receive subscription status updates
2. **Subscription Management**: Add endpoints to:
   - View current subscription
   - Cancel subscription
   - Update payment method
   - Change subscription plan
3. **Database Tracking**: Consider storing Square subscription ID in Professional model for easier management

