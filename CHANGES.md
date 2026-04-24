# CV-Parser — Audit-Driven Improvements

> **Scope:** Full codebase audit of a FastAPI + Next.js 15 CV parsing system, followed by structured
> implementation of every non-WhatsApp finding. All 12 feature groups were implemented and tested
> in sequence. Final test result: **57/57 backend tests passing**, **9/9 frontend routes compiled**
> with real TypeScript checking enabled.

---

## Table of Contents

1. [Feature 1 — Code Redundancy & Route Fixes](#feature-1--code-redundancy--route-fixes)
2. [Feature 2 — Skills Taxonomy Unification](#feature-2--skills-taxonomy-unification)
3. [Feature 3 — Analytics & Parser Fixes](#feature-3--analytics--parser-fixes)
4. [Feature 4 — Schema Safety: Match Score Validation](#feature-4--schema-safety-match-score-validation)
5. [Feature 5 — Frontend Type & UX Fixes](#feature-5--frontend-type--ux-fixes)
6. [Feature 6 — Auth Config Hardening](#feature-6--auth-config-hardening)
7. [Feature 7 — Frontend Auth & Session Fixes](#feature-7--frontend-auth--session-fixes)
8. [Feature 8 — Backend Auth Completeness](#feature-8--backend-auth-completeness)
9. [Feature 9 — Login Rate Limiting](#feature-9--login-rate-limiting)
10. [Feature 10 — Performance Improvements](#feature-10--performance-improvements)
11. [Feature 11 — TypeScript Build Quality](#feature-11--typescript-build-quality)
12. [Feature 12 — Classifier Probability Fix](#feature-12--classifier-probability-fix)

---

## Feature 1 — Code Redundancy & Route Fixes

**Audit IDs:** R2, R4, R5, B7, W6

### R2 — `_candidate_list_item` helper unused in `list_candidates`

**Problem:** The `_candidate_list_item(candidate)` helper was defined in `api/routes.py` immediately
after the `list_candidates` endpoint, but `list_candidates` never called it — it repeated the same
14-field inline dict instead. Only `list_duplicate_candidates` used the helper.

**Fix:** Changed `list_candidates` to call `_candidate_list_item(c)` for each candidate, eliminating
the duplicate inline dict.

**File:** `cv_system_output/api/routes.py`

---

### R4 — `auth.py` re-read env vars that `config.py` already owns

**Problem:** `auth.py` had:
```python
SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-please-change-in-production")
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24"))
```
These two settings are already centralised in `config.py`'s `Settings` class (which reads `.env` via
`pydantic-settings`). If both were set via different mechanisms, they could diverge silently.

**Fix:** Removed the `os.getenv` calls from `auth.py`. Values now come from `settings`:
```python
from config import settings
SECRET_KEY = settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_HOURS = settings.ACCESS_TOKEN_EXPIRE_HOURS
```

**Files:** `cv_system_output/auth.py`, `cv_system_output/config.py`

---

### R5 — `datetime` imported inside functions in `crud.py`

**Problem:** Two functions in `crud.py` (`get_or_create_whatsapp_conversation` and
`update_whatsapp_conversation`) each had `from datetime import datetime, timezone` as a local
import inside the function body — a code smell that makes the dependency invisible at the module level.

**Fix:** Moved both imports to the top of `crud.py` alongside the other standard library imports.

**File:** `cv_system_output/database/crud.py`

---

### B7 — Double DB fetch on candidate delete

**Problem:** The delete route fetched the candidate once to capture its name for the audit log, then
`crud.delete_candidate` fetched it *again* internally (`db.get(Candidate, candidate_id)`). Two
database round-trips for the same row.

**Fix:** Changed `crud.delete_candidate` return type from `bool` to `Optional[str]`. It now returns
the candidate's name (or the ID as a fallback) on success, or `None` if not found. The route
uses the returned name directly — no pre-fetch needed.

```python
# Before
def delete_candidate(db: Session, candidate_id: str) -> bool: ...

# After
def delete_candidate(db: Session, candidate_id: str) -> Optional[str]:
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        return None
    name = candidate.name
    db.delete(candidate)
    db.commit()
    return name or candidate_id
```

**Files:** `cv_system_output/database/crud.py`, `cv_system_output/api/routes.py`

---

### W6 — Activity log written before match completes

**Problem:** In `match_job_file`, `crud.log_activity(status="success")` was called *before*
`match_job()` ran. If matching threw an exception, the audit log incorrectly recorded a success.

**Fix:** Moved `crud.log_activity(...)` to after `match_job()` returns its result.

**File:** `cv_system_output/api/routes.py`

---

## Feature 2 — Skills Taxonomy Unification

**Audit ID:** R1

### Problem

The skills vocabulary existed in two separate places with divergent content:

- `parser/parser.py` — `SKILLS_KEYWORDS` list (~65 items)
- `matching/matcher.py` — `SKILLS_DATABASE` set (~80 items)

They shared ~90% of entries but each had unique extras. Any addition to one required manual
mirroring in the other — a maintenance trap that had already led to drift.

### Fix

Created a single shared module `cv_system_output/skills_taxonomy.py`:

```python
SKILLS: list[str] = [
    "python", "java", "javascript", "typescript", "c++", "c#", "php", "ruby",
    "swift", "kotlin", "go", "rust", "scala", "r", "matlab", "perl", "erlang",
    # ... ~80 items total (superset of both original lists)
]

SKILLS_SET: frozenset[str] = frozenset(SKILLS)
```

- `parser/parser.py` now imports: `from skills_taxonomy import SKILLS as SKILLS_KEYWORDS`
- `matching/matcher.py` now imports: `from skills_taxonomy import SKILLS_SET as SKILLS_DATABASE`

The matcher's original set was the superset; 11 skills previously missing from the parser
(`perl`, `erlang`, `jquery`, `webpack`, `git`, `mariadb`, `analytics`, `data science`, `nlp`,
`presentation`, `critical thinking`) are now available to both.

`SKILLS_SET` uses `frozenset` for O(1) membership checks in the matcher; `SKILLS` uses `list` to
preserve an ordered sequence for the parser.

**Files:** `cv_system_output/skills_taxonomy.py` *(new)*, `cv_system_output/parser/parser.py`,
`cv_system_output/matching/matcher.py`

---

## Feature 3 — Analytics & Parser Fixes

**Audit IDs:** W1, W2, W3

### W1 — Seniority level ignored job title when `years_experience` was present

**Problem:** `infer_seniority_level` in `analytics.py` checked years of experience first:
```python
if years_experience is not None:
    if years_experience >= 6: return "Senior"
    if years_experience >= 3: return "Mid"
    return "Junior"
# keyword check only reached if years_experience is None
```
A "Senior Software Engineer" with 2 years of extractable experience would be labelled "Junior"
because the title keyword check was never reached. In practice, most CVs have extractable year
ranges, so title-based inference almost never ran.

**Fix:** Reversed the order — title keywords are checked first; years of experience is the fallback:
```python
# Check title keywords first (e.g. "Senior", "Junior" in job title)
for level, keywords in SENIORITY_KEYWORDS.items():
    ...
    if match: return level

# Fall back to years of experience
if years_experience is not None:
    ...
```

**File:** `cv_system_output/analytics.py`

---

### W2 — `CURRENT_YEAR` frozen at process startup

**Problem:** `CURRENT_YEAR = datetime.now(timezone.utc).year` was computed once at module import
time. If the app started in December and ran past midnight into January, all experience duration
calculations (`2020 – present`) would use the old year, giving off-by-one results.

**Fix:** Removed the module-level constant. The year is now computed fresh inside
`extract_years_of_experience()` on every call:
```python
def extract_years_of_experience(text: str) -> Optional[float]:
    current_year = datetime.now(timezone.utc).year  # computed per-call
    ...
```

**File:** `cv_system_output/analytics.py`

---

### W3 — Name comma-check rejected valid "Last, First" format

**Problem:** The name validation guard in `parser/parser.py` read:
```python
if "," in normalized and normalized.count(",") > 0:
    return False
```
The first condition (`"," in normalized`) already guarantees `count(",") > 0`, so the second
check added nothing. The intent was to allow exactly one comma (for "Smith, John" formats) while
rejecting multi-comma strings. As written, "Smith, John" was incorrectly rejected.

**Fix:** Changed to check for more than one comma:
```python
if normalized.count(",") > 1:
    return False
```
Single-comma names like "Smith, John" are now accepted. Strings with two or more commas
(which are unlikely to be names) are still rejected.

**File:** `cv_system_output/parser/parser.py`

---

## Feature 4 — Schema Safety: Match Score Validation

**Audit ID:** W4

### Problem

`MatchedCandidateResult.final_score` had a Pydantic constraint `Field(ge=0.0, le=1.0)`.
The `/match` endpoint accepted `text_weight` and `skill_weight` via form fields with no check
that they summed to ≤ 1.0. A request with `text_weight=0.8, skill_weight=0.5` could produce
`final_score > 1.0`, causing Pydantic to raise a `ValidationError` and return a 500.

### Fix — Two-layer defence

**Layer 1 — Schema validation** (`api/schemas.py`): Added a `@model_validator` to `JobMatchRequest`
that rejects requests where the weights sum exceeds 1.0 before any processing begins:
```python
@model_validator(mode="after")
def weights_must_not_exceed_one(self) -> "JobMatchRequest":
    total = self.text_weight + self.skill_weight
    if total > 1.0 + 1e-9:
        raise ValueError(
            f"text_weight + skill_weight must be ≤ 1.0 (got {total:.4f}). "
            "Example valid combination: text_weight=0.7, skill_weight=0.3."
        )
    return self
```

**Layer 2 — Runtime cap** (`matching/matcher.py`): The score computation now clamps to 1.0
regardless of weights, as a safety net for any future code path that bypasses the schema:
```python
final_score = min(1.0, (text_weight * text_score) + (skill_weight * skill_score))
```

**Files:** `cv_system_output/api/schemas.py`, `cv_system_output/matching/matcher.py`

---

## Feature 5 — Frontend Type & UX Fixes

**Audit IDs:** I6, R3, R6

### I6 — `ApiCandidateListItem` missing `years_experience` and `seniority_level`

**Problem:** The backend's `CandidateListItem` response schema included `years_experience` and
`seniority_level`, but the TypeScript interface `ApiCandidateListItem` in `frontend/lib/api.ts`
did not declare them. This meant the frontend couldn't access these fields without a type assertion,
and they couldn't be surfaced in the candidates list without an additional API call per candidate.

**Fix:** Added both fields to the TypeScript interface:
```typescript
export interface ApiCandidateListItem {
  // ...existing fields...
  years_experience: number | null
  seniority_level: string | null
}
```

**File:** `frontend/lib/api.ts`

---

### R3 — `use-mobile` and `use-toast` hooks duplicated

**Problem:** Two identical copies of each hook existed:
- `frontend/hooks/use-mobile.ts` and `frontend/components/ui/use-mobile.tsx`
- `frontend/hooks/use-toast.ts` and `frontend/components/ui/use-toast.ts`

Page-level files imported from `@/hooks/...`; the sidebar imported from `@/components/ui/...`.
Any change to one copy had to be manually mirrored.

**Fix:** Deleted the `components/ui/` copies. The canonical versions in `hooks/` are the single
source of truth. All existing imports from `@/hooks/...` continue to work unchanged.

**Files deleted:** `frontend/components/ui/use-mobile.tsx`,
`frontend/components/ui/use-toast.ts`

---

### R6 — Delete candidate dialog duplicated across two pages

**Problem:** Identical `<AlertDialog>` markup and `handleDeleteCandidate` / `confirmDeleteCandidate`
logic existed in both `app/page.tsx` and `app/candidates/page.tsx`. A UI change or bug fix had
to be applied twice.

**Fix:** Extracted into a shared `<DeleteCandidateDialog>` component:

```typescript
// frontend/components/delete-candidate-dialog.tsx
export function DeleteCandidateDialog({
  candidate,   // { id: string; name: string } | null
  deleting,    // boolean
  onConfirm,   // () => void
  onCancel,    // () => void
}: DeleteCandidateDialogProps) { ... }
```

Both pages now import and render `<DeleteCandidateDialog>` with the appropriate props.

**Files:** `frontend/components/delete-candidate-dialog.tsx` *(new)*,
`frontend/app/page.tsx`, `frontend/app/candidates/page.tsx`

---

## Feature 6 — Auth Config Hardening

**Audit IDs:** B3, B4, A4, A5, A6

### B3 + A5 — Demo credentials permanently active in production

**Problem:** The `DEMO_USERS` fallback (`admin/admin123`, `demo/demo123`) in `auth.py` had no way
to disable it in production. Additionally, the password comparison used `==` instead of a
constant-time comparison function, making it vulnerable to timing side-channel attacks.

**Fix:**
1. Added `ENABLE_DEMO_CREDENTIALS: bool = False` to `config.py` (defaults to off in production).
2. Gated the fallback behind the flag:
```python
if settings.ENABLE_DEMO_CREDENTIALS:
    expected = DEMO_USERS.get(username, "")
    if expected and hmac.compare_digest(expected, password):
        return True
```
`hmac.compare_digest` compares strings in constant time regardless of content, eliminating
the timing side-channel.

**Files:** `cv_system_output/auth.py`, `cv_system_output/config.py`

---

### A4 — Login page exposed plaintext credentials

**Problem:** The login page UI displayed `Demo workers: admin/admin123 or demo/demo123` — visible
to anyone who opened the login page, including in production deployments.

**Fix:** Replaced with a neutral message: `Contact your administrator for login credentials.`

**File:** `frontend/app/login/page.tsx`

---

### A6 — No `SECRET_KEY` strength enforcement at startup

**Problem:** The app would start and issue JWTs using the default `"dev-key-please-change-in-production"`
key, with no warning or error, in a production deployment that omitted `SECRET_KEY` from the
environment.

**Fix:** Added a `@model_validator(mode="after")` to `Settings` in `config.py` that validates
`SECRET_KEY` on startup:

```python
@model_validator(mode="after")
def enforce_strong_secret_key(self) -> "Settings":
    if self.TESTING or self.DEBUG:
        return self  # skip in test/dev
    if self.SECRET_KEY == "dev-key-please-change-in-production":
        raise ValueError("SECRET_KEY is set to the default development value...")
    if len(self.SECRET_KEY) < 32:
        raise ValueError(f"SECRET_KEY is too short ({len(self.SECRET_KEY)} chars)...")
    return self
```

A `TESTING: bool = False` flag was added to `Settings` so the validator is automatically skipped
during the test run. `cv_system_output/conftest.py` (new file) sets
`os.environ.setdefault("TESTING", "true")` before any app module is imported.

---

### B4 — Backend URL hardcoded as localhost in settings endpoint

**Problem:** `GET /api/v1/settings/status` returned `backend_url_hint="http://127.0.0.1:8000"` —
a hardcoded string. In production deployments (e.g. Render), the settings page always showed the
wrong URL.

**Fix:** Added `BACKEND_URL: str = "http://127.0.0.1:8000"` to `Settings`, and changed the route to:
```python
backend_url_hint=settings.BACKEND_URL
```
Deployments set `BACKEND_URL` in their environment and it appears correctly in the UI.

**Files:** `cv_system_output/config.py`, `cv_system_output/api/routes.py`

---

### R7 — Orphaned dead code inside backend directory

**Problem:** `cv_system_output/frontend/components/JobMatcher.tsx` (356 lines) and
`cv_system_output/package-lock.json` (empty lockfile) were sitting inside the Python backend
directory — unreachable by the real frontend and serving no purpose.

**Fix:** Both deleted.

---

## Feature 7 — Frontend Auth & Session Fixes

**Audit IDs:** W5, A7, A8, A9, A11

### W5 — `getAccessToken()` returned a never-resolving Promise

**Problem:** When called without a stored token, `getAccessToken()` called
`window.location.assign("/login")` then returned `new Promise(() => {})` — a Promise that never
resolves or rejects. Any `await apiFetch(...)` call in this state would hang indefinitely.
React state updates, `finally` blocks, and error boundaries never fired for those requests.

**Fix:** Throw immediately after navigating:
```typescript
async function getAccessToken(): Promise<string> {
  const token = getStoredToken()
  if (token) return token

  if (typeof window !== "undefined") {
    window.location.assign("/login")
  }
  throw new ApiRequestError("/api/v1/login", 401, "Session expired — please sign in again.")
}
```

**File:** `frontend/lib/api.ts`

---

### A7 — No 401 interception in `apiFetch`

**Problem:** When a backend-issued JWT expired server-side, any protected API call would receive a
401 response, but the frontend had no centralised handling. Each page would need its own error
handling to detect and redirect — and most did not.

**Fix:** Added a 401 check inside `apiFetch` before the generic error handler:
```typescript
if (response.status === 401 && path !== "/api/v1/login") {
  logoutWorker()
  if (typeof window !== "undefined") {
    window.location.assign("/login")
  }
  throw new ApiRequestError(path, 401, "Session expired — please sign in again.")
}
```
Excludes the login endpoint itself to avoid redirect loops.

**File:** `frontend/lib/api.ts`

---

### A8 — Module-level token cache could go stale

**Problem:** `let accessToken: string | null = null` cached the token in module memory as an
optimisation over localStorage reads. This creates a risk: if `logoutWorker()` is called from one
context while another has already read the token into a local variable, the in-memory cache
could persist a token that was meant to be cleared.

**Fix:** Removed the module-level variable entirely. All token reads go directly to `localStorage`.
The performance difference is negligible for browser JavaScript. `loginWorker`, `logoutWorker`,
and `getStoredToken` were all updated accordingly.

**File:** `frontend/lib/api.ts`

---

### A9 — No server-side auth guard (flash of protected content)

**Problem:** Auth was enforced only client-side. Before React hydrated, an unauthenticated user
would briefly see the protected page's layout/shell before being redirected. Next.js middleware
could prevent this, but middleware can't read `localStorage`.

**Solution:** Set a lightweight `cvparser_session=1` cookie (not the JWT token itself) at login.
Middleware can read cookies. Created `frontend/proxy.ts` (Next.js 16.2+'s replacement for
`middleware.ts`) that redirects to `/login` if the session cookie is absent:

```typescript
export function proxy(request: NextRequest) {
  if (isPublicPath(pathname)) return NextResponse.next()

  const sessionCookie = request.cookies.get("cvparser_session")
  if (!sessionCookie?.value) {
    const loginUrl = request.nextUrl.clone()
    loginUrl.pathname = "/login"
    return NextResponse.redirect(loginUrl)
  }
  return NextResponse.next()
}
```

`loginWorker()` sets the cookie; `logoutWorker()` clears it via `document.cookie`.

**Files:** `frontend/proxy.ts` *(new)*, `frontend/lib/api.ts`

---

### A11 — No idle timeout / auto-logout

**Problem:** A session with a long-lived JWT (24 hours default) could be left open on an unattended
workstation indefinitely, with no automatic sign-out.

**Fix:** Two new files:

**`frontend/hooks/use-idle-timeout.ts`** — tracks user activity events (`mousemove`, `mousedown`,
`keydown`, `touchstart`, `scroll`, `click`). After a configurable idle period (default 30 min),
calls `onIdle`. Two minutes before logout, sets `isWarning=true` and starts a seconds countdown.

**`frontend/components/session-guard.tsx`** — renders a modal `<Dialog>` warning when `isWarning`
is true:
- "Stay signed in" button calls `resetTimer()` (dismisses warning, restarts all timers)
- "Sign out now" button calls `logoutWorker()` and redirects immediately
- Dialog cannot be dismissed by clicking outside or pressing Escape

`SessionGuard` is mounted in `frontend/app/layout.tsx` so it covers every page. It is a no-op
on `/login` (checked via `usePathname()`).

**Files:** `frontend/hooks/use-idle-timeout.ts` *(new)*,
`frontend/components/session-guard.tsx` *(new)*, `frontend/app/layout.tsx`

---

## Feature 8 — Backend Auth Completeness

**Audit IDs:** A1, A2, A3

### A1 — Logout endpoint with JWT denylist

**Problem:** There was no logout endpoint. Once a JWT was issued, it was valid until its natural
expiry — there was no server-side way to invalidate it (e.g., on password change, suspicious
activity, or explicit logout).

**Fix:** Added an in-memory JWT denylist to `auth.py`:

```python
_token_denylist: dict[str, float] = {}  # jti → expiry timestamp

def revoke_token(jti: str, exp_timestamp: float) -> None:
    _prune_denylist()  # remove already-expired entries first
    _token_denylist[jti] = exp_timestamp
```

Every token now receives a unique `jti` (JWT ID — a UUID) claim at creation time. `verify_token`
rejects any token whose `jti` is in the denylist. `_prune_denylist()` removes entries whose
natural expiry has passed, so the dict never grows unboundedly.

**`POST /api/v1/logout`** revokes the caller's token and returns 204 No Content.

The frontend's `logoutWorker()` fires the endpoint with `keepalive: true` (ensuring the request
completes even if the page unloads) before clearing `localStorage` and the session cookie.

**Files:** `cv_system_output/auth.py`, `cv_system_output/api/routes.py`, `frontend/lib/api.ts`

---

### A2 — Token refresh mechanism

**Problem:** Users had no way to extend their session without re-entering their password. A 24-hour
token would simply expire, forcing a re-login.

**Fix:** Added `POST /api/v1/auth/refresh`. The caller presents their current valid token; the
endpoint revokes it (adds its `jti` to the denylist) and issues a fresh token with a new `jti`
and full expiry window. The old token is immediately unusable.

Frontend: `refreshToken()` function added to `api.ts`. It calls the endpoint, stores the new
token in `localStorage`, and updates the session cookie's `max-age`.

**Files:** `cv_system_output/auth.py`, `cv_system_output/api/routes.py`, `frontend/lib/api.ts`

---

### A3 — Worker management endpoints

**Problem:** There was a `POST /api/v1/admin/users` endpoint to *create* workers, but no way to
list, deactivate, or reset passwords for existing workers via the API.

**New endpoints (all admin-only):**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/admin/users` | List all worker accounts |
| `DELETE` | `/api/v1/admin/users/{username}` | Soft-deactivate a worker |
| `POST` | `/api/v1/admin/users/{username}/reset-password` | Reset a worker's password |

Deactivation is a soft delete (`is_active=False`) — audit history is preserved. Guards prevent
admins from deactivating themselves or built-in accounts. Password reset requires minimum 8
characters and rejects built-in accounts.

`WorkerUserResponse` schema was extended with `created_at: datetime | None` for display in admin UIs.

**New CRUD functions:** `list_worker_users`, `deactivate_worker_user`, `update_worker_password`

**New frontend functions:** `fetchWorkerUsers`, `deactivateWorkerUser`, `resetWorkerPassword`

**Files:** `cv_system_output/database/crud.py`, `cv_system_output/auth.py`,
`cv_system_output/api/routes.py`, `frontend/lib/api.ts`

---

## Feature 9 — Login Rate Limiting

**Audit ID:** I1

### Problem

`POST /api/v1/login` had no request throttling. An attacker could make thousands of login attempts
per second — a trivial brute-force against the `admin/admin123` demo credentials or any weak
worker password.

### Fix

Integrated `slowapi` (the standard rate-limiting library for FastAPI/Starlette).

**`cv_system_output/limiter.py`** *(new)* — a shared `Limiter` instance in its own module to avoid
circular imports between `main.py` and `routes.py`:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])
```

**`main.py`** — attaches the limiter to `app.state` and registers the 429 exception handler:
```python
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

**`api/routes.py`** — the login handler gets a rate limit decorator and a `request: Request`
parameter (required by slowapi for IP extraction). The old `request: LoginRequest` parameter
was renamed to `body` to avoid the naming collision:
```python
@router.post("/login", ...)
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    ...
```

Rate: **10 attempts per minute per IP**. High enough for legitimate use (shared NAT, team logins),
low enough to make brute-force impractical. Exceeding the limit returns HTTP 429.

`slowapi>=0.1.9` was added to `requirements.txt`.

**Files:** `cv_system_output/limiter.py` *(new)*, `cv_system_output/main.py`,
`cv_system_output/api/routes.py`, `cv_system_output/requirements.txt`

---

## Feature 10 — Performance Improvements

**Audit IDs:** I3, I4

### I3 — TF-IDF vectorizer rebuilt on every match request

**Problem:** `match_candidates()` in `matching/matcher.py` created a new `CandidateMatcher` on
every call. `CandidateMatcher.__init__` fits a TF-IDF vectorizer over the entire candidate corpus
(`fit_transform`). With 1000 candidates this takes seconds — and it was happening on every single
`/match` request, even when the corpus hadn't changed at all.

**Fix:** Added a module-level cache keyed by `(candidate_count, newest_candidate_id)`:

```python
_matcher_cache: dict[tuple, CandidateMatcher] = {}
_cache_lock = Lock()

def _cache_key(candidates: list[dict]) -> tuple:
    if not candidates:
        return (0, None)
    return (len(candidates), candidates[0].get("candidate_id"))
```

The key detects corpus changes (upload → count increases; delete → count decreases) and is derived
in O(1) from the already-loaded candidate list — no extra DB query. On a cache hit, the expensive
`fit_transform` is skipped entirely. The cache holds at most one `CandidateMatcher` at a time
(cleared on any miss) so memory stays bounded. A `threading.Lock` guards concurrent requests that
arrive before the cache is populated.

**File:** `cv_system_output/matching/matcher.py`

---

### I4 — Duplicate detection loaded entire candidate table

**Problem:** `find_duplicate_candidate_groups` in `crud.py` called `list_all_candidates(db)` which
loaded *all* candidate rows — including `cv_text`, `experience`, and `education` (`Text` columns,
potentially kilobytes per row) — just to group candidates by email/phone. With 10,000 candidates
this is a large unnecessary data transfer.

**Fix:** Replaced with a 4-stage strategy that only loads what is actually needed:

**Stage 1 — SQL GROUP BY for emails:**
```python
norm_email_col = func.lower(func.trim(Candidate.email))
dup_email_stmt = (
    select(norm_email_col.label("norm_email"))
    .where(Candidate.email.isnot(None))
    .group_by(norm_email_col)
    .having(func.count() > 1)
)
```
Only duplicate email values (not rows) are returned from the database.

**Stage 2 — Slim `(id, phone)` fetch for phone duplicates:**
```python
slim_phone_stmt = select(Candidate.id, Candidate.phone).where(Candidate.phone.isnot(None))
```
Loads only two columns for all candidates — a fraction of the payload compared to full ORM objects.
Phone normalisation happens in Python on this tiny dataset.

**Stage 3 — Targeted full-row fetch:**
Only the candidate IDs identified as duplicates are loaded in full:
```python
full_rows_stmt = select(Candidate).where(Candidate.id.in_(duplicate_id_set))
```
If 10,000 candidates have 20 duplicates, only 20 full rows are fetched.

**Stage 4 — Python grouping** runs over the small duplicate set using the same logic as before.

**Bonus fix (same feature):** The match route's enrichment loop used `next(c for c in all_candidates_orm if c.id == ...)` — an O(N) linear scan per result row. Replaced with a pre-built dict:
```python
candidates_by_id = {c.id: c for c in all_candidates_orm}  # O(N) once
...
candidate_orm = candidates_by_id.get(match_result.candidate_id)  # O(1) per lookup
```

**Files:** `cv_system_output/database/crud.py`, `cv_system_output/api/routes.py`

---

## Feature 11 — TypeScript Build Quality

**Audit ID:** I5

### Problem

`frontend/next.config.mjs` contained:
```javascript
typescript: {
  ignoreBuildErrors: true,
}
```
This flag silently skips TypeScript type checking during `next build`. Any type error introduced
by a developer would not fail the build — it would ship to production undetected.

### Fix

Ran `npx tsc --noEmit` first to surface any errors that were being suppressed. Exit code: **0** —
no type errors existed at all. The flag was pure cargo-cult configuration.

Removed the entire `typescript` block:
```javascript
// Before
const nextConfig = {
  typescript: { ignoreBuildErrors: true },
  images: { unoptimized: true },
}

// After
const nextConfig = {
  images: { unoptimized: true },
}
```

The production build output now shows `Running TypeScript … Finished TypeScript` — real compile-time
checking runs on every deploy. Future type errors will break the build immediately.

**File:** `frontend/next.config.mjs`

---

## Feature 12 — Classifier Probability Fix

**Audit ID:** I8

### Problem

When the supervised Naive Bayes classifier (`classifier/supervised.py`) was used, it returned only
the top category and its confidence score. In `classify_cv`, this was used to populate `all_scores`
as a sparse dict:
```python
all_scores={category: (confidence if category == top_category else 0.0) for category in MAIN_CATEGORIES}
```
Every non-winning category was silently assigned `0.0` — not its actual predicted probability.
This made `all_scores` misleading for any UI or downstream logic that used it to show confidence
across categories (e.g., "79% IT, 11% Sales, 10% Finance" vs "79% IT, 0% Sales, 0% Finance").

Ironically, the model *already computed* the full softmax distribution internally — it just
discarded it before returning.

### Fix

**`supervised.py`** — extended `predict()` to return the full probability distribution as a third
element:
```python
def predict(self, text: str) -> tuple[str, float, dict[str, float]] | None:
    ...
    probabilities = {cat: round(v / total_exp, 4) for cat, v in exp_scores.items()}
    top_category = max(probabilities, key=probabilities.__getitem__)
    confidence = probabilities[top_category]
    return top_category, confidence, probabilities  # full distribution included
```

**`classifier.py`** — unpacks the three-tuple and builds `all_scores` from the real probabilities:
```python
top_category, confidence, probabilities = result
all_scores = {
    category: probabilities.get(category, 0.0)
    for category in MAIN_CATEGORIES
}
```
Categories that the model was not trained on default to `0.0`; all trained categories get their
genuine softmax probability.

**Verified:** For a "python software engineer machine learning" CV the distribution is:
```
IT      : 0.7887
Sales   : 0.1127   ← real probability, was previously forced to 0.0
Finance : 0.0986   ← real probability, was previously forced to 0.0
Sum     : 1.0000
```

**Files:** `cv_system_output/classifier/supervised.py`,
`cv_system_output/classifier/classifier.py`

---

## Test Results

All changes were tested after each feature. Final state:

| Suite | Result |
|-------|--------|
| Backend (`pytest tests/test_system.py`) | **57 / 57 passed** |
| Frontend (`npm run build`) | **9 / 9 routes compiled** |
| TypeScript (`tsc --noEmit`) | **0 errors** |
| Rate limiter smoke test | **429 on 11th request — PASS** |
| Classifier probability smoke test | **Sum = 1.0000, all categories non-zero — PASS** |
