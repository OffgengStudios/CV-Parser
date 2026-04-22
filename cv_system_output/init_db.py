#!/usr/bin/env python
"""Initialize and verify database schema."""

import sys
from pathlib import Path

from database.session import create_tables, engine
from logger import get_logger

log = get_logger(__name__)

def init_database():
    """Initialize database schema."""
    print("[*] Initializing database schema...")

    try:
        # Test connection first
        print("  [1/2] Testing database connection...", end=" ")
        conn = engine.connect()
        print("OK")
        conn.close()

        # Create tables
        print("  [2/2] Creating tables...", end=" ")
        create_tables()
        print("OK")

        print("\n[+] Database initialized successfully!")
        print("\nTables created/verified:")
        print("  - candidates")
        print("  - candidate_skills")
        print("  - upload_logs")
        print("  - whatsapp_conversations")
        print("  - whatsapp_messages")
        print("  - whatsapp_media_uploads")

        return True

    except Exception as e:
        print(f"FAILED")
        print(f"\n[-] Database initialization failed:")
        print(f"  {e}")
        log.error(f"Database initialization failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
