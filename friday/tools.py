import asyncio
import os
import json
import subprocess
import requests
import datetime
import ctypes
import zipfile
import xml.etree.ElementTree as ET
from email.utils import parseaddr
from typing import Optional
from urllib.parse import quote
from livekit.agents import function_tool, RunContext
from langchain_community.tools import DuckDuckGoSearchResults
from .calendar_tools import (
    list_calendar_events,
    create_calendar_event,
    delete_calendar_event,
)
from .paths import STATE_DIR, PROJECT_ROOT, ensure_data_dirs
from .reminders import add_reminder, cancel_pending_reminder, pending_reminders
from .memory_store import (
    clear_memory_items,
    delete_memory_item,
    load_memory_items,
    save_memory_item,
)
from .actions import stage_action

# ────────────── GENERAL TOOLS ────────────── #

@function_tool()
async def get_weather(context: RunContext, city: Optional[str] = None) -> str:
    """Get weather for an explicitly requested city, or the configured home location."""
    location = (city or "").strip() or os.getenv("FRIDAY_WEATHER_LOCATION", "").strip()
    if not location:
        return "Please tell me which city to check for weather."
    try:
        response = requests.get(f"https://wttr.in/{quote(location, safe='')}?format=3", timeout=10)
        response.raise_for_status()
        return response.text.strip()
    except Exception as e:
        return f"Weather error for {location}: {str(e)}"

@function_tool()
async def search_web(context: RunContext, query: str) -> str:
    """Search the web and return a short list of titled results with source links and snippets."""
    query = query.strip()
    if not query:
        return "Please provide a topic or question to search for."
    try:
        search = DuckDuckGoSearchResults(
            num_results=5,
            output_format="list",
            backend="text",
        )
        results = await asyncio.to_thread(search.invoke, {"query": query})
        if not results:
            return f"No web results found for: {query}"

        formatted = []
        for index, result in enumerate(results, start=1):
            title = str(result.get("title") or "Untitled result").strip()
            url = str(result.get("href") or result.get("link") or "").strip()
            snippet = str(result.get("body") or result.get("snippet") or "").strip()
            if url.startswith(("https://", "http://")):
                heading = f"{index}. [{title}]({url})"
            else:
                heading = f"{index}. {title}"
            formatted.append(f"{heading}\n   {snippet[:600]}" if snippet else heading)
        return "Web search results (snippets; open the links for full details):\n" + "\n\n".join(formatted)
    except Exception as e:
        return f"Web search is temporarily unavailable: {str(e)}"

@function_tool()
async def send_email(context: RunContext, to_email: str, subject: str, message: str, cc_email: Optional[str] = None) -> str:
    """Prepare an email draft for the desktop approval window; never send it directly."""
    try:
        if not os.getenv("GMAIL_USER") or not os.getenv("GMAIL_APP_PASSWORD"):
            return "Gmail credentials are not configured."
        recipient = parseaddr(to_email)[1]
        cc = parseaddr(cc_email)[1] if cc_email else ""
        if "@" not in recipient or (cc_email and "@" not in cc):
            return "Please provide a valid recipient email address."
        payload = {
            "to_email": recipient,
            "cc_email": cc or None,
            "subject": subject.strip(),
            "message": message,
        }
        preview = {
            "to": recipient,
            "cc": cc,
            "subject": payload["subject"],
            "body": message,
        }
        action_id = stage_action("send_email", payload, preview)
        return (f"Email draft prepared for {recipient}, subject ‘{payload['subject']}’ "
                f"(review ID {action_id}). It will not be sent until the user approves the review window.")
    except Exception as e:
        return f"Email draft error: {str(e)}"

# ────────────── NOTE, JOURNAL, MOOD ────────────── #

NOTES_FILE = STATE_DIR / "user_notes.json"
MOOD_LOG = STATE_DIR / "mood_log.json"


@function_tool()
async def remember_user_info(context: RunContext, category: str, key: str, value: str) -> str:
    """Save an explicitly requested user preference or ongoing project. Category must be Preference or Project."""
    try:
        item = save_memory_item(category, key, value)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return f"I couldn't save that memory: {exc}"
    return f"Saved {item['category'].lower()} '{item['key']}' to Friday's memory. You can ask me to change or forget it any time."


@function_tool()
async def list_saved_memory(context: RunContext) -> str:
    """Show all saved preferences and ongoing projects, including IDs for editing or forgetting."""
    try:
        items = load_memory_items()
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return f"I couldn't read Friday's saved memory: {exc}"
    if not items:
        return "Friday has no saved preferences or projects yet."
    return "Saved preferences and projects:\n" + "\n".join(
        f"- [{item['category']}] {item['key']}: {item['value']} (ID {item['id']})"
        for item in items
    )


@function_tool()
async def forget_saved_memory(context: RunContext, memory_id: str) -> str:
    """Forget one saved memory using its ID from the memory list."""
    try:
        forgotten = delete_memory_item(memory_id)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return f"I couldn't update Friday's memory: {exc}"
    return "That saved memory has been forgotten." if forgotten else "I couldn't find a saved memory with that ID."


@function_tool()
async def clear_saved_memory(context: RunContext) -> str:
    """Forget all saved preferences and project memories when the user explicitly asks."""
    try:
        count = clear_memory_items()
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return f"I couldn't clear Friday's memory: {exc}"
    return f"Forgot all {count} saved memories."

@function_tool()
async def save_note(context: RunContext, key: str, note: str) -> str:
    ensure_data_dirs()
    notes = {}
    if os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, 'r') as f:
            notes = json.load(f)
    notes[key] = note
    with open(NOTES_FILE, 'w') as f:
        json.dump(notes, f)
    return f"Saved note under '{key}'."

@function_tool()
async def recall_note(context: RunContext, key: str) -> str:
    if not os.path.exists(NOTES_FILE):
        return "No notes found."
    with open(NOTES_FILE, 'r') as f:
        notes = json.load(f)
    return notes.get(key, f"No note found for '{key}'.")

@function_tool()
async def journal_today(context: RunContext, entry: str) -> str:
    ensure_data_dirs()
    today = datetime.date.today().isoformat()
    filename = STATE_DIR / f"journal_{today}.txt"
    with open(filename, "a") as f:
        f.write(f"{entry}\n")
    return f"Journal entry saved for {today}."

@function_tool()
async def log_mood(context: RunContext, mood: str) -> str:
    ensure_data_dirs()
    log = []
    if os.path.exists(MOOD_LOG):
        with open(MOOD_LOG, 'r') as f:
            log = json.load(f)
    entry = {"timestamp": datetime.datetime.now().isoformat(), "mood": mood}
    log.append(entry)
    with open(MOOD_LOG, 'w') as f:
        json.dump(log, f)
    return f"Mood logged: {mood}"

# ────────────── MEDIA & FILES ────────────── #

@function_tool()
async def play_sound(context: RunContext, file_path: str) -> str:
    try:
        subprocess.Popen(["start", file_path], shell=True)
        return f"Playing {file_path}"
    except Exception as e:
        return f"Audio error: {str(e)}"

def _extract_searchable_chunks(path):
    extension = path.suffix.lower()
    if extension in {".txt", ".md", ".rst"}:
        return [(f"line {number}", line) for number, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ) if line.strip()]
    if extension == ".docx":
        with zipfile.ZipFile(path) as archive:
            xml_bytes = archive.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        chunks = []
        for paragraph_number, paragraph in enumerate(root.iter(f"{namespace}p"), 1):
            text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t")).strip()
            if text:
                chunks.append((f"paragraph {paragraph_number}", text))
        return chunks
    if extension == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path), strict=False)
        chunks = []
        for page_number, page in enumerate(reader.pages[:250], 1):
            text = page.extract_text() or ""
            chunks.extend((f"page {page_number}, line {line_number}", line)
                          for line_number, line in enumerate(text.splitlines(), 1) if line.strip())
        return chunks
    return []


@function_tool()
async def search_local_files(context: RunContext, keyword: str) -> str:
    """Search local text, Markdown, PDF, and Word DOCX files in docs and Friday's state folder."""
    ensure_data_dirs()
    terms = [term.casefold() for term in keyword.split() if term.strip()]
    if not terms:
        return "Enter a word or phrase to search for."
    matches = []
    failures = 0
    extensions = {".txt", ".md", ".rst", ".pdf", ".docx"}
    scanned = 0
    for directory in (STATE_DIR, PROJECT_ROOT / "docs"):
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in extensions:
                continue
            try:
                if path.stat().st_size > 25 * 1024 * 1024:
                    continue
                chunks = _extract_searchable_chunks(path)
                scanned += 1
                relative = path.relative_to(PROJECT_ROOT)
                for location, text in chunks:
                    folded = text.casefold()
                    if all(term in folded for term in terms):
                        excerpt = " ".join(text.split())
                        if len(excerpt) > 280:
                            excerpt = excerpt[:277].rstrip() + "..."
                        matches.append(f"- {relative} ({location}): {excerpt}")
                        if len(matches) >= 12:
                            return "Matches (up to 12):\n" + "\n".join(matches)
            except Exception:
                failures += 1
    if matches:
        return "Matches:\n" + "\n".join(matches)
    if failures:
        return f"No matching text found in {scanned} files. {failures} files could not be read or searched."
    return f"No matching text found in {scanned} searchable files."

# ────────────── MUSIC CONTROL ────────────── #

@function_tool()
async def control_music(context: RunContext, command: str) -> str:
    key_map = {
        "play": 0xB3,
        "pause": 0xB3,
        "next": 0xB0,
        "previous": 0xB1
    }
    vk_code = key_map.get(command.lower())
    if vk_code is not None:
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0)
        return f"Media command '{command}' executed."
    else:
        return "Invalid media command."

@function_tool()
async def set_volume(context: RunContext, level: int) -> str:
    """Adjust system volume (0–100%)"""
    if not 0 <= level <= 100:
        return "Please provide a volume level between 0 and 100."
    try:
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(level / 100.0, None)
        return f"Volume set to {level}%."
    except Exception as e:
        return f"Volume control error: {e}"

# ────────────── MISCELLANEOUS ────────────── #

@function_tool()
async def create_reminder(context: RunContext, task: str, time: str) -> str:
    """Schedule a desktop reminder for a future time. Accept an ISO timestamp or a time such as 'in 20 minutes' or 'tomorrow at 3 PM'."""
    ensure_data_dirs()
    try:
        reminder = add_reminder(task, time)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return f"I couldn't set that reminder: {exc}"
    due = datetime.datetime.fromisoformat(reminder["due_at"])
    return (f"Reminder set: {task} — {due.strftime('%A, %B %d at %I:%M %p')} "
            f"(ID {reminder['id']}). Friday will alert you while the app is running.")


@function_tool()
async def list_reminders(context: RunContext) -> str:
    """List Friday's upcoming reminders, including their IDs."""
    try:
        reminders = pending_reminders()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return f"I couldn't read the reminders: {exc}"
    if not reminders:
        return "You have no upcoming reminders."
    lines = ["Your upcoming reminders:"]
    for reminder in reminders:
        due = datetime.datetime.fromisoformat(reminder["due_at"])
        lines.append(f"- {due.strftime('%a %b %d, %I:%M %p')}: {reminder['task']} (ID {reminder['id']})")
    return "\n".join(lines)


@function_tool()
async def cancel_reminder(context: RunContext, reminder_id: str) -> str:
    """Cancel a pending reminder using the ID returned by the reminder list."""
    try:
        cancelled = cancel_pending_reminder(reminder_id)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return f"I couldn't cancel that reminder: {exc}"
    return "Reminder cancelled." if cancelled else "No pending reminder matched that ID."

@function_tool()
async def summarize_text(context: RunContext, text: str) -> str:
    lines = text.strip().split('. ')
    summary = '. '.join(lines[:2]) + ("..." if len(lines) > 2 else "")
    return f"Summary: {summary}"

@function_tool()
async def generate_affirmation(context: RunContext, topic: Optional[str] = None) -> str:
    topic = topic or "self-worth"
    affirmations = {
        "self-worth": "You are enough, just as you are.",
        "stress": "This too shall pass. Breathe and let go.",
        "focus": "You have the strength to stay centered and clear."
    }
    return affirmations.get(topic.lower(), "You are capable and strong. Keep going!")
