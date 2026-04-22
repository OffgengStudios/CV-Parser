# QUICK FIX GUIDE
## Top 5 Critical Issues to Fix Immediately

### 1. 🔴 Fix CORS Configuration (5 minutes)

**File**: `main.py`
**Current** (UNSAFE):
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ❌ INSECURE
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Fix** (SAFE):
```python
import os
allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # ✓ Only trusted domains
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],  # ✓ Specific methods
    allow_headers=["Content-Type", "Authorization"],  # ✓ Specific headers
)
```

**Update .env**:
```env
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com
```

---

### 2. 🔴 Remove Secrets from Git (10 minutes)

**Commands**:
```bash
# 1. Remove from git history
git filter-branch --tree-filter 'rm -f cv_system_output/Secrets/*.json' HEAD

# 2. Or use git-filter-repo (recommended)
git filter-repo --path cv_system_output/Secrets/ --invert-paths

# 3. Force push (only if not shared)
git push --force-with-lease origin clean-main

# 4. Add to .gitignore
echo "Secrets/" >> .gitignore
echo ".env" >> .gitignore
echo "*.json" >> .gitignore
git add .gitignore
git commit -m "Add secrets to gitignore"
```

---

### 3. 🔴 Fix Missing cv_text Parameter (5 minutes)

**File**: `database/crud.py:20`
**Current**:
```python
def create_candidate(
    db: Session,
    name: Optional[str],
    email: Optional[str],
    # ... missing cv_text
```

**Fix**:
```python
def create_candidate(
    db: Session,
    name: Optional[str],
    email: Optional[str],
    phone: Optional[str],
    skills: list[str],
    experience: Optional[str],
    education: Optional[str],
    cv_text: Optional[str],  # ✓ ADD THIS
    category: Optional[str],
    subcategory: Optional[str],
    confidence: Optional[float],
    years_experience: Optional[float],
    seniority_level: Optional[str],
    source_filename: Optional[str],
    saved_upload_filename: Optional[str],
) -> Candidate:
    candidate = Candidate(
        name=name,
        email=email,
        phone=phone,
        experience=experience,
        education=education,
        cv_text=cv_text,  # ✓ ADD THIS
        category=category,
        # ... rest
```

---

### 4. 🔴 Replace Broad Exception Handling (30 minutes)

**Pattern**: Instead of `except Exception:`, use specific exceptions

**File**: `matching/matcher.py:135`
**Current**:
```python
try:
    self.cv_tfidf_matrix = self.vectorizer.fit_transform(self.cv_texts)
except Exception as e:  # ❌ Too broad
    log.warning(f"TF-IDF fitting failed: {e}. Using fallback.")
    self.cv_tfidf_matrix = None
```

**Fix**:
```python
try:
    self.cv_tfidf_matrix = self.vectorizer.fit_transform(self.cv_texts)
except (ValueError, MemoryError) as e:  # ✓ Specific exceptions
    log.warning(f"TF-IDF fitting failed: {e}. Using fallback.")
    self.cv_tfidf_matrix = None
except Exception:  # If you must catch all, re-raise critical ones
    log.critical("Unexpected error in TF-IDF fitting", exc_info=True)
    raise
```

**Files to fix**:
- `classifier/supervised.py:142`
- `database/session.py:48`
- `parser/extractor.py:66`
- `parser/extractor.py:100`
- `matching/matcher.py:135`
- `matching/matcher.py:204`

---

### 5. 🔴 Add Basic Authentication (1-2 hours)

**Step 1**: Update requirements.txt
```
python-jose[cryptography]==3.3.0  # Already there ✓
```

**Step 2**: Create auth module `auth.py`
```python
from datetime import datetime, timedelta
from jose import JWTError, jwt
from pydantic import BaseModel
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredentials

SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-in-production")
ALGORITHM = "HS256"

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: str | None = None

security = HTTPBearer()

def create_access_token(user_id: str, expires_delta: timedelta | None = None):
    to_encode = {"user_id": user_id}
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id
```

**Step 3**: Protect endpoints
```python
@router.post("/upload", response_model=UploadBatchResponse)
async def upload_cv(
    files: list[UploadFile],
    current_user: str = Depends(get_current_user),  # ✓ ADD THIS
    db: Session = Depends(get_db),
):
    # Endpoint now requires valid JWT token
```

**Step 4**: Create login endpoint
```python
@router.post("/login", response_model=Token)
def login(username: str, password: str):
    # Implement your auth logic (check database, etc.)
    # For now, simple demo:
    if username == "admin" and password == "changeme":
        token = create_access_token(username)
        return {"access_token": token}
    raise HTTPException(status_code=401, detail="Invalid credentials")
```

**Update .env**:
```env
SECRET_KEY=your-very-long-random-secret-key-here
```

---

## Testing the Fixes

```bash
# 1. Test CORS
curl -i -X OPTIONS http://localhost:8000/api/v1/candidates \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET"

# 2. Test authentication
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"changeme"}'

# Get token, then use it:
curl -X GET http://localhost:8000/api/v1/candidates \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"

# 3. Run tests
pytest tests/ -v

# 4. Check for secrets
git grep -i "password\|secret\|key" | grep -v ".md"
```

---

## Priority Fix Checklist

- [ ] Fix CORS configuration
- [ ] Remove secrets from git
- [ ] Update .gitignore
- [ ] Add cv_text to create_candidate
- [ ] Replace broad exceptions (6 locations)
- [ ] Add basic authentication
- [ ] Run tests and verify
- [ ] Update database with migration
- [ ] Test with PostgreSQL connection
- [ ] Document breaking changes

**Estimated Time**: 3-4 hours for all fixes
