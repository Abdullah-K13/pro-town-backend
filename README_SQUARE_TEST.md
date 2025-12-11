# Square Payment Testing

## Test Script Created

Created `test_square_payment.py` - an independent Python script for testing Square payment functionality.

## Features

### 1. **create_card_nonce(card_details)**
Creates a payment token (nonce) from card details.

**Note:** In production, card nonces should be created on the frontend using Square Web Payments SDK. This is for backend testing only.

**Test Card Numbers:**
- Visa: `4111111111111111`
- Mastercard: `5105105105105100`
- Amex: `378282246310005`

### 2. **create_customer(customer_data)**
Creates a customer in Square with email, name, phone, etc.

### 3. **attach_card_to_customer(customer_id, card_nonce)**
Attaches a card to an existing customer.

## Usage

```bash
cd c:\Users\abdul\OneDrive\Desktop\Git\protown_backend
python test_square_payment.py
```

## Requirements

The script needs:
- `squareup` package
- `python-dotenv` package  
- `.env` file with `SQUARE_ACCESS_TOKEN` and `SQUARE_LOCATION_ID`

## Example Code

```python
from test_square_payment import create_card_nonce, create_customer

# Create customer
customer_result = create_customer({
    "email": "test@example.com",
    "given_name": "John",
    "family_name": "Doe"
})

# Tokenize card
card_result = create_card_nonce({
    "card_number": "4111111111111111",
    "exp_month": 12,
    "exp_year": 2025,
    "cvv": "123",
    "postal_code": "12345"
})

print(f"Customer ID: {customer_result['customer_id']}")
print(f"Card Nonce: {card_result['nonce']}")
```
