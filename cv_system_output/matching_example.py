"""
Example of using the matching engine directly (without API)

Run with: python -m pytest matching_example.py -v -s
Or: python matching_example.py
"""
from matching import CandidateMatcher, match_candidates, MatchResult


def example_direct_usage():
    """Example: Direct matching engine usage."""
    print("\n=== Direct Matching Engine Usage ===\n")

    # Sample candidates (in real system, fetch from database)
    candidates = [
        {
            "candidate_id": "cand_001",
            "name": "Alice Johnson",
            "cv_text": """
                Python Developer with 5 years experience.
                Proficient in Django and FastAPI.
                Experience with PostgreSQL and MongoDB.
                AWS certified. Docker and Kubernetes expert.
                Led team of 3 developers on microservices project.
            """,
        },
        {
            "candidate_id": "cand_002",
            "name": "Bob Smith",
            "cv_text": """
                JavaScript full-stack developer.
                React and Node.js specialist.
                5 years in web development.
                Experience with MySQL and Redis.
                Google Analytics expertise.
            """,
        },
        {
            "candidate_id": "cand_003",
            "name": "Charlie Brown",
            "cv_text": """
                Accountant with 10 years experience.
                Proficient in Excel, QuickBooks, Xero.
                Strong in financial reporting and audit.
                SAP and database experience.
            """,
        },
    ]

    # Job description
    job_description = """
        We are seeking a Senior Python Developer to join our team.

        Requirements:
        - 5+ years Python experience
        - Django or FastAPI framework experience
        - Strong PostgreSQL skills
        - Docker and Kubernetes knowledge
        - AWS experience
        - Leadership and team management

        Nice to have:
        - Open source contributions
        - CI/CD pipeline experience
    """

    # Run matching
    print("Matching candidates against job description...\n")
    results = match_candidates(
        job_description=job_description,
        candidates=candidates,
        text_weight=0.7,
        skill_weight=0.3,
    )

    # Display results
    for idx, result in enumerate(results, 1):
        print(f"{idx}. {result.name} (ID: {result.candidate_id})")
        print(f"   Final Score:     {result.final_score:.2%}")
        print(f"   Text Similarity: {result.similarity_score:.2%}")
        print(f"   Skill Match:     {result.skill_match_score:.2%}")
        print(f"   Matched Skills:  {', '.join(result.matched_skills) or 'None'}")
        print()


def example_batch_matching():
    """Example: Batch matching multiple jobs."""
    print("\n=== Batch Matching Example ===\n")

    candidates = [
        {
            "candidate_id": "emp_001",
            "name": "Engineer A",
            "cv_text": "Python Django PostgreSQL Docker AWS Kubernetes",
        },
        {
            "candidate_id": "emp_002",
            "name": "Engineer B",
            "cv_text": "JavaScript React Node.js MongoDB Redis",
        },
    ]

    jobs = [
        ("Backend", "Python Django FastAPI PostgreSQL Docker AWS"),
        ("Frontend", "React JavaScript TypeScript HTML CSS"),
        ("Operations", "Kubernetes Docker AWS Linux CI/CD"),
    ]

    matcher = CandidateMatcher(candidates)

    for job_title, job_desc in jobs:
        print(f"Job: {job_title}")
        results = matcher.match(job_desc)
        for result in results:
            print(f"  {result.name}: {result.final_score:.2%}")
        print()


def example_weight_comparison():
    """Example: Compare different weight configurations."""
    print("\n=== Weight Configuration Impact ===\n")

    candidates = [
        {
            "candidate_id": "c1",
            "name": "Candidate 1",
            "cv_text": """
                Senior Software Engineer with expertise in Python, Django, Flask,
                FastAPI, PostgreSQL, MongoDB, Docker, Kubernetes, AWS, CI/CD, Git.
                10 years of experience building scalable systems.
            """,
        },
    ]

    job_description = """
        Junior Python developer needed for startup.
        Must know Python. Experience with Django or Flask helpful.
    """

    print("Same candidate matched with different weight configurations:\n")

    configs = [
        (0.9, 0.1),  # Prioritize text similarity
        (0.7, 0.3),  # Balanced (default)
        (0.5, 0.5),  # Equal weight
        (0.1, 0.9),  # Prioritize skills
    ]

    for text_w, skill_w in configs:
        results = match_candidates(
            job_description,
            candidates,
            text_weight=text_w,
            skill_weight=skill_w,
        )
        result = results[0]
        print(
            f"Text: {text_w:.1f} | Skills: {skill_w:.1f} → "
            f"Score: {result.final_score:.2%} "
            f"(Text: {result.similarity_score:.2%}, Skills: {result.skill_match_score:.2%})"
        )


if __name__ == "__main__":
    print("=" * 60)
    print("Candidate Matching Engine Examples")
    print("=" * 60)

    example_direct_usage()
    example_batch_matching()
    example_weight_comparison()

    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)
