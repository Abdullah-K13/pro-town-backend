# Square Environment Setup Guide

## Overview

Square has two environments:
- **Sandbox**: For testing with test cards (no real money)
- **Production**: For real transactions with real credit cards

## Important: Test Cards Only Work in Sandbox

❌ **You CANNOT use test cards in production**
- Test cards like `4111 1111 1111 1111` will be **declined** in production
- Production requires **real credit cards** with real money

✅ **Test cards ONLY work in sandbox**
- Use sandbox for development and testing
- No real money is charged
- Perfect for testing subscription flows

---

## How to Switch Environments

### Option 1: Update `.env` File (Recommended)

Edit your `.env` file and change:

```env
# For Testing (Sandbox)
SQUARE_ENVIRONMENT=sandbox
SQUARE_ACCESS_TOKEN=your_sandbox_access_token
SQUARE_LOCATION_ID=your_sandbox_location_id

# For Production (Real Transactions)
# SQUARE_ENVIRONMENT=production
# SQUARE_ACCESS_TOKEN=your_production_access_token
# SQUARE_LOCATION_ID=your_production_location_id
```

### Option 2: Set Environment Variable Directly

**Windows (PowerShell):**
```powershell
$env:SQUARE_ENVIRONMENT="sandbox"
```

**Windows (CMD):**
```cmd
set SQUARE_ENVIRONMENT=sandbox
```

**Linux/Mac:**
```bash
export SQUARE_ENVIRONMENT=sandbox
```

---

## Getting Sandbox Credentials

1. **Go to Square Developer Dashboard**: https://developer.squareup.com/apps
2. **Select your application**
3. **Go to "Credentials" tab**
4. **Copy "Sandbox" credentials**:
   - Access Token (starts with `sandbox-sq0atb-...`)
   - Location ID (starts with `L...`)

---

## Test Cards for Sandbox

### Successful Payment Cards

| Card Number | CVV | Expiry | ZIP | Result |
|------------|-----|--------|-----|--------|
| `4111 1111 1111 1111` | Any 3 digits | Any future date | Any 5 digits | ✅ Success |
| `4000 0000 0000 0002` | Any 3 digits | Any future date | Any 5 digits | ❌ Declined |
| `4000 0000 0000 9995` | Any 3 digits | Any future date | Any 5 digits | ❌ Insufficient Funds |

### Example Test Card
- **Card Number**: `4111 1111 1111 1111`
- **CVV**: `123`
- **Expiry**: `12/26` (or any future date)
- **ZIP**: `12345` (or any 5 digits)

---

## Current Environment Check

Your current environment is determined by the `SQUARE_ENVIRONMENT` variable in your `.env` file.

**To check your current environment:**
```python
import os
print(os.getenv("SQUARE_ENVIRONMENT", "production"))
```

Or check your `.env` file directly.

---

## When to Use Each Environment

### Use Sandbox When:
- ✅ Developing and testing your application
- ✅ Testing subscription flows
- ✅ Testing payment processing
- ✅ Testing error handling
- ✅ Demo/testing with clients
- ✅ Learning Square API

### Use Production When:
- ✅ Ready to accept real payments
- ✅ Launching to real users
- ✅ Processing actual transactions
- ✅ Going live

---

## Switching Between Environments

### For Testing (Right Now):
1. Open your `.env` file
2. Change:
   ```
   SQUARE_ENVIRONMENT=sandbox
   ```
3. Make sure you have **sandbox** access token:
   ```
   SQUARE_ACCESS_TOKEN=sandbox-sq0atb-...
   SQUARE_LOCATION_ID=your_sandbox_location_id
   ```
4. Restart your FastAPI server
5. Test with test cards

### For Production (When Ready):
1. Open your `.env` file
2. Change:
   ```
   SQUARE_ENVIRONMENT=production
   ```
3. Make sure you have **production** access token:
   ```
   SQUARE_ACCESS_TOKEN=EAAABlxyz... (production token)
   SQUARE_LOCATION_ID=your_production_location_id
   ```
4. Restart your FastAPI server
5. Use real credit cards

---

## Important Notes

1. **Different Credentials**: Sandbox and Production use different:
   - Access Tokens
   - Location IDs
   - Application IDs

2. **Different Data**: 
   - Sandbox data is separate from production
   - Subscriptions created in sandbox won't appear in production
   - Customers are separate

3. **No Real Money in Sandbox**:
   - All transactions are simulated
   - No actual charges occur
   - Perfect for testing

4. **Real Money in Production**:
   - All transactions are real
   - Real charges occur
   - Use only when ready

---

## Quick Test

After switching to sandbox, test with:

```bash
curl -X POST "http://localhost:8000/auth/signup?role=professional" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "password": "password123",
    "subscription_plan_variation_id": "LYIAHPLNYRD3AX5FPCDDYDV3",
    "payment_source_id": "cnon:card-nonce-ok",
    "location_id": "your_sandbox_location_id"
  }'
```

**Note**: The `payment_source_id` should come from Square Web Payments SDK using test card `4111 1111 1111 1111`.

---

## Troubleshooting

### Error: "Invalid card number"
- **Cause**: Using test card in production
- **Solution**: Switch to sandbox environment

### Error: "Card declined"
- **Cause**: Using declined test card (`4000 0000 0000 0002`)
- **Solution**: Use success test card (`4111 1111 1111 1111`)

### Error: "Invalid access token"
- **Cause**: Using production token in sandbox (or vice versa)
- **Solution**: Use matching credentials for your environment

---

## Summary

- **For Testing**: Use `SQUARE_ENVIRONMENT=sandbox` with test cards
- **For Production**: Use `SQUARE_ENVIRONMENT=production` with real cards
- **Test cards ONLY work in sandbox**
- **Always test thoroughly in sandbox before going to production**

