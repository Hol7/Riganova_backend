#!/bin/bash
set -e

# Wait for the database to be ready
until pg_isready -h db -p 5432 -U livraison_user; do
  echo "Waiting for postgres..."
  sleep 2
done

# Run Alembic migrations
alembic upgrade head

# Start FastAPI app
exec uvicorn app.main:app --host 0.0.0.0 --port 8000