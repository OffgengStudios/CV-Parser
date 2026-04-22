#!/bin/bash
# setup_postgres.sh — Quick PostgreSQL setup script

set -e

echo "=== CV System PostgreSQL Setup ==="
echo ""

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL is not installed."
    echo "Please install from: https://www.postgresql.org/download/"
    exit 1
fi

echo "✓ PostgreSQL found"

# Get database credentials
read -p "Enter PostgreSQL superuser (default: postgres): " PG_USER
PG_USER=${PG_USER:-postgres}

read -sp "Enter PostgreSQL superuser password: " PG_PASSWORD
echo ""

read -p "Enter new database name (default: cv_system): " DB_NAME
DB_NAME=${DB_NAME:-cv_system}

read -p "Enter database username (default: cv_user): " DB_USER
DB_USER=${DB_USER:-cv_user}

read -sp "Enter database user password: " DB_USER_PASSWORD
echo ""

# Create database and user
echo ""
echo "Creating database and user..."

PGPASSWORD=$PG_PASSWORD psql -U "$PG_USER" -h localhost <<EOF
CREATE DATABASE $DB_NAME;
CREATE USER $DB_USER WITH PASSWORD '$DB_USER_PASSWORD';
ALTER ROLE $DB_USER SET client_encoding TO 'utf8';
ALTER ROLE $DB_USER SET default_transaction_isolation TO 'read committed';
ALTER ROLE $DB_USER SET default_transaction_deferrable TO on;
ALTER ROLE $DB_USER SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
EOF

echo "✓ Database and user created"

# Update .env file
ENV_FILE=".env"
if [ -f "$ENV_FILE" ]; then
    echo ""
    echo "Updating $ENV_FILE..."

    # Create new connection string
    CONNECTION_STRING="postgresql://$DB_USER:$DB_USER_PASSWORD@localhost:5432/$DB_NAME"

    # Update or add DATABASE_URL
    if grep -q "^DATABASE_URL=" "$ENV_FILE"; then
        sed -i.bak "s|^DATABASE_URL=.*|DATABASE_URL=$CONNECTION_STRING|" "$ENV_FILE"
    else
        echo "DATABASE_URL=$CONNECTION_STRING" >> "$ENV_FILE"
    fi

    echo "✓ .env file updated"
fi

# Install dependencies
echo ""
read -p "Install Python dependencies? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    pip install -r requirements.txt
    echo "✓ Dependencies installed"
fi

# Run migrations
echo ""
read -p "Run database migrations? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    alembic upgrade head
    echo "✓ Migrations completed"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Connection details:"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo "  Host: localhost:5432"
echo ""
echo "Connection string:"
echo "  $CONNECTION_STRING"
echo ""
echo "Start the app with: python main.py"
