import os
import re
import hashlib
import asyncio
from pathlib import Path
from core.config import AUDIO_CACHE_DIR, Config

# ─── Language detection (no external library needed) ─────────────────────────
# Unicode block ranges for script identification
_DEVANAGARI_RE = re.compile(r'[\u0900-\u097F]')   # Hindi / Marathi / Sanskrit
_ARABIC_RE     = re.compile(r'[\u0600-\u06FF]')   # Arabic / Urdu
_BENGALI_RE    = re.compile(r'[\u0980-\u09FF]')   # Bengali
_TAMIL_RE      = re.compile(r'[\u0B80-\u0BFF]')   # Tamil
_TELUGU_RE     = re.compile(r'[\u0C00-\u0C7F]')   # Telugu
_GURMUKHI_RE   = re.compile(r'[\u0A00-\u0A7F]')   # Punjabi (Gurmukhi)
_GUJARATI_RE   = re.compile(r'[\u0A80-\u0AFF]')   # Gujarati
_CJK_RE        = re.compile(r'[\u4E00-\u9FFF]')   # Chinese/Japanese

# ─── Hinglish detection (Hindi words written in Roman / Latin script) ─────────
# Comprehensive list of Roman Hindi / Hinglish keywords
_HINGLISH_MARKERS = {
    # Pronouns
    "mera", "meri", "mere", "mujhe", "mujhko", "mai", "main", "hum", "hume", "humein", "hame", "hamein",
    "tera", "teri", "tere", "tujhe", "tujhko", "tu", "tum", "tumhe", "tumhein", "tumko",
    "aap", "aapko", "aapka", "aapki", "aapke", "aapne",
    "uska", "uski", "uske", "use", "usey", "usko", "unka", "unki", "unke", "unhe", "unhein",
    "iska", "iski", "iske", "ise", "isey", "isko", "inke", "inki", "inka", "inhe",
    "hamara", "hamari", "hamare", "tumhara", "tumhari", "tumhare",
    # Question words
    "kya", "kaise", "kaisa", "kaisi", "kaun", "kon", "kab", "kahan", "kahaan", "kidhar", "kyun", "kyu", "kyunki",
    "kitna", "kitni", "kitne", "konsa", "konsi", "konse",
    # Verbs / Imperatives
    "karo", "kardo", "kar", "kr", "kro", "krdo", "karna", "karega", "karegi", "karenge", "karta", "karti", "karte",
    "kholo", "khol", "kholdo", "kholna", "kholiye",
    "band", "bandh", "roko", "ruk", "ruko",
    "batao", "btao", "bata", "batana", "bataiye", "batao na",
    "dikhao", "dikha", "dikhana", "dikhaiye",
    "sunao", "suno", "sun", "sunna", "suniye",
    "bolo", "bol", "bolna", "boliye", "kaho", "kaha",
    "chalao", "chala", "chalu", "chalana", "chal", "chalo",
    "bajao", "baja", "bajane",
    "badhao", "badha", "kam", "ghatao", "ghata",
    "dekh", "dekho", "dekhna", "dekhiye",
    "dedo", "de", "dena", "dijiye", "do",
    "lelo", "le", "lena", "lijiye", "lo",
    "jao", "ja", "jana", "jaiye",
    "aao", "aa", "aana", "aaiye",
    "bhejo", "bhej", "bhejna",
    "likho", "likh", "likhna",
    "padho", "padh", "padhna",
    "samjhao", "samjha", "samajh",
    "hatao", "hata", "hataiye",
    "lagao", "laga", "rakho", "rakh",
    "bujhao", "bujha", "jalao", "jala",
    # Postpositions / particles
    "mein", "me", "ko", "ka", "ki", "ke", "se", "pe", "par", "tak", "wala", "wali", "wale", "keliye",
    # Auxiliary verbs
    "hai", "hain", "ho", "hoon", "hun", "tha", "thi", "the", "hoga", "hogi", "hoge",
    # Adverbs / Conjunctions / Everyday terms
    "nahi", "nahin", "nhi", "na", "mat", "haan", "han", "ji",
    "abhi", "yahan", "wahan", "idhar", "udhar", "aur", "ya", "lekin", "parantu",
    "bahut", "bohot", "boht", "thoda", "thodi", "zyada", "jyada",
    "accha", "achha", "theek", "thik", "sahi", "galat", "sach", "jhooth", "badhiya", "mast",
    "bhai", "yaar", "dost", "bhaiya", "didi", "sahab", "saheb",
    "namaste", "namaskar", "dhanyavaad", "dhanyawad", "shukriya", "alvida",
    "zaroor", "zarur", "bilkul", "bas", "sirf",
    "kuch", "kuchh", "sab", "sabko", "sabse", "phir", "fir",
    "aaj", "kal", "parso", "subah", "dopahar", "shaam", "raat", "din", "waqt", "samay",
    "jawab", "sawal", "baat", "mausam", "taapman", "khabar",
    "hindi", "hinglish",
}

# Regex to split text into words (handles punctuation)
_WORD_SPLIT_RE = re.compile(r'[a-zA-Z]+')

# Phrases that explicitly ask to use Hindi
_EXPLICIT_HINDI_PHRASES = [
    "speak in hindi", "talk in hindi", "reply in hindi", "answer in hindi",
    "in hindi", "hindi me", "hindi mein", "hindi bolo", "hindi me bolo",
    "hindi mein bolo", "hindi me baat", "hindi mein baat", "hindi bhasha",
    "mujhe hindi me", "mujhe hindi mein"
]

def _is_hinglish(text: str) -> bool:
    """
    Detects Hinglish (Hindi in Roman script) by identifying Hindi marker words or phrases.
    """
    t_lower = text.lower().strip()
    # Check explicit Hindi request phrases
    if any(p in t_lower for p in _EXPLICIT_HINDI_PHRASES):
        return True

    words = [w.lower() for w in _WORD_SPLIT_RE.findall(text)]
    if len(words) < 1:
        return False

    # English words that could overlap with Roman Hindi
    english_overlap = {
        "band", "par", "mat", "bat", "ja", "de", "le", "na", "the", "me",
        "phone", "mobile", "computer", "status", "lock", "unlock",
        "screenshot", "battery", "volume", "ok", "hi", "hello", "do",
        "time", "date", "day", "news", "weather", "set", "save", "open", "launch", "is"
    }

    all_hindi = [w for w in words if w in _HINGLISH_MARKERS]
    strong_hindi = [w for w in all_hindi if w not in english_overlap]

    # At least 1 strong (unambiguous) Hindi word present
    if strong_hindi:
        # If total phrase is short (1-5 words), 1 strong Hindi word is enough!
        # e.g., "phone kholo", "pw khol do", "kya haal hai", "aap kaise ho"
        if len(words) <= 5:
            return True
        # For longer text, require at least 1 strong and >= 20% Hindi content or >= 2 strong
        if len(strong_hindi) >= 2 or (len(all_hindi) / len(words) >= 0.2):
            return True

    return False


def translate_to_hindi(text: str) -> str:
    """
    Translates an English text to natural Hindi using Google Translate endpoint.
    Zero API key required, highly reliable for knowledge and system descriptions.
    """
    if not text or not text.strip():
        return ""
    try:
        import urllib.request
        import json
        clean = text.strip()
        # Limit to 500 chars for instant speed
        sample = clean[:500]
        url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=hi&dt=t&q=" + urllib.parse.quote(sample)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                translated = "".join([part[0] for part in data[0] if part and part[0]])
                return translated.strip()
    except Exception as e:
        print(f"[VoiceEngine] Translation to Hindi failed: {e}")
    return text


def detect_language(text: str) -> str:
    """
    Detects input language from text.
    Returns: 'hi' (Devanagari Hindi), 'hinglish' (Latin-script Hindi),
             'ar', 'bn', 'ta', 'te', 'pa', 'gu', 'zh', or 'en'.
    """
    if not text:
        return 'en'
    # 1. Script-based detection (Devanagari, Arabic, Bengali, etc.)
    if _DEVANAGARI_RE.search(text):
        return 'hi'
    if _ARABIC_RE.search(text):
        return 'ar'
    if _BENGALI_RE.search(text):
        return 'bn'
    if _TAMIL_RE.search(text):
        return 'ta'
    if _TELUGU_RE.search(text):
        return 'te'
    if _GURMUKHI_RE.search(text):
        return 'pa'
    if _GUJARATI_RE.search(text):
        return 'gu'
    if _CJK_RE.search(text):
        return 'zh'
    # 2. Hinglish detection (Latin-script Hindi)
    if _is_hinglish(text):
        return 'hinglish'
    return 'en'


def pick_voice_for_lang(lang_code: str) -> str:
    """
    Returns the best edge-tts voice for a given language code.
    Falls back to the user's configured voice for English.
    """
    # Map language → preferred edge-tts voice
    lang_voice_map = {
        'hi': 'hi-IN-MadhurNeural',          # Hindi Devanagari
        'hinglish': 'hi-IN-MadhurNeural',     # Hinglish → reply in Hindi voice
        'hi-f': 'hi-IN-SwaraNeural',          # Hindi female
        'mr': 'mr-IN-AarohiNeural',           # Marathi
        'bn': 'bn-IN-TanishaaNeural',         # Bengali
        'ta': 'ta-IN-PallaviNeural',          # Tamil
        'te': 'te-IN-ShrutiNeural',           # Telugu
        'gu': 'gu-IN-DhwaniNeural',           # Gujarati
        'pa': 'pa-IN-OjaswanthNeural',        # Punjabi
        'ur': 'ur-PK-AsadNeural',             # Urdu
        'ar': 'ar-SA-ZariyahNeural',          # Arabic
        'fr': 'fr-FR-HenriNeural',            # French
        'de': 'de-DE-KillianNeural',          # German
        'es': 'es-ES-AlvaroNeural',           # Spanish
        'zh': 'zh-CN-YunxiNeural',            # Chinese
        'ja': 'ja-JP-KeitaNeural',            # Japanese
        'en': Config.get_voice(),              # English → user preference
    }
    return lang_voice_map.get(lang_code, Config.get_voice())


class VoiceEngine:

    @staticmethod
    def _get_filename(text: str, voice: str) -> str:
        h = hashlib.md5(f"{text}_{voice}".encode("utf-8")).hexdigest()
        return f"speech_{h}.mp3"

    @classmethod
    async def synthesize(cls, text: str, voice: str = None) -> str:
        """
        Synthesizes text to an MP3 file using edge-tts.
        Auto-detects language from the text if no voice is specified.
        Returns the relative URL to the audio file (e.g. /audio/speech_xxx.mp3).
        """
        if not text or not text.strip():
            return ""

        clean_text = text.strip()

        # Auto-detect language and pick an appropriate voice
        if voice:
            voice_name = voice
        else:
            lang = detect_language(clean_text)
            voice_name = pick_voice_for_lang(lang)

        filename = cls._get_filename(clean_text, voice_name)
        file_path = AUDIO_CACHE_DIR / filename

        # Return cached audio if already synthesized
        if file_path.exists() and file_path.stat().st_size > 0:
            return f"/audio/{filename}"

        try:
            import edge_tts
            communicate = edge_tts.Communicate(
                text=clean_text,
                voice=voice_name,
                rate=Config.get_speech_speed(),
                pitch=Config.get_speech_pitch()
            )
            await communicate.save(str(file_path))
            return f"/audio/{filename}"
        except Exception as e:
            print(f"[VoiceEngine] edge-tts error with voice {voice_name}: {e}. Trying fallback voice.")
            # Fallback: try user's default voice
            try:
                import edge_tts
                fallback_voice = Config.get_voice()
                fallback_filename = cls._get_filename(clean_text, fallback_voice)
                fallback_path = AUDIO_CACHE_DIR / fallback_filename
                communicate = edge_tts.Communicate(
                    text=clean_text,
                    voice=fallback_voice,
                    rate=Config.get_speech_speed(),
                    pitch=Config.get_speech_pitch()
                )
                await communicate.save(str(fallback_path))
                return f"/audio/{fallback_filename}"
            except Exception as e2:
                print(f"[VoiceEngine] edge-tts fallback failed: {e2}. Trying pyttsx3.")
                try:
                    import pyttsx3
                    wav_filename = filename.replace(".mp3", ".wav")
                    wav_path = AUDIO_CACHE_DIR / wav_filename
                    engine = pyttsx3.init()
                    engine.save_to_file(clean_text, str(wav_path))
                    engine.runAndWait()
                    return f"/audio/{wav_filename}"
                except Exception as e3:
                    print(f"[VoiceEngine] pyttsx3 fallback failed: {e3}")
                    return ""

    @classmethod
    def get_available_voices(cls):
        """Returns all available TTS voices grouped by language."""
        return [
            # ── English ────────────────────────────────────────────────────────
            {"id": "en-GB-RyanNeural",         "name": "JARVIS British (Ryan) ★",  "lang": "English", "gender": "Male"},
            {"id": "en-GB-ThomasNeural",        "name": "British Formal (Thomas)",  "lang": "English", "gender": "Male"},
            {"id": "en-GB-SoniaNeural",         "name": "FRIDAY British (Sonia)",   "lang": "English", "gender": "Female"},
            {"id": "en-US-ChristopherNeural",   "name": "US Assistant (Christopher)","lang": "English","gender": "Male"},
            {"id": "en-US-JennyNeural",         "name": "US Natural (Jenny)",        "lang": "English","gender": "Female"},
            {"id": "en-IN-NeerjaNeural",        "name": "Indian English (Neerja)",   "lang": "English","gender": "Female"},
            {"id": "en-IN-PrabhatNeural",       "name": "Indian English (Prabhat)",  "lang": "English","gender": "Male"},
            # ── Hindi ─────────────────────────────────────────────────────────
            {"id": "hi-IN-MadhurNeural",        "name": "हिंदी — Madhur (Male) ★",  "lang": "Hindi",  "gender": "Male"},
            {"id": "hi-IN-SwaraNeural",         "name": "हिंदी — Swara (Female)",   "lang": "Hindi",  "gender": "Female"},
            # ── Regional Indian ────────────────────────────────────────────────
            {"id": "mr-IN-AarohiNeural",        "name": "मराठी — Aarohi",           "lang": "Marathi","gender": "Female"},
            {"id": "bn-IN-TanishaaNeural",      "name": "বাংলা — Tanishaa",         "lang": "Bengali","gender": "Female"},
            {"id": "ta-IN-PallaviNeural",       "name": "தமிழ் — Pallavi",          "lang": "Tamil",  "gender": "Female"},
            {"id": "te-IN-ShrutiNeural",        "name": "తెలుగు — Shruti",          "lang": "Telugu", "gender": "Female"},
            {"id": "gu-IN-DhwaniNeural",        "name": "ગુજરાતી — Dhwani",        "lang": "Gujarati","gender": "Female"},
            {"id": "pa-IN-OjaswanthNeural",     "name": "ਪੰਜਾਬੀ — Ojaswanth",     "lang": "Punjabi","gender": "Male"},
            {"id": "ur-PK-AsadNeural",          "name": "اردو — Asad",              "lang": "Urdu",   "gender": "Male"},
            # ── International ──────────────────────────────────────────────────
            {"id": "ar-SA-ZariyahNeural",       "name": "عربي — Zariyah",           "lang": "Arabic", "gender": "Female"},
            {"id": "fr-FR-HenriNeural",         "name": "Français — Henri",         "lang": "French", "gender": "Male"},
            {"id": "de-DE-KillianNeural",       "name": "Deutsch — Killian",        "lang": "German", "gender": "Male"},
            {"id": "es-ES-AlvaroNeural",        "name": "Español — Álvaro",         "lang": "Spanish","gender": "Male"},
            {"id": "zh-CN-YunxiNeural",         "name": "中文 — Yunxi",             "lang": "Chinese","gender": "Male"},
            {"id": "ja-JP-KeitaNeural",         "name": "日本語 — Keita",           "lang": "Japanese","gender": "Male"},
        ]

