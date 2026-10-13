"""One-shot action queue for changes that require a user approval in the GUI."""

import email.message
import os
import smtplib
import threading
import time
import uuid


_PENDING = {}
_LOCK = threading.Lock()
_MAX_AGE_SECONDS = 600


def stage_action(kind: str, payload: dict, preview: dict) -> str:
    action_id = uuid.uuid4().hex[:8].upper()
    with _LOCK:
        now = time.time()
        for stale_id in [key for key, item in _PENDING.items()
                         if now - item["created_at"] > _MAX_AGE_SECONDS]:
            _PENDING.pop(stale_id, None)
        _PENDING[action_id] = {
            "id": action_id,
            "kind": kind,
            "payload": payload,
            "preview": preview,
            "created_at": now,
        }
    return action_id


def take_pending_actions():
    """Transfer staged actions to the UI for explicit approval; discard stale requests."""
    with _LOCK:
        now = time.time()
        actions = [item for item in _PENDING.values()
                   if now - item["created_at"] <= _MAX_AGE_SECONDS]
        _PENDING.clear()
    return actions


def execute_approved_action(action: dict) -> str:
    if time.time() - action.get("created_at", 0) > _MAX_AGE_SECONDS:
        raise RuntimeError("This review request expired. Please ask Friday to prepare it again.")
    kind = action["kind"]
    payload = action["payload"]
    if kind == "send_email":
        gmail_user = os.getenv("GMAIL_USER")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD")
        if not gmail_user or not gmail_password:
            raise RuntimeError("Gmail credentials are not configured.")
        message = email.message.EmailMessage()
        message["From"] = gmail_user
        message["To"] = payload["to_email"]
        if payload.get("cc_email"):
            message["Cc"] = payload["cc_email"]
        message["Subject"] = payload["subject"]
        message.set_content(payload["message"])
        recipients = [payload["to_email"]]
        if payload.get("cc_email"):
            recipients.append(payload["cc_email"])
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            server.starttls()
            server.login(gmail_user, gmail_password)
            server.send_message(message, to_addrs=recipients)
        return f"Email sent to {payload['to_email']}."

    from .calendar_tools import get_calendar_service
    service = get_calendar_service()
    if kind == "create_calendar_event":
        created = service.events().insert(calendarId="primary", body=payload).execute()
        return f"Calendar event created: {created.get('summary', 'Untitled event')}."
    if kind == "delete_calendar_event":
        service.events().delete(calendarId="primary", eventId=payload["event_id"]).execute()
        return f"Calendar event deleted: {action['preview'].get('summary', 'event')}."
    raise ValueError(f"Unknown approved action: {kind}")
