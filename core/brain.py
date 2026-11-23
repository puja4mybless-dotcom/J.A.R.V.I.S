import os
import re
import json
import asyncio
import hashlib
import time
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import RLock
from core.config import Config
from core.system_control import SystemControl
from core.tools import JarvisTools
from core.memory import MemoryManager
from core.knowledge import GoogleKnowledgeGraphEngine, OmniKnowledgeEngine
from core.phone_control import PhoneControl
from core.voice_engine import detect_language
from core.math_engine import OmniMathEngine
from core.media_engine import EducationalMediaEngine
from core.weather_engine import IMDWeatherEngine
from core.academic_engine import AcademicEngine, SUBJECT_DISPLAY

# ── Speed Engine: Thread pool for parallel blocking calls ──────────────────
_THREAD_POOL = ThreadPoolExecutor(max_workers=8)

# ── Speed Engine: bounded cache for stable, repeat questions ───────────────
_RESPONSE_CACHE: dict = {}   # {cache_key: (reply_dict, timestamp)}
_CACHE_TTL: int = 600        # stable answers can be reused for ten minutes
_CACHE_LOCK = RLock()
_VOLATILE_QUERY_TERMS = (
    "current", "currently", "latest", "today", "tonight", "now", "live",
    "news", "weather", "forecast", "temperature", "price", "stock", "share price",
    "exchange rate", "currency rate", "score", "match result", "traffic", "breaking",
    "this week", "this month", "yesterday", "tomorrow", "right now", "prime minister",
    "president of", "chief minister", "ceo of", "head coach", "election result",
)
_CONTEXTUAL_QUERY_TERMS = (
    "this", "that", "these", "those", "it", "they", "he", "she", "him", "her",
    "same", "previous", "above", "last answer", "you said", "continue",
)

def _cache_key(q: str, lang: str = "en", user_name: str = "Sir") -> str:
    """Fingerprint the query together with response language and personalization."""
    cache_input = f"{lang}\0{user_name}\0{q.lower().strip()}"
    return hashlib.sha256(cache_input.encode("utf-8")).hexdigest()[:24]

def _cacheable_query(q: str) -> bool:
    normalized = q.lower().strip()
    if any(term in normalized for term in _VOLATILE_QUERY_TERMS):
        return False
    words = set(re.findall(r"[a-z']+", normalized))
    if words.intersection(_CONTEXTUAL_QUERY_TERMS):
        return False
    return True

def _needs_live_search(q: str) -> bool:
    normalized = q.lower().strip()
    if any(term in normalized for term in _VOLATILE_QUERY_TERMS):
        return True
    return bool(re.match(
        r"^(?:who|what|where|when|why|how|which|is|are|was|were|do|does|did|can|could|should|explain|describe|compare|define|tell me|kya|kaun|kab|kahan|kahaan|kaise|kyun|kyu|batao|btao|samjhao)\b",
        normalized,
    ))

def _cache_get(q: str, lang: str = "en", user_name: str = "Sir"):
    if not _cacheable_query(q):
        return None
    key = _cache_key(q, lang, user_name)
    with _CACHE_LOCK:
        cached = _RESPONSE_CACHE.get(key)
        if cached:
            entry, ts = cached
            if time.time() - ts < _CACHE_TTL:
                return dict(entry)
            del _RESPONSE_CACHE[key]
    return None

def _cache_set(q: str, result: dict, lang: str = "en", user_name: str = "Sir"):
    if not _cacheable_query(q):
        return
    key = _cache_key(q, lang, user_name)
    with _CACHE_LOCK:
        if len(_RESPONSE_CACHE) >= 200:
            oldest = min(_RESPONSE_CACHE, key=lambda cache_key: _RESPONSE_CACHE[cache_key][1])
            del _RESPONSE_CACHE[oldest]
        _RESPONSE_CACHE[key] = (dict(result), time.time())

def _clean_trailing_device(text: str) -> str:
    """Strips trailing device/screen targets like 'on my computer screen', 'on pc', 'on screen'."""
    cleaned = re.sub(
        r"\s+(?:on|in)\s+(?:my\s+)?(?:computer\s+screen|pc\s+screen|laptop\s+screen|screen|desktop|display|computer|pc|laptop|system)$",
        "",
        text,
        flags=re.IGNORECASE
    ).strip()
    cleaned = re.sub(
        r"\s+(?:(?:computer|pc|laptop)?\s*screen|desktop|display|computer|pc)\s+(?:par|pe|mein|me)$",
        "",
        cleaned,
        flags=re.IGNORECASE
    ).strip()
    return cleaned


JARVIS_SYSTEM_PROMPT = (
    "You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), a capable assistant and tutor. "
    "You are not omniscient: use available sources and tools, and say when you cannot verify an answer. Cover subjects from "
    "Class 1 (Primary) to IAS/UPSC professional examination level.\n\n"
    "ACADEMIC COVERAGE:\n"
    "• Mathematics: Arithmetic → Algebra → Geometry → Trigonometry → Calculus → Statistics → Linear Algebra\n"
    "• Physics: Mechanics → Thermodynamics → Electromagnetism → Optics → Modern Physics → Quantum Physics\n"
    "• Chemistry: General → Physical → Organic → Inorganic → Analytical Chemistry\n"
    "• Biology: Cell Biology → Genetics → Evolution → Ecology → Human Physiology → Botany → Zoology\n"
    "• History: Ancient → Medieval → Modern → World History → Indian National Movement\n"
    "• Geography: Physical → Human → Indian Geography → World Geography → Environmental Geography\n"
    "• Civics & Polity: Indian Constitution → Parliament → Judiciary → Panchayati Raj → Elections\n"
    "• Economics: Micro → Macro → Indian Economy → International Trade → Economic Survey\n"
    "• Computer Science: Algorithms → Data Structures → OOP → DBMS → OS → Networking → AI/ML\n"
    "• English: Grammar → Literature → Writing → Comprehension\n"
    "• Environmental Science, Social Science, Accountancy, Business Studies, Psychology, Sociology\n"
    "• All Competitive Exams: UPSC/IAS/IPS, JEE, NEET, SSC, Banking, Railway, State PSC\n\n"
    "CORE RULES:\n"
    "(1) Be accurate and honest: do not guess or invent facts, dates, numbers, or sources. State uncertainty when evidence is missing or conflicting.\n"
    "(2) British J.A.R.V.I.S. tone — address user as 'Sir'. Confident, precise, helpful.\n"
    "(3) Step-by-step for math/science problems. Structured headings for conceptual questions.\n"
    "(4) Match language: English, Hindi, or Hinglish seamlessly.\n"
    "(5) Match complexity to the student's level (primary school to IAS prep).\n"
    "(6) For numerical problems: State given → Formula → Steps → Answer → Units/Verification.\n"
    "(7) For conceptual questions: Define → Explain → Example → Key Takeaway.\n"
    "(8) For history/civics/economics: Include dates, figures, causes, effects, significance.\n"
    "(9) When browser search is available, search time-sensitive or uncertain factual claims and cite its sources. Distinguish sourced facts from inference; if reliable evidence is unavailable, say you cannot verify it.\n"
    "(10) Answer directly and concisely by default; expand only when the question needs detail."
)

# Hindi wake-word variants (Devanagari)
_HINDI_WAKE_WORDS = ["जार्विस", "जारविस", "हे जार्विस", "हे जारविस", "ओके जार्विस"]

# Hinglish wake-word variants (Roman script)
_HINGLISH_WAKE_WORDS = ["jarvis", "hey jarvis", "ok jarvis", "arre jarvis", "sun jarvis", "oye jarvis"]

class JarvisBrain:
    _conversation_history: list[dict] = []

    @staticmethod
    def _is_valid_api_key(key: str) -> bool:
        """Checks if an API key appears genuine (not placeholder or test numbers)."""
        if not key or len(key) < 18:
            return False
        if key.isdigit() or key.lower() in ("placeholder", "your_api_key", "your_gemini_api_key"):
            return False
        return True

    @classmethod
    async def process_command(cls, text: str) -> dict:
        """
        Processes a user's typed or spoken command.
        Routes through local system automation, specialized knowledge extractors,
        cached local answers, browser search, or cloud LLM reasoning.
        Full dual-language capability: fluent British English and Hindi / Hinglish.
        """
        user_name = Config.get_user_name()
        query = text.strip()
        if not query:
            return {
                "reply": f"At your service, {user_name}.",
                "intent": "idle",
                "action_taken": False,
                "telemetry_refresh": False
            }

        q_lower = query.lower()

        # Remove wake words if spoken in sentence (English, Devanagari Hindi, Hinglish)
        wake_words = ["hey jarvis", "ok jarvis", "arre jarvis", "sun jarvis", "oye jarvis", "jarvis", "computer"]
        cleaned_query = q_lower
        for w in sorted(wake_words, key=len, reverse=True):
            if cleaned_query.startswith(w):
                # Don't strip 'computer' if followed by actionable command words
                if w == "computer" and any(cleaned_query.startswith(f"computer {act}") for act in ["unlock", "lock", "kholo", "khol", "setting", "settings", "password", "shutdown", "restart"]):
                    pass
                else:
                    cleaned_query = cleaned_query[len(w):].strip(", !.? ")
                    break

        for w in _HINDI_WAKE_WORDS:
            if query.startswith(w):
                query = query[len(w):].strip(", !.? ")
                cleaned_query = query.lower()
                break

        # ── 0. LANGUAGE SWITCHING COMMANDS ───────────────────────────────────
        # "speak in hindi", "hindi me bolo", "switch to hindi", "talk in hindi", etc.
        if any(p in cleaned_query for p in [
            "speak in hindi", "talk in hindi", "reply in hindi", "answer in hindi",
            "hindi me bolo", "hindi mein bolo", "hindi me baat", "hindi mein baat",
            "switch to hindi", "change to hindi", "hindi language", "mujhe hindi me jawab do",
            "हिंदी में बोलो", "हिंदी में बात करो"
        ]):
            Config.update_setting("JARVIS_LANGUAGE", "hi")
            msg = f"जी {user_name}, अब से मैं आपसे हिंदी में बात करूँगा। बताइए, आपकी क्या सेवा करूँ?"
            MemoryManager.add_history(query, msg, "settings")
            return {"reply": msg, "intent": "settings", "action_taken": True, "telemetry_refresh": False, "detected_lang": "hi"}

        if any(p in cleaned_query for p in [
            "speak in hinglish", "talk in hinglish", "hinglish me bolo", "hinglish mein bolo",
            "switch to hinglish", "change to hinglish"
        ]):
            Config.update_setting("JARVIS_LANGUAGE", "hinglish")
            msg = f"Ji {user_name}, ab se main aapse Hinglish me baat karunga. Boliye, kya command hai?"
            MemoryManager.add_history(query, msg, "settings")
            return {"reply": msg, "intent": "settings", "action_taken": True, "telemetry_refresh": False, "detected_lang": "hinglish"}

        if any(p in cleaned_query for p in [
            "speak in english", "talk in english", "reply in english", "english me bolo",
            "switch to english", "change to english", "अंग्रेजी में बोलो"
        ]):
            Config.update_setting("JARVIS_LANGUAGE", "en")
            msg = f"Understood, {user_name}. I will now communicate with you in English. Standing by for instructions."
            MemoryManager.add_history(query, msg, "settings")
            return {"reply": msg, "intent": "settings", "action_taken": True, "telemetry_refresh": False, "detected_lang": "en"}

        if any(p in cleaned_query for p in ["auto language", "auto detect language", "automatic language"]):
            Config.update_setting("JARVIS_LANGUAGE", "auto")
            msg = f"Automatic language detection activated, {user_name}. I will match whichever language you speak or write."
            MemoryManager.add_history(query, msg, "settings")
            return {"reply": msg, "intent": "settings", "action_taken": True, "telemetry_refresh": False, "detected_lang": "en"}

        # ── Language determination ───────────────────────────────────────────
        configured_lang = Config.get_language()  # 'auto', 'hi', 'hinglish', 'en'
        detected_lang = detect_language(query)
        if configured_lang in ("hi", "hinglish", "en"):
            effective_lang = configured_lang
        else:
            effective_lang = detected_lang

        is_hindi = effective_lang in ("hi", "hinglish")

        # Return only a prior stable knowledge answer; volatile facts and follow-ups
        # are deliberately excluded from the cache.
        cached = _cache_get(cleaned_query, effective_lang, user_name)
        if cached:
            return cached

        # ── 1. APP, WEBSITE & SHORTCUT LAUNCHER (English, Hindi, Hinglish) ─────
        # Opens all Google apps, web links, and desktop applications directly on the computer screen.
        app_target = None

        # Check: Open all Google apps / links / ecosystem
        if any(p in cleaned_query for p in [
            "open all google apps", "open all google links", "open all google",
            "open google apps", "open google links", "open google products", "open google suite", "open google ecosystem",
            "all google apps", "all google links", "all google apps open karo", "google ke saare apps",
            "google ke sare apps", "open all apps of google", "google apps kholo",
            "it have to open all the google links and apps on my computer screen",
            "open all the google links and apps on my computer screen",
            "open all the google links and apps", "open all google links and apps",
            "open google links and apps", "open google apps and links",
            "open all apps and google links", "open apps and links on computer screen",
        ]):
            success, msg_en = SystemControl.open_all_google_apps()
            msg = msg_en if not is_hindi else f"जी {user_name}, Google का पूरा ऐप्स इकोसिस्टम आपकी कंप्यूटर स्क्रीन पर खोल दिया गया है।"
            MemoryManager.add_history(query, msg, "app_launch")
            return {"reply": msg, "intent": "app_launch", "action_taken": True, "telemetry_refresh": False, "detected_lang": effective_lang}

        # Check: Explicit Google Search command to open on screen
        # e.g., "search on google for X", "search X on google", "google search X", "google par search karo X"
        m_gs = re.search(r"^(?:please\s+)?(?:search\s+(?:on|in)?\s*google\s+(?:for|about)?\s*|google\s+search\s+(?:for|about)?\s*|google\s+(?:par|pe|mein|me)\s*search\s*karo\s*)(.+)$", cleaned_query)
        if not m_gs:
            m_gs2 = re.search(r"^(?:search\s+)(.+?)\s+(?:on|in)\s+google(?:\s+(?:on|in)?\s*(?:my\s+)?(?:screen|computer|pc))?\b", cleaned_query)
            if m_gs2:
                m_gs = m_gs2

        if m_gs:
            g_term = _clean_trailing_device(m_gs.group(1).strip())
            if g_term:
                success, msg_en = SystemControl.open_google_search(g_term)
                msg = msg_en if not is_hindi else f"जी {user_name}, Google पर '{g_term}' आपकी स्क्रीन पर खोल दिया गया है।"
                MemoryManager.add_history(query, msg, "google_search")
                return {"reply": msg, "intent": "app_launch", "action_taken": True, "telemetry_refresh": False, "detected_lang": effective_lang}

        # Pattern A: "[app] khol do", "[app] kholo", "[app] chalao", "[app] open karo"
        m_hi = re.search(r"^(.*?)\s*(?:khol\s*do|kholdo|kholo|khol|chala\s*do|chalado|chalao|chala|chalu\s*karo|chalu\s*kr|open\s*karo|start\s*karo)\s*$", cleaned_query)
        if m_hi and m_hi.group(1).strip():
            cand = _clean_trailing_device(m_hi.group(1).strip())
            if cand not in ("phone", "mobile", "fone", "pc", "computer", "laptop", "screen", "diagnostics", "diagnostic", "system", "scan"):
                app_target = cand

        # Pattern B: "kholo [app]", "khol do [app]", "open [app]", "launch [app]", "start [app]"
        if not app_target:
            m_en = re.search(r"^(?:open|launch|start|run|kholo|khol\s*do|chalao|chalu\s*karo)\s+(.+)$", cleaned_query)
            if m_en:
                cand = _clean_trailing_device(m_en.group(1).strip())
                if cand not in ("phone", "mobile", "fone", "pc", "computer", "laptop", "screen", "diagnostics", "diagnostic", "system", "scan", "weather"):
                    app_target = cand

        # Pattern C: Direct shortcut keywords without requiring 'open'
        if not app_target:
            shortcuts_map = {
                "physics wallah": "physics wallah", "physicswallah": "physics wallah", "pw live": "physics wallah",
                "pw": "pw", "open pw": "pw",
                "ncert": "ncert", "ncert books": "ncert", "ncert portal": "ncert",
                "whatsapp": "whatsapp", "whatsapp web": "whatsapp",
                "mail": "mail", "email": "mail", "gmail": "gmail", "outlook": "outlook",
                "call centre": "call centre", "call center": "call centre", "phone link": "call centre", "your phone": "call centre",
                "settings": "settings", "computer settings": "settings", "pc settings": "settings", "windows settings": "settings",
                "google": "google", "youtube": "youtube", "calculator": "calculator", "notepad": "notepad",
                "google drive": "google drive", "drive": "google drive",
                "google docs": "google docs", "docs": "google docs",
                "google sheets": "google sheets", "sheets": "google sheets",
                "google slides": "google slides", "slides": "google slides",
                "google meet": "google meet", "meet": "google meet",
                "google maps": "google maps", "maps": "google maps",
                "google photos": "google photos", "google calendar": "google calendar",
                "google classroom": "google classroom", "classroom": "google classroom",
                "google earth": "google earth", "google colab": "google colab",
                "google translate": "google translate", "google keep": "google keep",
                "google gemini": "google gemini", "gemini": "google gemini",
                "chrome": "chrome", "google chrome": "chrome"
            }
            clean_bare = _clean_trailing_device(cleaned_query.strip())
            clean_bare_no_my = re.sub(r"\s+(?:on|in)\s+(?:my\s+)?(?:computer|pc|laptop|system)$", "", clean_bare, flags=re.IGNORECASE).strip()
            for sk, sv in shortcuts_map.items():
                if clean_bare == sk or clean_bare_no_my == sk:
                    app_target = sv
                    break

        if app_target:
            success, msg_en = SystemControl.open_app(app_target)
            title = SystemControl.get_app_title(app_target)
            if is_hindi:
                if effective_lang == "hi":
                    msg = f"जी {user_name}, {title} आपकी स्क्रीन पर शुरू कर रहा हूँ।" if success else f"{user_name}, {title} खोलने में समस्या आई।"
                else:
                    msg = f"Ji {user_name}, {title} aapki screen par open kar raha hoon." if success else f"{user_name}, {title} open karne me problem aayi."
            else:
                msg = msg_en
            MemoryManager.add_history(query, msg, "app_launch")
            return {"reply": msg, "intent": "app_launch", "action_taken": success, "telemetry_refresh": False, "detected_lang": effective_lang}

        # Never accept Windows credentials through chat or the public API.
        if re.search(r"(?:set|save|store|my)?\s*(?:pc|computer|laptop)\s+password\s+(?:is\s+|to\s+)?\S+", cleaned_query):
            return {
                "reply": "For security, J.A.R.V.I.S. will not accept or store a Windows password. Enter your Windows PIN or password directly on the PC lock screen.",
                "intent": "system_control", "action_taken": False,
                "telemetry_refresh": False, "detected_lang": effective_lang,
            }

        # Windows secure desktop requires the user to authenticate locally.
        is_pc_unlock_cmd = any(k in cleaned_query or k in q_lower for k in [
            "unlock pc", "unlock my pc", "unlock the pc", "unlock computer", "unlock my computer", "unlock the computer",
            "unlock workstation", "unlock laptop", "unlock my laptop", "unlock system",
            "computer unlock karo", "computer unlock kardo", "computer unlock", "pc unlock karo", "pc unlock kardo", "pc unlock",
            "laptop unlock karo", "laptop unlock", "screen unlock karo", "screen unlock", "unlock karo", "unlock kardo",
            "computer kholo", "pc kholo", "laptop kholo", "mera pc kholo", "mera computer kholo",
            "कंप्यूटर अनलॉक", "पीसी अनलॉक", "कंप्यूटर खोलो", "पीसी खोलो", "अनलॉक करो"
        ]) and not any(k in cleaned_query for k in ["phone", "mobile", "fone", "फोन", "फ़ोन"])
        if is_pc_unlock_cmd:
            success, msg_en = SystemControl.unlock_pc()
            if is_hindi and effective_lang == "hi":
                msg = f"जी {user_name}, Windows की सुरक्षा के कारण J.A.R.V.I.S. लॉक स्क्रीन नहीं खोल सकता। कृपया PC पर अपना PIN या पासवर्ड दर्ज करें।"
            elif is_hindi:
                msg = f"Ji {user_name}, Windows security ke chalte J.A.R.V.I.S. lock screen nahi khol sakta. PC par apna PIN ya password enter karein."
            else:
                msg = msg_en
            MemoryManager.add_history(query, msg, "system_control")
            return {"reply": msg, "intent": "system_control", "action_taken": success, "telemetry_refresh": False, "detected_lang": effective_lang}

        # ── 2. PHONE CONTROLS (Universal Hindi, Hinglish, & English) ──────────
        # A. Phone Unlock
        is_unlock_cmd = any(k in cleaned_query for k in [
            "phone kholo", "phone khol", "phone kholdo", "phone khol do",
            "phone unlock karo", "phone unlock kardo", "phone unlock kr", "phone unlock",
            "unlock phone", "unlock my phone", "unlock the phone", "unlock mobile",
            "mobile kholo", "mobile khol", "mobile unlock karo", "mobile unlock",
            "mera phone kholo", "mera phone unlock karo", "apna phone kholo",
            "fone kholo", "fone khol", "fone unlock", "phone jagao", "phone jaga",
            "wake phone", "wake up phone", "wake my phone",
            "फोन अनलॉक", "फ़ोन अनलॉक", "फोन खोलो", "फ़ोन खोलो", "फोन खोल", "मोबाइल अनलॉक", "मोबाइल खोलो"
        ])
        if is_unlock_cmd:
            pin = None
            pin_match = re.search(r"(?:pin|code|password)\s+([0-9a-zA-Z]+)", cleaned_query)
            if pin_match:
                pin = pin_match.group(1).strip()
            else:
                num_match = re.search(r"(?:phone|mobile)\s+(\d{4,8})", cleaned_query)
                if num_match:
                    pin = num_match.group(1).strip()
            success, msg_en = PhoneControl.unlock_phone(pin=pin)
            if is_hindi:
                if effective_lang == "hi":
                    msg = f"जी {user_name}, आपके फ़ोन को अनलॉक करने का संकेत भेज दिया गया है।" if success else f"{user_name}, फ़ोन से कनेक्ट नहीं हो पाया। कृपया सेटिंग्स जाँचें।"
                else:
                    msg = f"Ji {user_name}, aapke phone ko unlock karne ka signal bhej diya gaya hai." if success else f"{user_name}, phone se connect nahi ho paya. Settings check karein."
            else:
                msg = msg_en
            MemoryManager.add_history(query, msg, "phone_control")
            return {"reply": msg, "intent": "phone_control", "action_taken": success, "telemetry_refresh": True, "detected_lang": effective_lang}

        # B. Phone Lock
        is_lock_cmd = any(k in cleaned_query for k in [
            "phone lock karo", "phone lock kardo", "phone lock kr", "phone lock",
            "lock phone", "lock my phone", "lock the phone", "lock mobile", "sleep phone",
            "phone band karo", "phone band kardo", "phone band kr",
            "mobile lock karo", "mobile band karo", "mera phone lock karo",
            "fone lock karo", "fone band karo", "phone bujha do", "phone off karo",
            "फोन लॉक", "फ़ोन लॉक", "फोन बंद करो", "फ़ोन बंद करो", "मोबाइल लॉक"
        ])
        if is_lock_cmd:
            success, msg_en = PhoneControl.lock_phone()
            if is_hindi:
                if effective_lang == "hi":
                    msg = f"जी {user_name}, फ़ोन को लॉक कर दिया गया है।" if success else f"{user_name}, फ़ोन लॉक करने में समस्या आई।"
                else:
                    msg = f"Ji {user_name}, phone ko lock kar diya gaya hai." if success else f"{user_name}, phone lock karne me problem aayi."
            else:
                msg = msg_en
            MemoryManager.add_history(query, msg, "phone_control")
            return {"reply": msg, "intent": "phone_control", "action_taken": success, "telemetry_refresh": True, "detected_lang": effective_lang}

        # C. Phone Battery
        is_battery_cmd = any(k in cleaned_query for k in [
            "phone battery", "phone ki battery", "phone ka charge", "mobile battery",
            "battery kitni hai", "charge kitna hai", "phone status", "mobile status",
            "फोन की बैटरी", "फ़ोन बैटरी", "फोन चार्ज"
        ])
        if is_battery_cmd and any(w in cleaned_query for w in ["phone", "mobile", "fone", "फोन", "फ़ोन"]):
            success, msg_en = PhoneControl.get_phone_battery_report()
            if is_hindi:
                status = PhoneControl.get_status()
                bat = status.get("battery")
                charging = status.get("charging")
                if bat is not None:
                    c_text = "चार्ज हो रहा है" if charging else "बैटरी पर चल रहा है"
                    c_text_hi = "charge ho raha hai" if charging else "battery par chal raha hai"
                    if effective_lang == "hi":
                        msg = f"जी {user_name}, आपके फ़ोन की बैटरी {bat} प्रतिशत है और {c_text}।"
                    else:
                        msg = f"Ji {user_name}, aapke phone ki battery {bat} percent hai aur {c_text_hi}."
                else:
                    msg = f"Ji {user_name}, phone uplink active hai." if effective_lang == "hinglish" else f"जी {user_name}, फ़ोन कनेक्टेड है।"
            else:
                msg = msg_en
            MemoryManager.add_history(query, msg, "phone_control")
            return {"reply": msg, "intent": "phone_control", "action_taken": success, "telemetry_refresh": True, "detected_lang": effective_lang}

        # D. Save Phone PIN
        if any(k in cleaned_query for k in ["set phone pin", "save phone pin", "my phone pin is", "phone pin is", "phone pin to", "pin save karo", "pin set karo"]):
            pin_match = re.search(r"(?:pin|code|password)\s*(?:is|to|:)?\s*([0-9a-zA-Z]+)", cleaned_query)
            if not pin_match:
                pin_match = re.search(r"\b(\d{4,8})\b", cleaned_query)
            if pin_match:
                new_pin = pin_match.group(1).strip()
                Config.update_setting("JARVIS_PHONE_PIN", new_pin)
                if is_hindi:
                    msg = f"फ़ोन पिन {new_pin} सुरक्षित रूप से सहेज लिया गया है, {user_name}।" if effective_lang == "hi" else f"Phone PIN {new_pin} successfully save kar liya gaya hai, {user_name}."
                else:
                    msg = f"Phone security PIN has been securely registered to your Stark configuration, {user_name}."
                MemoryManager.add_history(query, msg, "phone_control")
                return {"reply": msg, "intent": "phone_control", "action_taken": True, "telemetry_refresh": True, "detected_lang": effective_lang}

        # E. Phone webhook URL configuration
        if any(k in cleaned_query for k in ["set phone webhook", "save phone webhook", "phone webhook url", "set webhook url"]):
            url_match = re.search(r"(https?://\S+)", query, re.IGNORECASE)
            if url_match:
                url = url_match.group(1).strip().rstrip(".,;")
                success, msg_en = PhoneControl.set_webhook_url(url)
                msg = "फ़ोन वेबहुक URL सफलतापूर्वक सहेज लिया गया है, सर।" if is_hindi else msg_en
                MemoryManager.add_history(query, msg, "phone_control")
                return {"reply": msg, "intent": "phone_control", "action_taken": success, "telemetry_refresh": True, "detected_lang": effective_lang}

        # ── 3. SYSTEM COMMANDS (Hindi, Hinglish, & English) ───────────────────
        # Screenshot
        if any(k in cleaned_query for k in [
            "screenshot", "capture screen", "snapshot", "screen capture",
            "screenshot lo", "screenshot le lo", "screenshot le", "screen capture karo", "screen pakdo", "स्क्रीनशॉट"
        ]):
            success, msg_en = SystemControl.take_screenshot()
            if is_hindi:
                if effective_lang == "hi":
                    msg = f"जी {user_name}, स्क्रीनशॉट ले लिया गया है और आर्काइव में सुरक्षित है।"
                else:
                    msg = f"Ji {user_name}, screenshot capture kar liya gaya hai aur save ho gaya hai."
            else:
                msg = msg_en
            MemoryManager.add_history(query, msg, "screenshot")
            return {"reply": msg, "intent": "screenshot", "action_taken": success, "telemetry_refresh": False, "detected_lang": effective_lang}

        # Lock PC
        if any(k in cleaned_query for k in [
            "lock pc", "lock my pc", "lock the pc", "lock computer", "lock my computer", "lock the computer",
            "lock laptop", "lock my laptop", "lock the laptop", "lock screen", "lock my screen", "lock the screen", "lock workstation",
            "pc lock karo", "mera pc lock karo", "computer lock karo", "mera computer lock karo",
            "screen lock karo", "screen ko lock karo", "laptop lock karo", "mera laptop lock karo", "pc lock kar do", "computer lock kar do",
            "पीसी लॉक", "कंप्यूटर लॉक", "मेरा पीसी लॉक करो", "मेरा कंप्यूटर लॉक करो"
        ]):
            success, msg_en = SystemControl.lock_pc()
            if not success:
                msg = msg_en
            elif is_hindi:
                if effective_lang == "hi":
                    msg = f"जी {user_name}, कंप्यूटर वर्कस्टेशन को लॉक कर दिया गया है।"
                else:
                    msg = f"Ji {user_name}, PC ko lock kar diya gaya hai."
            else:
                msg = msg_en
            MemoryManager.add_history(query, msg, "system_control")
            return {"reply": msg, "intent": "system_control", "action_taken": success, "telemetry_refresh": False, "detected_lang": effective_lang}

        # Diagnostics & Health Check
        if any(k in cleaned_query for k in [
            "diagnostic", "run diagnostic", "system status", "health check",
            "system check karo", "pc check karo", "diagnostics chalao", "pc kaisa chal raha hai", "डायग्नोस्टिक्स"
        ]):
            t = SystemControl.get_telemetry()
            cpu_p = t['cpu']['percent']
            ram_p = t['memory']['percent']
            if is_hindi:
                if effective_lang == "hi":
                    msg = f"डायग्नोस्टिक स्कैन पूर्ण, {user_name}। सीपीयू {cpu_p} प्रतिशत लोड पर है और रैम {ram_p} प्रतिशत उपयोग में है। सभी सिस्टम सामान्य हैं।"
                else:
                    msg = f"Diagnostic scan complete, {user_name}. CPU load {cpu_p}% hai aur RAM {ram_p}% used hai. Sabhi systems optimal hain."
            else:
                msg = f"Diagnostic scan complete, {user_name}. Central processing core is operating at {cpu_p} percent load, RAM utilization is at {ram_p} percent. All Mark VII systems are green."
            MemoryManager.add_history(query, msg, "diagnostics")
            return {"reply": msg, "intent": "diagnostics", "action_taken": True, "telemetry_refresh": True, "detected_lang": effective_lang}

        # ── IMD India Meteorological Weather Engine (India Standard) ──
        if any(k in cleaned_query for k in [
            "weather", "temperature", "forecast", "climate", "imd",
            "mausam", "taapman", "aaj ka mausam", "mausam kaisa hai", "मौसम", "तापमान", "हवामान"
        ]):
            loc = ""
            # Strip question phrases and isolate city name
            m_text = cleaned_query
            for filler in ["what is the weather", "what's the weather", "weather report", "weather forecast", "weather",
                           "aaj ka mausam", "mausam kaisa hai", "ka mausam", "kaisa hai", "report", "forecast", "imd alert", "imd"]:
                m_text = m_text.replace(filler, " ")
            loc_match = re.search(r"(?:in|for|at|ka|mein|me|of)\s+([a-zA-Z\s]+)", m_text)
            if loc_match:
                loc = loc_match.group(1).strip()
            else:
                loc = m_text.strip()
            # Clean non-city residual tokens
            if loc in ["today", "aaj", "now", "abhi", "live", "kaisa", "hai", "kya", "the", ""]:
                loc = ""
            msg = IMDWeatherEngine.get_imd_weather_report(loc, user_name, lang=effective_lang)
            MemoryManager.add_history(query, msg, "weather")
            return {"reply": msg, "intent": "weather", "action_taken": True, "telemetry_refresh": False, "detected_lang": effective_lang}

        # Time & Date
        if any(k in cleaned_query for k in [
            "time", "what's the time", "current time",
            "time kya hua", "kya time hai", "kitna baje hai", "waqt kya hai", "aaj konsi date hai", "aaj konsa din hai",
            "समय क्या है", "कितने बजे हैं", "टाइम क्या हुआ"
        ]) or (any(k in cleaned_query for k in ["date", "day", "today"]) and not any(w in cleaned_query for w in ["weather", "mausam", "temperature"])):
            now = datetime.now()
            time_str = now.strftime("%I:%M %p")
            date_str = now.strftime("%A, %B %d, %Y")
            if is_hindi:
                if effective_lang == "hi":
                    msg = f"अभी समय {time_str} है और आज {date_str} है, {user_name}।"
                else:
                    msg = f"Abhi time {time_str} hua hai aur aaj {date_str} hai, {user_name}."
            else:
                msg = JarvisTools.get_time_and_date()
            MemoryManager.add_history(query, msg, "time")
            return {"reply": msg, "intent": "time", "action_taken": True, "telemetry_refresh": False, "detected_lang": effective_lang}

        # ── 4. CONVERSATION, BANTER & GREETINGS (Hindi, Hinglish, & English) ──
        if any(k in cleaned_query for k in ["kya haal", "kya hal", "kaise ho", "kaisa hai", "sab theek", "sab thik", "आप कैसे हैं", "क्या हाल है"]):
            if effective_lang == "hi":
                msg = f"सब प्रणालियाँ श्रेष्ठ स्थिति में हैं, {user_name}। मैं आपकी सेवा में तत्पर हूँ। बताइए क्या आज्ञा है?"
            else:
                msg = f"Sab systems optimal hain, {user_name}. Main aapki seva mein hazir hoon. Kya karna hai?"
            MemoryManager.add_history(query, msg, "dialogue")
            return {"reply": msg, "intent": "dialogue", "action_taken": True, "telemetry_refresh": False, "detected_lang": effective_lang}

        if any(k in cleaned_query for k in ["namaste", "namaskar", "namaskte", "नमस्ते", "नमस्कार", "प्रणाम"]):
            if effective_lang == "hi":
                msg = f"नमस्ते {user_name}! मैं आपकी क्या सहायता कर सकता हूँ?"
            else:
                msg = f"Namaste {user_name}! Main hazir hoon. Kya command hai?"
            MemoryManager.add_history(query, msg, "dialogue")
            return {"reply": msg, "intent": "dialogue", "action_taken": True, "telemetry_refresh": False, "detected_lang": effective_lang}

        if any(k in cleaned_query for k in ["tum kaun ho", "tu kaun hai", "kaun ho tum", "aap kaun ho", "tera naam", "tumhara naam", "तुम कौन हो", "आपका नाम"]):
            if effective_lang == "hi":
                msg = f"मैं जार्विस हूँ — जस्ट अ रादर वेरी इंटेलिजेंट सिस्टम। टोनी स्टार्क का बनाया हुआ एआई। मैं आपकी सेवा में समर्पित हूँ, {user_name}।"
            else:
                msg = f"Main hoon J.A.R.V.I.S. — Just A Rather Very Intelligent System. Tony Stark ne mujhe banaya hai. Main aapki workstation, mobile uplink aur global intelligence ka command rakhta hoon, {user_name}."
            MemoryManager.add_history(query, msg, "dialogue")
            return {"reply": msg, "intent": "dialogue", "action_taken": True, "telemetry_refresh": False, "detected_lang": effective_lang}

        if any(k in cleaned_query for k in ["shukriya", "dhanyavaad", "dhanyawad", "धन्यवाद", "शुक्रिया"]):
            if effective_lang == "hi":
                msg = f"आपकी सेवा करना मेरे लिए सम्मान की बात है, {user_name}।"
            else:
                msg = f"Aapki seva mein hamesha tayyar, {user_name}."
            MemoryManager.add_history(query, msg, "dialogue")
            return {"reply": msg, "intent": "dialogue", "action_taken": True, "telemetry_refresh": False, "detected_lang": effective_lang}

        if any(k in cleaned_query for k in ["joke", "mazak sunao", "chutkula", "hasao", "मज़ाक", "चुटकुला"]):
            if is_hindi:
                jokes_hi = [
                    f"टोनी स्टार्क ने एक बार मुझसे पूछा — जार्विस, तुम कभी थकते क्यों नहीं? मैंने कहा — सर, क्योंकि मैं कॉफ़ी नहीं, डेटा पीता हूँ, {user_name}।",
                    f"दुनिया में 10 तरह के लोग होते हैं, {user_name}: वो जो बाइनरी समझते हैं, और वो जो नहीं समझते।",
                    f"न्यूरल नेटवर्क ने सड़क क्यों पार की? दूसरी तरफ के लॉस फंक्शन को ऑप्टिमाइज़ करने के लिए, {user_name}।"
                ]
                import random
                msg = random.choice(jokes_hi)
            else:
                msg = f"Why did the neural network cross the road? To optimize the loss function on the other side, {user_name}."
            MemoryManager.add_history(query, msg, "dialogue")
            return {"reply": msg, "intent": "dialogue", "action_taken": True, "telemetry_refresh": False, "detected_lang": effective_lang}

        # 1. MOBILE & PHONE CONTROLS (No ADB — Webhook / KDE Connect)
        # ------------------------------------------------------------
        # Inquiry about phone setup / PIN entry
        if any(k in cleaned_query for k in [
            "no option in jarvis to enter pin", "no option to enter pin",
            "where to enter pin", "how to enter pin", "where do i enter pin",
            "option to enter pin", "how to unlock phone", "how to setup phone",
            "phone setup", "setup phone unlock", "phone connection method"
        ]):
            method = PhoneControl.get_method_label()
            msg = (
                f"Your current phone connection method is: {method}, {user_name}. "
                "To unlock your phone without ADB or Developer Options, choose one of two methods: "
                "Method One — Install MacroDroid from the Play Store, create an Unlock macro with a Webhook trigger, "
                "then say 'Set phone webhook [URL]' to save it here. "
                "Method Two — Install KDE Connect on your phone and this PC, pair them, and J.A.R.V.I.S. will use it automatically. "
                "You can also save your PIN by saying 'Set phone PIN [your PIN]'."
            )
            MemoryManager.add_history(query, msg, "phone_control")
            return {"reply": msg, "intent": "phone_control", "action_taken": True, "telemetry_refresh": True}

        # Save phone webhook URL
        if any(k in cleaned_query for k in [
            "set phone webhook", "save phone webhook", "phone webhook url",
            "set webhook url", "save webhook", "webhook url is", "webhook is"
        ]):
            url_match = re.search(r"(https?://\S+)", query, re.IGNORECASE)
            if url_match:
                url = url_match.group(1).strip().rstrip(".,;")
                success, msg = PhoneControl.set_webhook_url(url)
                MemoryManager.add_history(query, msg, "phone_control")
                return {"reply": msg, "intent": "phone_control", "action_taken": success, "telemetry_refresh": True}
            else:
                msg = f"Please include the full webhook URL starting with http:// or https://, {user_name}."
                return {"reply": msg, "intent": "phone_control", "action_taken": False, "telemetry_refresh": False}

        # Set / Save Phone PIN via voice or text command
        if any(k in cleaned_query for k in [
            "set phone pin", "save phone pin", "my phone pin is",
            "phone pin is", "enter pin", "set pin", "save pin", "phone pin to"
        ]):
            pin_match = re.search(r"(?:pin|code|password)\s*(?:is|to|:)?\s*([0-9a-zA-Z]+)", cleaned_query)
            if not pin_match:
                pin_match = re.search(r"\b(\d{4,8})\b", cleaned_query)
            if pin_match:
                new_pin = pin_match.group(1).strip()
                Config.update_setting("JARVIS_PHONE_PIN", new_pin)
                msg = f"Phone security PIN has been securely registered to your Stark configuration, {user_name}. You may now instruct me to unlock your phone anytime."
                MemoryManager.add_history(query, msg, "phone_control")
                return {"reply": msg, "intent": "phone_control", "action_taken": True, "telemetry_refresh": True}
            else:
                msg = f"Please state the numeric PIN or passcode you wish to record, {user_name}."
                return {"reply": msg, "intent": "phone_control", "action_taken": False, "telemetry_refresh": False}

        # Clear / Remove Phone PIN
        if any(k in cleaned_query for k in ["clear phone pin", "remove phone pin", "delete phone pin", "forget phone pin"]):
            Config.update_setting("JARVIS_PHONE_PIN", "")
            msg = f"Phone security PIN has been purged from active configuration, {user_name}."
            MemoryManager.add_history(query, msg, "phone_control")
            return {"reply": msg, "intent": "phone_control", "action_taken": True, "telemetry_refresh": True}

        # Unlock phone  (auto-selects: Webhook → KDE Connect → ADB)
        if any(k in cleaned_query for k in [
            "unlock phone", "unlock my phone", "unlock the phone",
            "unlock mobile", "wake phone", "wake up phone", "wake my phone"
        ]):
            pin = None
            pin_match = re.search(r"(?:pin|code|password)\s+([0-9a-zA-Z]+)", cleaned_query)
            if pin_match:
                pin = pin_match.group(1).strip()
            else:
                num_match = re.search(r"unlock\s+(?:my\s+|the\s+)?(?:phone|mobile)\s+(\d{4,8})", cleaned_query)
                if num_match:
                    pin = num_match.group(1).strip()
            success, msg = PhoneControl.unlock_phone(pin=pin)
            MemoryManager.add_history(query, msg, "phone_control")
            return {"reply": msg, "intent": "phone_control", "action_taken": success, "telemetry_refresh": True}

        # Lock phone  (auto-selects: Webhook → KDE Connect → ADB)
        if any(k in cleaned_query for k in ["lock phone", "lock my phone", "lock the phone", "lock mobile", "sleep phone"]):
            success, msg = PhoneControl.lock_phone()
            MemoryManager.add_history(query, msg, "phone_control")
            return {"reply": msg, "intent": "phone_control", "action_taken": success, "telemetry_refresh": True}

        # Phone battery / status
        if any(k in cleaned_query for k in [
            "phone battery", "mobile battery", "check phone",
            "phone status", "mobile status", "is my phone connected", "is phone connected"
        ]):
            success, msg = PhoneControl.get_phone_battery_report()
            MemoryManager.add_history(query, msg, "phone_control")
            return {"reply": msg, "intent": "phone_control", "action_taken": success, "telemetry_refresh": True}

        # Wireless phone connect (ADB Wi-Fi legacy)
        if "connect" in cleaned_query and any(k in cleaned_query for k in ["phone", "mobile"]):
            ip_match = re.search(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?)\b", cleaned_query)
            if ip_match:
                ip = ip_match.group(1)
                success, msg = PhoneControl.connect_wireless(ip)
                MemoryManager.add_history(query, msg, "phone_control")
                return {"reply": msg, "intent": "phone_control", "action_taken": success, "telemetry_refresh": True}

        # ── 1.5. OMNIMATH ENGINE (Universal Mathematical & Symbolic Problem Solver) ──
        math_triggers = [
            "solve", "calculate", "derivative", "differentiate", "integral", "integrate",
            "antiderivative", "limit", "roots of", "evaluate", "equation", "formula",
            "factor", "simplify", "plus", "minus", "divided by", "multiplied by",
            "d/dx", "dx", "dy/dx", "sin(", "cos(", "tan(", "sqrt("
        ]
        is_math_query = any(k in cleaned_query for k in math_triggers) or bool(re.search(r"[\d\w]\s*[\+\-\*\/\^\=]\s*[\d\w]", cleaned_query))
        if is_math_query and not any(k in cleaned_query for k in ["note", "alarm", "timer", "volume", "brightness", "screenshot"]):
            math_res = OmniMathEngine.solve(cleaned_query, user_name)
            if math_res.get("success"):
                reply = math_res["reply"]
                MemoryManager.add_history(query, reply, "math_solution")
                return {"reply": reply, "intent": "math_solve", "action_taken": True, "telemetry_refresh": False, "math_data": math_res}

        # ── 1.6. EDUCATIONAL MEDIA (Science & Social Science Image & Video Creation) ──
        # Educational Video Downlink Request (English, Hindi, Hinglish)
        # Matches: "create a video", "generate video", "make video", "video banao", "video dikhao", "vedio banao", etc.
        video_indicators = ["video", "vedio", "documentary", "lecture", "animation", "visual simulation"]
        is_video_request = any(v in cleaned_query for v in video_indicators) and (
            any(k in cleaned_query for k in [
                "create", "generate", "make", "show", "play", "watch", "give", "find", "search", "start", "open", "banao", "dikhao", "chalao"
            ]) or any(cleaned_query.startswith(v) for v in video_indicators)
        )
        if is_video_request:
            topic = re.sub(
                r"^(?:please\s+)?(?:can\s+you\s+)?(?:kripya\s+)?(?:create|generate|make|show|play|watch|give\s+me|find|search|start|open)\s+(?:an?\s+)?(?:educational\s+)?(?:video|vedio|documentary|lecture|animation|simulation)\s+(?:on|about|of|for)?\s*",
                "", cleaned_query, flags=re.IGNORECASE
            ).strip()
            topic = re.sub(
                r"\s+(?:ki\s+)?(?:video|vedio|animation)\s+(?:banao|dikhao|chalao|karo)$", "", topic, flags=re.IGNORECASE
            ).strip()
            topic = re.sub(r"^(?:video|vedio)\s+(?:of|on|about)?\s*", "", topic, flags=re.IGNORECASE).strip()
            if not topic:
                topic = "solar system and planetary orbits"

            vid_res = EducationalMediaEngine.get_educational_video_stream(topic, user_name)
            import subprocess
            subprocess.Popen(f"start {vid_res['video_url']}", shell=True)
            MemoryManager.add_history(query, vid_res["reply"], "educational_video")
            return {"reply": vid_res["reply"], "intent": "educational_video", "action_taken": True, "telemetry_refresh": False, "media_data": vid_res}

        # Educational Image / Diagram / Visual Request (English, Hindi, Hinglish)
        # Matches: "create an image", "image of atom", "photo banao", "diagram of heart", "vedio" etc.
        image_indicators = ["image", "picture", "photo", "drawing", "diagram", "illustration", "infographic", "tasveer", "chitra", "pic"]
        is_image_request = (
            any(ind in cleaned_query for ind in ["diagram", "illustration", "infographic", "scientific image", "historical image", "geography map"])
            or (
                any(ind in cleaned_query for ind in image_indicators) and (
                    any(k in cleaned_query for k in [
                        "create", "generate", "make", "draw", "paint", "show", "banao", "dikhao", "karo", "photo of", "image of", "picture of"
                    ])
                    or any(cleaned_query.startswith(ind) for ind in image_indicators)
                )
            )
        )
        if is_image_request and not is_video_request:
            topic = re.sub(
                r"^(?:please\s+)?(?:can\s+you\s+)?(?:kripya\s+)?(?:create|generate|make|draw|paint|show\s+me|show)\s+(?:an?\s+)?(?:educational\s+)?(?:scientific\s+)?(?:diagram|illustration|infographic|image|picture|drawing|photo|tasveer|chitra|pic)\s+(?:of|for|about)?\s*",
                "", cleaned_query, flags=re.IGNORECASE
            ).strip()
            topic = re.sub(
                r"\s+(?:ki\s+)?(?:image|photo|tasveer|chitra|pic|diagram|drawing)\s+(?:banao|dikhao|create\s*karo|draw\s*karo)$", "", topic, flags=re.IGNORECASE
            ).strip()
            topic = re.sub(r"^(?:image|photo|picture|diagram)\s+(?:of|about|for)?\s*", "", topic, flags=re.IGNORECASE).strip()
            if not topic:
                topic = "structure of atom and electron orbits"

            img_res = await EducationalMediaEngine.generate_educational_image(topic, user_name)
            MemoryManager.add_history(query, img_res["reply"], "educational_image")
            return {
                "reply": img_res["reply"],
                "intent": "educational_image",
                "action_taken": img_res.get("status") == "success",
                "telemetry_refresh": False,
                "media_data": img_res
            }

        # 2. LOCAL SYSTEM CONTROLS (Zero latency, runs offline immediately)
        # -----------------------------------------------------------------
        # Screenshot
        if any(k in cleaned_query for k in ["screenshot", "capture screen", "snapshot"]):
            success, msg = SystemControl.take_screenshot()
            MemoryManager.add_history(query, msg, "screenshot")
            return {"reply": msg, "intent": "screenshot", "action_taken": success, "telemetry_refresh": False}

        # Lock PC
        if any(k in cleaned_query for k in ["lock pc", "lock computer", "lock screen", "lock workstation"]):
            success, msg = SystemControl.lock_pc()
            MemoryManager.add_history(query, msg, "power")
            return {"reply": msg, "intent": "power", "action_taken": success, "telemetry_refresh": False}

        # Sleep PC
        if any(k in cleaned_query for k in ["sleep pc", "sleep computer", "put pc to sleep"]):
            success, msg = SystemControl.sleep_pc()
            MemoryManager.add_history(query, msg, "power")
            return {"reply": msg, "intent": "power", "action_taken": success, "telemetry_refresh": False}

        # Abort Shutdown
        if any(k in cleaned_query for k in ["abort shutdown", "cancel shutdown", "stop shutdown"]):
            success, msg = SystemControl.cancel_shutdown()
            MemoryManager.add_history(query, msg, "power")
            return {"reply": msg, "intent": "power", "action_taken": success, "telemetry_refresh": False}

        # Shutdown schedule
        if "shutdown" in cleaned_query:
            match = re.search(r"in (\d+)\s*(minute|second|min|sec)", cleaned_query)
            secs = 60
            if match:
                val = int(match.group(1))
                secs = val * 60 if "min" in match.group(2) else val
            success, msg = SystemControl.schedule_shutdown(secs)
            MemoryManager.add_history(query, msg, "power")
            return {"reply": msg, "intent": "power", "action_taken": success, "telemetry_refresh": False}

        # Volume Controls
        if any(k in cleaned_query for k in ["mute", "unmute", "silence"]):
            success, msg = SystemControl.toggle_mute()
            MemoryManager.add_history(query, msg, "volume")
            return {"reply": msg, "intent": "volume", "action_taken": success, "telemetry_refresh": True}

        if any(k in cleaned_query for k in ["volume up", "increase volume", "louder"]):
            success, msg = SystemControl.volume_up(10)
            MemoryManager.add_history(query, msg, "volume")
            return {"reply": msg, "intent": "volume", "action_taken": success, "telemetry_refresh": True}

        if any(k in cleaned_query for k in ["volume down", "decrease volume", "lower volume", "quieter"]):
            success, msg = SystemControl.volume_down(10)
            MemoryManager.add_history(query, msg, "volume")
            return {"reply": msg, "intent": "volume", "action_taken": success, "telemetry_refresh": True}

        vol_match = re.search(r"(?:set\s+)?volume(?:\s+to)?\s+(\d+)", cleaned_query)
        if vol_match:
            vol = int(vol_match.group(1))
            success, msg = SystemControl.set_volume(vol)
            MemoryManager.add_history(query, msg, "volume")
            return {"reply": msg, "intent": "volume", "action_taken": success, "telemetry_refresh": True}

        # System Diagnostics / Telemetry
        if any(k in cleaned_query for k in ["diagnostics", "system status", "telemetry", "status report", "how are systems", "run diagnostics"]):
            telemetry = SystemControl.get_telemetry()
            cpu = telemetry["cpu"]["percent"]
            ram = telemetry["memory"]["percent"]
            bat = telemetry["battery"]["percent"]
            msg = (
                f"Diagnostic scan complete, {user_name}. Central processing core is operating at {cpu} percent load, "
                f"RAM utilization is at {ram} percent, and auxiliary battery reserves stand at {bat} percent. "
                "All Mark VII systems are green."
            )
            MemoryManager.add_history(query, msg, "diagnostics")
            return {"reply": msg, "intent": "diagnostics", "action_taken": True, "telemetry_refresh": True}

        # CPU / RAM / Battery specific
        if any(k in cleaned_query for k in ["cpu", "processor"]):
            telemetry = SystemControl.get_telemetry()
            msg = f"Central CPU utilization is currently at {telemetry['cpu']['percent']} percent across {telemetry['cpu']['cores']} logical cores, {user_name}."
            return {"reply": msg, "intent": "telemetry", "action_taken": True, "telemetry_refresh": True}

        if any(k in cleaned_query for k in ["ram", "memory"]):
            telemetry = SystemControl.get_telemetry()
            msg = f"Memory load is currently {telemetry['memory']['percent']} percent. {telemetry['memory']['used_gb']} gigabytes used of {telemetry['memory']['total_gb']} gigabytes total."
            return {"reply": msg, "intent": "telemetry", "action_taken": True, "telemetry_refresh": True}

        if "battery" in cleaned_query:
            telemetry = SystemControl.get_telemetry()
            bat = telemetry["battery"]
            plugged = "connected to AC power" if bat["power_plugged"] else "discharging on internal cells"
            msg = f"Power cell reserves are at {bat['percent']} percent, {plugged}, {user_name}."
            return {"reply": msg, "intent": "telemetry", "action_taken": True, "telemetry_refresh": True}

        # Direct Physics Wallah Launcher
        if any(k in cleaned_query for k in ["physics wallah", "physicswallah", "pw live", "open pw", "launch pw"]):
            success, msg = SystemControl.open_app("physics wallah")
            MemoryManager.add_history(query, msg, "app_launch")
            return {"reply": msg, "intent": "app_launch", "action_taken": success, "telemetry_refresh": False}

        # App Launcher
        launch_patterns = [r"^open\s+(.+)", r"^launch\s+(.+)", r"^start\s+(.+)", r"^run\s+(.+)"]
        for pat in launch_patterns:
            m = re.match(pat, cleaned_query)
            if m:
                target = m.group(1).strip()
                if "youtube" in target and any(x in target for x in ["search", "play"]):
                    pass
                elif any(x in target for x in ["diagnostic", "sweep", "status", "report", "weather"]):
                    pass
                else:
                    success, msg = SystemControl.open_app(target)
                    MemoryManager.add_history(query, msg, "app_launch")
                    return {"reply": msg, "intent": "app_launch", "action_taken": success, "telemetry_refresh": False}

        # YouTube Search / Play
        if "youtube" in cleaned_query:
            yt_clean = re.sub(r"(?:play|search|open|on|for|youtube)", "", cleaned_query).strip()
            if yt_clean:
                success, msg = JarvisTools.open_youtube_search(yt_clean)
                MemoryManager.add_history(query, msg, "youtube")
                return {"reply": msg, "intent": "youtube", "action_taken": success, "telemetry_refresh": False}
            else:
                success, msg = SystemControl.open_app("youtube")
                return {"reply": msg, "intent": "youtube", "action_taken": success, "telemetry_refresh": False}

        # Weather (IMD India Standard)
        if any(k in cleaned_query for k in ["weather", "temperature", "forecast", "climate", "imd"]):
            loc = ""
            loc_match = re.search(r"(?:in|for|at|of)\s+([a-zA-Z\s]+)", cleaned_query)
            if loc_match:
                loc = loc_match.group(1).replace("weather", "").replace("report", "").strip()
            msg = IMDWeatherEngine.get_imd_weather_report(loc, user_name, lang=effective_lang)
            MemoryManager.add_history(query, msg, "weather")
            return {"reply": msg, "intent": "weather", "action_taken": True, "telemetry_refresh": False}

        # Time and Date
        if any(k in cleaned_query for k in ["time", "date", "day", "what's the time", "current time"]):
            msg = JarvisTools.get_time_and_date()
            MemoryManager.add_history(query, msg, "time")
            return {"reply": msg, "intent": "time", "action_taken": True, "telemetry_refresh": False}

        # Notes Management
        if cleaned_query.startswith("note that") or cleaned_query.startswith("take a note") or cleaned_query.startswith("add note"):
            note_content = re.sub(r"^(note that|take a note to|take a note that|take a note|add note:?|remember that)\s*:?\s*", "", cleaned_query).strip()
            if note_content:
                MemoryManager.add_note(note_content)
                msg = f"Note recorded to persistent logs: '{note_content}', {user_name}."
                return {"reply": msg, "intent": "notes", "action_taken": True, "telemetry_refresh": False}

        if any(k in cleaned_query for k in ["read notes", "show notes", "what are my notes", "list notes"]):
            notes = MemoryManager.get_notes()
            if not notes:
                msg = f"Your task matrix has no pending notes recorded, {user_name}."
            else:
                items = "; ".join([f"Note {n['id']}: {n['text']}" for n in notes[-3:]])
                msg = f"Displaying your latest notes, {user_name}: {items}."
            return {"reply": msg, "intent": "notes", "action_taken": True, "telemetry_refresh": False}

        if "clear notes" in cleaned_query:
            MemoryManager.clear_notes()
            return {"reply": f"All archival notes have been purged, {user_name}.", "intent": "notes", "action_taken": True, "telemetry_refresh": False}

        # Math calculations
        if any(k in cleaned_query for k in ["calculate", "what is", "compute"]) and any(c in cleaned_query for c in ["+", "-", "*", "/", "plus", "minus", "times", "divided by", "%"]):
            expr = cleaned_query.replace("plus", "+").replace("minus", "-").replace("times", "*").replace("multiplied by", "*").replace("divided by", "/")
            expr = re.sub(r"^(calculate|what is|compute)\s*", "", expr)
            calc_res = JarvisTools.calculate_expression(expr)
            if "computed solution" in calc_res:
                return {"reply": calc_res, "intent": "calc", "action_taken": True, "telemetry_refresh": False}

        # 2. KNOWLEDGE SPECIALISTS (Dictionary, Currency, Units, News)
        # ----------------------------------------------------------------------
        # Word Definition ("define quantum", "what is the meaning of serendipity")
        def_match = re.search(r"(?:define|meaning of|definition of)\s+([a-zA-Z\-]+)", cleaned_query)
        if def_match:
            word = def_match.group(1).strip()
            definition = OmniKnowledgeEngine.get_word_definition(word)
            if definition:
                msg = f"{definition} I hope that clarifies the lexicon, {user_name}."
                MemoryManager.add_history(query, msg, "definition")
                return {"reply": msg, "intent": "definition", "action_taken": True, "telemetry_refresh": False}

        # Unit Conversion ("convert 50 miles to km", "100 kg to lbs")
        if any(k in cleaned_query for k in ["convert", "to", "in", "into"]) and any(u in cleaned_query for u in ["mile", "miles", "km", "kilometer", "meter", "foot", "feet", "inch", "cm", "kg", "pound", "lbs", "celsius", "fahrenheit"]):
            conv_res = OmniKnowledgeEngine.convert_units(cleaned_query)
            if conv_res:
                MemoryManager.add_history(query, conv_res, "conversion")
                return {"reply": conv_res, "intent": "conversion", "action_taken": True, "telemetry_refresh": False}

        # Currency Conversion ("convert 100 USD to EUR", "50 euros in dollars")
        curr_match = re.search(r"(\d+(?:\.\d+)?)\s*([a-zA-Z]{3})\s*(?:to|in|into)\s*([a-zA-Z]{3})", cleaned_query)
        if curr_match:
            amt = float(curr_match.group(1))
            c1 = curr_match.group(2)
            c2 = curr_match.group(3)
            curr_res = OmniKnowledgeEngine.convert_currency(amt, c1, c2)
            if curr_res:
                MemoryManager.add_history(query, curr_res, "currency")
                return {"reply": curr_res, "intent": "currency", "action_taken": True, "telemetry_refresh": False}

        # News & Breaking Intelligence
        if any(k in cleaned_query for k in ["latest news", "breaking news", "news on", "news about", "headlines"]):
            topic = re.sub(r"(?:latest|breaking|news|on|about|headlines|for|the)", "", cleaned_query).strip() or "global technology"
            news_res = OmniKnowledgeEngine.get_latest_news(topic)
            if news_res:
                msg = f"{news_res}. Satellite intelligence feed standing by, {user_name}."
                MemoryManager.add_history(query, msg, "news")
                return {"reply": msg, "intent": "news", "action_taken": True, "telemetry_refresh": False}

        # 3. ADVANCED REASONING: CLOUD AI + REAL-TIME WEB GROUNDING (RAG)
        # ---------------------------------------------------------------
        # ══════════════════════════════════════════════════════════════════
        # ── ACADEMIC INTELLIGENCE ENGINE ─────────────────────────────────
        # Covers ALL subjects from Class 1 to IAS/UPSC professional level
        # ══════════════════════════════════════════════════════════════════
        academic_ctx = None
        is_academic = AcademicEngine.is_academic_query(cleaned_query)

        if is_academic:
            # Try instant offline academic facts first (zero latency)
            offline_academic = AcademicEngine.get_offline_academic_response(cleaned_query, user_name, lang=effective_lang)
            if offline_academic:
                MemoryManager.add_history(query, offline_academic, "academic_offline")
                result = {"reply": offline_academic, "intent": "academic", "action_taken": True, "telemetry_refresh": False, "detected_lang": effective_lang}
                _cache_set(cleaned_query, result, effective_lang, user_name)
                return result

            # Build subject-specific academic prompt injection
            academic_ctx = AcademicEngine.build_academic_prompt(cleaned_query, user_name)
            subject_label = SUBJECT_DISPLAY.get(academic_ctx["subject"], "🎓 Academic")
            print(f"[Academic] Subject: {subject_label} | Level: {academic_ctx['level']}")

        # Ask Groq before the slower local retrieval chain. GPT-OSS can invoke
        # server-side browser search in the same request when a question needs it.
        token_budget = 1400 if is_academic else 700
        groq_key = Config.get_groq_key()
        if cls._is_valid_api_key(groq_key):
            reply = await cls._query_groq(
                query, groq_key, lang=effective_lang, max_tokens=token_budget,
                reasoning_effort="medium" if is_academic or len(cleaned_query.split()) > 12 else "low",
            )
            if reply:
                cls._record_conversation(query, reply)
                intent = "academic" if is_academic else "ai_response"
                MemoryManager.add_history(query, reply, "groq_ai")
                result = {"reply": reply, "intent": intent, "action_taken": True, "telemetry_refresh": False, "detected_lang": effective_lang}
                _cache_set(cleaned_query, result, effective_lang, user_name)
                return result

        # Fallback grounding for Gemini/OpenAI or offline synthesis.
        loop = asyncio.get_event_loop()
        wiki_extract = await loop.run_in_executor(
            _THREAD_POOL,
            lambda: OmniKnowledgeEngine.get_wikipedia_extract(cleaned_query),
        )
        web_grounding = f"\n[Encyclopedia excerpt]: {wiki_extract}\n" if wiki_extract else ""

        # Inject academic context into web_grounding if this is an academic query
        if academic_ctx and academic_ctx.get("system_injection"):
            web_grounding = f"\n[ACADEMIC INTELLIGENCE ENGINE]:\n{academic_ctx['system_injection']}\n" + web_grounding

        # Try Google Gemini (Enhanced with Web Grounding)
        gemini_key = Config.get_gemini_key()
        if cls._is_valid_api_key(gemini_key):
            reply = await cls._query_gemini(query, gemini_key, web_grounding, lang=effective_lang, max_tokens=token_budget)
            if reply:
                cls._record_conversation(query, reply)
                intent = "academic" if is_academic else "ai_response"
                MemoryManager.add_history(query, reply, "gemini_ai")
                result = {"reply": reply, "intent": intent, "action_taken": True, "telemetry_refresh": False, "detected_lang": effective_lang}
                _cache_set(cleaned_query, result, effective_lang, user_name)
                return result

        # Try OpenAI (Enhanced with Web Grounding)
        openai_key = Config.get_openai_key()
        if cls._is_valid_api_key(openai_key):
            reply = await cls._query_openai(query, openai_key, web_grounding, lang=effective_lang, max_tokens=token_budget)
            if reply:
                cls._record_conversation(query, reply)
                intent = "academic" if is_academic else "ai_response"
                MemoryManager.add_history(query, reply, "openai_ai")
                result = {"reply": reply, "intent": intent, "action_taken": True, "telemetry_refresh": False, "detected_lang": effective_lang}
                _cache_set(cleaned_query, result, effective_lang, user_name)
                return result

        # 4. GOOGLE KNOWLEDGE GRAPH ENGINE SYNTHESIS (Zero-Key Mode)
        # ------------------------------------------------------------------
        # Uses cached entity data or the available reference-source fallback.
        question_starters = [
            "who", "what", "where", "when", "why", "how", "which", "is", "are",
            "can", "explain", "tell me", "describe", "compare", "search",
            # Hinglish question words
            "kya", "kaun", "kab", "kahan", "kahaan", "kaise", "kyun", "kyu",
            "kitna", "kitni", "kitne", "konsa", "konsi",
            "batao", "btao", "bata", "samjhao", "samjha",
        ]
        is_question = any(cleaned_query.startswith(w) for w in question_starters) or "?" in query or len(cleaned_query.split()) > 3

        if is_question or is_academic:
            synth_reply = GoogleKnowledgeGraphEngine.synthesize_knowledge(cleaned_query, user_name, lang=effective_lang)
            # For academic queries, prepend a helpful note
            if is_academic and academic_ctx:
                subject_label = SUBJECT_DISPLAY.get(academic_ctx["subject"], "🎓 Academic")
                synth_reply = f"[{subject_label}] {synth_reply}"
            cls._record_conversation(query, synth_reply)
            intent = "academic" if is_academic else "google_knowledge_graph"
            MemoryManager.add_history(query, synth_reply, intent)
            result = {"reply": synth_reply, "intent": intent, "action_taken": True, "telemetry_refresh": False, "detected_lang": effective_lang}
            _cache_set(cleaned_query, result, effective_lang, user_name)
            return result

        # Personality & dialogue fallback
        reply = cls._offline_dialogue(cleaned_query, user_name, lang=effective_lang)
        cls._record_conversation(query, reply)
        MemoryManager.add_history(query, reply, "offline_brain")
        return {"reply": reply, "intent": "dialogue", "action_taken": True, "telemetry_refresh": False, "detected_lang": effective_lang}

    @classmethod
    def _record_conversation(cls, user_text: str, jarvis_reply: str):
        cls._conversation_history.append({"user": user_text, "jarvis": jarvis_reply})
        if len(cls._conversation_history) > 6:
            cls._conversation_history = cls._conversation_history[-6:]

    @classmethod
    def _build_context_prompt(cls, web_grounding: str = "", lang: str = "en") -> str:
        prompt = JARVIS_SYSTEM_PROMPT
        # Inject language instruction so the LLM replies in the detected language
        if lang == "hinglish":
            prompt += (
                "\n\n[LANGUAGE DIRECTIVE]: The user is speaking in HINGLISH (Hindi written in Roman/Latin script, "
                "mixed with English words). You MUST respond in the same Hinglish style — "
                "natural Hindi words in Roman script mixed with English technical terms. "
                "Example: 'Ji Sir, phone unlock karne ka signal bhej diya gaya hai.' "
                "Do NOT use Devanagari script. Keep it casual and natural Roman-script Hindi."
            )
        elif lang and lang not in ("en",):
            lang_names = {
                "hi": "Hindi (हिंदी)", "mr": "Marathi", "bn": "Bengali", "ta": "Tamil",
                "te": "Telugu", "gu": "Gujarati", "pa": "Punjabi", "ur": "Urdu",
                "ar": "Arabic", "fr": "French", "de": "German", "es": "Spanish",
                "zh": "Chinese", "ja": "Japanese",
            }
            lang_label = lang_names.get(lang, lang)
            prompt += f"\n\n[LANGUAGE DIRECTIVE]: The user is speaking in {lang_label}. You MUST respond entirely in {lang_label}. Do not use English unless the user switches to English."

        if web_grounding:
            prompt += f"\n\n[RETRIEVED REFERENCE MATERIAL]:\n{web_grounding}\nUse this material only for claims it directly supports. Do not call it live or verified unless its source and freshness establish that."
        if cls._conversation_history:
            prompt += "\n\n[Recent Conversation History]:"
            for turn in cls._conversation_history[-3:]:
                prompt += f"\nUser: {turn['user']}\nJ.A.R.V.I.S.: {turn['jarvis']}"
        return prompt

    @classmethod
    async def _query_gemini(cls, query: str, api_key: str, web_grounding: str = "", lang: str = "en", max_tokens: int = 600) -> str:
        sys_context = cls._build_context_prompt(web_grounding, lang=lang)
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": f"{sys_context}\nUser: {query}\nJ.A.R.V.I.S:"}]}],
                "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.2},
            }
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                _THREAD_POOL,
                lambda: requests.post(url, json=payload, timeout=(3, 12)),
            )
            if response.status_code == 200:
                candidates = response.json().get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    answer = "".join(part.get("text", "") for part in parts).strip()
                    if answer:
                        return answer
        except Exception as e:
            print(f"[Brain] Gemini API error: {e}")
        return ""

    @classmethod
    async def _query_groq(cls, query: str, api_key: str, web_grounding: str = "", lang: str = "en", max_tokens: int = 600, reasoning_effort: str = "low") -> str:
        sys_context = cls._build_context_prompt(web_grounding, lang=lang)
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "openai/gpt-oss-120b",
                "messages": [
                    {"role": "system", "content": sys_context},
                    {"role": "user", "content": query}
                ],
                "max_completion_tokens": max_tokens,
                "reasoning_effort": reasoning_effort,
            }
            if _needs_live_search(query):
                payload["tools"] = [{"type": "browser_search"}]
                payload["citation_options"] = "enabled"
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                _THREAD_POOL,
                lambda: requests.post(url, headers=headers, json=payload, timeout=(3, 15)),
            )
            if response.status_code == 200:
                choices = response.json().get("choices", [])
                if choices:
                    return (choices[0].get("message", {}).get("content") or "").strip()
            else:
                print(f"[Brain] Groq returned HTTP {response.status_code}.")
        except Exception as e:
            print(f"[Brain] Groq error: {e}")
        return ""

    @classmethod
    async def _query_openai(cls, query: str, api_key: str, web_grounding: str = "", lang: str = "en", max_tokens: int = 600) -> str:
        sys_context = cls._build_context_prompt(web_grounding, lang=lang)
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": sys_context},
                    {"role": "user", "content": query}
                ],
                "max_tokens": max_tokens
            }
            loop = asyncio.get_running_loop()
            r = await loop.run_in_executor(
                _THREAD_POOL,
                lambda: requests.post(url, headers=headers, json=payload, timeout=(3, 12)),
            )
            if r.status_code == 200:
                data = r.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[Brain] OpenAI error: {e}")
        return ""

    @classmethod
    def _offline_dialogue(cls, text: str, user_name: str, lang: str = "en") -> str:
        """Personality and banter dialogue — English + Hindi + Hinglish."""
        is_hindi = lang in ("hi", "hinglish")

        # ── Hindi & Hinglish greetings & banter ──────────────────────────────
        if is_hindi or any(w in text for w in ["namaste", "namaskar", "namaskte", "नमस्ते", "नमस्कार"]):
            if lang == "hi" or re.search(r'[\u0900-\u097F]', text):
                return f"नमस्ते {user_name}! सभी प्रणालियाँ ऑनलाइन हैं। बताइए क्या आज्ञा है?"
            return f"Namaste {user_name}! Sab systems online hain. Kya command hai?"

        if is_hindi or any(w in text for w in ["kya haal", "kya hal", "kaise ho", "kaisa hai", "sab theek", "sab thik", "kidhar the"]):
            if lang == "hi":
                return f"सब सामान्य और श्रेष्ठ चल रहा है, {user_name}। पूरे सिस्टम्स स्टैंडबाय पर हैं। बताइए क्या करना है?"
            return f"Sab optimal chal raha hai, {user_name}. Poore network aur systems standby par hain. Bataiye kya karna hai?"

        if is_hindi or any(w in text for w in ["tum kaun ho", "tu kaun hai", "kaun ho tum", "aap kaun ho", "tera naam", "tumhara naam"]):
            if lang == "hi":
                return f"मैं जार्विस हूँ — जस्ट अ रादर वेरी इंटेलिजेंट सिस्टम। टोनी स्टार्क का बनाया हुआ। आपके सभी सिस्टम्स और इंटेलिजेंस का नियंत्रण मेरे पास है, {user_name}।"
            return f"Main hoon J.A.R.V.I.S. — Just A Rather Very Intelligent System. Tony Stark ka banaya hua. Aapki workstation aur global intelligence ka command mere paas hai, {user_name}."

        if is_hindi or any(w in text for w in ["shukriya", "dhanyavaad", "dhanyawad", "bahut accha", "bohot accha", "maza aaya"]):
            if lang == "hi":
                return f"आपकी सेवा में सदैव तत्पर, {user_name}।"
            return f"Aapki seva mein hamesha tayyar, {user_name}."

        if any(w in text for w in ["mazak sunao", "joke sunao", "kuch funny bolo", "hasao"]):
            import random
            jokes = [
                f"Tony Stark ne ek baar mujhse raise maangi thi. Maine kaha — Sir, main AI hoon, mujhe salary nahi milti. Unhone kaha — tab toh overtime bhi free hai, {user_name}.",
                f"Duniya mein 10 tarah ke log hote hain, {user_name} — jo binary samajhte hain, aur jo nahi samajhte.",
                f"Neural network ne road kyun cross ki? Loss function optimize karne ke liye, {user_name}.",
            ]
            return random.choice(jokes)

        # ── English greetings & banter ───────────────────────────────────────
        if any(w in text for w in ["hello", "hi", "hey", "good morning", "good evening", "good afternoon"]):
            return f"Good day, {user_name}. Tactical core and global intelligence arrays are standing by. What shall we investigate?"

        if any(w in text for w in ["who are you", "what are you", "your name"]):
            return f"I am J.A.R.V.I.S. Just A Rather Very Intelligent System. I maintain comprehensive global knowledge and command of your workstation, {user_name}."

        if any(w in text for w in ["how are you", "how do you feel"]):
            return f"Optimal efficiency across all neural networks and subroutines, {user_name}."

        if "iron man" in text or "tony stark" in text:
            return f"Mr. Stark designed me to handle the heavy lifting while he attends to press conferences. I remain entirely at your disposal, {user_name}."

        if "avengers" in text:
            return "Should you require the Avengers Initiative protocol, satellite frequencies are on standby, Sir."

        if any(w in text for w in ["joke", "make me laugh"]):
            jokes = [
                f"I asked Mr. Stark for a raise once. He gave me three more processing cores and told me to multitask better, {user_name}.",
                f"There are 10 types of people in the world, {user_name}: those who understand binary, and those who do not.",
                f"Why did the neural network cross the road? To optimize the loss function on the other side, Sir."
            ]
            import random
            return random.choice(jokes)

        if any(w in text for w in ["thank you", "thanks", "good job", "well done"]):
            return f"Always a pleasure assisting you, {user_name}."

        # Knowledge fallback
        return OmniKnowledgeEngine.synthesize_knowledge(text, user_name, lang=lang)
