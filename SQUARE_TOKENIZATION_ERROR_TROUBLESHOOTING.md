# Square Tokenization Error Troubleshooting

## Error: `TokenizationError: Tokenization has failed - An unknown error has occurred`

This error occurs when Square's Web Payments SDK fails to tokenize a card on the frontend.

---

## 🔍 Common Causes

### 1. **Invalid or Missing Application ID**
- Square Application ID is incorrect or missing
- Application ID doesn't match the environment (sandbox vs production)

### 2. **Environment Mismatch**
- Using sandbox Application ID with production Square
- Using production Application ID with sandbox Square

### 3. **Invalid Card Data**
- Card number is invalid or test card not recognized
- Expiry date is invalid
- CVV is invalid

### 4. **Network/CORS Issues**
- CORS not configured properly
- Network request blocked
- SSL/TLS certificate issues

### 5. **Square SDK Configuration Issues**
- SDK not properly initialized
- Missing required configuration
- SDK version incompatibility

---

## ✅ Step-by-Step Troubleshooting

### **Step 1: Verify Square Configuration**

Check your backend endpoint returns correct config:

```bash
GET /payments/square-config
```

**Expected Response:**
```json
{
  "application_id": "sandbox-sq0idb-XXXXXXXXXXXX",
  "location_id": "LXXXXXXXXXXXXXXXX"
}
```

**Check for PRODUCTION:**
- ✅ Application ID is not empty
- ✅ Application ID does NOT start with `sandbox-` (production format: `sq0idb-XXXXXXXXXXXX`)
- ✅ Location ID is not empty
- ✅ Using production Square account (not sandbox)

---

### **Step 2: Verify Frontend SDK Initialization**

Your frontend code should look like this:

```javascript
// 1. Get config from backend
const configResponse = await fetch('/payments/square-config');
const config = await configResponse.json();

// 2. Initialize Square Payments
const payments = Square.payments(config.application_id, config.location_id);

// 3. Create card payment method
const card = await payments.card();

// 4. Attach to DOM
await card.attach('#card-container');

// 5. Tokenize on form submit
async function handleSubmit(event) {
  event.preventDefault();
  
  try {
    const tokenResult = await card.tokenize();
    if (tokenResult.status === 'OK') {
      const token = tokenResult.token;
      // Use token.token (this is your payment_source_id)
      console.log('Token:', token.token);
    } else {
      console.error('Tokenization failed:', tokenResult.errors);
    }
  } catch (error) {
    console.error('Tokenization error:', error);
  }
}
```

---

### **Step 3: Check Square Application Settings**

1. Go to [Square Developer Dashboard](https://developer.squareup.com/apps)
2. Select your application
3. Check **Application Settings**:
   - ✅ Application ID matches what you're using
   - ✅ Environment (Sandbox/Production) matches your code
   - ✅ Application is active

4. Check **OAuth** settings:
   - ✅ Required scopes are enabled
   - ✅ Access token is valid

---

### **Step 4: Verify Card Numbers**

**For PRODUCTION Environment:**
- ⚠️ **You MUST use REAL credit cards** - test cards will NOT work
- ⚠️ **Real charges will be made** - use test mode or small amounts
- ✅ Use actual credit/debit cards from users
- ✅ Cards must be valid and have sufficient funds

**For SANDBOX Environment (testing only):**
- `4111 1111 1111 1111` - Visa (always succeeds)
- `4000 0000 0000 0002` - Visa (declined)
- `5555 5555 5555 4444` - Mastercard (always succeeds)
- `3782 822463 10005` - American Express (always succeeds)

**Card Details:**
- **CVV:** Real CVV for production, any 3-4 digits for sandbox
- **Expiry:** Real future date for production, any future date for sandbox
- **ZIP:** Real ZIP code for production, any 5 digits for sandbox

---

### **Step 5: Check Browser Console for Detailed Errors**

Open browser DevTools (F12) and check:

1. **Console Tab:**
   - Look for detailed error messages
   - Check for CORS errors
   - Check for network errors

2. **Network Tab:**
   - Find the `card-nonce` request
   - Check request payload
   - Check response status and body
   - Look for error details in response

---

### **Step 6: Verify Square SDK Script Loading**

Make sure Square SDK is loaded correctly:

```html
<!-- For PRODUCTION (use this) -->
<script type="text/javascript" src="https://web.squarecdn.com/v1/square.js"></script>

<!-- For SANDBOX (do NOT use in production) -->
<!-- <script type="text/javascript" src="https://sandbox.web.squarecdn.com/v1/square.js"></script> -->
```

**Check:**
- ✅ Script loads without errors
- ✅ `Square` object is available in console
- ✅ Using PRODUCTION SDK URL: `https://web.squarecdn.com/v1/square.js`
- ❌ NOT using sandbox URL in production

---

## 🐛 Common Issues & Solutions

### **Issue 1: "Application ID not found"**

**Symptom:** 400 error with message about application ID

**Solution:**
```javascript
// Verify application ID is correct
console.log('Application ID:', config.application_id);

// Make sure it's not undefined or empty
if (!config.application_id) {
  console.error('Application ID is missing!');
}
```

---

### **Issue 2: Environment Mismatch**

**Symptom:** Works in sandbox but not production (or vice versa)

**Solution for PRODUCTION:**
```javascript
// For PRODUCTION - always use production SDK
const sdkUrl = 'https://web.squarecdn.com/v1/square.js';

// Verify Application ID is NOT sandbox
if (config.application_id.startsWith('sandbox-')) {
  console.error('❌ ERROR: Using sandbox Application ID in production!');
  console.error('   Application ID:', config.application_id);
  console.error('   This will cause tokenization to fail.');
  // Don't proceed - fix Application ID first
}

// Production Application IDs should NOT start with "sandbox-"
// Example: "sq0idb-XXXXXXXXXXXX" (no "sandbox-" prefix)
```

---

### **Issue 3: CORS Errors**

**Symptom:** CORS policy errors in console

**Solution:**
- Ensure your backend allows CORS from your frontend domain
- Check Square's CORS settings in dashboard
- Verify frontend domain is whitelisted

---

### **Issue 4: Invalid Card Data**

**Symptom:** Tokenization fails with specific card

**Solution:**
```javascript
// Validate card before tokenization
const cardData = await card.getCardData();
console.log('Card data:', cardData);

// Check if card is valid
if (!cardData) {
  console.error('Card data is invalid');
  return;
}
```

---

### **Issue 5: SDK Not Initialized**

**Symptom:** `Square is not defined` or `payments is not a function`

**Solution:**
```javascript
// Wait for SDK to load
if (typeof Square === 'undefined') {
  console.error('Square SDK not loaded!');
  // Wait and retry or show error to user
  return;
}

// Verify payments object
if (!Square.payments) {
  console.error('Square.payments not available!');
  return;
}
```

---

## 🔧 Debug Code Template

Use this template to debug tokenization:

```javascript
async function debugTokenization() {
  try {
    // Step 1: Get config
    console.log('Step 1: Fetching config...');
    const configResponse = await fetch('/payments/square-config');
    const config = await configResponse.json();
    console.log('Config:', config);
    
    if (!config.application_id) {
      throw new Error('Application ID missing from config');
    }
    
    // Step 2: Check Square SDK
    console.log('Step 2: Checking Square SDK...');
    if (typeof Square === 'undefined') {
      throw new Error('Square SDK not loaded');
    }
    console.log('Square SDK loaded:', typeof Square.payments);
    
    // Step 3: Initialize payments
    console.log('Step 3: Initializing payments...');
    const payments = Square.payments(config.application_id, config.location_id);
    console.log('Payments initialized:', payments);
    
    // Step 4: Create card
    console.log('Step 4: Creating card payment method...');
    const card = await payments.card();
    console.log('Card created:', card);
    
    // Step 5: Get card data
    console.log('Step 5: Getting card data...');
    const cardData = await card.getCardData();
    console.log('Card data:', cardData);
    
    // Step 6: Tokenize
    console.log('Step 6: Tokenizing card...');
    const tokenResult = await card.tokenize();
    console.log('Token result:', tokenResult);
    
    if (tokenResult.status === 'OK') {
      console.log('✅ Success! Token:', tokenResult.token.token);
      return tokenResult.token.token;
    } else {
      console.error('❌ Tokenization failed:', tokenResult.errors);
      throw new Error('Tokenization failed: ' + JSON.stringify(tokenResult.errors));
    }
  } catch (error) {
    console.error('❌ Error in tokenization:', error);
    console.error('Error details:', {
      message: error.message,
      stack: error.stack,
      name: error.name
    });
    throw error;
  }
}
```

---

## 📋 Production Environment Checklist

Before reporting the issue, verify:

- [ ] **Application ID is correct and not empty**
- [ ] **Application ID does NOT start with `sandbox-`** (production format: `sq0idb-XXXXXXXXXXXX`)
- [ ] **Location ID is correct and not empty**
- [ ] **Square SDK script is loaded from PRODUCTION URL:** `https://web.squarecdn.com/v1/square.js`
- [ ] **NOT using sandbox SDK URL** (`https://sandbox.web.squarecdn.com/v1/square.js`)
- [ ] **Using REAL credit cards** (test cards don't work in production)
- [ ] **Card expiry is in the future**
- [ ] **CVV is provided and correct**
- [ ] **ZIP code is provided and correct**
- [ ] **No CORS errors in console**
- [ ] **Network requests are not blocked**
- [ ] **Browser console shows detailed error**
- [ ] **Square Developer Dashboard shows app is active**
- [ ] **Environment variable `SQUARE_ENVIRONMENT=production`** (or not set, defaults to sandbox)
- [ ] **Using production Square account credentials**

---

## 🆘 Still Having Issues?

1. **Check Square Status:**
   - Visit [Square Status Page](https://status.squareup.com/)
   - Check for any ongoing issues

2. **Review Square Documentation:**
   - [Web Payments SDK Guide](https://developer.squareup.com/docs/web-payments/overview)
   - [Tokenization Errors](https://developer.squareup.com/docs/web-payments/take-card-payment#handle-errors)

3. **Check Square Developer Forums:**
   - Search for similar issues
   - Post your error details (without sensitive data)

4. **Contact Square Support:**
   - If issue persists, contact Square support with:
     - Application ID
     - Error message
     - Request/response details (from Network tab)
     - Environment (sandbox/production)

---

## 🔐 Security Notes

- ⚠️ Never log full card numbers
- ⚠️ Never send card data to your backend directly
- ✅ Always use Square SDK to tokenize cards
- ✅ Only send tokens (not card data) to your backend
- ✅ Tokens are single-use and expire quickly

