# Production Environment Setup Guide

## ⚠️ CRITICAL: Production Configuration

This guide ensures your Square integration is correctly configured for **PRODUCTION** environment.

---

## 🔑 Environment Variables

### **Required for Production:**

```bash
# .env file
SQUARE_ACCESS_TOKEN=your_production_access_token
SQUARE_APPLICATION_ID=sq0idb-XXXXXXXXXXXX  # NO "sandbox-" prefix!
SQUARE_LOCATION_ID=LXXXXXXXXXXXXXXXX
SQUARE_ENVIRONMENT=production  # Explicitly set to production
```

### **Important Notes:**

1. **Application ID Format:**
   - ✅ Production: `sq0idb-XXXXXXXXXXXX` (no prefix)
   - ❌ Sandbox: `sandbox-sq0idb-XXXXXXXXXXXX` (has "sandbox-" prefix)
   - ⚠️ If your Application ID starts with `sandbox-`, you're using sandbox credentials!

2. **SQUARE_ENVIRONMENT:**
   - Set to `production` explicitly
   - If not set, defaults to `sandbox` in some code paths

3. **Access Token:**
   - Must be from **production** Square account
   - Get from: Square Developer Dashboard → Your App → OAuth → Production

---

## 🌐 Frontend Configuration

### **1. Square SDK Script (PRODUCTION)**

```html
<!-- ✅ CORRECT: Production SDK -->
<script type="text/javascript" src="https://web.squarecdn.com/v1/square.js"></script>

<!-- ❌ WRONG: Sandbox SDK (do NOT use in production) -->
<!-- <script type="text/javascript" src="https://sandbox.web.squarecdn.com/v1/square.js"></script> -->
```

### **2. Frontend Initialization Code**

```javascript
// Get config from backend
const config = await fetch('/payments/square-config').then(r => r.json());

// Verify it's production
if (config.application_id.startsWith('sandbox-')) {
  console.error('❌ ERROR: Backend is returning sandbox Application ID!');
  console.error('   Check your SQUARE_APPLICATION_ID environment variable');
  throw new Error('Sandbox Application ID detected in production');
}

// Initialize Square Payments (production)
const payments = Square.payments(config.application_id, config.location_id);

// Create card payment method
const card = await payments.card();
await card.attach('#card-container');
```

---

## ✅ Verification Steps

### **Step 1: Check Backend Config Endpoint**

```bash
curl http://localhost:8000/payments/square-config
```

**Expected Response (Production):**
```json
{
  "application_id": "sq0idb-XXXXXXXXXXXX",  // NO "sandbox-" prefix
  "location_id": "LXXXXXXXXXXXXXXXX"
}
```

**❌ Wrong Response (Sandbox):**
```json
{
  "application_id": "sandbox-sq0idb-XXXXXXXXXXXX",  // Has "sandbox-" prefix
  "location_id": "LXXXXXXXXXXXXXXXX"
}
```

### **Step 2: Verify Environment Variables**

```bash
# Check your .env file
cat .env | grep SQUARE

# Should show:
# SQUARE_APPLICATION_ID=sq0idb-XXXXXXXXXXXX  (no sandbox-)
# SQUARE_ENVIRONMENT=production
# SQUARE_ACCESS_TOKEN=EAA... (production token)
```

### **Step 3: Test Backend Connection**

```bash
curl http://localhost:8000/payments/test-connection
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Square API connection successful",
  "environment": "production",
  "locations_count": 1,
  "location_ids": ["LXXXXXXXXXXXXXXXX"]
}
```

---

## 🔒 Production Security Checklist

- [ ] **Access Token is from production account** (not sandbox)
- [ ] **Application ID does NOT start with `sandbox-`**
- [ ] **Using production Square Developer Dashboard** (not sandbox)
- [ ] **Location ID is from production location**
- [ ] **Environment variable `SQUARE_ENVIRONMENT=production`**
- [ ] **Frontend uses production SDK URL**
- [ ] **HTTPS enabled** (required for production)
- [ ] **Real credit cards only** (test cards won't work)

---

## 🧪 Testing in Production

### **⚠️ Important Warnings:**

1. **Real Charges:** All transactions in production are REAL and will charge real cards
2. **No Test Cards:** Test card numbers (like `4111 1111 1111 1111`) will NOT work
3. **Refunds:** You may need to issue refunds for test transactions
4. **Use Small Amounts:** Test with minimal amounts first

### **Safe Testing Approach:**

1. **Use Square's Test Mode:**
   - Some Square accounts have a "test mode" toggle
   - Check Square Dashboard settings

2. **Use Real Cards with Small Amounts:**
   - Use a real card you control
   - Test with $0.01 or $1.00
   - Issue refund immediately after test

3. **Monitor Transactions:**
   - Check Square Dashboard → Transactions
   - Verify charges appear correctly
   - Issue refunds for test transactions

---

## 🐛 Common Production Issues

### **Issue 1: "Application ID not found"**

**Cause:** Using sandbox Application ID in production

**Fix:**
```bash
# Check your .env
SQUARE_APPLICATION_ID=sq0idb-XXXXXXXXXXXX  # Remove "sandbox-" if present
```

### **Issue 2: Tokenization fails with 400**

**Cause:** Environment mismatch (sandbox SDK with production ID or vice versa)

**Fix:**
- Use production SDK: `https://web.squarecdn.com/v1/square.js`
- Use production Application ID (no `sandbox-` prefix)

### **Issue 3: "Invalid card" errors**

**Cause:** Using test card numbers in production

**Fix:**
- Use REAL credit cards only
- Test cards only work in sandbox

### **Issue 4: CORS errors**

**Cause:** Production domain not whitelisted

**Fix:**
- Add your production domain to Square Dashboard
- Check CORS settings in Square Developer Dashboard

---

## 📊 Production vs Sandbox Comparison

| Feature | Production | Sandbox |
|---------|-----------|---------|
| **Application ID** | `sq0idb-...` | `sandbox-sq0idb-...` |
| **SDK URL** | `https://web.squarecdn.com/v1/square.js` | `https://sandbox.web.squarecdn.com/v1/square.js` |
| **API Base** | `https://connect.squareup.com` | `https://connect.squareupsandbox.com` |
| **Cards** | Real cards only | Test cards work |
| **Charges** | Real money | Fake money |
| **Access Token** | Production token | Sandbox token |
| **Dashboard** | production.squareup.com | sandbox.squareup.com |

---

## 🔍 Quick Verification Script

Add this to your frontend to verify production setup:

```javascript
async function verifyProductionSetup() {
  try {
    // 1. Get config
    const config = await fetch('/payments/square-config').then(r => r.json());
    
    // 2. Check Application ID
    if (config.application_id.startsWith('sandbox-')) {
      console.error('❌ SANDBOX Application ID detected!');
      console.error('   Application ID:', config.application_id);
      console.error('   This is a SANDBOX ID, not production!');
      return false;
    }
    
    // 3. Check SDK URL
    const scripts = Array.from(document.scripts);
    const squareScript = scripts.find(s => s.src.includes('squarecdn.com'));
    
    if (squareScript && squareScript.src.includes('sandbox')) {
      console.error('❌ SANDBOX SDK detected!');
      console.error('   SDK URL:', squareScript.src);
      console.error('   Should use: https://web.squarecdn.com/v1/square.js');
      return false;
    }
    
    // 4. Verify Square object
    if (typeof Square === 'undefined') {
      console.error('❌ Square SDK not loaded!');
      return false;
    }
    
    console.log('✅ Production setup verified!');
    console.log('   Application ID:', config.application_id);
    console.log('   Location ID:', config.location_id);
    return true;
  } catch (error) {
    console.error('❌ Verification failed:', error);
    return false;
  }
}

// Call on page load
verifyProductionSetup();
```

---

## 📞 Support

If issues persist:

1. **Check Square Status:** https://status.squareup.com/
2. **Square Developer Docs:** https://developer.squareup.com/docs
3. **Square Support:** Contact through Square Dashboard

---

## ✅ Final Checklist Before Going Live

- [ ] All environment variables set to production values
- [ ] Application ID does NOT start with `sandbox-`
- [ ] Frontend uses production SDK URL
- [ ] Backend `SQUARE_ENVIRONMENT=production`
- [ ] Tested with real card (small amount)
- [ ] Verified transaction appears in Square Dashboard
- [ ] HTTPS enabled
- [ ] CORS configured for production domain
- [ ] Error handling implemented
- [ ] Logging enabled for debugging

