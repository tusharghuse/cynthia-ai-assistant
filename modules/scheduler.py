"""
modules/scheduler.py
====================
Manages timed reminders.
- Runs in a background thread so Cynthia can keep talking
- Checks every 30 seconds if a reminder is due
- Fires the TTS engine when the time matches

Reminders are stored in data/reminders.json.
"""

import json
import os
import threading
import time
from datetime import datetime
from utils.logger import log

REMINDERS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "reminders.json")


class ReminderScheduler:
    def __init__(self, voice):
        self.voice = voice          # Voice instance so we can speak reminders
        self.running = False
        os.makedirs(os.path.dirname(REMINDERS_FILE), exist_ok=True)
        if not os.path.exists(REMINDERS_FILE):
            self._save([])

    # ── Public API ────────────────────────────────────────────────────────────

    def add_reminder(self, time_str: str, label: str):
        """
        Add a reminder.
        time_str: "17:00" or "5:00 PM" style string
        label:    what to say when the reminder fires
        """
        reminders = self._load()
        reminders.append({
            "time": time_str,
            "label": label if label else "Time's up!",
            "fired": False
        })
        self._save(reminders)
        log(f"Reminder added: {time_str} — {label}")

    def start(self):
        """Start the background thread that checks for due reminders."""
        self.running = True
        thread = threading.Thread(target=self._loop, daemon=True)
        thread.start()
        log("Reminder scheduler started.")

    def get_all(self) -> list:
        """Return every stored reminder."""
        return self._load()

    def stop(self):
        self.running = False

    # ── Background loop ───────────────────────────────────────────────────────

    def _loop(self):
        """Check reminders every 30 seconds."""
        while self.running:
            self._check_reminders()
            time.sleep(30)

    def _check_reminders(self):
        """Fire any reminders whose time has arrived."""
        now       = datetime.now()
        now_str   = now.strftime("%H:%M")   # 24-hour "HH:MM"
        reminders = self._load()
        changed   = False

        for reminder in reminders:
            if reminder["fired"]:
                continue

            # Normalise stored time to HH:MM for comparison
            stored = self._normalise_time(reminder["time"])
            if stored == now_str:
                message = f"Reminder: {reminder['label']}"
                log(f"Firing reminder: {message}")
                self.voice.speak(message)
                reminder["fired"] = True
                changed = True

        if changed:
            self._save(reminders)

    # ── Time normalisation ────────────────────────────────────────────────────

    def _normalise_time(self, time_str: str) -> str:
        """
        Convert various time formats to 24-hour "HH:MM".
        Handles: "5 PM", "5:30 PM", "17:00", "5:00 PM"
        """
        time_str = time_str.strip().upper()
        for fmt in ("%I:%M %p", "%I %p", "%H:%M", "%I:%M%p", "%I%p"):
            try:
                return datetime.strptime(time_str, fmt).strftime("%H:%M")
            except ValueError:
                continue
        return time_str  # return as-is if parsing fails

    # ── Storage ───────────────────────────────────────────────────────────────

    def _load(self) -> list:
        try:
            with open(REMINDERS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save(self, reminders: list):
        with open(REMINDERS_FILE, "w") as f:
            json.dump(reminders, f, indent=2)
