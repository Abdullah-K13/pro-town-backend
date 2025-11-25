# Verification-Based Subscription Flow

## Overview

This document describes the new subscription flow where professionals register with card details, but are **not charged until admin verifies them**.

---

## Flow Summary

### Registration (No Charge)
1. Professional registers with card details
2. Card is **validated** (checked for validity)
3. Card is **saved** securely in Square
4. Subscription plan is **stored** for later
5. **NO CHARGE** occurs
6. Professional account created with `verified_status = False`

### Admin Verification (Charge Happens)
1. Admin reviews professional's application
2. Admin sets `verified_status = True`
3. System automatically:
   - Creates Square subscription
   - **Charges the card** (first payment)
   - Sets up automatic recurring payments
   - Sets `subscription_active = True`

---

## Database Changes

### New Fields in `professionals` Table

1. **`pending_subscription_plan_variation_id`** (VARCHAR(255), nullable)
   - Stores the Square subscription plan variation ID selected during registration
   - Cleared when subscription is activated
   - Values: `"LYIAHPLNYRD3AX5FPCDDYDV3"` (Monthly) or `"VGMYZYBSVKPM3CJWYK35FS7N"` (Yearly)

2. **`square_customer_id`** (VARCHAR(255), nullable)
   - Stores the Square customer ID for payment processing
   - Used when creating subscription after verification

### Migration

Run the migration script:
```sql
-- See migrations/add_pending_subscription_fields.sql
ALTER TABLE professionals 
ADD COLUMN IF NOT EXISTS pending_subscription_plan_variation_id VARCHAR(255);

ALTER TABLE professionals 
ADD COLUMN IF NOT EXISTS square_customer_id VARCHAR(255);
```

---

## API Endpoints

### 1. Professional Registration

**Endpoint**: `POST /auth/signup?role=professional`

**Request Body**:
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "password": "password123",
  "phone_number": "1234567890",
  "subscription_plan_variation_id": "LYIAHPLNYRD3AX5FPCDDYDV3",
  "payment_source_id": "cnon:card-token-from-square",
  "location_id": "L630MQ9S2T49X"
}
```

**What Happens**:
- ✅ Professional account created
- ✅ Square customer created
- ✅ Card validated and saved (no charge)
- ✅ Subscription plan stored
- ❌ **NO subscription created**
- ❌ **NO charge made**

**Response**:
```json
{
  "message": "Professional created successfully",
  "access_token": "...",
  "user": {...},
  "subscription": {
    "subscription_created": false,
    "card_validated": true,
    "card_saved": true,
    "plan_name": "Pro Town Network Monthly",
    "message": "Card validated and saved. Subscription will be activated when admin verifies your account. No charge has been made yet."
  }
}
```

---

### 2. Admin Verification

**Endpoint**: `PUT /professional/{professional_id}`

**Request Body**:
```json
{
  "verified_status": true
}
```

**What Happens**:
- ✅ Professional verified
- ✅ System checks for pending subscription
- ✅ Creates Square subscription
- ✅ **Charges card immediately** (first payment)
- ✅ Sets up automatic recurring payments
- ✅ Sets `subscription_active = True`

**Response**:
```json
{
  "id": 123,
  "name": "John Doe",
  "email": "john@example.com",
  "verified_status": true,
  "subscription_active": true,
  ...
}
```

---

## Step-by-Step Flow

### Step 1: Professional Registers

```
Professional fills form
    ↓
Enters card details
    ↓
Square tokenizes card → source_id
    ↓
POST /auth/signup
    ↓
✅ Create Professional account
✅ Create Square customer
✅ Create card on file (validates card)
✅ Save card_id to PaymentMethod table
✅ Store subscription_plan_variation_id
✅ Set verified_status = False
✅ Set subscription_active = False
    ↓
❌ NO subscription created
❌ NO charge made
```

### Step 2: Admin Verifies

```
Admin reviews application
    ↓
Admin sets verified_status = True
    ↓
PUT /professional/{id}
    ↓
System detects verification
    ↓
✅ Get saved card_id
✅ Get pending_subscription_plan_variation_id
✅ Create Square subscription
✅ 💳 CHARGE CARD (first payment)
✅ Set subscription_active = True
✅ Clear pending_subscription_plan_variation_id
    ↓
✅ Subscription active
✅ Recurring payments set up
```

---

## Important Points

### ✅ Benefits

1. **No Charge Until Verified**: Professionals aren't charged until admin approves
2. **Early Card Validation**: Invalid cards are caught during registration
3. **Admin Control**: Admin decides when to activate subscription
4. **Secure**: Cards stored securely in Square (PCI compliant)

### ⚠️ Considerations

1. **Card Expiration**: If verification takes too long, card might expire
2. **Failed Charge**: If card fails when verified, subscription won't activate
3. **Rejection**: If professional is rejected, card is saved but never used

### 🔄 Error Handling

- **Card Validation Fails**: Professional account created, but card not saved
- **Subscription Creation Fails**: Professional verified, but subscription not activated (can retry)
- **Payment Fails**: Professional verified, but charge fails (admin can retry)

---

## Testing

### Test Registration (No Charge)

```bash
curl -X POST "http://localhost:8000/auth/signup?role=professional" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "password": "password123",
    "subscription_plan_variation_id": "LYIAHPLNYRD3AX5FPCDDYDV3",
    "payment_source_id": "cnon:card-nonce-ok",
    "location_id": "L630MQ9S2T49X"
  }'
```

**Expected**: Account created, card validated, **NO charge**

### Test Verification (Charge Happens)

```bash
curl -X PUT "http://localhost:8000/professional/123" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -d '{
    "verified_status": true
  }'
```

**Expected**: Professional verified, subscription created, **CHARGE MADE**

---

## Database State Examples

### After Registration
```sql
SELECT id, email, verified_status, subscription_active, 
       pending_subscription_plan_variation_id, square_customer_id
FROM professionals
WHERE id = 123;

-- Result:
-- verified_status = false
-- subscription_active = false
-- pending_subscription_plan_variation_id = "LYIAHPLNYRD3AX5FPCDDYDV3"
-- square_customer_id = "customer-id-from-square"
```

### After Verification
```sql
SELECT id, email, verified_status, subscription_active, 
       pending_subscription_plan_variation_id, square_customer_id
FROM professionals
WHERE id = 123;

-- Result:
-- verified_status = true
-- subscription_active = true
-- pending_subscription_plan_variation_id = NULL (cleared)
-- square_customer_id = "customer-id-from-square"
```

---

## Frontend Integration

### Registration Form
```javascript
// 1. Collect professional info
// 2. Collect subscription plan selection
// 3. Tokenize card with Square
// 4. Send to signup endpoint
// 5. Show message: "Card validated. Subscription will activate when verified."
```

### Admin Dashboard
```javascript
// 1. Show pending professionals
// 2. Admin reviews and verifies
// 3. System automatically creates subscription
// 4. Show success: "Professional verified. Subscription activated."
```

---

## Summary

- ✅ **Registration**: Card validated, saved, but **NO charge**
- ✅ **Verification**: Admin verifies → Subscription created → **CHARGE HAPPENS**
- ✅ **Automatic**: Recurring payments set up automatically
- ✅ **Secure**: Cards stored securely in Square
- ✅ **Flexible**: Admin controls when charging starts

---

## Migration Required

**Before using this flow**, run the database migration:

```bash
# Connect to your database and run:
psql -d your_database -f migrations/add_pending_subscription_fields.sql
```

Or manually:
```sql
ALTER TABLE professionals 
ADD COLUMN IF NOT EXISTS pending_subscription_plan_variation_id VARCHAR(255);

ALTER TABLE professionals 
ADD COLUMN IF NOT EXISTS square_customer_id VARCHAR(255);
```

