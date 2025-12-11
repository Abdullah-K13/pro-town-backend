# Square Frontend SDK Test

## Test File Created

Created `test_square_frontend.html` - a standalone HTML file to test Square Web Payments SDK from the frontend.

## Setup Instructions

### 1. Get Your Square Application ID

1. Go to https://developer.squareup.com/apps
2. Select your application (or create one)
3. Copy your **Sandbox Application ID**
4. Open `test_square_frontend.html` and replace:
   ```javascript
   const APPLICATION_ID = 'sandbox-sq0idb-YOUR_APP_ID_HERE';
   ```

### 2. Run the Test File

Simply open the HTML file in your browser:
```bash
# Option 1: Double-click the file
test_square_frontend.html

# Option 2: Open with browser
start test_square_frontend.html  # Windows
open test_square_frontend.html   # Mac
```

## What It Does

1. **Displays a payment form** with:
   - Customer email input
   - Cardholder name input
   - Square card input (handles card number, expiration, CVV, ZIP)

2. **Tokenizes the card** when you click "Tokenize Card"

3. **Displays results**:
   - ✅ Card Token (nonce) - Use this for payments
   - Card Brand (Visa, Mastercard, etc.)
   - Last 4 digits
   - Expiration date
   - Postal code
   - Customer info

## Test Cards (Sandbox)

- **Visa:** 4111 1111 1111 1111
- **Mastercard:** 5105 1051 0510 5100
- **Amex:** 3782 822463 10005

**For all cards:**
- Expiration: Any future date
- CVV: Any 3-4 digits
- ZIP: Any 5 digits

## Next Steps

After getting the token, you can:
1. Send it to your backend
2. Use it to create a payment
3. Save it as a card on file for a customer

## Important Notes

- ⚠️ **Sandbox Mode**: This uses Square's sandbox environment
- 🔒 **Never store card details**: Only store the token
- 📱 **Production**: Change to production app ID for live cards
