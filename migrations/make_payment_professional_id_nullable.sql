-- Migration: Make professional_id nullable in payments table
-- This allows payments to be created during application process before professional account exists
-- Run this SQL in your PostgreSQL database

ALTER TABLE payments ALTER COLUMN professional_id DROP NOT NULL;

-- Verify the change
-- SELECT column_name, is_nullable 
-- FROM information_schema.columns 
-- WHERE table_name = 'payments' AND column_name = 'professional_id';

