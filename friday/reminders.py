"""Persistent, local reminders used by Friday's chat tools and desktop UI."""

import datetime as dt
import json
import re
import threading
import uuid

from .paths import STATE_DIR, ensure_data_dirs


LOCAL_TZ = dt.timezone(dt.timedelta(hours=5, minutes=30), name="Asia/Kolkata")
REMINDERS_FILE = STATE_DIR / "reminders.json"
_LOCK = threading.Lock()


def _read_all():
    ensure_data_dirs()
    if not REMINDERS_FILE.exists():
        return []
    with REMINDERS_FILE.open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, list):
        raise ValueError("The reminders file has an invalid format.")
    return data


def _write_all(reminders):
    ensure_data_dirs()
    temp_file = REMINDERS_FILE.with_suffix(".tmp")
    with temp_file.open("w", encoding="utf-8") as stream:
        json.dump(reminders, stream, ensure_ascii=False, indent=2)
    temp_file.replace(REMINDERS_FILE)


def parse_due_time(value: str) -> dt.datetime:
    """Parse ISO timestamps and common relative/local times into Asia/Kolkata."""
    value = value.strip()
    now = dt.datetime.now(LOCAL_TZ)
    relative = re.fullmatch(
        r"in\s+(\d+)\s+(minutes?|mins?|hours?|hrs?|days?)", value, re.IGNORECASE
    )
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2).lower()
        if amount < 1:
            raise ValueError("Choose a reminder time in the future.")
        if unit.startswith(("m",)):
            due = now + dt.timedelta(minutes=amount)
        elif unit.startswith(("h",)):
            due = now + dt.timedelta(hours=amount)
        else:
            due = now + dt.timedelta(days=amount)
    else:
        normalized = value.replace("Z", "+00:00")
        try:
            due = dt.datetime.fromisoformat(normalized)
        except ValueError:
            due = None

        if due is None:
            local_text = re.sub(r"^at\s+", "", value, flags=re.IGNORECASE)
            day_offset = 0
            day_match = re.match(r"^(today|tomorrow)\s+(?:at\s+)?(.+)$", local_text, re.IGNORECASE)
            if day_match:
                day_offset = 1 if day_match.group(1).lower() == "tomorrow" else 0
                local_text = day_match.group(2)
            parsed_time = None
            for fmt in ("%I:%M %p", "%I %p", "%H:%M", "%I:%M%p", "%I%p"):
                try:
                    parsed_time = dt.datetime.strptime(local_text, fmt).time()
                    break
                except ValueError:
                    continue
            if parsed_time is None:
                raise ValueError(
                    "I couldn't understand that time. Try ‘in 20 minutes’, ‘tomorrow at 3 PM’, "
                    "or an ISO date and time."
                )
            due = dt.datetime.combine(now.date() + dt.timedelta(days=day_offset), parsed_time, LOCAL_TZ)
            if day_offset == 0 and due <= now:
                due += dt.timedelta(days=1)
        elif due.tzinfo is None:
            due = due.replace(tzinfo=LOCAL_TZ)
        else:
            due = due.astimezone(LOCAL_TZ)

    if due <= now:
        raise ValueError("Choose a reminder time in the future.")
    return due


def add_reminder(task: str, due_text: str):
    task = task.strip()
    if not task:
        raise ValueError("A reminder needs a task description.")
    due = parse_due_time(due_text)
    now = dt.datetime.now(LOCAL_TZ)
    reminder = {
        "id": uuid.uuid4().hex[:8],
        "task": task,
        "due_at": due.isoformat(),
        "created_at": now.isoformat(),
        "notified": False,
        "cancelled": False,
    }
    with _LOCK:
        reminders = _read_all()
        reminders.append(reminder)
        _write_all(reminders)
    return reminder


def pending_reminders():
    with _LOCK:
        reminders = _read_all()
    pending = [r for r in reminders if not r.get("notified") and not r.get("cancelled")]
    return sorted(pending, key=lambda r: r["due_at"])


def cancel_pending_reminder(reminder_id: str):
    with _LOCK:
        reminders = _read_all()
        for reminder in reminders:
            if reminder.get("id", "").lower() == reminder_id.strip().lower():
                if reminder.get("notified") or reminder.get("cancelled"):
                    return False
                reminder["cancelled"] = True
                _write_all(reminders)
                return True
    return False


def claim_due_reminders():
    """Atomically mark due reminders notified and return them once."""
    now = dt.datetime.now(LOCAL_TZ)
    due = []
    with _LOCK:
        reminders = _read_all()
        changed = False
        for reminder in reminders:
            if reminder.get("notified") or reminder.get("cancelled"):
                continue
            if dt.datetime.fromisoformat(reminder["due_at"]).astimezone(LOCAL_TZ) <= now:
                reminder["notified"] = True
                due.append(reminder)
                changed = True
        if changed:
            _write_all(reminders)
    return due
