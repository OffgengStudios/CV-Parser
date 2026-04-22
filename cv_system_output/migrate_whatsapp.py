#!/usr/bin/env python
"""
migrate_whatsapp.py - Create WhatsApp tables in the database.

This script creates the new WhatsApp-related tables needed for the integration.
Run this ONCE after updating the code:

    python migrate_whatsapp.py
"""
import sys
from pathlib import Path

# Add parent dir to path so we can import modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.session import Base, engine
from database.models import (
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppMediaUpload,
)
from logger import get_logger

log = get_logger(__name__)


def run_migration():
    """Create all tables defined in models."""
    print("[*] Starting WhatsApp database migration...")

    try:
        # Create all tables (idempotent - won't fail if they exist)
        Base.metadata.create_all(engine)
        print("[+] Migration completed successfully!")
        print("\n[*] Tables created/verified:")
        print("  - whatsapp_conversations")
        print("  - whatsapp_messages")
        print("  - whatsapp_media_uploads")
        return True

    except Exception as e:
        print(f"[-] Migration failed: {e}")
        log.error(f"Migration error: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
