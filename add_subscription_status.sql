-- Add subscription_status column to professionals table
ALTER TABLE professionals ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(50);

-- Update existing records based on subscription_active
UPDATE professionals 
SET subscription_status = CASE 
    WHEN subscription_active = true THEN 'ACTIVE'
    ELSE NULL
END
WHERE subscription_status IS NULL;
