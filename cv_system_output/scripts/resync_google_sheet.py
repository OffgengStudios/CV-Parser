r"""
Rewrite the main Google Sheets tab from the current database snapshot.

Usage:
    ..\.venv\Scripts\python.exe .\scripts\resync_google_sheet.py
"""
from database import crud
from database.session import SessionLocal
from google_sheets import is_configured, replace_main_sheet


def main() -> int:
    if not is_configured():
        print("Google Sheets is not configured.")
        return 1

    db = SessionLocal()
    try:
        candidates = crud.list_all_candidates(db)
        replace_main_sheet(candidates)
    finally:
        db.close()

    print(f"Replaced main Google Sheet tab with {len(candidates)} candidate rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
