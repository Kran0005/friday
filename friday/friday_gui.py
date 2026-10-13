import os
import json
import math
import random
import customtkinter as ctk
import pyttsx3
import threading
import time
import tkinter as tk
from tkinter import messagebox
from tkinter import filedialog
import numpy as np
import pyaudio
import wave
from .friday_core import FridayCore
from .hotword_module import HotwordListener
from .audio_devices import get_input_device_index
from .paths import VOICEPRINTS_DIR, ensure_data_dirs
from .reminders import claim_due_reminders
from .memory_store import (
    MEMORY_CATEGORIES,
    clear_memory_items,
    delete_memory_item,
    load_memory_items,
    save_memory_item,
)
from .actions import execute_approved_action, take_pending_actions
import speech_recognition as sr

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "window": "#10141D",
    "panel": "#171D29",
    "panel_soft": "#1D2533",
    "accent": "#4F8CFF",
    "text": "#F3F6FC",
    "muted": "#9AA8BD",
    "holo": "#FFAA36",
    "holo_dim": "#75451D",
}

class FridayGUI(ctk.CTk):
    def __init__(self, enable_voice=True):
        super().__init__()
        self.title("Friday - Personal Assistant")
        self.geometry("1240x840")
        self.minsize(980, 700)
        self.configure(fg_color=COLORS["window"])
        self.protocol("WM_DELETE_WINDOW", self.close_app)

        self.friday = FridayCore()
        self.listener = None
        self.tts_engine = None
        self.voice_auth_enabled = True
        self.current_user = None
        self.voice_available = False
        self._action_review_queue = []
        self._action_review_open = False
        self._hologram_state = "idle"

        self.sidebar_frame = ctk.CTkFrame(
            self, width=220, corner_radius=18, fg_color=COLORS["panel"]
        )
        self.sidebar_frame.pack(side="left", fill="y", padx=(14, 8), pady=14)
        self.sidebar_frame.pack_propagate(False)

        self.main_frame = ctk.CTkFrame(
            self, corner_radius=18, fg_color=COLORS["window"]
        )
        self.main_frame.pack(side="right", expand=True, fill="both", padx=(8, 14), pady=14)

        brand = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        brand.pack(fill="x", padx=18, pady=(22, 24))
        ctk.CTkLabel(
            brand, text="F", width=38, height=38, corner_radius=12,
            fg_color=COLORS["accent"], text_color="white",
            font=("Segoe UI", 19, "bold"),
        ).pack(side="left", padx=(0, 11))
        brand_text = ctk.CTkFrame(brand, fg_color="transparent")
        brand_text.pack(side="left", anchor="center")
        ctk.CTkLabel(brand_text, text="FRIDAY", text_color=COLORS["text"],
                     font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ctk.CTkLabel(brand_text, text="PERSONAL ASSISTANT", text_color=COLORS["muted"],
                     font=("Segoe UI", 9, "bold")).pack(anchor="w")

        ctk.CTkLabel(self.sidebar_frame, text="YOUR TOOLS", text_color=COLORS["muted"],
                     font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", padx=18, pady=(0, 8))
        self.create_sidebar_button("🎙️ Speak", self.speak_callback)
        self.create_sidebar_button("📅 Calendar", self.calendar_callback)
        self.create_sidebar_button("⏰ Reminders", self.reminders_callback)
        self.create_sidebar_button("📝 Notes", self.notes_callback)
        self.create_sidebar_button("🧠 Memory", self.open_memory_manager)
        self.create_sidebar_button("🎵 Music", self.music_callback)
        self.create_sidebar_button("📊 Mood", self.mood_callback)
        self.create_sidebar_button("🔊 Volume", self.volume_callback)
        self.create_sidebar_button("⚙️ Settings", self.settings_callback)
        self.create_sidebar_button("➕ Add User", self.add_user_callback)

        ctk.CTkLabel(self.sidebar_frame, text="VOICE ACCESS", text_color=COLORS["muted"],
                     font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", padx=18, pady=(22, 4))
        self.auth_switch = ctk.CTkSwitch(self.sidebar_frame, text="Voice authentication", command=self.toggle_auth,
                                         font=("Segoe UI", 12))
        self.auth_switch.select()
        self.auth_switch.pack(pady=10)

        self.wakeword_label = ctk.CTkLabel(self.sidebar_frame, text="Starting voice input...", text_color=COLORS["muted"])
        self.wakeword_label.pack(anchor="w", padx=18, pady=(12, 4))

        self.mic_level_label = ctk.CTkLabel(self.sidebar_frame, text="Mic level unavailable", text_color=COLORS["muted"])
        self.mic_level_label.pack(anchor="w", padx=18, pady=4)

        header = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(8, 4))
        heading = ctk.CTkFrame(header, fg_color="transparent")
        heading.pack(side="left", anchor="w")
        ctk.CTkLabel(heading, text="Assistant", text_color=COLORS["text"],
                     font=("Segoe UI", 24, "bold")).pack(anchor="w")
        ctk.CTkLabel(heading, text="A calm place to think, plan, and get things done.",
                     text_color=COLORS["muted"], font=("Segoe UI", 12)).pack(anchor="w", pady=(2, 0))
        self.connection_badge = ctk.CTkLabel(
            header, text="●  TEXT MODE", text_color="#9FE3C0", fg_color="#1A352F",
            corner_radius=12, padx=12, pady=7, font=("Segoe UI", 10, "bold"),
        )
        self.connection_badge.pack(side="right", anchor="n", pady=8)

        self.hologram = tk.Canvas(
            self.main_frame, height=340, bg="#080D19", highlightthickness=1,
            highlightbackground="#202B3B", bd=0,
        )
        self.hologram.pack(fill="x", padx=12, pady=(0, 10))
        self._hologram_phase = 0.0
        self._animate_hologram()

        self.status_display = ctk.CTkTextbox(
            self.main_frame, font=("Segoe UI", 14), wrap="word",
            fg_color=COLORS["panel"], text_color=COLORS["text"],
            border_width=1, border_color="#252E3D", corner_radius=16,
            scrollbar_button_color="#35445A", scrollbar_button_hover_color=COLORS["accent"],
        )
        self.status_display.pack(expand=True, fill="both", padx=12, pady=(0, 10))
        # CTkTextbox forbids font overrides on text tags because they bypass its scaling.
        self.status_display.tag_config("timestamp", foreground=COLORS["muted"])
        self.status_display.tag_config("user", foreground="#8DB6FF")
        self.status_display.tag_config("assistant", foreground="#8FE0C0")
        self.status_display.tag_config("system", foreground="#F0C778")
        self.status_display.insert("end", "FRIDAY\n", "assistant")
        self.status_display.insert("end", "\nHello! Type a message below, or say ‘Hey Jarvis’ when a microphone is available.\n")
        self.status_display.configure(state="disabled")

        input_frame = ctk.CTkFrame(self.main_frame, fg_color=COLORS["panel"], corner_radius=15,
                                   border_width=1, border_color="#252E3D")
        input_frame.pack(fill="x", padx=12, pady=(0, 12))
        self.prompt_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Type a command or message...",
            height=48, fg_color="transparent", border_width=0,
            text_color=COLORS["text"], placeholder_text_color=COLORS["muted"],
            font=("Segoe UI", 14),
        )
        self.prompt_entry.pack(side="left", fill="x", expand=True, padx=(14, 4), pady=5)
        self.prompt_entry.bind("<Return>", self.submit_prompt)
        self.send_button = ctk.CTkButton(input_frame, text="Send  ↑", width=104, height=40,
                                         corner_radius=11, font=("Segoe UI", 12, "bold"),
                                         command=self.submit_prompt)
        self.send_button.pack(side="right", padx=7, pady=7)

        ensure_data_dirs()
        if enable_voice:
            try:
                self.listener = HotwordListener(self.on_wakeword_detected, str(VOICEPRINTS_DIR))
                self.listener.start()
                self.voice_available = True
                self.connection_badge.configure(text="●  VOICE READY", text_color="#9FE3C0")
                self.wakeword_label.configure(text="🔈 Listening for Hey Jarvis", text_color="lightgray")
                threading.Thread(target=self.monitor_mic, daemon=True).start()
            except RuntimeError as exc:
                self._show_microphone_unavailable(exc)
        else:
            self._show_microphone_unavailable()
        self.after(5000, self._check_due_reminders)

    def _show_microphone_unavailable(self, error=None):
        self.listener = None
        self.connection_badge.configure(text="●  TEXT MODE · MIC OFF", text_color="#F0C778",
                                        fg_color="#3A3020")
        self.wakeword_label.configure(text="🎙️ Mic unavailable", text_color="orange")
        self.auth_switch.configure(state="disabled")
        if error:
            self.update_status(f"Voice wake-up unavailable: {error}")

    def _check_due_reminders(self):
        if not self.winfo_exists():
            return
        try:
            for reminder in claim_due_reminders():
                message = f"⏰ Reminder: {reminder['task']}"
                self.update_status(message)
                threading.Thread(target=self.speak_response, args=(message,), daemon=True).start()
        except (OSError, ValueError) as exc:
            self.update_status(f"⚠️ Couldn't check reminders: {exc}")
        self.after(5000, self._check_due_reminders)

    def _animate_hologram(self):
        """Draw a layered amber projection with a quiet, state-aware pulse."""
        if not self.winfo_exists():
            return
        canvas = self.hologram
        width = max(canvas.winfo_width(), 420)
        height = max(canvas.winfo_height(), 240)
        cx, cy = width / 2, height / 2
        radius = min(height * 0.43, width * 0.265)
        phase = self._hologram_phase
        active = self._hologram_state == "thinking"
        speed = 1.65 if active else 0.72
        pulse = (math.sin(math.radians(phase * (1.6 if active else 0.72))) + 1) / 2
        canvas.delete("all")

        # Deep blue architectural silhouette and perspective floor.
        canvas.create_rectangle(0, 0, width, height, fill="#080D19", outline="")
        canvas.create_rectangle(0, height * .68, width, height, fill="#0A1020", outline="")
        canvas.create_line(0, height * .68, width, height * .68, fill="#1B2A40", width=1)
        vanishing_y = height * .66
        for x in (0, width * .12, width * .28, width * .72, width * .88, width):
            canvas.create_line(cx, vanishing_y, x, height, fill="#101D30", width=1)
        for fraction in (.76, .84, .93):
            y = height * fraction
            canvas.create_line(width * .04, y, width * .96, y, fill="#101D30", width=1)
        # Architectural uprights frame the projection like a glass chamber.
        for x, top, bottom in ((width*.08, .08, .72), (width*.19, .04, .58),
                               (width*.81, .04, .58), (width*.92, .08, .72)):
            canvas.create_line(x, height*top, x, height*bottom, fill="#16243A", width=2)
            canvas.create_line(x+4, height*top, x+4, height*bottom, fill="#101A2B", width=1)
        canvas.create_line(0, cy, width, cy, fill="#111D2D", width=1)
        canvas.create_line(cx, 0, cx, height, fill="#111D2D", width=1)
        for x, y, dx, dy in ((22, 22, 1, 1), (width-22, 22, -1, 1),
                             (22, height-22, 1, -1), (width-22, height-22, -1, -1)):
            canvas.create_line(x, y, x + 18*dx, y, fill="#273348", width=1)
            canvas.create_line(x, y, x, y + 18*dy, fill="#273348", width=1)

        # Layered light wells create an amber bloom without external assets.
        for layer, factor in enumerate((1.30, 1.22, 1.13, 1.04)):
            r = radius * factor
            color = ("#17130F", "#20170F", "#291A0D", "#311D0C")[layer]
            canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill=color, outline="")

        # Multiple broken rings create the layered holographic wheel.
        for ring, factor in enumerate((1.0, 0.94, 0.88, 0.78, 0.72, 0.63, 0.57, 0.47, 0.39, 0.27)):
            r = radius * factor
            box = (cx-r, cy-r, cx+r, cy+r)
            canvas.create_oval(*box, outline="#493019" if ring % 2 else "#382617", width=1)
            if ring in (0, 2, 3, 5, 6, 8):
                segments = (13, 8, 7, 10, 6, 8)[(0, 2, 3, 5, 6, 8).index(ring)]
                gap = 8 if ring in (0, 5) else 16
                direction = 1 if ring % 2 else -1
                offset = phase * speed * direction * (1 + ring * 0.12) + ring * 29
                for segment in range(segments):
                    start = offset + segment * (360 / segments)
                    extent = 360 / segments - gap
                    canvas.create_arc(*box, start=start, extent=extent, style="arc",
                                      outline=COLORS["holo"] if segment % 3 == 0 else "#92551F",
                                      width=2 if ring < 5 else 1)

        # Fine radial etching around the outside.
        for tick in range(120):
            angle = math.radians(tick * 3 + phase * 0.12 * speed)
            major = tick % 10 == 0
            outer = radius * (0.99 if major else 0.95 if tick % 2 == 0 else 0.92)
            inner = radius * (0.84 if major else 0.90 if tick % 2 == 0 else 0.92)
            color = "#FFC15A" if major else "#825022"
            canvas.create_line(cx + math.cos(angle)*inner, cy + math.sin(angle)*inner,
                               cx + math.cos(angle)*outer, cy + math.sin(angle)*outer,
                               fill=color, width=2 if major else 1)

        # Fine circuit spokes and segmented data bands.
        for spoke in range(32):
            angle = math.radians(spoke * 11.25 - phase * .1 * speed)
            inner, outer = radius * .43, radius * (.53 if spoke % 4 else .61)
            canvas.create_line(cx+math.cos(angle)*inner, cy+math.sin(angle)*inner,
                               cx+math.cos(angle)*outer, cy+math.sin(angle)*outer,
                               fill="#75451D" if spoke % 4 else "#B16A27", width=1)

        # Stable constellation of sparks, with a gentle rotating brightness pulse.
        rng = random.Random(41)
        for dot in range(150):
            angle = rng.random() * math.tau
            distance = radius * (0.32 + rng.random() * 0.73)
            x = cx + math.cos(angle) * distance
            y = cy + math.sin(angle) * distance
            twinkle = (math.sin(phase * 0.035 + dot * 1.7) + 1) / 2
            fill = "#FFD27A" if twinkle > (0.84 if active else 0.91) else ("#A96024" if twinkle > 0.48 else "#51351F")
            size = 1.2 if twinkle < 0.85 else 2.5
            canvas.create_oval(x-size, y-size, x+size, y+size, fill=fill, outline="")

        # Central reactor and animated signal trace.
        core = radius * (0.23 + pulse * (0.025 if active else 0.012))
        canvas.create_oval(cx-radius*.31, cy-radius*.31, cx+radius*.31, cy+radius*.31,
                           outline="#79471D", width=1)
        canvas.create_oval(cx-core*1.55, cy-core*1.55, cx+core*1.55, cy+core*1.55,
                           outline="#B56B25" if active else "#8F541F", width=2)
        canvas.create_oval(cx-core, cy-core, cx+core, cy+core,
                           fill="#251A13", outline=COLORS["holo"], width=2)
        canvas.create_oval(cx-core*0.48, cy-core*0.48, cx+core*0.48, cy+core*0.48,
                           fill="#FFB544", outline="#FFE0A0", width=1)
        trace = []
        for point in range(81):
            x = cx - core * 1.28 + point * (core * 2.56 / 80)
            envelope = math.exp(-((x-cx)/(core*0.8))**2)
            y = cy + math.sin(point * 0.44 + phase * 0.11) * core * 0.33 * envelope
            trace.extend((x, y))
        canvas.create_line(*trace, fill="#FFE2A1", width=2, smooth=True)
        canvas.create_text(cx, cy + radius*0.31, text="F R I D A Y",
                           fill="#F0AE4E", font=("Segoe UI", 10, "bold"))
        canvas.create_text(cx, cy + radius*0.40, text="NEURAL PROJECTION  ·  01",
                           fill="#9C672F", font=("Segoe UI", 7, "bold"))

        # Small telemetry labels keep the scene readable and intentional.
        label_color = "#DB9841" if active else "#A8763C"
        canvas.create_text(18, 16, anchor="nw", text="FRIDAY  /  HOLOGRAPHIC INTERFACE",
                           fill=label_color, font=("Segoe UI", 8, "bold"))
        canvas.create_text(width-18, 16, anchor="ne", text="CORE 01   ·   ONLINE",
                           fill="#6F829D", font=("Segoe UI", 8, "bold"))
        state_label = "PROCESSING REQUEST" if active else ("VOICE LINK ACTIVE" if self.voice_available else "TEXT LINK · STANDBY")
        canvas.create_text(18, height-15, anchor="sw", text=state_label,
                           fill=label_color, font=("Segoe UI", 8, "bold"))
        meter_x, meter_y = width-18, height-15
        for bar in range(12):
            bar_height = 3 + ((bar * 7 + int(phase / 8)) % 10 if active else (bar % 4) * 2)
            canvas.create_line(meter_x-bar*7, meter_y, meter_x-bar*7,
                               meter_y-bar_height, fill="#C17A30" if bar < 8 else "#553A22", width=2)

        self._hologram_phase = (phase + (3.2 if active else 1.9)) % 360
        self.after(70, self._animate_hologram)

    def alert_missing(self, name, path):
        msg = f"⚠️ {name} missing: {path}"
        self.update_status(msg)
        self.speak_response(f"{name} is missing.")
        messagebox.showerror("Missing File", msg)

    def toggle_auth(self):
        self.voice_auth_enabled = bool(self.auth_switch.get())
        if self.listener is not None:
            self.listener.set_auth_enabled(self.voice_auth_enabled)
        self.update_status(f"🔒 Voice authentication {'enabled' if self.voice_auth_enabled else 'disabled'}.")

    def create_sidebar_button(self, text, command):
        btn = ctk.CTkButton(
            self.sidebar_frame, text=text, width=184, height=42, command=command,
            anchor="w", corner_radius=11, fg_color="transparent",
            hover_color=COLORS["panel_soft"], text_color="#D8E1EF",
            font=("Segoe UI", 12),
        )
        btn.pack(fill="x", padx=12, pady=3)

    def update_status(self, message):
        self.status_display.configure(state="normal")
        timestamp = time.strftime("[%H:%M:%S] ")
        tag = "system"
        if "You:" in message:
            tag = "user"
        elif "Friday:" in message:
            tag = "assistant"
        self.status_display.insert("end", timestamp, "timestamp")
        self.status_display.insert("end", f"{message}\n\n", tag)
        self.status_display.see("end")
        self.status_display.configure(state="disabled")

    def speak_response(self, message):
        try:
            if self.tts_engine is None:
                self.tts_engine = pyttsx3.init()
                self.tts_engine.setProperty("rate", 170)
            self.tts_engine.say(message)
            self.tts_engine.runAndWait()
        except Exception as e:
            error = str(e)
            self.after(0, lambda error=error: self.update_status(
                f"🔇 Speech output unavailable; replies remain visible as text. {error}"
            ))

    def submit_prompt(self, _event=None):
        prompt = self.prompt_entry.get().strip()
        if not prompt:
            return
        self.prompt_entry.delete(0, "end")
        self.handle_prompt(prompt)

    def close_app(self):
        if self.listener is not None:
            self.listener.stop()
        self.friday.stop()
        self.destroy()

    def handle_prompt(self, prompt):
        self._hologram_state = "thinking"
        self.update_status(f"🧠 You: {prompt}")
        self.connection_badge.configure(text="●  THINKING", text_color="#B5CCFF", fg_color="#202E49")

        def run():
            response_text = self.friday.ask(prompt)
            actions = take_pending_actions()
            def finish_response():
                self._hologram_state = "idle"
                self.update_status(f"🤖 Friday: {response_text}")
                if self.voice_available:
                    self.connection_badge.configure(text="●  VOICE READY", text_color="#9FE3C0",
                                                    fg_color="#1A352F")
                else:
                    self.connection_badge.configure(text="●  TEXT MODE · MIC OFF", text_color="#F0C778",
                                                    fg_color="#3A3020")
                self._action_review_queue.extend(actions)
                if self._action_review_queue:
                    self.after(250, self._show_next_action_review)
            self.after(0, finish_response)
            self.speak_response(response_text)
        threading.Thread(target=run, daemon=True).start()

    def _show_next_action_review(self):
        if self._action_review_queue and self.winfo_exists() and not self._action_review_open:
            self._action_review_open = True
            self._review_pending_action(self._action_review_queue.pop(0))

    def _review_pending_action(self, action):
        preview = action["preview"]
        kind = action["kind"]
        labels = {
            "send_email": ("Review email", "Send this email?", "Send email"),
            "create_calendar_event": ("Review calendar event", "Create this calendar event?", "Create event"),
            "delete_calendar_event": ("Review calendar deletion", "Delete this calendar event?", "Delete event"),
        }
        title, question, approve_text = labels.get(kind, ("Review action", "Approve this action?", "Approve"))
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("650x620")
        dialog.minsize(540, 480)
        dialog.configure(fg_color=COLORS["window"])
        dialog.transient(self)
        dialog.grab_set()
        dialog.protocol("WM_DELETE_WINDOW", lambda: reject())

        ctk.CTkLabel(dialog, text=question, text_color=COLORS["text"],
                     font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=22, pady=(20, 4))
        ctk.CTkLabel(dialog, text="Friday will make no change unless you approve below.",
                     text_color=COLORS["muted"], font=("Segoe UI", 12)).pack(anchor="w", padx=22, pady=(0, 14))

        details = ctk.CTkScrollableFrame(dialog, fg_color=COLORS["panel"], corner_radius=14)
        details.pack(expand=True, fill="both", padx=22, pady=(0, 14))
        if kind == "send_email":
            fields = [("To", preview.get("to", "")), ("Cc", preview.get("cc") or "—"),
                      ("Subject", preview.get("subject", ""))]
        elif kind == "create_calendar_event":
            fields = [("Event", preview.get("summary", "")), ("Starts", preview.get("start", "")),
                      ("Ends", preview.get("end", "")), ("Repeats", preview.get("recurrence", "Does not repeat"))]
        else:
            fields = [("Event", preview.get("summary", "")), ("When", preview.get("when", "")),
                      ("Calendar ID", preview.get("event_id", ""))]
        for label, value in fields:
            ctk.CTkLabel(details, text=label.upper(), text_color="#F5B45E",
                         font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", padx=14, pady=(12, 2))
            ctk.CTkLabel(details, text=value, text_color=COLORS["text"],
                         font=("Segoe UI", 13), anchor="w", justify="left",
                         wraplength=540).pack(fill="x", padx=14, pady=(0, 4))
        if kind == "send_email":
            ctk.CTkLabel(details, text="MESSAGE", text_color="#F5B45E",
                         font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", padx=14, pady=(12, 2))
            body = ctk.CTkTextbox(details, height=190, wrap="word", fg_color=COLORS["panel_soft"],
                                  text_color=COLORS["text"], corner_radius=10)
            body.pack(fill="x", padx=14, pady=(0, 14))
            body.insert("1.0", preview.get("body", ""))
            body.configure(state="disabled")
        elif kind == "delete_calendar_event":
            ctk.CTkLabel(details, text="This removes the event from Google Calendar.",
                         text_color="#F0C778", wraplength=540, justify="left").pack(fill="x", padx=14, pady=12)

        footer = ctk.CTkFrame(dialog, fg_color="transparent")
        footer.pack(fill="x", padx=22, pady=(0, 20))
        status = ctk.CTkLabel(footer, text="", text_color=COLORS["muted"])
        status.pack(side="left")

        def reject():
            self.update_status(f"Cancelled: {title.lower()}.")
            try:
                dialog.grab_release()
                dialog.destroy()
            except Exception:
                pass
            self._action_review_open = False
            if self.winfo_exists() and self._action_review_queue:
                self.after(150, self._show_next_action_review)

        def approve():
            approve_button.configure(state="disabled")
            cancel_button.configure(state="disabled")
            dialog.protocol("WM_DELETE_WINDOW", lambda: None)
            status.configure(text="Applying approved change…")

            def run_action():
                try:
                    result = execute_approved_action(action)
                except Exception as exc:
                    result = f"Action failed: {exc}"
                def finish():
                    self.update_status(f"✅ {result}")
                    try:
                        dialog.grab_release()
                        dialog.destroy()
                    except Exception:
                        pass
                    self._action_review_open = False
                    if self.winfo_exists() and self._action_review_queue:
                        self.after(150, self._show_next_action_review)
                self.after(0, finish)

            threading.Thread(target=run_action, daemon=True).start()

        cancel_button = ctk.CTkButton(footer, text="Cancel", width=100, height=40,
                                      fg_color=COLORS["panel_soft"], hover_color="#303B4D",
                                      command=reject)
        cancel_button.pack(side="right", padx=(8, 0))
        approve_color = "#8A3D3D" if kind == "delete_calendar_event" else COLORS["accent"]
        approve_hover = "#A84A4A" if kind == "delete_calendar_event" else "#3B76E0"
        approve_button = ctk.CTkButton(footer, text=approve_text, width=140, height=40,
                                       fg_color=approve_color, hover_color=approve_hover,
                                       command=approve)
        approve_button.pack(side="right")

    def on_wakeword_detected(self, transcribed_text, user_verified):
        self.wakeword_label.configure(text="✅ Wakeword Detected", text_color="green")
        self.after(3000, lambda: self.wakeword_label.configure(text="🔈 Listening...", text_color="lightgray"))

        if not self.voice_auth_enabled or user_verified:
            self.handle_prompt(transcribed_text)
        else:
            self.update_status("🚫 Voice mismatch. Access denied.")
            self.speak_response("Sorry, you're not authorized.")

    def monitor_mic(self):
        p = pyaudio.PyAudio()
        try:
            device_index = get_input_device_index(p)
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True,
                            input_device_index=device_index, frames_per_buffer=1024)
            while True:
                data = np.frombuffer(stream.read(1024, exception_on_overflow=False), dtype=np.int16)
                level = np.linalg.norm(data) / 1000
                self.mic_level_label.configure(text=f"🎚️ Mic Level: {level:.2f}")
                time.sleep(0.1)
        except Exception as exc:
            message = str(exc)
            self.after(0, lambda message=message: self.update_status(
                f"🎙️ Microphone meter unavailable: {message}"
            ))
        finally:
            p.terminate()

    def add_user_callback(self):
        name = ctk.CTkInputDialog(text="Enter your name:", title="New User Registration").get_input()
        if name:
            path = os.path.join(str(VOICEPRINTS_DIR), f"{name}.wav")
            self.update_status(f"🎤 Recording voice sample for {name}...")
            self.record_audio(path)
            self.update_status(f"✅ Voiceprint saved for {name}.")

    def open_memory_manager(self):
        window = ctk.CTkToplevel(self)
        window.title("Friday Memory")
        window.geometry("700x600")
        window.minsize(560, 440)
        window.configure(fg_color=COLORS["window"])
        window.transient(self)

        ctk.CTkLabel(window, text="Friday's memory", text_color=COLORS["text"],
                     font=("Segoe UI", 22, "bold")).pack(anchor="w", padx=22, pady=(20, 4))
        ctk.CTkLabel(
            window,
            text="Only explicitly saved preferences and projects appear here. Saved items are used in Friday's AI context; don't store passwords or secrets.",
            text_color=COLORS["muted"], font=("Segoe UI", 11), wraplength=640, justify="left",
        ).pack(anchor="w", padx=22, pady=(0, 14))

        controls = ctk.CTkFrame(window, fg_color="transparent")
        controls.pack(fill="x", padx=22, pady=(0, 10))
        rows = ctk.CTkScrollableFrame(window, fg_color=COLORS["panel"], corner_radius=14)
        rows.pack(expand=True, fill="both", padx=22, pady=(0, 20))

        def render_rows():
            for child in rows.winfo_children():
                child.destroy()
            try:
                items = load_memory_items()
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                ctk.CTkLabel(rows, text=f"Could not load saved memory: {exc}",
                             text_color="#F0C778", wraplength=580).pack(padx=16, pady=18)
                return
            if not items:
                ctk.CTkLabel(rows, text="Nothing saved yet. Add a preference or project to get started.",
                             text_color=COLORS["muted"], wraplength=580).pack(padx=16, pady=22)
                return
            for item in items:
                card = ctk.CTkFrame(rows, fg_color=COLORS["panel_soft"], corner_radius=12)
                card.pack(fill="x", padx=8, pady=6)
                details = ctk.CTkFrame(card, fg_color="transparent")
                details.pack(side="left", expand=True, fill="x", padx=14, pady=12)
                ctk.CTkLabel(details, text=f"{item['category'].upper()}  ·  {item['key']}",
                             text_color="#F5B45E", font=("Segoe UI", 12, "bold"),
                             anchor="w", wraplength=440).pack(fill="x", anchor="w")
                ctk.CTkLabel(details, text=item["value"], text_color=COLORS["text"],
                             font=("Segoe UI", 12), anchor="w", justify="left",
                             wraplength=440).pack(fill="x", anchor="w", pady=(5, 0))
                actions = ctk.CTkFrame(card, fg_color="transparent")
                actions.pack(side="right", padx=10)
                ctk.CTkButton(
                    actions, text="Edit", width=66, height=30,
                    command=lambda current=item: self._edit_memory_item(window, current, render_rows),
                ).pack(pady=3)
                ctk.CTkButton(
                    actions, text="Forget", width=66, height=30, fg_color="#623B3B",
                    hover_color="#824B4B",
                    command=lambda current=item: forget_one(current),
                ).pack(pady=3)

        def forget_one(item):
            if not messagebox.askyesno("Forget memory", f"Forget ‘{item['key']}’?", parent=window):
                return
            try:
                delete_memory_item(item["id"])
                render_rows()
                self.update_status(f"🧠 Forgot saved memory: {item['key']}")
            except (OSError, ValueError) as exc:
                messagebox.showerror("Memory error", str(exc), parent=window)

        ctk.CTkButton(
            controls, text="＋  Add memory", height=38,
            command=lambda: self._edit_memory_item(window, None, render_rows),
        ).pack(side="left")

        def forget_all():
            if not messagebox.askyesno("Forget all memory", "Remove every saved preference and project?", parent=window):
                return
            try:
                count = clear_memory_items()
                render_rows()
                self.update_status(f"🧠 Forgot all {count} saved memories.")
            except (OSError, ValueError) as exc:
                messagebox.showerror("Memory error", str(exc), parent=window)

        ctk.CTkButton(controls, text="Forget all", height=38, fg_color="#623B3B",
                      hover_color="#824B4B", command=forget_all).pack(side="right")
        render_rows()

    def _edit_memory_item(self, parent, item, on_saved):
        dialog = ctk.CTkToplevel(parent)
        dialog.title("Edit memory" if item else "Add memory")
        dialog.geometry("560x460")
        dialog.minsize(500, 420)
        dialog.configure(fg_color=COLORS["window"])
        dialog.transient(parent)

        ctk.CTkLabel(dialog, text="What should Friday remember?", text_color=COLORS["text"],
                     font=("Segoe UI", 18, "bold")).pack(anchor="w", padx=22, pady=(20, 14))
        ctk.CTkLabel(dialog, text="Type", text_color=COLORS["muted"]).pack(anchor="w", padx=22)
        category = ctk.CTkOptionMenu(dialog, values=list(MEMORY_CATEGORIES), width=200)
        category.pack(anchor="w", padx=22, pady=(4, 12))
        ctk.CTkLabel(dialog, text="Short name", text_color=COLORS["muted"]).pack(anchor="w", padx=22)
        key_entry = ctk.CTkEntry(dialog, placeholder_text="e.g. Preferred response style", height=38)
        key_entry.pack(fill="x", padx=22, pady=(4, 12))
        ctk.CTkLabel(dialog, text="Details", text_color=COLORS["muted"]).pack(anchor="w", padx=22)
        value_entry = ctk.CTkTextbox(dialog, height=140, wrap="word")
        value_entry.pack(fill="both", expand=True, padx=22, pady=(4, 14))
        if item:
            category.set(item["category"])
            key_entry.insert(0, item["key"])
            value_entry.insert("1.0", item["value"])

        def save():
            try:
                saved = save_memory_item(category.get(), key_entry.get(), value_entry.get("1.0", "end").strip())
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                messagebox.showerror("Could not save memory", str(exc), parent=dialog)
                return
            dialog.destroy()
            on_saved()
            self.update_status(f"🧠 Saved memory: {saved['key']}")

        ctk.CTkButton(dialog, text="Save memory", height=40, command=save).pack(anchor="e", padx=22, pady=(0, 18))

    def record_audio(self, filepath, duration=4):
        p = pyaudio.PyAudio()
        try:
            device_index = get_input_device_index(p)
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True,
                            input_device_index=device_index, frames_per_buffer=1024)
            frames = []
            for _ in range(int(16000 / 1024 * duration)):
                frames.append(stream.read(1024))
            stream.stop_stream()
            stream.close()
            with wave.open(filepath, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(16000)
                wf.writeframes(b''.join(frames))
        finally:
            p.terminate()

    # Button actions
    def speak_callback(self): self.handle_prompt("How can I help you today?")
    def calendar_callback(self): self.handle_prompt("What’s on my calendar today?")
    def notes_callback(self): self.handle_prompt("Show me my saved notes.")
    def music_callback(self): self.handle_prompt("Play some music.")
    def mood_callback(self): self.handle_prompt("Log my mood as relaxed.")
    def reminders_callback(self): self.handle_prompt("List my upcoming reminders.")
    def volume_callback(self): self.handle_prompt("Set the volume to 60%.")
    def settings_callback(self): self.handle_prompt("Open settings and preferences.")

if __name__ == '__main__':
    app = FridayGUI()
    app.mainloop()
