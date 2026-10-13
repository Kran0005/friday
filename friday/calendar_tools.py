import datetime as dt
import os
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.rrule import rrulestr
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from livekit.agents import function_tool, RunContext

from .actions import stage_action
from .paths import PRIVATE_DIR, PROJECT_ROOT, ensure_data_dirs


SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_PATH = PRIVATE_DIR / "token.json"
CREDENTIALS_PATH = PRIVATE_DIR / "calendar_credentials.json"
load_dotenv(PROJECT_ROOT / ".env")
TIME_ZONE_NAME = os.getenv("FRIDAY_TIMEZONE", "Asia/Kolkata")


def get_local_timezone():
    try:
        return ZoneInfo(TIME_ZONE_NAME)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"Unknown FRIDAY_TIMEZONE '{TIME_ZONE_NAME}'. Set it to a time zone such as Asia/Kolkata."
        ) from exc


def get_calendar_service():
    ensure_data_dirs()
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.is_file():
                raise FileNotFoundError(f"Google Calendar credentials not found: {CREDENTIALS_PATH}")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return build("calendar", "v3", credentials=creds)


def _parse_event_time(value: str) -> dt.datetime:
    value = value.strip().replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Use a date and time such as 2026-10-20T15:00 or include a UTC offset.") from exc
    local_tz = get_local_timezone()
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=local_tz)
    return parsed.astimezone(local_tz)


def _format_event_time(event_part: dict) -> str:
    if event_part.get("dateTime"):
        value = dt.datetime.fromisoformat(event_part["dateTime"].replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=get_local_timezone())
        return value.astimezone(get_local_timezone()).strftime("%a %b %d, %Y at %I:%M %p %Z")
    return dt.date.fromisoformat(event_part["date"]).strftime("%a %b %d, %Y (all day)")


def _event_bounds(event: dict) -> tuple[dt.datetime, dt.datetime]:
    local_tz = get_local_timezone()
    if event.get("start", {}).get("dateTime"):
        start = dt.datetime.fromisoformat(event["start"]["dateTime"].replace("Z", "+00:00"))
        end = dt.datetime.fromisoformat(event["end"]["dateTime"].replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=local_tz)
        if end.tzinfo is None:
            end = end.replace(tzinfo=local_tz)
        return start.astimezone(local_tz), end.astimezone(local_tz)
    start_date = dt.date.fromisoformat(event["start"]["date"])
    end_date = dt.date.fromisoformat(event["end"]["date"])
    return (dt.datetime.combine(start_date, dt.time.min, local_tz),
            dt.datetime.combine(end_date, dt.time.min, local_tz))


def _normalize_recurrence(value: Optional[str], start: dt.datetime) -> list[str]:
    if not value or value.strip().lower() in {"none", "no", "never", "one-time", "once"}:
        return []
    aliases = {
        "daily": "FREQ=DAILY",
        "every day": "FREQ=DAILY",
        "weekly": "FREQ=WEEKLY",
        "every week": "FREQ=WEEKLY",
        "monthly": "FREQ=MONTHLY",
        "every month": "FREQ=MONTHLY",
        "yearly": "FREQ=YEARLY",
        "annually": "FREQ=YEARLY",
        "weekdays": "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR",
    }
    normalized = aliases.get(value.strip().lower(), value.strip())
    if normalized.upper().startswith("RRULE:"):
        normalized = normalized.split(":", 1)[1]
    normalized = normalized.upper()
    allowed_fields = {"FREQ", "INTERVAL", "BYDAY", "BYMONTHDAY", "BYMONTH", "COUNT", "UNTIL", "WKST"}
    parts = {}
    for field in normalized.split(";"):
        key, separator, field_value = field.partition("=")
        if not separator or key not in allowed_fields or not field_value:
            raise ValueError("Recurrence must be a simple rule such as weekly, weekdays, or FREQ=WEEKLY;BYDAY=MO,WE.")
        parts[key] = field_value
    if parts.get("FREQ") not in {"DAILY", "WEEKLY", "MONTHLY", "YEARLY"}:
        raise ValueError("Recurrence frequency must be daily, weekly, monthly, or yearly.")
    if "INTERVAL" in parts and (not parts["INTERVAL"].isdigit() or int(parts["INTERVAL"]) < 1):
        raise ValueError("Recurrence interval must be a positive number.")
    rule = "RRULE:" + normalized
    # Parse now so invalid rules are rejected before a review request is staged.
    rrulestr(rule, dtstart=start)
    return [rule]


def _find_conflicts(service, start: dt.datetime, end: dt.datetime, recurrence: list[str]):
    local_tz = get_local_timezone()
    duration = end - start
    recurring = bool(recurrence)
    if recurring:
        candidates = rrulestr(recurrence[0], dtstart=start).between(
            start, start + dt.timedelta(days=366), inc=True
        )
        horizon = (candidates[-1] if candidates else start) + duration
    else:
        candidates = [start]
        horizon = end

    query_start = start - max(duration, dt.timedelta(days=1))
    query_end = horizon + dt.timedelta(days=1)
    result = service.events().list(
        calendarId="primary",
        timeMin=query_start.isoformat(),
        timeMax=query_end.isoformat(),
        maxResults=2500,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    conflicts = []
    existing_events = result.get("items", [])
    for candidate_start in candidates:
        candidate_end = candidate_start + duration
        for event in existing_events:
            existing_start, existing_end = _event_bounds(event)
            if candidate_start < existing_end and existing_start < candidate_end:
                conflicts.append((candidate_start, event))
                if len(conflicts) >= 8:
                    return conflicts
    return conflicts


@function_tool()
async def list_calendar_events(context: RunContext, days: int = 1) -> str:
    """List upcoming Google Calendar events in the user's configured local time zone. Include IDs for event management."""
    if not 1 <= days <= 90:
        return "Choose a calendar range from 1 to 90 days."
    try:
        local_tz = get_local_timezone()
        now = dt.datetime.now(local_tz)
        end = now + dt.timedelta(days=days)
        result = get_calendar_service().events().list(
            calendarId="primary", timeMin=now.isoformat(), timeMax=end.isoformat(),
            maxResults=50, singleEvents=True, orderBy="startTime",
        ).execute()
        events = result.get("items", [])
        if not events:
            return "No upcoming events found."
        lines = ["Upcoming calendar events:"]
        for event in events:
            lines.append(
                f"- {_format_event_time(event['start'])}: {event.get('summary', 'No title')} "
                f"(ID {event['id']})"
            )
        return "\n".join(lines)
    except Exception as exc:
        return f"Calendar lookup failed: {exc}"


@function_tool()
async def create_calendar_event(
    context: RunContext,
    summary: str,
    start_time: str,
    end_time: Optional[str] = None,
    recurrence: Optional[str] = None,
) -> str:
    """Prepare a calendar event for user approval. Times accept ISO timestamps; recurrence accepts daily, weekly, weekdays, monthly, yearly, or an RRULE such as FREQ=WEEKLY;BYDAY=MO,WE."""
    try:
        local_tz = get_local_timezone()
        start = _parse_event_time(start_time)
        end = _parse_event_time(end_time) if end_time else start + dt.timedelta(hours=1)
        if end <= start:
            return "The event end time must be later than the start time."
        if start <= dt.datetime.now(local_tz):
            return "The event start time must be in the future."
        recurrence_rules = _normalize_recurrence(recurrence, start)
        body = {
            "summary": summary.strip(),
            "start": {"dateTime": start.isoformat(), "timeZone": TIME_ZONE_NAME},
            "end": {"dateTime": end.isoformat(), "timeZone": TIME_ZONE_NAME},
        }
        if recurrence_rules:
            body["recurrence"] = recurrence_rules

        service = get_calendar_service()
        conflicts = _find_conflicts(service, start, end, recurrence_rules)
        if conflicts:
            lines = []
            for occurrence_start, event in conflicts:
                lines.append(
                    f"- {occurrence_start.strftime('%a %b %d, %I:%M %p %Z')}: "
                    f"{event.get('summary', 'Untitled event')}"
                )
            horizon_note = " Conflicts were checked over the next 12 months." if recurrence_rules else ""
            return "This event overlaps existing calendar events:\n" + "\n".join(lines) + horizon_note + " Please choose another time."

        preview = {
            "summary": body["summary"],
            "start": start.strftime("%A, %B %d at %I:%M %p %Z"),
            "end": end.strftime("%A, %B %d at %I:%M %p %Z"),
            "recurrence": recurrence_rules[0] if recurrence_rules else "Does not repeat",
        }
        action_id = stage_action("create_calendar_event", body, preview)
        recurrence_note = " It repeats as requested." if recurrence_rules else ""
        return (f"Calendar event prepared for review (ID {action_id}); it does not overlap existing events. "
                f"No event will be created until the user approves the review window.{recurrence_note}")
    except Exception as exc:
        return f"I couldn't prepare that calendar event: {exc}"


@function_tool()
async def delete_calendar_event(context: RunContext, event_id: str) -> str:
    """Prepare a calendar event deletion for user approval. Use an event ID from the calendar list."""
    try:
        service = get_calendar_service()
        event = service.events().get(calendarId="primary", eventId=event_id).execute()
        when = _format_event_time(event.get("start", {}))
        preview = {
            "summary": event.get("summary", "Untitled event"),
            "when": when,
            "event_id": event_id,
        }
        action_id = stage_action(
            "delete_calendar_event", {"event_id": event_id}, preview
        )
        return (f"Prepared deletion of ‘{preview['summary']}’ at {when} for review "
                f"(ID {action_id}); it will not be deleted until the user approves the review window.")
    except Exception as exc:
        return f"I couldn't prepare that calendar deletion: {exc}"
