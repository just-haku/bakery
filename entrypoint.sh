#!/bin/bash
set -e

echo "=== BAKERY MANAGEMENT SYSTEM ==="
echo "Waiting for MySQL database ($DB_HOST:$DB_PORT)..."

max_tries=30
count=0
until nc -z -v -w30 "$DB_HOST" "$DB_PORT" > /dev/null 2>&1 || [ $count -ge $max_tries ]; do
    echo "MySQL is unavailable - sleeping 1s ($count/$max_tries)"
    sleep 1
    count=$((count+1))
done

if [ $count -ge $max_tries ]; then
    echo "Error: MySQL database did not become available in time."
    exit 1
fi

echo "MySQL is up and running!"

# Make and apply database migrations
echo "Generating and applying database migrations..."
python manage.py makemigrations authentication products custom_orders kitchen_bom pos dashboard inventory --noinput
python manage.py migrate --noinput

# Collect static files if in production mode
if [ "$DEBUG" = "False" ] || [ "$DEBUG" = "false" ] || [ "$DEBUG" = "0" ]; then
    echo "Collecting static files for production..."
    python manage.py collectstatic --noinput --clear || true
fi

echo "Starting application with command: $@"
exec "$@"
