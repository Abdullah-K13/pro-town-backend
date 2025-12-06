# Verification-Based Subscription Flow

This document outlines the complete flow for professional registration, card validation, admin verification, and subscription activation.

## 1. Professional Registration (Frontend)

**Endpoint**: `POST /auth/signup` (role="professional")

The professional registers and selects a subscription plan.

1.  **User Input**:
    *   Personal/Business details (Name, Email, etc.)
    *   Subscription Plan Selection (Monthly/Yearly)
    *   Card Details (via Square Web Payments SDK)

2.  **Frontend Action**:
    *   Tokenize card using Square SDK -> Get `source_id`.
    *   Send `source_id` and `subscription_plan_variation_id` to backend.

3.  **Backend Action**:
    *   Creates `Professional` record.
    *   Creates Square Customer.
    *   **Validates Card**: Calls `create_card_on_file` (0 charge).
    *   **Saves Card**: Stores `card_id` in `payment_methods` table.
    *   **Pending State**: Sets `pending_subscription_plan_variation_id` and `square_customer_id`.
    *   **Status**: `subscription_active = False`, `verified_status = False`.

**Result**: Professional account created, card validated and saved, but **NO CHARGE** made yet.

## 2. Admin Verification (Admin Panel)

**Endpoint**: `PUT /professionals/{id}`

The admin reviews the professional's details and documents.

1.  **Admin Action**:
    *   Admin clicks "Verify" button.
    *   Frontend sends `{ "verified_status": true }`.

2.  **Backend Action**:
    *   Updates `verified_status = True`.
    *   **Checks for Pending Subscription**: Sees `pending_subscription_plan_variation_id`.
    *   **Retrieves Payment Method**: Gets default card from `payment_methods`.
    *   **Activates Subscription**: Calls Square `create_subscription` API.
        *   **CHARGE HAPPENS HERE**: Square charges the card immediately.
    *   **Updates Professional**:
        *   `subscription_active = True`
        *   `square_subscription_id = "sub_..."` (Saved for future management)
        *   `pending_subscription_plan_variation_id = None`

**Result**: Professional is verified, subscription is active, and card is charged.

## 3. Subscription Management (Professional Panel)

### Cancel Subscription
**Endpoint**: `POST /payments/subscriptions/{subscription_id}/cancel`

1.  **Professional Action**: Clicks "Cancel Subscription".
2.  **Backend Action**:
    *   Uses stored `square_subscription_id`.
    *   Calls Square API to cancel.
    *   Updates `subscription_active = False`.
    *   Clears `square_subscription_id`.

### Update Subscription (Upgrade/Downgrade)
**Endpoint**: `POST /payments/subscriptions/{subscription_id}/update`

1.  **Professional Action**: Selects new plan.
2.  **Backend Action**:
    *   Calls Square API to update plan variation.
    *   Updates local record (if needed).

## Key Database Fields

### `professionals` Table
*   `verified_status`: Boolean (Triggers charge when changed False -> True)
*   `subscription_active`: Boolean (Current status)
*   `pending_subscription_plan_variation_id`: String (Plan waiting to be activated)
*   `square_customer_id`: String (Link to Square customer)
*   `square_subscription_id`: String (Link to active Square subscription)

### `payment_methods` Table
*   `square_card_id`: String (The card to be charged)
*   `is_default`: Boolean (Must be true for subscription charge)
