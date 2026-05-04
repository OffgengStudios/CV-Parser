"""
tests/test_system.py — Integration and unit tests for the CV system.

Run with: pytest tests/ -v
"""
import io
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from docx import Document
from docx.oxml import parse_xml

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from analytics import build_candidate_analytics, summarize_batch
from database.session import Base, get_db
from parser.parser import infer_name_from_filename, parse_cv, should_prefer_filename_name
from parser.extractor import extract_text, sanitize_text
from classifier.classifier import classify_cv
from api.pipeline import process_cv_file
from auth import get_current_user, require_admin_user
from google_sheets import (
    ANALYTICS_HEADERS,
    SHEET_HEADERS,
    build_main_sheet_values,
    candidate_to_sheet_row,
)


# ---------------------------------------------------------------------------
# Test database — in-memory SQLite, isolated per test session
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite://"  # In-memory

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = lambda: "test-user"


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Sample CV text fixtures
# ---------------------------------------------------------------------------

IT_CV_TEXT = """
John Smith
john.smith@example.com
+44 7700 900123

Summary
Experienced software engineer with 5 years in backend development.

Skills
Python, Django, FastAPI, Docker, Kubernetes, PostgreSQL, AWS, CI/CD, Git

Experience
Senior Software Developer - TechCorp Ltd (2020-2024)
Developed microservices using Python and FastAPI.
Deployed infrastructure on AWS using Terraform.

Education
BSc Computer Science - University of London (2019)
"""

MARKETING_CV_TEXT = """
Sarah Johnson
sarah.j@marketingpro.com
07800 123456

Profile
Digital marketing specialist with expertise in SEO and content marketing.

Key Skills
SEO, SEM, Google Analytics, Google Ads, Facebook Ads, HubSpot, Copywriting,
Content Marketing, Social Media, Email Marketing, Mailchimp

Work History
Marketing Manager - BrandX Agency (2021-2024)
Led SEO strategy resulting in 40% organic traffic increase.
Managed Google Ads campaigns with £50k monthly budget.

Education
BA Marketing - Manchester Metropolitan University (2020)
"""

SALES_CV_TEXT = """
Michael Brown
m.brown@salesstar.co.uk
+44 20 7946 0958

Objective
Target-driven sales professional with proven B2B sales track record.

Skills
Salesforce, CRM, Lead Generation, Cold Calling, Negotiation,
Pipeline Management, Account Management, B2B Sales, Upselling

Experience
Senior Account Executive - SalesCo (2019-2024)
Exceeded revenue targets by 125% for 3 consecutive years.
Managed pipeline of £2M+ in annual opportunities.

Education
BSc Business Studies (2018)
"""

ADMIN_CV_TEXT = """
Emma Wilson
emma.wilson@office.com
020 8123 4567

Profile
Experienced office administrator with expertise in scheduling and Microsoft Office.

Skills
Microsoft Office, Excel, Outlook, SharePoint, Data Entry, Scheduling,
Calendar Management, Correspondence, Record Keeping, QuickBooks

Experience
Office Manager - AdminPro Ltd (2018-2024)
Managed executive calendars and travel arrangements.
Processed expense reports and maintained filing systems.

Education
HND Business Administration (2017)
"""

TRADE_CV_TEXT = """
David Jones
d.jones@tradeswork.com
07912 345678

Profile
Qualified electrician with 10 years experience in commercial installations.

Skills
Electrical Installation, Health and Safety, First Aid, AutoCAD,
Quality Control, HVAC, Maintenance, ISO Standards

Experience
Senior Electrician - PowerTech Ltd (2014-2024)
Managed commercial electrical installation projects.
Supervised team of 5 junior electricians on site.

Education
City & Guilds Level 3 Electrical Installation (2013)
NVQ Level 3 Electrotechnical Services (2014)
"""

ELIZABETH_STYLE_CV_TEXT = """
ELIZABETH APEKU CLINICAL TRAINIG/WORK EXPERIENCE
P.O.BOX AD 805, KAKUMDO CAPE COAST. 2025-2026
elizabethapek399@gmail.com
Doctors in service clinic (Central Region, Cape Coast. Abura)
Contact: +233 557709859
PROFESSIONAL SUMMARY
Registered general nurse with 2 years of clinical experience.
"""

DARLINGTON_STYLE_CV_TEXT = """
DARLINGTON
FRANCIS
+233505532293
ASARE
darlintinasare24@gmail.com
WORK EXPERIENCE
GHANA TELECOM [TELECEL COMPANY Customer Service Agent]
"""

REGINA_STYLE_CV_TEXT = """
CURRICULUM VITAE
Name : Regina Ofori
Telephone Number : +233552011575
Email : reginareg001@gmail.com
Fiesta Royal Hotel Front Point Security 02/2024 - Present
Gloria's Inn Waitress 03/2023 - 05/2023
"""

SAMUEL_STYLE_CV_TEXT = """
SAMUEL KOFI YEBOAH
summy3666@gmail.com
Clinical Nutrition and Dietetics graduate with practical experience in hospital-based dietary assessment,
patient counselling, and nutritional planning.
Dietetic Intern
Greater Accra Regional Hospital
"""

GIDEON_STYLE_CV_TEXT = """
GIDEON KWAME ONOMAH
gideononumah01@gmail.com
Agricultural Biotechnology graduate with molecular biology techniques, genetic engineering,
plant tissue culture, and soil and environmental analysis experience.
Research Intern
Assisted in DNA extraction, PCR, and gel electrophoresis for crop trait studies.
AgriBusiness and Entrepreneurship certification.
"""

JACQUELINE_STYLE_CV_TEXT = """
JACQUELINE TINGANI
jacquelinetingani@gmail.com
Results-driven Accounting graduate with 2 years of experience in data enumeration and market data collection.
Financial Analysis & Reporting
Market Research & Data Collection
Microsoft Excel & MS Office Suite
"""

JEDIDIALLA_STYLE_CV_TEXT = """
JEDIDIALLA SARFO ADJEPONG
Customer service representative
Experience: 1 year | Available: Immediately | Location: Accra & Tema Region
jedidialla2@gmail.com |
+233262734398
ABOUT ME
I have good communication skills.
WORK EXPERIENCE
Mad. Irene
Internship & Graduate | Call Representative
2025-11-01 | Currently working here
No Experience |
EDUCATION
University of Education, Winneba
High School (S.S.C.E) | WASSCE certi\x00cate
JOB SKILLS
Digital marketing and writing
LANGUAGE SKILLS
Akan English
CERTIFICATES & AWARDS
"""


# ---------------------------------------------------------------------------
# Parser unit tests
# ---------------------------------------------------------------------------

class TestParser:
    def test_extract_email(self):
        parsed = parse_cv(sanitize_text(IT_CV_TEXT))
        assert parsed.email == "john.smith@example.com"

    def test_extract_phone_uk(self):
        parsed = parse_cv(sanitize_text(IT_CV_TEXT))
        assert parsed.phone is not None
        assert "7700" in parsed.phone or "900123" in parsed.phone

    def test_extract_name(self):
        parsed = parse_cv(sanitize_text(IT_CV_TEXT))
        assert parsed.name == "John Smith"

    def test_extract_name_ignores_section_heading(self):
        parsed = parse_cv(
            "Personal Details\nRebecca Hammond\nrebecca@example.com\n+233 24 111 2222"
        )
        assert parsed.name == "Rebecca Hammond"

    def test_extract_name_ignores_marital_status_line(self):
        parsed = parse_cv(
            "MARITAL STATUS SINGLE\nSalome Ibiang\nsalome@example.com\n+233 24 111 2222"
        )
        assert parsed.name == "Salome Ibiang"

    def test_extract_name_ignores_biodata_line(self):
        parsed = parse_cv(
            "Sex Female\nFawzia Akpaka\nfawzia@example.com\n+233 24 111 2222"
        )
        assert parsed.name == "Fawzia Akpaka"

    def test_extract_name_ignores_address_line(self):
        parsed = parse_cv(
            "Nungua-Accra\nPhilia Hammond\nphilia@example.com\n+233 24 111 2222"
        )
        assert parsed.name == "Philia Hammond"

    def test_extract_name_ignores_combined_heading_text(self):
        parsed = parse_cv(
            "ELIZABETH APEKU CLINICAL TRAINIG/WORK EXPERIENCE\nElizabeth Apeku\n+233 55 770 9859"
        )
        assert parsed.name == "Elizabeth Apeku"

    def test_extract_name_strips_name_prefix(self):
        parsed = parse_cv("Name : Regina Ofori\nregina@example.com\n+233 24 111 2222")
        assert parsed.name == "Regina Ofori"

    def test_extract_name_from_split_top_lines(self):
        parsed = parse_cv(sanitize_text(DARLINGTON_STYLE_CV_TEXT))
        assert parsed.name == "Darlington Francis Asare"

    def test_infer_name_from_filename_handles_camel_case(self):
        assert infer_name_from_filename("RebeccaHammond-CV.pdf") == "Rebecca Hammond"

    def test_infer_name_from_filename_handles_role_suffix(self):
        assert infer_name_from_filename("Elizabeth Apeku - Registered Nurse.pdf") == "Elizabeth Apeku"

    def test_should_prefer_filename_name_when_extracted_name_is_location_text(self):
        assert should_prefer_filename_name(
            "Cape Coast Abura",
            "Elizabeth Apeku - Registered Nurse.pdf",
        )

    def test_extract_skills_not_empty(self):
        parsed = parse_cv(sanitize_text(IT_CV_TEXT))
        assert len(parsed.skills) > 0

    def test_extract_known_skills(self):
        parsed = parse_cv(sanitize_text(IT_CV_TEXT))
        skill_names_lower = [s.lower() for s in parsed.skills]
        assert "python" in skill_names_lower
        assert "docker" in skill_names_lower

    def test_missing_email_returns_none(self):
        parsed = parse_cv("John Doe\nSoftware Developer with Python experience.")
        assert parsed.email is None

    def test_missing_phone_returns_none(self):
        parsed = parse_cv("Jane Doe\njane@example.com\nMarketing professional.")
        assert parsed.phone is None

    def test_year_range_not_extracted_as_phone(self):
        parsed = parse_cv("Work Experience\n2025-2026\nRegistered Nurse")
        assert parsed.phone is None

    def test_labeled_phone_is_preferred_over_dates(self):
        parsed = parse_cv(
            "Experience\n2025-2026\nPhone: +233 24 123 4567\nEmail: nurse@example.com"
        )
        assert parsed.phone == "+233 24 123 4567"

    def test_ghana_number_starting_with_233_is_treated_as_phone(self):
        parsed = parse_cv("Contact\n233241234567\nEmail: test@example.com")
        assert parsed.phone is not None
        assert "233" in parsed.phone

    def test_extract_us_phone_number(self):
        parsed = parse_cv("Phone: +1 (415) 555-2671\nEmail: us@example.com")
        assert parsed.phone == "+1 415-555-2671"

    def test_extract_uk_phone_number(self):
        parsed = parse_cv("Mobile: +44 7700 900123\nEmail: uk@example.com")
        assert parsed.phone == "+44 7700 900123"

    def test_extract_phone_from_realistic_ghana_cv_with_year_range(self):
        parsed = parse_cv(sanitize_text(ELIZABETH_STYLE_CV_TEXT))
        assert parsed.phone == "+233 55 770 9859"

    def test_empty_cv_text(self):
        parsed = parse_cv("")
        assert parsed.name is None
        assert parsed.email is None
        assert parsed.skills == []

    def test_experience_section_extracted(self):
        parsed = parse_cv(sanitize_text(IT_CV_TEXT))
        assert parsed.experience is not None
        assert len(parsed.experience) > 10

    def test_education_section_extracted(self):
        parsed = parse_cv(sanitize_text(IT_CV_TEXT))
        assert parsed.education is not None

    def test_parse_sales_rep_pdf_shape_with_irregular_sections(self):
        parsed = parse_cv(sanitize_text(JEDIDIALLA_STYLE_CV_TEXT))
        assert parsed.name == "Jedidialla Sarfo Adjepong"
        assert parsed.email == "jedidialla2@gmail.com"
        assert parsed.phone == "+233 26 273 4398"
        assert "communication" in [skill.lower() for skill in parsed.skills]
        assert parsed.experience is not None
        assert "No Experience" in parsed.experience
        assert parsed.education is not None
        assert "LANGUAGE SKILLS" not in parsed.education

    def test_parser_returns_partial_result_for_messy_unsectioned_cv(self):
        parsed = parse_cv(
            sanitize_text(
                """
                No Experience | Name: Akua Mensah | Email akua@example.com
                Mobile: +233 24 111 2222
                Python / Excel / Customer service
                """
            )
        )
        assert parsed.email == "akua@example.com"
        assert parsed.phone == "+233 24 111 2222"
        assert "excel" in [skill.lower() for skill in parsed.skills]

    def test_docx_extraction_reads_text_boxes(self):
        doc = Document()
        paragraph = doc.add_paragraph()
        paragraph._p.append(
            parse_xml(
                """
                <w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                     xmlns:v="urn:schemas-microsoft-com:vml">
                  <w:pict>
                    <v:shape>
                      <v:textbox>
                        <w:txbxContent>
                          <w:p>
                            <w:r><w:t>Faustina Okyere</w:t></w:r>
                          </w:p>
                        </w:txbxContent>
                      </v:textbox>
                    </v:shape>
                  </w:pict>
                </w:r>
                """
            )
        )

        temp_dir = Path(__file__).parent / "_tmp_docx"
        temp_dir.mkdir(exist_ok=True)
        path = temp_dir / f"{uuid.uuid4().hex}.docx"
        try:
            doc.save(path)
            assert "Faustina Okyere" in extract_text(path)
        finally:
            path.unlink(missing_ok=True)


class TestAnalytics:
    def test_build_candidate_analytics_normalizes_fields(self):
        analytics = build_candidate_analytics(
            name="  JOHN   DOE  ",
            email="John.Doe@Example.com ",
            phone=" +233 24 123 4567 ",
            skills=["python", "PYTHON", "power bi"],
            experience_text="5 years experience from 2019-2024",
            category="IT",
            subcategory="Data Analyst",
        )
        assert analytics.name == "JOHN DOE"
        assert analytics.email == "john.doe@example.com"
        assert analytics.skills == ["Power BI", "Python"]
        assert analytics.category == "Information Technology (IT)"
        assert analytics.years_experience == 6.0
        assert analytics.seniority_level == "Senior"

    def test_summarize_batch_returns_expected_metrics(self):
        candidates = [
            SimpleNamespace(
                category="Healthcare",
                years_experience=2.0,
                skills=[SimpleNamespace(skill="Python"), SimpleNamespace(skill="Excel")],
            ),
            SimpleNamespace(
                category="Healthcare",
                years_experience=4.0,
                skills=[SimpleNamespace(skill="Excel")],
            ),
            SimpleNamespace(
                category="Sales",
                years_experience=6.0,
                skills=[SimpleNamespace(skill="CRM")],
            ),
        ]
        summary = summarize_batch(candidates)
        assert summary["total_cvs_processed"] == 3
        assert summary["count_per_category"]["Healthcare"] == 2
        assert summary["top_skills"][0][0] == "Excel"
        assert summary["average_years_per_category"]["Healthcare"] == 3.0


# ---------------------------------------------------------------------------
# Classifier unit tests
# ---------------------------------------------------------------------------

class TestClassifier:
    def test_classify_it(self):
        result = classify_cv(sanitize_text(IT_CV_TEXT))
        assert result.category == "Information Technology (IT)"
        assert result.subcategory == "Software Development"
        assert result.confidence > 0.3

    def test_classify_marketing(self):
        result = classify_cv(sanitize_text(MARKETING_CV_TEXT))
        assert result.subcategory == "Digital Marketing"
        assert result.category == "Marketing"

    def test_classify_sales(self):
        result = classify_cv(sanitize_text(SALES_CV_TEXT))
        assert result.subcategory in {"Account Executive", "Business Development"}
        assert result.category == "Sales"

    def test_classify_administration(self):
        result = classify_cv(sanitize_text(ADMIN_CV_TEXT))
        assert result.category == "Administration & Operations"
        assert result.subcategory in {"Administrative Support", "Office Operations"}

    def test_classify_trade(self):
        result = classify_cv(sanitize_text(TRADE_CV_TEXT))
        assert result.category in {"Skilled Trades", "Engineering"}

    def test_classify_agriculture_research(self):
        result = classify_cv(sanitize_text(GIDEON_STYLE_CV_TEXT))
        assert result.category == "Agriculture"

    def test_classify_healthcare_nutrition(self):
        result = classify_cv(sanitize_text(SAMUEL_STYLE_CV_TEXT))
        assert result.category == "Healthcare"

    def test_classify_finance_data_research(self):
        result = classify_cv(sanitize_text(JACQUELINE_STYLE_CV_TEXT))
        assert result.category == "Business & Finance"

    def test_classify_security_hospitality_cv(self):
        result = classify_cv(sanitize_text(REGINA_STYLE_CV_TEXT))
        assert result.category in {"Security & Protective Services", "Hospitality & Tourism"}

    def test_all_scores_present(self):
        result = classify_cv(sanitize_text(IT_CV_TEXT))
        assert "Information Technology (IT)" in result.all_scores
        assert "Administration & Operations" in result.all_scores
        assert "Healthcare" in result.all_scores

    def test_confidence_is_normalized(self):
        result = classify_cv(sanitize_text(IT_CV_TEXT))
        assert 0.0 <= result.confidence <= 1.0
        total = sum(result.all_scores.values())
        assert abs(total - 1.0) < 0.01  # Scores sum to ~1.0

    def test_empty_text_does_not_crash(self):
        result = classify_cv("")
        assert result.category == "Administration & Operations"
        assert result.subcategory == "Administrative Support"
        assert result.confidence == 0.0

    def test_matched_keywords_populated(self):
        result = classify_cv(sanitize_text(IT_CV_TEXT))
        assert len(result.matched_keywords["Information Technology (IT)"]) > 0


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------

def _make_cv_upload(text: str, filename: str = "test_cv.txt") -> tuple:
    """Helper: returns (files dict, content) for TestClient upload."""
    content = text.encode("utf-8")
    return {"file": (filename, io.BytesIO(content), "application/octet-stream")}


class TestAPI:
    def test_root(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "service" in resp.json()

    def test_legacy_static_ui_is_not_served(self, client):
        resp = client.get("/app")
        assert resp.status_code == 404

    def test_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"] == "ok"

    def test_settings_status(self, client):
        app.dependency_overrides[require_admin_user] = lambda: "admin"
        try:
            resp = client.get("/api/v1/settings/status")
            assert resp.status_code == 200
            data = resp.json()
            assert "google_sheets_configured" in data
            assert "google_sheets_tab_name" in data
        finally:
            app.dependency_overrides.pop(require_admin_user, None)

    def test_upload_invalid_extension(self, client):
        files = [("files", ("resume.txt", io.BytesIO(b"John Doe"), "text/plain"))]
        resp = client.post("/api/v1/upload", files=files)
        assert resp.status_code == 201
        data = resp.json()
        assert data["success_count"] == 0
        assert data["failure_count"] == 1

    def test_list_candidates_empty(self, client):
        resp = client.get("/api/v1/candidates")
        assert resp.status_code == 200
        data = resp.json()
        assert "candidates" in data
        assert "total" in data

    def test_get_nonexistent_candidate(self, client):
        resp = client.get("/api/v1/candidates/nonexistent-id-000")
        assert resp.status_code == 404

    def test_delete_nonexistent_candidate(self, client):
        resp = client.delete("/api/v1/candidates/nonexistent-id-000")
        assert resp.status_code == 404

    def test_list_candidates_invalid_category(self, client):
        resp = client.get("/api/v1/candidates?category=Finance")
        assert resp.status_code == 400

    def test_upload_logs(self, client):
        resp = client.get("/api/v1/uploads/logs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_upload_allows_large_batch_requests(self, client):
        files = [
            ("files", (f"resume{i}.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf"))
            for i in range(21)
        ]
        resp = client.post("/api/v1/upload", files=files)
        assert resp.status_code == 201
        data = resp.json()
        assert data["total_files"] == 21
        assert "batch_summary" in data

    def test_download_selected_candidate_cvs_as_zip(self, client, monkeypatch):
        from api import routes as routes_module
        from database import crud

        upload_dir = Path(__file__).parent / "_tmp_zip_uploads" / uuid.uuid4().hex
        upload_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(routes_module.settings, "UPLOAD_DIR", upload_dir)

        saved_filename = "stored-cv.pdf"
        (upload_dir / saved_filename).write_bytes(b"%PDF-1.4 test cv")

        db = TestSessionLocal()
        try:
            candidate = crud.create_candidate(
                db=db,
                name="Zip Candidate",
                email="zip@example.com",
                phone=None,
                skills=["Python"],
                experience=None,
                education=None,
                cv_text="Zip Candidate Python",
                category="Information Technology (IT)",
                subcategory="Software Development",
                confidence=0.9,
                years_experience=3,
                seniority_level="Mid",
                source_filename="Zip Candidate CV.pdf",
                saved_upload_filename=saved_filename,
            )
        finally:
            db.close()

        resp = client.post(
            "/api/v1/candidates/cv-zip",
            json={"candidate_ids": [candidate.id], "zip_name": "shortlist"},
        )

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        assert 'filename="shortlist.zip"' in resp.headers["content-disposition"]

        with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
            assert archive.namelist() == ["Zip Candidate CV.pdf"]
            assert archive.read("Zip Candidate CV.pdf") == b"%PDF-1.4 test cv"


class TestPipeline:
    def test_process_cv_file_persists_saved_upload_filename(self, monkeypatch):
        from api import pipeline as pipeline_module

        upload_dir = Path(__file__).parent / "_tmp_uploads" / uuid.uuid4().hex
        upload_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(pipeline_module.settings, "UPLOAD_DIR", upload_dir)
        monkeypatch.setattr(
            pipeline_module,
            "extract_text",
            lambda path: ELIZABETH_STYLE_CV_TEXT,
        )
        monkeypatch.setattr(pipeline_module, "append_candidate", lambda candidate: None)

        db = TestSessionLocal()
        try:
            candidate = process_cv_file(
                file_content=b"%PDF-1.4 test content",
                original_filename="Elizabeth Apeku - Registered Nurse.pdf",
                db=db,
            )
            assert candidate.saved_upload_filename is not None
            assert (upload_dir / candidate.saved_upload_filename).exists()

            refreshed = db.get(type(candidate), candidate.id)
            assert refreshed is not None
            assert refreshed.saved_upload_filename == candidate.saved_upload_filename
        finally:
            db.close()

    def test_process_cv_file_persists_partial_result_when_classification_fails(self, monkeypatch):
        from api import pipeline as pipeline_module

        upload_dir = Path(__file__).parent / "_tmp_uploads" / uuid.uuid4().hex
        upload_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(pipeline_module.settings, "UPLOAD_DIR", upload_dir)
        monkeypatch.setattr(
            pipeline_module,
            "extract_text",
            lambda path: JEDIDIALLA_STYLE_CV_TEXT,
        )
        monkeypatch.setattr(
            pipeline_module,
            "classify_cv",
            lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad format")),
        )
        monkeypatch.setattr(pipeline_module, "append_candidate", lambda candidate: None)

        db = TestSessionLocal()
        try:
            candidate = process_cv_file(
                file_content=b"%PDF-1.4 test content",
                original_filename="JedidiallaSarfoAdjepong.pdf",
                db=db,
            )
            assert candidate.name == "Jedidialla Sarfo Adjepong"
            assert candidate.email == "jedidialla2@gmail.com"
            assert candidate.category == "Administration & Operations"
            assert candidate.confidence == 0.0
        finally:
            db.close()


class TestGoogleSheets:
    def test_main_sheet_headers_match_requested_template(self):
        assert SHEET_HEADERS == [
            "Candidate Name",
            "Email",
            "Skills",
            "Category",
            "Experience",
            "Upload Date",
            "candidate_id",
        ]

    def test_candidate_to_sheet_row_includes_two_level_category_fields(self):
        candidate = SimpleNamespace(
            id="candidate-123",
            name="Jane Doe",
            email="jane@example.com",
            years_experience=4.0,
            seniority_level="Mid",
            skills=[SimpleNamespace(skill="python"), SimpleNamespace(skill="excel")],
            experience="Operations support",
            education="BSc",
            category="Administration & Operations",
            subcategory="Administrative Support",
            confidence=0.82,
            source_filename="jane.pdf",
            created_at=datetime(2026, 3, 31, 10, 0, tzinfo=timezone.utc),
        )

        row = candidate_to_sheet_row(candidate)

        assert row[0] == "Jane Doe"
        assert row[1] == "jane@example.com"
        assert row[2] == "python, excel"
        assert row[3] == "Administration & Operations"
        assert row[4] == "4.0"
        assert row[5] == "2026-03-31T10:00:00+00:00"
        assert row[6] == "candidate-123"

    def test_build_main_sheet_values_replaces_tab_with_header_and_rows(self):
        candidate = SimpleNamespace(
            id="candidate-123",
            name="Jane Doe",
            email="jane@example.com",
            years_experience=4.0,
            skills=[SimpleNamespace(skill="python")],
            category="Administration & Operations",
            created_at=datetime(2026, 3, 31, 10, 0, tzinfo=timezone.utc),
        )

        values = build_main_sheet_values([candidate])

        assert values[0] == SHEET_HEADERS
        assert values[1][0] == "Jane Doe"
        assert values[1][6] == "candidate-123"

    def test_analytics_headers_are_stable(self):
        assert ANALYTICS_HEADERS == [
            "batch_timestamp",
            "metric_type",
            "dimension",
            "value",
        ]
