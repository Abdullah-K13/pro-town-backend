import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routers.payment import create_square_subscription, CreateSubscriptionRequest

class TestSubscriptionCreation(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_payload = None  # No auth by default

    @patch('routers.payment.create_subscription')
    def test_direct_customer_and_card(self, mock_create_subscription):
        """Test creating subscription with direct customer_id and card_id"""
        # Setup mock return
        mock_create_subscription.return_value = {
            "success": True,
            "subscription": {"id": "sub_123"},
            "subscription_id": "sub_123",
            "status": "ACTIVE"
        }

        # Request with direct customer_id and card_id
        request = CreateSubscriptionRequest(
            plan_variation_id="plan_var_123",
            card_id="ccof_123",
            customer_id="cust_123",
            location_id="loc_123"
        )

        # Call function
        response = create_square_subscription(
            request=request,
            db=self.mock_db,
            payload=None  # No auth
        )

        # Verify response
        self.assertTrue(response["success"])
        self.assertEqual(response["customer_id"], "cust_123")
        self.assertEqual(response["subscription_id"], "sub_123")

        # Verify create_subscription was called with correct args
        mock_create_subscription.assert_called_once_with(
            customer_id="cust_123",
            location_id="loc_123",
            plan_variation_id="plan_var_123",
            source_id=None,
            card_id="ccof_123",
            idempotency_key=None
        )

    @patch('routers.payment.create_subscription')
    @patch('routers.payment.create_card_on_file')
    def test_direct_customer_and_source(self, mock_create_card, mock_create_subscription):
        """Test creating subscription with customer_id and source_id (new card)"""
        # Setup mock returns
        # Note: In the actual implementation, create_subscription handles source_id -> card_id conversion
        # internally if source_id is passed. However, our router passes source_id to create_subscription
        # so we just need to verify that call.
        
        mock_create_subscription.return_value = {
            "success": True,
            "subscription": {"id": "sub_456"},
            "subscription_id": "sub_456",
            "status": "ACTIVE"
        }

        # Request with customer_id and source_id
        request = CreateSubscriptionRequest(
            plan_variation_id="plan_var_456",
            source_id="cnon:card-nonce-123",
            customer_id="cust_456",
            location_id="loc_456"
        )

        # Call function
        response = create_square_subscription(
            request=request,
            db=self.mock_db,
            payload=None
        )

        # Verify
        self.assertTrue(response["success"])
        mock_create_subscription.assert_called_once_with(
            customer_id="cust_456",
            location_id="loc_456",
            plan_variation_id="plan_var_456",
            source_id="cnon:card-nonce-123",
            card_id=None,
            idempotency_key=None
        )

    def test_missing_payment_method(self):
        """Test error when no payment method provided"""
        request = CreateSubscriptionRequest(
            plan_variation_id="plan_var_123",
            customer_id="cust_123"
        )
        
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as cm:
            create_square_subscription(
                request=request,
                db=self.mock_db,
                payload=None
            )
        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("Either source_id (new card) or card_id (saved card) must be provided", cm.exception.detail)

if __name__ == '__main__':
    unittest.main()
