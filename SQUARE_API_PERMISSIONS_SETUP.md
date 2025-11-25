# Square API Permissions Setup Guide

## How to Check and Update Square API Permissions

### Step 1: Access Square Developer Dashboard

1. Go to [Square Developer Dashboard](https://developer.squareup.com/apps)
2. Log in with your Square account
3. Select your application

### Step 2: Check OAuth Scopes

1. In your application dashboard, go to **OAuth** section
2. Check the **OAuth Scopes** that are enabled
3. For catalog/subscription access, you need:
   - `ITEMS_READ` - To read catalog items
   - `ITEMS_WRITE` - To write catalog items (if needed)
   - `SUBSCRIPTIONS_READ` - To read subscriptions
   - `SUBSCRIPTIONS_WRITE` - To write subscriptions (if needed)

### Step 3: Update OAuth Scopes

1. Click **Edit** on OAuth settings
2. Enable the required scopes:
   - ✅ `ITEMS_READ`
   - ✅ `SUBSCRIPTIONS_READ`
   - ✅ `SUBSCRIPTIONS_WRITE` (if you need to create subscriptions)
3. **Save** the changes

### Step 4: Regenerate Access Token

**Important:** After changing OAuth scopes, you MUST regenerate your access token!

1. Go to **OAuth** section
2. Click **Regenerate** or **Create Token**
3. Copy the new **Access Token**
4. Update your `.env` file:
   ```
   SQUARE_ACCESS_TOKEN=your_new_access_token_here
   ```

### Step 5: Verify Token Permissions

You can test if your token has the right permissions by calling:
```bash
GET /payments/catalog/debug
```

If you still get 404, the issue might be:
- No catalog objects exist yet
- Token is for wrong environment (sandbox vs production)
- Location ID mismatch

## Required Permissions for Payment Endpoints

### For Catalog/Subscription Access:
- `ITEMS_READ` - **Required** for fetching subscription plans and items
- `SUBSCRIPTIONS_READ` - **Required** for reading subscription data

### For Payment Processing:
- `PAYMENTS_WRITE` - **Required** for processing payments
- `PAYMENTS_READ` - **Required** for reading payment status

### For Card Management:
- `CUSTOMERS_WRITE` - **Required** for saving payment methods
- `CUSTOMERS_READ` - **Required** for reading customer data

## Common Issues

### Issue 1: "Resource not found" after adding permissions
**Solution:** Regenerate your access token after changing scopes

### Issue 2: Token works but no subscription plans found
**Solution:** 
- Check if subscription plans exist in Square Dashboard → Catalog
- Verify you're using the correct environment (sandbox vs production)
- Ensure plans are published/active

### Issue 3: Different environments
**Solution:** Make sure:
- `SQUARE_ENVIRONMENT` in `.env` matches where you created plans
- `SQUARE_ACCESS_TOKEN` is for the same environment
- Sandbox token won't see production catalog and vice versa

## Testing Your Permissions

After updating permissions and regenerating token:

1. **Test Catalog Access:**
   ```bash
   GET /payments/catalog/debug
   ```
   Should return all catalog object types

2. **Test Subscription Plans:**
   ```bash
   GET /payments/subscription-plans
   ```
   Should return your subscription plans (if they exist)

3. **Test Payment Processing:**
   ```bash
   POST /payments/process-application
   ```
   Should process payments successfully

## Quick Checklist

- [ ] OAuth scopes include `ITEMS_READ`
- [ ] OAuth scopes include `SUBSCRIPTIONS_READ`
- [ ] Access token regenerated after scope changes
- [ ] `.env` file updated with new token
- [ ] Environment matches (sandbox/production)
- [ ] Subscription plans exist in Square Dashboard
- [ ] Plans are published/active

