# PostgreSQL Setup Guide

## Overview

Your CV system has been switched to **PostgreSQL**. This provides better performance for production deployments compared to SQLite.

## Installation

### 1. Install PostgreSQL

**Windows:**
- Download from https://www.postgresql.org/download/windows/
- Run installer and remember your password for the `postgres` user
- PostgreSQL runs on `localhost:5432` by default

**macOS:**
```bash
brew install postgresql
brew services start postgresql
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

### 2. Create Database and User

Open PostgreSQL terminal (`psql`):

```bash
# Connect to PostgreSQL
psql -U postgres

# Inside psql shell:
CREATE DATABASE cv_system;
CREATE USER cv_user WITH PASSWORD 'your_secure_password';
ALTER ROLE cv_user SET client_encoding TO 'utf8';
ALTER ROLE cv_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE cv_user SET default_transaction_deferrable TO on;
ALTER ROLE cv_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE cv_system TO cv_user;
\q
```

### 3. Update Connection String

Edit `.env` file:

```env
# Option 1: Default postgres user (development only)
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/cv_system

# Option 2: Dedicated user (recommended)
DATABASE_URL=postgresql://cv_user:your_secure_password@localhost:5432/cv_system

# Option 3: Remote PostgreSQL (e.g., AWS RDS)
DATABASE_URL=postgresql://user:pass@host:5432/cv_system
```

### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `psycopg2-binary` — PostgreSQL driver
- `scikit-learn` — For candidate matching

### 5. Run Migrations

```bash
alembic upgrade head
```

Or let the app create tables on startup (automatic via `create_tables()`).

### 6. Start the Application

```bash
python main.py
```

The app will:
- Connect to PostgreSQL
- Create tables automatically
- Listen on `http://localhost:8000`

## Verification

Check the connection:

```bash
# Via psql
psql -U postgres -d cv_system -c "SELECT version();"

# Via Python
python -c "from database.session import engine; engine.connect(); print('Connected!')"
```

## Common Connection Strings

```
PostgreSQL local:
postgresql://postgres:password@localhost:5432/cv_system

With custom port:
postgresql://user:password@localhost:5433/cv_system

AWS RDS:
postgresql://admin:password@mydb.xxxx.us-east-1.rds.amazonaws.com:5432/cv_system

Docker:
postgresql://postgres:postgres@db:5432/cv_system

Azure Database:
postgresql://user@servername:password@servername.postgres.database.azure.com:5432/cv_system
```

## Troubleshooting

### Connection Refused
```
Error: could not connect to server: Connection refused
```
- Check PostgreSQL is running: `sudo systemctl status postgresql`
- Check credentials in `DATABASE_URL`
- Check port (default 5432)

### Database Does Not Exist
```
Error: database "cv_system" does not exist
```
- Create database: `createdb cv_system`

### Permission Denied
```
Error: permission denied for schema public
```
- Grant privileges:
```sql
GRANT ALL PRIVILEGES ON SCHEMA public TO cv_user;
```

### Too Many Connections
- Increase `max_connections` in `postgresql.conf`:
```
max_connections = 200
```

## Performance Tuning

For larger datasets, optimize PostgreSQL:

```sql
-- Increase shared buffers (after restarting PostgreSQL)
ALTER SYSTEM SET shared_buffers = '256MB';

-- Create indexes for common queries
CREATE INDEX idx_candidates_category ON candidates(category);
CREATE INDEX idx_candidates_email ON candidates(email);
CREATE INDEX idx_candidates_created ON candidates(created_at);

-- Vacuum and analyze
VACUUM ANALYZE;
```

## Backup and Restore

### Backup
```bash
pg_dump -U postgres cv_system > cv_system_backup.sql
```

### Restore
```bash
psql -U postgres cv_system < cv_system_backup.sql
```

### Full Backup (Compressed)
```bash
pg_dump -U postgres -Fc cv_system > cv_system_backup.dump
```

## Files Changed

- `.env` — Updated DATABASE_URL to PostgreSQL
- `config.py` — Updated default DATABASE_URL
- `requirements.txt` — Added `psycopg2-binary` and `scikit-learn`

## Migration from SQLite (if needed)

To migrate existing SQLite data to PostgreSQL:

```bash
# 1. Backup SQLite
cp cv_system.db cv_system_backup.db

# 2. Export SQLite data
sqlite3 cv_system.db .dump > sqlite_dump.sql

# 3. Create PostgreSQL tables
alembic upgrade head

# 4. Import data (may require manual conversion due to schema differences)
# Use a migration tool or script
```

---

**You're all set!** PostgreSQL is now your database backend. The system will work exactly the same, but with better performance and scalability.
