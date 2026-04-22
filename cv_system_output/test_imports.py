#!/usr/bin/env python
"""Verify all critical imports work before starting the API."""

import sys
from pathlib import Path

def test_imports():
    """Test all critical dependencies."""

    tests = [
        ("FastAPI", lambda: __import__("fastapi")),
        ("SQLAlchemy", lambda: __import__("sqlalchemy")),
        ("Pydantic", lambda: __import__("pydantic")),
        ("Parser", lambda: __import__("parser.parser", fromlist=["parse_cv"])),
        ("Classifier", lambda: __import__("classifier.classifier", fromlist=["classify_cv"])),
        ("Database", lambda: __import__("database.models", fromlist=["Candidate"])),
        ("Config", lambda: __import__("config", fromlist=["settings"])),
        ("Logger", lambda: __import__("logger", fromlist=["get_logger"])),
        ("Auth", lambda: __import__("auth", fromlist=["create_access_token"])),
    ]

    failed = []

    for i, (name, loader) in enumerate(tests, 1):
        try:
            print(f"[{i}/{len(tests)}] Testing {name}...", end=" ")
            loader()
            print("OK")
        except Exception as e:
            print(f"FAILED: {e}")
            failed.append((name, str(e)))

    print("\n" + "="*60)
    if failed:
        print(f"FAILED: {len(failed)} imports failed\n")
        for name, error in failed:
            print(f"  - {name}: {error}")
        return False
    else:
        print(f"SUCCESS: All {len(tests)} imports passed!")
        return True

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
