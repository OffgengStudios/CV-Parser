"""
skills_taxonomy.py — Single source of truth for the skills vocabulary.

Previously duplicated between parser/parser.py (SKILLS_KEYWORDS) and
matching/matcher.py (SKILLS_DATABASE). Both modules now import from here.

To add a new skill: append it to the appropriate section below.
The list is order-stable (important for parser's compiled regex patterns).
SKILLS_SET is a frozenset for O(1) lookup (used by the matcher).
"""

# ---------------------------------------------------------------------------
# Canonical skills list — the superset of both original lists
# ---------------------------------------------------------------------------
SKILLS: list[str] = [
    # Programming languages
    "python", "java", "javascript", "typescript", "c++", "c#", "golang", "ruby",
    "php", "swift", "kotlin", "rust", "scala", "r", "matlab", "perl", "erlang",
    # Web / frontend
    "html", "css", "react", "angular", "vue", "next.js", "nuxt", "svelte",
    "bootstrap", "tailwind", "jquery", "webpack",
    # Backend / infra
    "node.js", "django", "flask", "fastapi", "spring", "laravel", "express",
    "docker", "kubernetes", "terraform", "ansible", "jenkins", "ci/cd",
    "aws", "azure", "gcp", "linux", "nginx", "apache", "git",
    # Databases
    "postgresql", "mysql", "sqlite", "mongodb", "redis", "elasticsearch",
    "dynamodb", "cassandra", "oracle", "sql server", "mariadb",
    # Data / ML
    "machine learning", "deep learning", "tensorflow", "pytorch", "keras",
    "scikit-learn", "pandas", "numpy", "spark", "hadoop", "tableau", "power bi",
    "analytics", "data science", "nlp",
    # Office / admin
    "microsoft office", "excel", "word", "powerpoint", "outlook", "sharepoint",
    "google workspace", "google docs", "google sheets", "quickbooks", "sap",
    "sage", "xero", "data entry", "scheduling", "calendar management",
    # Marketing
    "seo", "sem", "google analytics", "google ads", "facebook ads", "instagram",
    "content marketing", "email marketing", "mailchimp", "hubspot", "crm",
    "copywriting", "brand management", "adobe creative suite", "photoshop",
    "illustrator", "canva", "social media", "wordpress",
    # Sales
    "salesforce", "sales strategy", "cold calling", "lead generation",
    "account management", "b2b", "b2c", "negotiation", "pipeline management",
    "customer acquisition", "upselling", "cross-selling",
    # Trade / technical
    "plumbing", "electrical", "carpentry", "welding", "hvac", "forklift",
    "autocad", "solidworks", "cnc", "quality control", "iso", "lean",
    "six sigma", "health and safety", "first aid",
    # Soft skills
    "project management", "agile", "scrum", "jira", "confluence",
    "communication", "leadership", "teamwork", "problem solving",
    "presentation", "critical thinking",
]

# Frozenset for O(1) membership testing (used by the matcher)
SKILLS_SET: frozenset[str] = frozenset(SKILLS)
