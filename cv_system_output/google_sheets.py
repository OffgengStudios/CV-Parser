from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from config import settings
from logger import get_logger

if TYPE_CHECKING:
    from database.models import Candidate

log = get_logger(__name__)

SHEET_HEADERS = [
    "Candidate Name",
    "Email",
    "Skills",
    "Category",
    "Experience",
    "Upload Date",
    "candidate_id",
]

ANALYTICS_HEADERS = [
    "batch_timestamp",
    "metric_type",
    "dimension",
    "value",
]


def is_configured() -> bool:
    return bool(
        settings.GOOGLE_SERVICE_ACCOUNT_FILE
        and settings.GOOGLE_SHEETS_SPREADSHEET_ID
    )


def candidate_to_sheet_row(candidate: "Candidate") -> list[str]:
    return [
        candidate.name or "",
        candidate.email or "",
        ", ".join(skill.skill for skill in candidate.skills),
        candidate.category or "",
        str(candidate.years_experience) if candidate.years_experience is not None else "",
        candidate.created_at.isoformat(),
        candidate.id,
    ]


def build_main_sheet_values(candidates: list["Candidate"]) -> list[list[str]]:
    return [SHEET_HEADERS, *[candidate_to_sheet_row(candidate) for candidate in candidates]]


def _column_letter(index: int) -> str:
    result = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _sheet_range(tab_name: str, cell_range: str) -> str:
    escaped = tab_name.replace("'", "''")
    return f"'{escaped}'!{cell_range}"


def _get_service():
    if not is_configured():
        return None

    credentials_path = settings.GOOGLE_SERVICE_ACCOUNT_FILE
    if credentials_path is None or not credentials_path.exists():
        log.warning("Google Sheets sync skipped: credentials file not found.")
        return None

    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        log.warning(
            "Google Sheets sync skipped: install google-api-python-client and google-auth."
        )
        return None

    credentials = Credentials.from_service_account_file(
        str(credentials_path),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=credentials)


def _ensure_header_row(service: Any, tab_name: str, headers: list[str]) -> None:
    response = service.spreadsheets().values().get(
        spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
        range=_sheet_range(tab_name, "1:1"),
    ).execute()
    values = response.get("values", [])
    if values and values[0] == headers:
        return

    service.spreadsheets().values().update(
        spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
        range=_sheet_range(tab_name, f"A1:{_column_letter(len(headers))}1"),
        valueInputOption="RAW",
        body={"values": [headers]},
    ).execute()


def _find_candidate_row(service: Any, candidate: "Candidate") -> int | None:
    response = service.spreadsheets().values().get(
        spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
        range=_sheet_range(settings.GOOGLE_SHEETS_TAB_NAME, "A:G"),
    ).execute()
    values = response.get("values", [])

    for index, row in enumerate(values, start=1):
        if index == 1:
            continue
        stored_candidate_id = row[6] if len(row) > 6 else ""
        if stored_candidate_id == candidate.id:
            return index
    return None


def sync_candidate(candidate: "Candidate") -> None:
    service = _get_service()
    if service is None:
        return

    _ensure_header_row(service, settings.GOOGLE_SHEETS_TAB_NAME, SHEET_HEADERS)
    values = [candidate_to_sheet_row(candidate)]
    row_index = _find_candidate_row(service, candidate)
    last_column = _column_letter(len(SHEET_HEADERS))

    if row_index is None:
        service.spreadsheets().values().append(
            spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
            range=_sheet_range(settings.GOOGLE_SHEETS_TAB_NAME, f"A:{last_column}"),
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        ).execute()
        log.info("Candidate synced to Google Sheets (append): id=%s", candidate.id)
        return

    service.spreadsheets().values().update(
        spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
        range=_sheet_range(
            settings.GOOGLE_SHEETS_TAB_NAME,
            f"A{row_index}:{last_column}{row_index}",
        ),
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()
    log.info("Candidate synced to Google Sheets (update): id=%s", candidate.id)


def replace_main_sheet(candidates: list["Candidate"]) -> None:
    service = _get_service()
    if service is None:
        return

    values = build_main_sheet_values(candidates)
    last_column = _column_letter(len(SHEET_HEADERS))
    service.spreadsheets().values().clear(
        spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
        range=_sheet_range(settings.GOOGLE_SHEETS_TAB_NAME, f"A:{last_column}"),
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
        range=_sheet_range(
            settings.GOOGLE_SHEETS_TAB_NAME,
            f"A1:{last_column}{len(values)}",
        ),
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()
    log.info(
        "Google Sheets main tab replaced from database snapshot: %s candidates",
        len(candidates),
    )


def delete_candidate(candidate_id: str) -> None:
    service = _get_service()
    if service is None:
        return

    _ensure_header_row(service, settings.GOOGLE_SHEETS_TAB_NAME, SHEET_HEADERS)
    response = service.spreadsheets().values().get(
        spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
        range=_sheet_range(settings.GOOGLE_SHEETS_TAB_NAME, "A:G"),
    ).execute()
    values = response.get("values", [])
    row_index = None
    for index, row in enumerate(values, start=1):
        if index == 1:
            continue
        stored_candidate_id = row[6] if len(row) > 6 else ""
        if stored_candidate_id == candidate_id:
            row_index = index
            break

    if row_index is None or row_index == 1:
        return

    spreadsheet = service.spreadsheets().get(
        spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID
    ).execute()
    sheet_id = spreadsheet["sheets"][0]["properties"]["sheetId"]

    for sheet in spreadsheet["sheets"]:
        if sheet["properties"]["title"] == settings.GOOGLE_SHEETS_TAB_NAME:
            sheet_id = sheet["properties"]["sheetId"]
            break

    service.spreadsheets().batchUpdate(
        spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
        body={
            "requests": [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": row_index - 1,
                            "endIndex": row_index,
                        }
                    }
                }
            ]
        },
    ).execute()
    log.info("Candidate removed from Google Sheets: id=%s", candidate_id)


def append_candidate(candidate: "Candidate") -> None:
    sync_candidate(candidate)


def append_batch_analytics(summary: dict[str, object]) -> None:
    service = _get_service()
    if service is None:
        return

    batch_timestamp = datetime.now(timezone.utc).isoformat()
    rows: list[list[str | int | float]] = [
        [batch_timestamp, "total_cvs_processed", "", summary["total_cvs_processed"]],
    ]

    for category, count in summary["count_per_category"].items():
        rows.append([batch_timestamp, "count_per_job_category", category, count])

    for skill, count in summary["top_skills"]:
        rows.append([batch_timestamp, "top_skill", skill, count])

    for category, average in summary["average_years_per_category"].items():
        rows.append([batch_timestamp, "average_years_experience", category, average])

    _ensure_header_row(
        service,
        settings.GOOGLE_SHEETS_ANALYTICS_TAB_NAME,
        ANALYTICS_HEADERS,
    )
    service.spreadsheets().values().append(
        spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
        range=_sheet_range(settings.GOOGLE_SHEETS_ANALYTICS_TAB_NAME, "A:D"),
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()
    log.info("Batch analytics appended to Google Sheets: %s", batch_timestamp)
