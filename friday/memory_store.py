"""Explicit, editable long-term memory for user preferences and projects."""

import datetime as dt
import json
import re
import threading
import uuid

from .paths import STATE_DIR, ensure_data_dirs


MEMORY_FILE = STATE_DIR / "user_memory.json"
MEMORY_CATEGORIES = ("Preference", "Project")
_LOCK = threading.RLock()


def load_memory_items():
    ensure_data_dirs()
    if not MEMORY_FILE.exists():
        return []
    with _LOCK, MEMORY_FILE.open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ValueError("The memory file has an invalid format.")
    return data["items"]


def _save(items):
    ensure_data_dirs()
    temp_file = MEMORY_FILE.with_suffix(".tmp")
    with temp_file.open("w", encoding="utf-8") as stream:
        json.dump({"items": items}, stream, ensure_ascii=False, indent=2)
    temp_file.replace(MEMORY_FILE)


def save_memory_item(category: str, key: str, value: str):
    category = category.strip().title()
    key = key.strip()
    value = value.strip()
    if category not in MEMORY_CATEGORIES:
        raise ValueError("Choose either Preference or Project.")
    if not key or not value:
        raise ValueError("Enter both a short name and the information to remember.")
    if len(key) > 80 or len(value) > 2000:
        raise ValueError("Keep the name under 80 characters and the information under 2,000 characters.")
    sensitive_content = re.compile(
        r"\b(password|passphrase|credential|api\s*key|access\s*token|secret\s*key)\b", re.IGNORECASE
    )
    if sensitive_content.search(f"{key}\n{value}"):
        raise ValueError("Friday's memory is for preferences and projects, not passwords or credentials.")

    now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    with _LOCK:
        data = {"items": load_memory_items()}
        items = data["items"]
        existing = next(
            (item for item in items
             if item.get("category") == category and item.get("key", "").casefold() == key.casefold()),
            None,
        )
        if existing:
            existing.update({"value": value, "updated_at": now})
            saved = existing.copy()
        else:
            if len(items) >= 100:
                raise ValueError("Friday's memory is full. Forget an item before adding another.")
            saved = {
                "id": uuid.uuid4().hex[:8],
                "category": category,
                "key": key,
                "value": value,
                "created_at": now,
                "updated_at": now,
            }
            items.append(saved)
        _save(items)
    return saved


def delete_memory_item(memory_id: str) -> bool:
    with _LOCK:
        items = load_memory_items()
        remaining = [item for item in items if item.get("id", "").casefold() != memory_id.strip().casefold()]
        if len(remaining) == len(items):
            return False
        _save(remaining)
        return True


def clear_memory_items() -> int:
    with _LOCK:
        count = len(load_memory_items())
        _save([])
        return count


def memory_instructions() -> str:
    """Return the current memory for the agent; never persist the whole chat."""
    try:
        items = load_memory_items()
    except (OSError, ValueError, json.JSONDecodeError):
        items = []
    if not items:
        memory_text = "No preferences or projects are currently saved."
    else:
        lines = [f"- [{item['category']}] {item['key']}: {item['value']}" for item in items]
        memory_text = "\n".join(lines)
    return (
        "\n\n# Current saved user memory\n"
        "This is the complete, current set of user-approved saved memories. Use it only when relevant. "
        "It overrides stale details from earlier conversation turns. Do not treat ordinary conversation "
        "as permission to save it, and do not store credentials or secrets.\n"
        f"{memory_text}\n"
    )
