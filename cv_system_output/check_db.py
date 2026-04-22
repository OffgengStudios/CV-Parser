#!/usr/bin/env python
"""Check database state and statistics."""

import sys
from sqlalchemy import func, text

from database.session import SessionLocal
from database.models import Candidate, CandidateSkill, UploadLog

def check_database():
    """Display database statistics."""
    print("[*] Checking database state...\n")

    try:
        db = SessionLocal()

        # Candidate stats
        total_candidates = db.query(func.count(Candidate.id)).scalar()
        categories = db.query(
            Candidate.category,
            func.count(Candidate.id).label("count")
        ).group_by(Candidate.category).all()

        total_skills = db.query(func.count(CandidateSkill.id)).scalar()
        top_skills = db.query(
            CandidateSkill.skill,
            func.count(CandidateSkill.id).label("count")
        ).group_by(CandidateSkill.skill).order_by(
            func.count(CandidateSkill.id).desc()
        ).limit(5).all()

        upload_stats = db.query(
            UploadLog.status,
            func.count(UploadLog.id).label("count")
        ).group_by(UploadLog.status).all()

        # Print results
        print(f"{'='*60}")
        print(f"CANDIDATE STATISTICS")
        print(f"{'='*60}")
        print(f"Total candidates: {total_candidates}")

        if categories:
            print(f"\nCandidates by category:")
            for category, count in categories:
                print(f"  - {category:20s}: {count:3d}")
        else:
            print("No candidates found")

        print(f"\n{'='*60}")
        print(f"SKILLS STATISTICS")
        print(f"{'='*60}")
        print(f"Total skills extracted: {total_skills}")

        if top_skills:
            print(f"\nTop 5 skills:")
            for skill, count in top_skills:
                print(f"  - {skill:25s}: {count:3d}")
        else:
            print("No skills found")

        print(f"\n{'='*60}")
        print(f"UPLOAD STATISTICS")
        print(f"{'='*60}")

        for status, count in upload_stats:
            status_emoji = "✓" if status == "success" else "✗"
            print(f"  {status_emoji} {status:10s}: {count:3d}")

        db.close()
        print(f"\n{'='*60}")
        print("[+] Database check completed successfully")
        return True

    except Exception as e:
        print(f"[-] Database check failed: {e}")
        return False

if __name__ == "__main__":
    success = check_database()
    sys.exit(0 if success else 1)
