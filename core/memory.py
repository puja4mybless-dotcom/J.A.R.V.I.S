import json
from datetime import datetime
from pathlib import Path
from core.config import DATA_DIR

NOTES_FILE = DATA_DIR / "notes.json"
HISTORY_FILE = DATA_DIR / "history.json"

class MemoryManager:
    @staticmethod
    def _read_json(filepath: Path, default):
        if not filepath.exists():
            return default
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    @staticmethod
    def _write_json(filepath: Path, data):
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Memory] Failed to write to {filepath}: {e}")

    @classmethod
    def get_notes(cls):
        return cls._read_json(NOTES_FILE, [])

    @classmethod
    def add_note(cls, text: str) -> dict:
        notes = cls.get_notes()
        note = {
            "id": len(notes) + 1,
            "text": text,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        notes.append(note)
        cls._write_json(NOTES_FILE, notes)
        return note

    @classmethod
    def delete_note(cls, note_id: int) -> bool:
        notes = cls.get_notes()
        filtered = [n for n in notes if n.get("id") != note_id]
        if len(filtered) != len(notes):
            # re-index
            for i, n in enumerate(filtered):
                n["id"] = i + 1
            cls._write_json(NOTES_FILE, filtered)
            return True
        return False

    @classmethod
    def clear_notes(cls):
        cls._write_json(NOTES_FILE, [])

    @classmethod
    def get_history(cls, limit: int = 50):
        history = cls._read_json(HISTORY_FILE, [])
        return history[-limit:]

    @classmethod
    def add_history(cls, user_text: str, jarvis_reply: str, intent: str = "general"):
        history = cls._read_json(HISTORY_FILE, [])
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user": user_text,
            "jarvis": jarvis_reply,
            "intent": intent
        }
        history.append(entry)
        if len(history) > 200:
            history = history[-200:]
        cls._write_json(HISTORY_FILE, history)
