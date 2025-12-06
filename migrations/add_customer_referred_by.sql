-- Migration: Add referred_by column to customers table
-- This allows tracking which professional referred a customer

-- Add referred_by column (Professional ID who referred this customer)
ALTER TABLE customers 
ADD COLUMN IF NOT EXISTS referred_by INTEGER NULL;

-- Add comment for documentation
COMMENT ON COLUMN customers.referred_by IS 'Professional ID who referred this customer';

