#!/bin/bash
# Run database migration to add indexes
# Usage: ./run_migration.sh

# Convert asyncpg URL to standard postgresql URL
# Replace postgresql+asyncpg:// with postgresql://
# Replace ssl=require with sslmode=require

DATABASE_URL="postgresql://neondb_owner:npg_K4PJwc3WzpGD@ep-small-breeze-adf9631c-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"

echo "Running database migration to add indexes..."
psql "$DATABASE_URL" -f add_indexes.sql

if [ $? -eq 0 ]; then
    echo "✅ Migration completed successfully!"
else
    echo "❌ Migration failed. Check the error above."
    exit 1
fi

