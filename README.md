# Friday voice assistant

This Windows Python project contains a LiveKit assistant, a desktop GUI,
wake-word detection, voice authentication, and calendar and local utility
integrations. The launcher-to-agent session is still experimental.

## Setup

1. Use Python 3.13 and run `.\setup_terminal_env.ps1`.
2. Activate the environment with `.\.venv313\Scripts\Activate.ps1`.
3. For voice authentication, install Visual Studio Build Tools with the C++
   workload, then run `python -m pip install -r requirements-voice-auth.txt`.
4. Configure LiveKit and Google Calendar credentials in `.env` or under
   `data/private`, as applicable. Wake-word detection uses openWakeWord and
   does not require a Picovoice account or access key.
5. Start Friday with `python friday_launcher.py`. If no microphone is available,
   it opens the GUI with a text command box instead.

The wake phrase is **“Hey Jarvis”**. Its openWakeWord ONNX model files are kept
in `assets/wakewords/openwakeword/`, so startup does not need to download them.
The pretrained model is from David Scripka’s [openWakeWord project](https://github.com/dscripka/openWakeWord)
and is licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).

Reminders accept relative times (for example, “in 20 minutes”), local clock times
(“tomorrow at 3 PM”), or ISO timestamps. Friday checks them while the desktop app
is open and can list or cancel pending reminders. Reminders are saved in
`data/state/reminders.json`; they do not generate notifications while Friday is closed.

Friday's long-term memory is opt-in: ask Friday to remember a preference or project,
or use the **Memory** button to add, edit, view, or forget saved items. Memories are
stored locally in `data/state/user_memory.json` and included in the configured AI
assistant context on each turn. Do not save passwords, API keys, or other secrets.

Email drafts and calendar event creation/deletion now require approval in Friday's
review window before any external change is made. Calendar times use
`FRIDAY_TIMEZONE` (default `Asia/Kolkata`), support recurring rules, and are checked
for overlaps before an event is staged. Local file search covers text, Markdown,
PDF, and DOCX files in `docs/` and `data/state/`; PDF support uses `pypdf`, included
in `requirements.txt`.

Web lookup returns up to five linked search results with snippets. Friday is instructed
to include those links when answering current or unfamiliar questions and to treat snippets
as partial evidence; open the linked pages for full details.

## Layout

- `friday/` contains the Python application modules.
- `assets/wakewords/` contains the retained Porcupine model and the active
  openWakeWord model assets.
- `data/` stores private credentials, user state, recordings, voiceprints, and
  local music.
- `docs/` contains project reference documents.
- `scripts/manual/` contains manual experiments; `vendor/nircmd/` contains the
  local Windows utility used by music controls.
- `archive/` preserves old installers and inactive project material.

`requirements.txt` lists runtime packages, `requirements-dev.txt` adds tools,
and `requirements-voice-auth.txt` adds the optional speaker-verification stack.
