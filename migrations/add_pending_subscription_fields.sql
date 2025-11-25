-- Migration: Add pending subscription fields to professionals table
-- This allows professionals to register with card details but not be charged until verified

-- Add pending_subscription_plan_variation_id column
ALTER TABLE professionals 
ADD COLUMN IF NOT EXISTS pending_subscription_plan_variation_id VARCHAR(255);

-- Add square_customer_id column
ALTER TABLE professionals 
ADD COLUMN IF NOT EXISTS square_customer_id VARCHAR(255);

-- Add comments for documentation
COMMENT ON COLUMN professionals.pending_subscription_plan_variation_id IS 'Square subscription plan variation ID stored during registration. Subscription will be created when professional is verified.';
COMMENT ON COLUMN professionals.square_customer_id IS 'Square customer ID for payment processing';

