# Professional Subscription Flow - Test Guide

This document provides test payloads and the exact sequence of API calls for creating a professional with subscription.

## 📋 Complete Flow Overview

### **Step 1: Create Professional** (POST /professionals/)
- Creates professional account
- Creates Square customer
- Creates card on file (validates card, NO CHARGE)
- Stores card for later use

### **Step 2: Verify Professional** (PUT /professionals/{id})
- Admin verifies the professional
- System automatically creates subscription (THIS IS WHERE CHARGE HAPPENS)
- Activates subscription

---

## 🔄 API Call Sequence

### **Internal Square API Calls (Automatic)**

When you call the endpoints below, these Square API calls happen automatically:

#### **During Professional Creation (Step 1):**
1. `POST /v2/customers` - Create Square customer
2. `PUT /v2/customers/{customer_id}` - Update customer details (if customer exists)
3. `POST /v2/cards` - Create card on file with customer_id
4. `POST /v2/cards/search` - Verify card belongs to customer (verification)

#### **During Professional Verification (Step 2):**
1. `GET /v2/locations` - Get available locations
2. `POST /v2/cards/search` - Get customer's cards to verify ownership
3. `POST /v2/subscriptions` - Create subscription (CHARGE HAPPENS HERE)

---

## 📝 Test Payloads

### **Step 1: Create Professional with Card**

**Endpoint:** `POST /professionals/`

**Content-Type:** `multipart/form-data`

**Form Fields:**
- `payload`: JSON string (see below)
- `insurance_document`: (optional) File upload

**Payload JSON:**
```json
{
  "name": "John Doe",
  "email": "john.doe@example.com",
  "password": "SecurePassword123!",
  "phone_number": "5551234567",
  "business_name": "John's Plumbing",
  "business_address": "123 Main St, City, State 12345",
  "service_id": 1,
  "state_id": 1,
  "city_id": 1,
  "subscription_plan_variation_id": "JDCZJQKUQOYZQI73XOMDOH3H",
  "payment_source_id": "cnon:card-nonce-from-square-web-payments-sdk"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/professionals/" \
  -H "Content-Type: multipart/form-data" \
  -F 'payload={
    "name": "John Doe",
    "email": "john.doe@example.com",
    "password": "SecurePassword123!",
    "phone_number": "5551234567",
    "business_name": "John'\''s Plumbing",
    "business_address": "123 Main St, City, State 12345",
    "service_id": 1,
    "state_id": 1,
    "city_id": 1,
    "subscription_plan_variation_id": "JDCZJQKUQOYZQI73XOMDOH3H",
    "payment_source_id": "cnon:card-nonce-from-square-web-payments-sdk"
  }'
```

**JavaScript/Fetch Example:**
```javascript
const formData = new FormData();
formData.append('payload', JSON.stringify({
  name: "John Doe",
  email: "john.doe@example.com",
  password: "SecurePassword123!",
  phone_number: "5551234567",
  business_name: "John's Plumbing",
  business_address: "123 Main St, City, State 12345",
  service_id: 1,
  state_id: 1,
  city_id: 1,
  subscription_plan_variation_id: "JDCZJQKUQOYZQI73XOMDOH3H",
  payment_source_id: "cnon:card-nonce-from-square-web-payments-sdk" // From Square Web Payments SDK
}));

fetch('http://localhost:8000/professionals/', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => console.log(data));
```

**Expected Response:**
```json
{
  "id": 72,
  "name": "John Doe",
  "email": "john.doe@example.com",
  "phone_number": "5551234567",
  "business_name": "John's Plumbing",
  "verified_status": false,
  "subscription_active": false,
  "pending_subscription_plan_variation_id": "JDCZJQKUQOYZQI73XOMDOH3H",
  "square_customer_id": "YF07GQCHR741E777FT79K3ENQG",
  "created_at": "2025-12-06T12:00:00"
}
```

**What Happens:**
1. ✅ Professional created in database
2. ✅ Square customer created (or reused if `square_customer_id` provided)
3. ✅ Card created on file with `customer_id` (validated, NO CHARGE)
4. ✅ Card verified to belong to customer
5. ✅ Payment method saved to database
6. ⚠️ Subscription NOT created yet (waiting for verification)

---

### **Step 2: Verify Professional (Triggers Subscription)**

**Endpoint:** `PUT /professionals/{professional_id}`

**Headers:**
```
Authorization: Bearer {admin_token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "verified_status": true
}
```

**cURL Example:**
```bash
curl -X PUT "http://localhost:8000/professionals/72" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "verified_status": true
  }'
```

**JavaScript/Fetch Example:**
```javascript
fetch('http://localhost:8000/professionals/72', {
  method: 'PUT',
  headers: {
    'Authorization': 'Bearer YOUR_ADMIN_TOKEN',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    verified_status: true
  })
})
.then(response => response.json())
.then(data => console.log(data));
```

**Expected Response:**
```json
{
  "id": 72,
  "name": "John Doe",
  "email": "john.doe@example.com",
  "verified_status": true,
  "subscription_active": true,
  "square_subscription_id": "sub_abc123xyz",
  "pending_subscription_plan_variation_id": null
}
```

**What Happens:**
1. ✅ Professional marked as verified
2. ✅ System gets customer's cards to verify ownership
3. ✅ System creates subscription with Square (CHARGE HAPPENS HERE)
4. ✅ Subscription ID stored in `square_subscription_id`
5. ✅ `subscription_active` set to `true`
6. ✅ `pending_subscription_plan_variation_id` cleared

---

## 🔑 Important Fields

### **Subscription Plan Variation IDs:**
- **Monthly:** `"LYIAHPLNYRD3AX5FPCDDYDV3"`
- **Yearly:** `"VGMYZYBSVKPM3CJWYK35FS7N"`
- **Testing:** `"JDCZJQKUQOYZQI73XOMDOH3H"`

### **Payment Source ID:**
- Must be a fresh token from Square Web Payments SDK
- Format: `"cnon:card-nonce-..."` or `"card-nonce-..."`
- Single-use only - expires quickly
- Generate immediately before API call

### **Optional Fields for Reusing Customer/Card:**
```json
{
  "square_customer_id": "YF07GQCHR741E777FT79K3ENQG",  // Reuse existing customer
  "card_id": "ccof:CA4SEP51EXDdNDCAy8-5kV7w6e0oAQ",    // Reuse existing card
  "location_id": "L1S5PMV6NM3J9"                       // Override location
}
```

---

## 🧪 Test Scenarios

### **Scenario 1: New Professional with New Card**
```json
{
  "name": "Jane Smith",
  "email": "jane.smith@example.com",
  "password": "SecurePassword123!",
  "phone_number": "5559876543",
  "business_name": "Jane's Electrical",
  "service_id": 2,
  "state_id": 1,
  "city_id": 1,
  "subscription_plan_variation_id": "JDCZJQKUQOYZQI73XOMDOH3H",
  "payment_source_id": "cnon:FRESH_TOKEN_FROM_SQUARE_SDK"
}
```

### **Scenario 2: Professional with Existing Customer (Reuse)**
```json
{
  "name": "Bob Johnson",
  "email": "bob.johnson@example.com",
  "password": "SecurePassword123!",
  "phone_number": "5551112233",
  "business_name": "Bob's HVAC",
  "service_id": 3,
  "state_id": 1,
  "city_id": 1,
  "subscription_plan_variation_id": "JDCZJQKUQOYZQI73XOMDOH3H",
  "payment_source_id": "cnon:FRESH_TOKEN_FROM_SQUARE_SDK",
  "square_customer_id": "EXISTING_CUSTOMER_ID"
}
```

### **Scenario 3: Professional with Existing Card (Reuse)**
```json
{
  "name": "Alice Williams",
  "email": "alice.williams@example.com",
  "password": "SecurePassword123!",
  "phone_number": "5554445566",
  "business_name": "Alice's Cleaning",
  "service_id": 4,
  "state_id": 1,
  "city_id": 1,
  "subscription_plan_variation_id": "JDCZJQKUQOYZQI73XOMDOH3H",
  "card_id": "ccof:EXISTING_CARD_ID",
  "square_customer_id": "EXISTING_CUSTOMER_ID"
}
```

---

## 🔍 Verification Steps

### **After Step 1 (Professional Creation):**
1. Check database: `professionals` table
   - `verified_status` = `false`
   - `subscription_active` = `false`
   - `pending_subscription_plan_variation_id` = plan ID
   - `square_customer_id` = customer ID

2. Check database: `payment_methods` table
   - `professional_id` = professional ID
   - `square_card_id` = card ID (starts with `ccof:`)
   - `is_default` = `true`

3. Check Square Dashboard:
   - Customer exists with correct email
   - Card exists and is linked to customer
   - NO subscription created yet

### **After Step 2 (Verification):**
1. Check database: `professionals` table
   - `verified_status` = `true`
   - `subscription_active` = `true`
   - `square_subscription_id` = subscription ID
   - `pending_subscription_plan_variation_id` = `null`

2. Check Square Dashboard:
   - Subscription exists and is ACTIVE
   - Initial charge processed
   - Card is linked to subscription

---

## ⚠️ Common Issues & Solutions

### **Issue: Card not associated with customer**
**Symptom:** 404 when fetching customer cards
**Solution:** Check logs for card creation response - should include `customer_id`

### **Issue: INVALID_CARD error**
**Symptom:** Card doesn't belong to customer
**Solution:** Ensure card was created with correct `customer_id` in Step 1

### **Issue: Location mismatch**
**Symptom:** `LOCATION_MISMATCH` error
**Solution:** System auto-fixes by using first available location

### **Issue: Payment token expired**
**Symptom:** "token expired" or "already used"
**Solution:** Generate fresh token from Square Web Payments SDK immediately before API call

---

## 📊 Log Messages to Watch For

### **Successful Flow:**
```
✅ Creating card for customer {customer_id}
✅ Card {card_id} created successfully for customer {customer_id}
✅ VERIFIED: Card {card_id} belongs to customer {customer_id}
✅ Verified card {card_id} belongs to customer {customer_id}
✅ Subscription activated for professional {id}: {subscription_id}
```

### **Error Indicators:**
```
❌ CRITICAL: Card {card_id} was created but has NO customer_id in response!
❌ CRITICAL: Stored card_id does NOT belong to customer
❌ CRITICAL: Customer has NO cards in Square (404)
```

---

## 🎯 Quick Test Checklist

- [ ] Professional created successfully
- [ ] Square customer created/reused
- [ ] Card created and verified to belong to customer
- [ ] Payment method saved to database
- [ ] Professional verified by admin
- [ ] Subscription created and charged
- [ ] Subscription ID stored in database
- [ ] Card visible in Square dashboard under customer
- [ ] Subscription visible in Square dashboard

