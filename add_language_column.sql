-- Migration: Add language column to episodes table
-- Run this SQL script on your database to add the language column

-- Add language column if it doesn't exist
ALTER TABLE episodes 
ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'en' NOT NULL;

-- Update existing rows to have default language
UPDATE episodes 
SET language = 'en' 
WHERE language IS NULL;

