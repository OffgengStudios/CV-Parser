from __future__ import annotations

import json
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


class GoogleSheetsError(RuntimeError):
    """Raised when Google Sheets is configured but the API request fails."""
    pass


def is_configured() -> bool:
    return bool(
        (settings.GOOGLE_SERVICE_ACCOUNT_FILE or settings.GOOGLE_SERVICE_ACCOUNT_JSON)
        and settings.GOOGLE_SHEETS_SPREADSHEET_ID
    )


def has_credentials() -> bool:
    return bool(
        settings.GOOGLE_SERVICE_ACCOUNT_JSON
        or (
            settings.GOOGLE_SERVICE_ACCOUNT_FILE
            and settings.GOOGLE_SERVICE_ACCOUNT_FILE.exists()
        )
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

    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        log.warning(
            "Google Sheets sync skipped: install google-api-python-client and google-auth."
        )
        return None

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    if settings.GOOGLE_SERVICE_ACCOUNT_JSON:
        try:
            service_account_info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
            credentials = Credentials.from_service_account_info(
                service_account_info,
                scopes=scopes,
            )
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            log.warning(f"Google Sheets sync skipped: invalid service account JSON: {exc}")
            return None
    else:
        credentials_path = settings.GOOGLE_SERVICE_ACCOUNT_FILE
        if credentials_path is None or not credentials_path.exists():
            log.warning("Google Sheets sync skipped: credentials file not found.")
            return None
        credentials = Credentials.from_service_account_file(
            str(credentials_path),
            scopes=scopes,
        )
    try:
        return build("sheets", "v4", credentials=credentials, cache_discovery=False)
    except Exception as exc:
        raise GoogleSheetsError(f"Could not create Google Sheets client: {exc}") from exc


def _google_error_message(exc: Exception) -> str:
    status_code = getattr(getattr(exc, "resp", None), "status", None)
    reason = getattr(getattr(exc, "resp", None), "reason", None)
    content = getattr(exc, "content", None)
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    parts = []
    if status_code:
        parts.append(f"HTTP {status_code}")
    if reason:
        parts.append(str(reason))
    if content:
        parts.append(str(content))
    return ": ".join(parts) if parts else str(exc)


def _execute(request: Any, action: str) -> dict[str, Any]:
    try:
        return request.execute()
    except Exception as exc:
        raise GoogleSheetsError(f"{action} failed: {_google_error_message(exc)}") from exc


def _get_sheet_id(service: Any, tab_name: str) -> int | None:
    spreadsheet = _execute(
        service.spreadsheets().get(
            spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
            includeGridData=False,
        ),
        "Reading spreadsheet metadata",
    )
    for sheet in spreadsheet.get("sheets", []):
        properties = sheet.get("properties", {})
        if properties.get("title") == tab_name:
            return properties.get("sheetId")
    return None


def _ensure_sheet_exists(service: Any, tab_name: str) -> int:
    sheet_id = _get_sheet_id(service, tab_name)
    if sheet_id is not None:
        return sheet_id

    response = _execute(
        service.spreadsheets().batchUpdate(
            spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
            body={
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": tab_name,
                            }
                        }
                    }
                ]
            },
        ),
        f"Creating Google Sheet tab '{tab_name}'",
    )
    replies = response.get("replies", [])
    return replies[0]["addSheet"]["properties"]["sheetId"]


def _ensure_header_row(service: Any, tab_name: str, headers: list[str]) -> None:
    _ensure_sheet_exists(service, tab_name)
    response = _execute(
        service.spreadsheets().values().get(
            spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
            range=_sheet_range(tab_name, "1:1"),
        ),
        f"Reading header row for '{tab_name}'",
    )
    values = response.get("values", [])
    if values and values[0] == headers:
        return

    _execute(
        service.spreadsheets().values().update(
            spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
            range=_sheet_range(tab_name, f"A1:{_column_letter(len(headers))}1"),
            valueInputOption="RAW",
            body={"values": [headers]},
        ),
        f"Writing header row for '{tab_name}'",
    )


def _find_candidate_row(service: Any, candidate: "Candidate") -> int | None:
    response = _execute(
        service.spreadsheets().values().get(
            spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
            range=_sheet_range(settings.GOOGLE_SHEETS_TAB_NAME, "A:G"),
        ),
        "Reading candidate rows from Google Sheets",
    )
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
        _execute(
            service.spreadsheets().values().append(
                spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
                range=_sheet_range(settings.GOOGLE_SHEETS_TAB_NAME, f"A:{last_column}"),
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": values},
            ),
            "Appending candidate to Google Sheets",
        )
        log.info("Candidate synced to Google Sheets (append): id=%s", candidate.id)
        return

    _execute(
        service.spreadsheets().values().update(
            spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
            range=_sheet_range(
                settings.GOOGLE_SHEETS_TAB_NAME,
                f"A{row_index}:{last_column}{row_index}",
            ),
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ),
        "Updating candidate in Google Sheets",
    )
    log.info("Candidate synced to Google Sheets (update): id=%s", candidate.id)


def replace_main_sheet(candidates: list["Candidate"]) -> None:
    service = _get_service()
    if service is None:
        return

    values = build_main_sheet_values(candidates)
    last_column = _column_letter(len(SHEET_HEADERS))
    _ensure_sheet_exists(service, settings.GOOGLE_SHEETS_TAB_NAME)
    _execute(
        service.spreadsheets().values().clear(
            spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
            range=_sheet_range(settings.GOOGLE_SHEETS_TAB_NAME, f"A:{last_column}"),
            body={},
        ),
        "Clearing main Google Sheet tab",
    )
    _execute(
        service.spreadsheets().values().update(
            spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
            range=_sheet_range(
                settings.GOOGLE_SHEETS_TAB_NAME,
                f"A1:{last_column}{len(values)}",
            ),
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ),
        "Writing main Google Sheet tab",
    )
    log.info(
        "Google Sheets main tab replaced from database snapshot: %s candidates",
        len(candidates),
    )


def delete_candidate(candidate_id: str) -> None:
    service = _get_service()
    if service is None:
        return

    _ensure_header_row(service, settings.GOOGLE_SHEETS_TAB_NAME, SHEET_HEADERS)
    response = _execute(
        service.spreadsheets().values().get(
            spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
            range=_sheet_range(settings.GOOGLE_SHEETS_TAB_NAME, "A:G"),
        ),
        "Reading candidate rows from Google Sheets",
    )
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

    sheet_id = _ensure_sheet_exists(service, settings.GOOGLE_SHEETS_TAB_NAME)

    _execute(
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
        ),
        "Deleting candidate row from Google Sheets",
    )
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
    _execute(
        service.spreadsheets().values().append(
            spreadsheetId=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
            range=_sheet_range(settings.GOOGLE_SHEETS_ANALYTICS_TAB_NAME, "A:D"),
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ),
        "Appending batch analytics to Google Sheets",
    )
    log.info("Batch analytics appended to Google Sheets: %s", batch_timestamp)
