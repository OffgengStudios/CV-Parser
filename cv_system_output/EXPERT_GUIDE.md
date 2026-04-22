# EXPERT GUIDE: Running the CV Parser System

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│              FastAPI Application (main.py)          │
│  ┌─────────────────────────────────────────────────┐ │
│  │ Startup Tasks:                                 │ │
│  │ 1. Load config (.env)                          │ │
│  │ 2. Initialize logger                           │ │
│  │ 3. Connect to PostgreSQL                        │ │
│  │ 4. Create tables (idempotent)                   │ │
│  │ 5. Mount API routes                            │ │
│  │ 6. Start uvicorn server                        │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
    ┌────────┐    ┌────────────┐    ┌──────────┐
    │ Parser │    │ Classifier │    │ Database │
    └────────┘    └────────────┘    └──────────┘
        │                │                │
        ▼                ▼                ▼
   Extract Text  Classify Job  Store Candidate
   From PDF/DOC  Category      + Skills
```

---

## PHASE 1: Environment Setup

### 1.1 Verify Python & Dependencies

```bash
# Check Python version (need 3.10+)
python --version
# Output should be: Python 3.11.x or 3.13.x

# Check virtual environment is active
which python
# Should show path to venv: .venv/Scripts/python (Windows)

# List installed packages
pip list | grep -E "fastapi|sqlalchemy|pydantic"
```

### 1.2 Verify Configuration

```bash
# Check if .env exists and has required values
cat cv_system_output/.env | grep -E "DATABASE_URL|SECRET_KEY|CORS_ORIGINS"

# Expected output:
# DATABASE_URL=postgresql://user:pass@localhost/db_name
# SECRET_KEY=your-secret-key
# CORS_ORIGINS=http://localhost:3000
```

### 1.3 Verify Database Connection

```bash
# Test PostgreSQL connection
psql -U postgres -c "SELECT version();"

# Or use Python to test:
python -c "
from sqlalchemy import create_engine
from config import settings
engine = create_engine(settings.DATABASE_URL)
conn = engine.connect()
print('✓ Database connected')
conn.close()
"
```

---

## PHASE 2: Pre-Flight Checks

### 2.1 Check Dependency Imports

```python
# test_imports.py
#!/usr/bin/env python
"""Verify all critical imports work."""

print("[1/7] Testing FastAPI...")
from fastapi import FastAPI
print("  ✓ FastAPI OK")

print("[2/7] Testing Database ORM...")
from database.models import Candidate, CandidateSkill
from database.session import Base, engine
print("  ✓ SQLAlchemy OK")

print("[3/7] Testing CV Parser...")
from parser.parser import parse_cv
from parser.extractor import extract_text
print("  ✓ Parser OK")

print("[4/7] Testing Classifier...")
from classifier.classifier import classify_cv, MAIN_CATEGORIES
print(f"  ✓ Classifier OK (categories: {len(MAIN_CATEGORIES)})")

print("[5/7] Testing API Pipeline...")
from api.pipeline import process_cv_file
print("  ✓ Pipeline OK")

print("[6/7] Testing Authentication...")
from auth import create_access_token, verify_credentials
print("  ✓ Auth OK")

print("[7/7] Testing Config...")
from config import settings
print(f"  ✓ Config OK (APP_VERSION={settings.APP_VERSION})")

print("\n✓ All imports successful!")
```

Run it:
```bash
python test_imports.py
```

---

## PHASE 3: Database Initialization

### 3.1 Create Tables

```python
# init_db.py
#!/usr/bin/env python
"""Initialize database schema."""

from database.session import create_tables
from logger import get_logger

log = get_logger(__name__)

print("[*] Initializing database schema...")
try:
    create_tables()
    print("[+] Database schema initialized successfully!")
    print("\nTables created:")
    print("  - candidates")
    print("  - candidate_skills")
    print("  - upload_logs")
    print("  - whatsapp_conversations (if WhatsApp enabled)")
    print("  - whatsapp_messages")
    print("  - whatsapp_media_uploads")
except Exception as e:
    print(f"[-] Database initialization failed: {e}")
    exit(1)
```

Run it:
```bash
python init_db.py
```

### 3.2 Verify Tables

```bash
# Check tables exist in PostgreSQL
psql -U postgres -d cv_system -c "\dt"
```

---

## PHASE 4: Start the Parser API

### 4.1 Development Mode (With Auto-Reload)

```bash
# Terminal 1: Start with UV (faster reload)
uv run python main.py

# Or with uvicorn directly:
uvicorn main:app --reload --port 8000 --host 127.0.0.1
```

### 4.2 Production Mode (No Auto-Reload)

```bash
# Multiple workers for production
uvicorn main:app --port 8000 --host 0.0.0.0 --workers 4
```

### 4.3 With Gunicorn (Production-Grade)

```bash
# Install gunicorn
pip install gunicorn

# Run with 4 workers
gunicorn main:app -w 4 -b 0.0.0.0:8000 --timeout 120
```

---

## PHASE 5: Verify API is Running

### 5.1 Health Check

```bash
# Check if API is responding
curl http://localhost:8000/

# Expected output:
# {
#   "service": "CV Parser API",
#   "version": "1.0.0",
#   "docs": "/docs",
#   "health": "/api/v1/health"
# }
```

### 5.2 Database Health Check

```bash
curl http://localhost:8000/api/v1/health

# Expected output:
# {
#   "status": "ok",
#   "version": "1.0.0",
#   "database": "ok"
# }
```

### 5.3 View Interactive API Docs

Open browser: http://localhost:8000/docs

---

## PHASE 6: Test the Parser

### 6.1 Get Authentication Token

```bash
# Login to get JWT token
TOKEN=$(curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | jq '.access_token' -r)

echo "Token: $TOKEN"
```

### 6.2 Test with Sample CV File

```bash
# Create a test PDF
# (Use any existing CV file or create one)

# Upload CV
curl -X POST http://localhost:8000/api/v1/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "files=@/path/to/resume.pdf"

# Expected response:
# {
#   "total_files": 1,
#   "success_count": 1,
#   "results": [{
#     "candidate_id": "abc-123",
#     "name": "John Doe",
#     "email": "john@example.com",
#     "category": "IT",
#     "skills_extracted": 8
#   }]
# }
```

### 6.3 List Parsed Candidates

```bash
# Get all candidates
curl http://localhost:8000/api/v1/candidates \
  -H "Authorization: Bearer $TOKEN" | jq

# Filter by category
curl "http://localhost:8000/api/v1/candidates?category=IT" \
  -H "Authorization: Bearer $TOKEN" | jq
```

---

## PHASE 7: Test Parser Components Directly

### 7.1 Test Text Extraction

```python
# test_parser.py
from parser.extractor import extract_text
from parser.parser import parse_cv

# Test with a PDF
pdf_path = "test_cv.pdf"
raw_text = extract_text(pdf_path)
print(f"Extracted {len(raw_text)} characters")

# Parse the text
parsed = parse_cv(raw_text)
print(f"Name: {parsed.name}")
print(f"Email: {parsed.email}")
print(f"Phone: {parsed.phone}")
print(f"Skills: {parsed.skills}")
print(f"Experience: {parsed.experience[:100]}..." if parsed.experience else "No experience")
```

Run:
```bash
python test_parser.py
```

### 7.2 Test Classification

```python
# test_classifier.py
from classifier.classifier import classify_cv
from parser.parser import parse_cv
from parser.extractor import extract_text

# Load and parse CV
text = extract_text("test_cv.pdf")
parsed = parse_cv(text)

# Classify
classification = classify_cv(text, skills=parsed.skills)
print(f"Category: {classification.category}")
print(f"Subcategory: {classification.subcategory}")
print(f"Confidence: {classification.confidence:.2%}")
```

Run:
```bash
python test_classifier.py
```

### 7.3 Test Full Pipeline

```python
# test_pipeline.py
from api.pipeline import process_cv_file
from database.session import SessionLocal

# Read CV file
with open("test_cv.pdf", "rb") as f:
    file_content = f.read()

# Process through pipeline
db = SessionLocal()
candidate = process_cv_file(
    file_content=file_content,
    original_filename="test_cv.pdf",
    db=db
)

print(f"✓ CV Processed!")
print(f"  Candidate ID: {candidate.id}")
print(f"  Name: {candidate.name}")
print(f"  Category: {candidate.category}")
print(f"  Confidence: {candidate.confidence:.2%}")
print(f"  Skills: {len(candidate.skills)}")
```

Run:
```bash
python test_pipeline.py
```

---

## PHASE 8: Monitor & Debug

### 8.1 Check Logs

```bash
# Real-time logs
tail -f cv_system.log

# Filter by severity
tail -f cv_system.log | grep ERROR
tail -f cv_system.log | grep WARNING
```

### 8.2 Check Database State

```python
# check_db.py
from database.session import SessionLocal
from database.models import Candidate, CandidateSkill

db = SessionLocal()

# Count candidates
count = db.query(Candidate).count()
print(f"Total candidates: {count}")

# List last 5 candidates
candidates = db.query(Candidate).order_by(Candidate.created_at.desc()).limit(5).all()
for c in candidates:
    print(f"  - {c.name} ({c.category}) - {len(c.skills)} skills")

# Count skills
skill_count = db.query(CandidateSkill).count()
print(f"Total skills extracted: {skill_count}")

db.close()
```

Run:
```bash
python check_db.py
```

### 8.3 Performance Monitoring

```bash
# Monitor API requests per second
watch -n 1 'curl -s http://localhost:8000/api/v1/health | jq'

# Load test (100 concurrent requests)
ab -n 1000 -c 100 http://localhost:8000/api/v1/health
```

---

## PHASE 9: Integration with WhatsApp (Optional)

### 9.1 Run With WhatsApp Support

The system automatically includes WhatsApp if `.env` has:
```bash
WHATSAPP_API_TOKEN=EAA...
WHATSAPP_PHONE_NUMBER_ID=123...
```

Endpoints available:
- `GET/POST /api/v1/whatsapp/webhook` - Receives messages from WhatsApp

### 9.2 Test WhatsApp Webhook

```bash
# Verify endpoint exists
curl http://localhost:8000/api/v1/whatsapp/webhook?hub.mode=subscribe&hub.challenge=test123&hub.verify_token=my_webhook_token

# Should return: test123
```

---

## PHASE 10: Production Deployment Checklist

- [ ] Set `DEBUG=false` in `.env`
- [ ] Set strong `SECRET_KEY`
- [ ] Configure `CORS_ORIGINS` for frontend domain only
- [ ] Use environment-specific database URL
- [ ] Enable HTTPS/TLS
- [ ] Configure error monitoring (Sentry)
- [ ] Set up log aggregation
- [ ] Configure database backups
- [ ] Set up rate limiting
- [ ] Use production-grade ASGI server (Gunicorn + Uvicorn)

---

## Quick Start Command

```bash
#!/bin/bash
# Run this script to start everything

cd cv_system_output

# 1. Activate venv
source .venv/Scripts/activate

# 2. Initialize DB
python init_db.py

# 3. Run tests
python test_imports.py

# 4. Start API
uvicorn main:app --reload --port 8000
```

---

## Troubleshooting Guide

| Issue | Cause | Solution |
|-------|-------|----------|
| "No module named 'fastapi'" | Missing dependencies | `pip install -r requirements.txt` |
| "Connection refused" at 5432 | PostgreSQL not running | `net start postgresql-x64-14` |
| "Invalid token" at login | Wrong credentials | Use `admin/admin123` for demo |
| "File too large" on upload | Max size exceeded | Increase `MAX_FILE_SIZE_MB` in `.env` |
| "PDF text empty" | Bad PDF format | Use standard PDFs, not scanned images |
| "Classification confidence low" | Insufficient text | Ensure CV has clear job category |

