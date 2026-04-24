"""
Two-level candidate classification.

Level 1: Main category
Level 2: Subcategory
"""
import re
from dataclasses import dataclass

from classifier.supervised import load_trained_model
from logger import get_logger

log = get_logger(__name__)

DEFAULT_MAIN_CATEGORY = "Administration & Operations"
DEFAULT_SUBCATEGORY = "Administrative Support"

TAXONOMY: dict[str, dict[str, dict[str, float]]] = {
    "Management": {
        "Operations Management": {
            "operations manager": 3.0,
            "general manager": 3.0,
            "assistant general manager": 3.0,
            "branch manager": 2.5,
            "business operations": 2.0,
            "daily operations": 2.0,
            "staff schedules": 1.5,
            "supervise daily": 1.5,
            "operations strategy": 2.0,
        },
        "Project Management": {
            "project manager": 3.0,
            "program manager": 3.0,
            "scrum master": 2.5,
            "pmp": 2.0,
            "delivery manager": 2.5,
            "stakeholder management": 1.5,
        },
    },
    "Business & Finance": {
        "Accounting & Bookkeeping": {
            "accountant": 3.0,
            "accounting graduate": 2.0,
            "account officer": 3.0,
            "bookkeeper": 3.0,
            "accounts payable": 2.5,
            "accounts receivable": 2.5,
            "quickbooks": 2.0,
            "xero": 2.0,
            "sage": 2.0,
            "payroll": 2.0,
            "reconciliation": 2.0,
        },
        "Financial Analysis": {
            "financial analyst": 3.0,
            "budgeting": 2.0,
            "forecasting": 2.0,
            "financial modeling": 2.5,
            "financial reporting": 2.5,
            "financial analysis": 2.5,
            "cost analysis": 2.0,
            "variance analysis": 2.0,
            "cash flow": 2.0,
            "audit": 1.5,
            "auditing": 1.5,
            "tax compliance": 2.0,
            "market research": 1.5,
            "data collection": 1.5,
            "customer surveys": 1.5,
            "spss": 2.0,
        },
    },
    "Information Technology (IT)": {
        "Software Development": {
            "software engineer": 3.0,
            "software developer": 3.0,
            "backend developer": 2.5,
            "frontend developer": 2.5,
            "full stack": 2.5,
            "react": 1.5,
            "node.js": 1.5,
            "java": 1.5,
            "python": 1.5,
            "typescript": 1.5,
            "api": 1.0,
            "microservices": 2.0,
        },
        "Data Analyst": {
            "data analyst": 3.0,
            "business intelligence": 2.5,
            "power bi": 2.5,
            "tableau": 2.5,
            "sql": 1.5,
            "excel": 1.0,
            "dashboard": 1.5,
            "reporting": 1.5,
            "analytics": 1.5,
            "data visualization": 2.0,
        },
        "Infrastructure & Cloud": {
            "devops": 3.0,
            "cloud engineer": 2.5,
            "systems administrator": 2.5,
            "network engineer": 2.5,
            "aws": 2.0,
            "azure": 2.0,
            "gcp": 2.0,
            "docker": 2.0,
            "kubernetes": 2.0,
            "terraform": 2.0,
            "linux": 1.5,
        },
        "Cybersecurity & Support": {
            "cybersecurity": 3.0,
            "security analyst": 2.5,
            "soc analyst": 2.5,
            "it support": 2.0,
            "help desk": 2.0,
            "technical support": 2.0,
            "incident response": 2.0,
            "troubleshooting": 1.5,
        },
    },
    "Engineering": {
        "Civil Engineering": {
            "civil engineer": 3.0,
            "structural engineer": 2.5,
            "site engineer": 2.5,
            "surveying": 2.0,
            "road design": 2.0,
        },
        "Mechanical Engineering": {
            "mechanical engineer": 3.0,
            "solidworks": 2.0,
            "autocad": 1.5,
            "maintenance engineer": 2.0,
            "hvac design": 2.0,
        },
        "Electrical Engineering": {
            "electrical engineer": 3.0,
            "power systems": 2.0,
            "electrical design": 2.5,
            "instrumentation": 2.0,
        },
    },
    "Healthcare": {
        "Nursing": {
            "registered nurse": 3.0,
            "nurse": 2.5,
            "midwife": 2.5,
            "patient care": 2.0,
            "clinical care": 2.0,
            "triage": 2.0,
        },
        "Medicine": {
            "medical doctor": 3.0,
            "physician": 3.0,
            "doctor": 2.5,
            "clinical diagnosis": 2.0,
            "surgery": 2.0,
        },
        "Pharmacy & Laboratory": {
            "pharmacist": 3.0,
            "pharmacy technician": 2.5,
            "laboratory scientist": 2.5,
            "medical laboratory": 2.5,
            "specimen": 1.5,
        },
        "Nutrition & Dietetics": {
            "nutrition": 2.5,
            "dietetics": 2.5,
            "dietetic": 2.5,
            "nutritionist": 3.0,
            "nutritional assessment": 2.5,
            "dietary planning": 2.5,
            "patient counselling": 2.0,
            "patient counseling": 2.0,
            "public health education": 1.5,
            "menu planning": 1.5,
        },
        "Psychology & Counseling": {
            "psychology": 2.5,
            "counseling": 2.0,
            "counselling": 2.0,
            "health education": 1.5,
            "patient records": 1.5,
            "medical records": 1.5,
            "hospital": 1.0,
        },
    },
    "Education": {
        "Teaching": {
            "teacher": 3.0,
            "tutor": 2.5,
            "lecturer": 3.0,
            "classroom management": 2.0,
            "lesson planning": 2.0,
        },
        "Academic Administration": {
            "administrator": 2.0,
            "headteacher": 2.5,
            "school administrator": 2.5,
            "academic coordinator": 2.5,
            "school operations": 2.5,
            "student admissions": 2.0,
            "student registrations": 2.0,
            "academic records": 2.0,
            "attendance records": 2.0,
            "pta": 1.5,
            "curriculum": 2.0,
        },
    },
    "Legal": {
        "Legal Practice": {
            "lawyer": 3.0,
            "attorney": 3.0,
            "solicitor": 3.0,
            "litigation": 2.0,
            "legal research": 2.0,
        },
        "Compliance & Paralegal": {
            "paralegal": 3.0,
            "compliance officer": 2.5,
            "legal assistant": 2.5,
            "contract review": 2.0,
        },
    },
    "Arts & Media": {
        "Graphic Design": {
            "graphic designer": 3.0,
            "photoshop": 2.0,
            "illustrator": 2.0,
            "canva": 1.5,
            "branding": 1.5,
        },
        "Content & Journalism": {
            "journalist": 3.0,
            "broadcasting": 2.5,
            "publisher": 2.0,
            "presenter": 2.0,
            "host": 2.0,
            "interviewing": 1.5,
            "audio editing": 2.0,
            "copywriter": 2.5,
            "editor": 2.5,
            "content writer": 2.5,
            "storytelling": 1.5,
        },
        "Video & Photography": {
            "videographer": 3.0,
            "video editor": 2.5,
            "photographer": 3.0,
            "premiere pro": 2.0,
        },
    },
    "Sales": {
        "Account Executive": {
            "account executive": 3.0,
            "account manager": 2.5,
            "relationship manager": 2.0,
            "client acquisition": 2.0,
        },
        "Business Development": {
            "business development": 3.0,
            "lead generation": 2.0,
            "cold calling": 2.0,
            "pipeline management": 2.0,
            "sales strategy": 2.0,
            "prospecting": 1.5,
        },
        "Retail Sales": {
            "sales representative": 2.5,
            "retail sales": 3.0,
            "cashier": 3.0,
            "sales personnel": 2.5,
            "customer service": 2.0,
            "customer service agent": 2.5,
            "customer service associate": 2.5,
            "shop attendant": 2.0,
            "merchandising": 2.0,
            "point of sale": 2.0,
        },
    },
    "Marketing": {
        "Digital Marketing": {
            "digital marketing": 3.0,
            "seo": 1.5,
            "sem": 1.5,
            "google analytics": 2.0,
            "google ads": 2.0,
            "facebook ads": 2.0,
            "email marketing": 2.0,
            "hubspot": 2.0,
            "mailchimp": 1.5,
        },
        "Brand & Communications": {
            "brand manager": 3.0,
            "communications": 2.0,
            "pr": 1.5,
            "campaign manager": 2.5,
            "market research": 2.0,
        },
        "Content & Social Media": {
            "content marketing": 2.5,
            "copywriting": 2.0,
            "social media": 2.0,
            "content creation": 2.0,
            "wordpress": 1.0,
        },
    },
    "Administration & Operations": {
        "Administrative Support": {
            "administrative assistant": 3.0,
            "administrator": 3.0,
            "administration": 2.0,
            "executive assistant": 3.0,
            "receptionist": 2.5,
            "data entry": 2.0,
            "calendar management": 2.0,
            "scheduling": 2.0,
            "records": 1.5,
            "filing": 2.0,
            "official documents": 2.0,
            "staff records": 2.0,
            "student records": 2.0,
            "registrations": 1.5,
            "correspondence": 1.5,
        },
        "Office Operations": {
            "office manager": 3.0,
            "office administrator": 3.0,
            "school fees": 1.5,
            "issue receipts": 1.5,
            "accounts": 1.0,
            "record keeping": 1.5,
            "documentation": 1.0,
            "travel arrangements": 1.5,
            "expense reports": 1.5,
        },
        "HR & Coordination": {
            "hr administration": 2.5,
            "coordinator": 2.0,
            "compliance": 1.0,
            "onboarding": 2.0,
            "recruitment": 2.0,
        },
    },
    "Agriculture": {
        "Crop Production": {
            "agronomist": 3.0,
            "crop production": 2.5,
            "irrigation": 2.0,
            "soil": 2.0,
            "soil research": 2.0,
            "farm management": 2.0,
            "agricultural biotechnology": 3.0,
            "sustainable agriculture": 2.5,
            "agroecology": 2.5,
            "agronomic data": 2.5,
            "crop trait studies": 2.0,
            "sorghum": 1.5,
        },
        "Livestock & Veterinary Support": {
            "livestock": 2.5,
            "poultry": 2.5,
            "veterinary": 2.5,
            "animal husbandry": 2.5,
        },
        "Agricultural Research": {
            "dna extraction": 2.5,
            "pcr": 2.5,
            "gel electrophoresis": 2.5,
            "plant tissue culture": 3.0,
            "soil chemistry": 2.0,
            "molecular biology": 2.0,
            "genetic engineering": 2.0,
            "crop species": 1.5,
            "agribusiness": 2.0,
            "agriconnect": 1.5,
        },
    },
    "Skilled Trades": {
        "Electrical": {
            "electrician": 3.0,
            "electrical installation": 3.0,
            "wiring": 2.0,
            "power tools": 1.5,
        },
        "Construction": {
            "carpenter": 3.0,
            "bricklaying": 3.0,
            "roofing": 3.0,
            "construction": 2.0,
            "site supervisor": 2.5,
            "foreman": 2.5,
        },
        "Automotive & Mechanical": {
            "mechanic": 3.0,
            "automotive technician": 3.0,
            "vehicle maintenance": 2.0,
            "diagnostics": 2.0,
        },
        "Plumbing & HVAC": {
            "plumber": 3.0,
            "hvac": 3.0,
            "pipe fitting": 2.0,
            "installation": 1.5,
        },
    },
    "Manufacturing": {
        "Production Operations": {
            "production": 2.5,
            "manufacturing": 2.5,
            "assembly line": 2.0,
            "machine operator": 2.5,
            "lean manufacturing": 2.0,
        },
        "Quality Assurance": {
            "quality assurance": 2.5,
            "quality control": 2.5,
            "iso": 1.5,
            "six sigma": 2.0,
            "compliance inspection": 2.0,
        },
        "CNC & Machining": {
            "cnc": 3.0,
            "machinist": 3.0,
            "solidworks": 1.5,
            "fabrication": 2.0,
            "welding": 2.5,
        },
    },
    "Transport & Logistics": {
        "Driving & Delivery": {
            "driver": 2.5,
            "delivery": 2.5,
            "forklift": 2.0,
            "truck driver": 3.0,
            "courier": 2.5,
        },
        "Warehouse & Inventory": {
            "warehouse": 2.5,
            "inventory": 2.0,
            "stock control": 2.0,
            "dispatch": 2.0,
            "packing": 1.5,
        },
        "Supply Chain": {
            "logistics coordinator": 3.0,
            "supply chain": 3.0,
            "procurement": 2.0,
            "shipping": 2.0,
            "freight": 2.0,
        },
    },
    "Hospitality & Tourism": {
        "Hotel Operations": {
            "hotel": 2.5,
            "front desk": 2.5,
            "housekeeping": 2.0,
            "guest relations": 2.0,
        },
        "Food & Beverage": {
            "chef": 3.0,
            "cook": 2.5,
            "waiter": 2.5,
            "bartender": 2.5,
            "restaurant": 2.0,
            "food preparation": 2.0,
        },
        "Travel & Guest Services": {
            "tourism": 2.5,
            "travel consultant": 3.0,
            "reservation": 2.0,
            "ticketing": 2.0,
        },
    },
    "Security & Protective Services": {
        "Security Guarding": {
            "security guard": 3.0,
            "security officer": 3.0,
            "point security": 2.5,
            "front point security": 3.0,
            "security personnel": 2.5,
            "cctv": 2.0,
            "surveillance": 2.0,
            "access control": 2.0,
        },
        "Law Enforcement": {
            "police": 3.0,
            "law enforcement": 3.0,
            "investigation": 2.0,
        },
        "Safety & Loss Prevention": {
            "loss prevention": 2.5,
            "health and safety": 2.0,
            "risk assessment": 2.0,
        },
    },
    "Social Services": {
        "Community Support": {
            "community outreach": 2.5,
            "social worker": 3.0,
            "support worker": 2.5,
            "case management": 2.0,
        },
        "Counseling & Case Work": {
            "counselor": 3.0,
            "case worker": 2.5,
            "mental health": 2.0,
            "psychosocial": 2.0,
        },
        "NGO & Development": {
            "ngo": 2.5,
            "nonprofit": 2.5,
            "development project": 2.0,
            "humanitarian": 2.0,
        },
    },
}

MAIN_CATEGORIES = list(TAXONOMY.keys())

_COMPILED_PATTERNS: dict[str, dict[str, list[tuple[str, float, re.Pattern]]]] = {
    main_category: {
        subcategory: [
            (keyword, weight, re.compile(r"\b" + re.escape(keyword) + r"\b", re.IGNORECASE))
            for keyword, weight in keywords.items()
        ]
        for subcategory, keywords in subcategories.items()
    }
    for main_category, subcategories in TAXONOMY.items()
}


def _predict_subcategory_for_category(text: str, main_category: str) -> str:
    subcategories = _COMPILED_PATTERNS.get(main_category, {})
    if not subcategories:
        return DEFAULT_SUBCATEGORY

    scores: dict[str, float] = {}
    for subcategory, patterns in subcategories.items():
        score = 0.0
        for _, weight, pattern in patterns:
            if pattern.search(text):
                score += weight
        scores[subcategory] = score

    if not scores:
        return DEFAULT_SUBCATEGORY
    return max(scores, key=scores.get)


@dataclass
class ClassificationResult:
    category: str
    subcategory: str
    confidence: float
    all_scores: dict[str, float]
    matched_keywords: dict[str, list[str]]


def classify_cv(text: str, skills: list[str] | None = None) -> ClassificationResult:
    combined_text = text
    if skills:
        combined_text += "\n" + " ".join(skills)

    trained_model = load_trained_model()
    if trained_model is not None:
        result = trained_model.predict(combined_text)
        if result is not None:
            top_category, confidence, probabilities = result
            if top_category in MAIN_CATEGORIES:
                top_subcategory = _predict_subcategory_for_category(combined_text, top_category)
                log.info(
                    f"Trained classification: {top_category} / {top_subcategory} "
                    f"(confidence={confidence:.2%})"
                )
                # Populate all_scores with real probabilities for every known
                # category. Categories the model was not trained on default to 0.0.
                all_scores = {
                    category: probabilities.get(category, 0.0)
                    for category in MAIN_CATEGORIES
                }
                return ClassificationResult(
                    category=top_category,
                    subcategory=top_subcategory,
                    confidence=confidence,
                    all_scores=all_scores,
                    matched_keywords={category: [] for category in MAIN_CATEGORIES},
                )

    main_scores: dict[str, float] = {}
    sub_scores: dict[str, dict[str, float]] = {}
    matched_keywords: dict[str, list[str]] = {category: [] for category in MAIN_CATEGORIES}

    for main_category, subcategories in _COMPILED_PATTERNS.items():
        main_score = 0.0
        sub_scores[main_category] = {}

        for subcategory, patterns in subcategories.items():
            score = 0.0
            for keyword, weight, pattern in patterns:
                if pattern.search(combined_text):
                    score += weight
                    matched_keywords[main_category].append(keyword)
            sub_scores[main_category][subcategory] = score
            main_score += score

        main_scores[main_category] = main_score

    total = sum(main_scores.values())
    if total == 0:
        log.warning(
            "No category keywords matched — defaulting to "
            f"{DEFAULT_MAIN_CATEGORY} / {DEFAULT_SUBCATEGORY}."
        )
        return ClassificationResult(
            category=DEFAULT_MAIN_CATEGORY,
            subcategory=DEFAULT_SUBCATEGORY,
            confidence=0.0,
            all_scores={category: 0.0 for category in MAIN_CATEGORIES},
            matched_keywords=matched_keywords,
        )

    confidence_scores = {
        category: round(score / total, 4) for category, score in main_scores.items()
    }
    top_category = max(confidence_scores, key=lambda category: confidence_scores[category])
    top_subcategory = max(
        sub_scores[top_category],
        key=lambda subcategory: sub_scores[top_category][subcategory],
    )

    log.info(
        f"Classification: {top_category} / {top_subcategory} "
        f"(confidence={confidence_scores[top_category]:.2%}) | "
        f"scores={confidence_scores}"
    )

    return ClassificationResult(
        category=top_category,
        subcategory=top_subcategory,
        confidence=confidence_scores[top_category],
        all_scores=confidence_scores,
        matched_keywords=matched_keywords,
    )
