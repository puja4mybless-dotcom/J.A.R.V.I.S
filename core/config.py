import os
from pathlib import Path
from dotenv import load_dotenv, set_key

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

# Load environment
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()

DATA_DIR = BASE_DIR / "data"
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
AUDIO_CACHE_DIR = BASE_DIR / "static" / "audio"

for directory in [DATA_DIR, SCREENSHOTS_DIR, AUDIO_CACHE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

class Config:
    @staticmethod
    def get(key: str, default: str = "") -> str:
        return os.getenv(key, default)

    @classmethod
    def get_user_name(cls) -> str:
        return cls.get("JARVIS_USER_NAME", "Sir")

    @classmethod
    def get_voice(cls) -> str:
        return cls.get("JARVIS_VOICE", "en-GB-RyanNeural")

    @classmethod
    def get_speech_speed(cls) -> str:
        return cls.get("JARVIS_SPEECH_SPEED", "+0%")

    @classmethod
    def get_speech_pitch(cls) -> str:
        return cls.get("JARVIS_SPEECH_PITCH", "+0Hz")

    @classmethod
    def get_gemini_key(cls) -> str:
        return cls.get("GEMINI_API_KEY", "").strip()

    @classmethod
    def get_groq_key(cls) -> str:
        return cls.get("GROQ_API_KEY", "").strip()

    @classmethod
    def get_openai_key(cls) -> str:
        return cls.get("OPENAI_API_KEY", "").strip()

    @classmethod
    def get_host(cls) -> str:
        return cls.get("HOST", "0.0.0.0")

    @classmethod
    def get_port(cls) -> int:
        try:
            return int(cls.get("PORT", "8000"))
        except ValueError:
            return 8000

    @classmethod
    def get_phone_pin(cls) -> str:
        return cls.get("JARVIS_PHONE_PIN", "").strip()

    @classmethod
    def get_phone_ip(cls) -> str:
        return cls.get("JARVIS_PHONE_IP", "").strip()

    @classmethod
    def get_language(cls) -> str:
        return cls.get("JARVIS_LANGUAGE", "auto").strip().lower()

    @classmethod
    def update_setting(cls, key: str, value: str):
        os.environ[key] = value
        try:
            if not ENV_PATH.exists():
                ENV_PATH.touch()
            set_key(str(ENV_PATH), key, value)
        except Exception as e:
            print(f"[Config] Error saving {key} to .env: {e}")
