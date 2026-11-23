"""
J.A.R.V.I.S. Google Knowledge Graph Engine
Google-level entity resolution, knowledge panels, factual intelligence,
dictionary definitions, and unit/currency conversions.
Uses an in-memory cache for repeated entity lookups; first-look-up latency depends on network sources.
"""

import re
import requests
import urllib.parse
import time
from threading import RLock
from datetime import datetime
from core.config import Config

class GoogleKnowledgeGraphEngine:
    """
    Google Knowledge Graph Engine for J.A.R.V.I.S.
    Resolves real-world entities, academic topics, concepts, historical figures,
    and facts using the configured Google API or available encyclopedia references.
    """
    HEADERS = {
        "User-Agent": "GoogleKnowledgeGraphEngine/3.0 (stark@jarvis.ai; Windows NT 10.0; Win64; x64)"
    }

    # In-memory entity cache for faster repeat lookups.
    _ENTITY_CACHE = {}
    _ENTITY_CACHE_TTL = 600
    _ENTITY_CACHE_LOCK = RLock()

    @staticmethod
    def normalize_text(text: str) -> str:
        if not text:
            return ""
        import unicodedata
        replacements = {
            "\u2212": "-",
            "\u22c5": " ",
            "⋅": " ",
            "•": "-",
            "–": "-",
            "—": "-",
            "’": "'",
            "‘": "'",
            "“": '"',
            "”": '"',
            "⁻¹": " per second",
            "⁻²": " per second squared",
            "²": " squared",
            "³": " cubed",
            "±": " plus or minus ",
            "×": " times ",
            "÷": " divided by ",
            "≈": " approximately ",
            "°": " degrees "
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        text = unicodedata.normalize('NFKD', text)
        text = "".join([c if ord(c) < 128 or c.isalnum() or c in " .,!?:;'\n\"-()" else " " for c in text])
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @classmethod
    def clean_query_entity(cls, query: str) -> str:
        """Strips question prefixes and filler words to extract the core Knowledge Graph entity."""
        clean_q = query.strip()
        prefixes = [
            "what is the definition of", "what is the meaning of", "what is the",
            "what is", "who is the", "who is", "where is the", "where is",
            "tell me about the", "tell me about", "explain the", "explain",
            "describe the", "describe", "how does", "why is the", "why is",
            "what are the", "what are", "kya hota hai", "kya hai", "kaun hai",
            "ke bare mein batao", "ke baare me batao"
        ]
        for p in prefixes:
            if clean_q.lower().startswith(p):
                clean_q = clean_q[len(p):].strip()
                break
        clean_q = clean_q.rstrip("?.! ")
        return clean_q or query.strip()

    @classmethod
    def query_knowledge_graph(cls, query: str) -> dict:
        """
        Queries Google Knowledge Graph to retrieve authoritative entity panel data.
        Returns a structured dictionary with:
        - entity_name
        - description (entity classification/subtitle)
        - detailed_description (full authoritative overview)
        - source
        """
        entity = cls.clean_query_entity(query)
        cache_key = entity.lower().strip()
        with cls._ENTITY_CACHE_LOCK:
            cached = cls._ENTITY_CACHE.get(cache_key)
            if cached:
                timestamp, cached_result = cached
                if time.time() - timestamp < cls._ENTITY_CACHE_TTL:
                    return dict(cached_result)
                del cls._ENTITY_CACHE[cache_key]

        def remember(result: dict) -> None:
            # Do not preserve volatile facts even for the normal cache window.
            volatile = ("current", "latest", "today", "now", "prime minister", "president", "chief minister", "ceo")
            if any(term in cache_key for term in volatile):
                return
            with cls._ENTITY_CACHE_LOCK:
                if len(cls._ENTITY_CACHE) >= 200:
                    oldest = min(cls._ENTITY_CACHE, key=lambda key: cls._ENTITY_CACHE[key][0])
                    del cls._ENTITY_CACHE[oldest]
                cls._ENTITY_CACHE[cache_key] = (time.time(), dict(result))

        # 1. Check official Google Knowledge Graph Search API if API key configured
        api_key = Config.get_gemini_key()
        if api_key and len(api_key) > 20 and not api_key.isdigit():
            try:
                url = f"https://kgsearch.googleapis.com/v1/entities:search?query={urllib.parse.quote(entity)}&key={api_key}&limit=1&indent=False"
                r = requests.get(url, timeout=2.0)
                if r.status_code == 200:
                    data = r.json()
                    items = data.get("itemListElement", [])
                    if items:
                        res = items[0].get("result", {})
                        out = {
                            "entity_name": res.get("name", entity.title()),
                            "description": res.get("description", ""),
                            "detailed_description": res.get("detailedDescription", {}).get("articleBody", ""),
                            "source": "Google Knowledge Graph API"
                        }
                        if out["detailed_description"]:
                            remember(out)
                            return out
            except Exception as e:
                print(f"[GoogleKG] Official API lookup error: {e}")

        # 2. Wikipedia REST fallback when the Google API returns no result.
        try:
            summary_url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(entity.replace(" ", "_"))
            r = requests.get(summary_url, headers=cls.HEADERS, timeout=2.0)
            if r.status_code == 200:
                d = r.json()
                extract = d.get("extract", "")
                if extract and d.get("type") != "disambiguation":
                    norm_extract = cls.normalize_text(extract)
                    out = {
                        "entity_name": d.get("title", entity.title()),
                        "description": d.get("description", ""),
                        "detailed_description": norm_extract,
                        "source": "Wikipedia REST API"
                    }
                    remember(out)
                    return out
        except Exception as e:
            print(f"[GoogleKG] Direct Entity Resolution error: {e}")

        # 3. High-Speed Knowledge Graph OpenSearch Entity Disambiguation
        try:
            search_url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(entity)}&limit=1&namespace=0&format=json"
            r2 = requests.get(search_url, headers=cls.HEADERS, timeout=2.0)
            if r2.status_code == 200:
                d2 = r2.json()
                if len(d2) > 1 and d2[1] and d2[1][0]:
                    best_title = urllib.parse.quote(d2[1][0].replace(" ", "_"))
                    r3 = requests.get("https://en.wikipedia.org/api/rest_v1/page/summary/" + best_title, headers=cls.HEADERS, timeout=2.0)
                    if r3.status_code == 200:
                        d3 = r3.json()
                        extract = d3.get("extract", "")
                        if extract:
                            norm_extract = cls.normalize_text(extract)
                            out = {
                                "entity_name": d3.get("title", entity.title()),
                                "description": d3.get("description", ""),
                                "detailed_description": norm_extract,
                                "source": "Wikipedia REST API"
                            }
                            remember(out)
                            return out
        except Exception as e:
            print(f"[GoogleKG] OpenSearch entity error: {e}")

        # 4. Google Suggest Entity Intelligence Fallback
        try:
            sugg_url = "https://suggestqueries.google.com/complete/search?client=firefox&q=" + urllib.parse.quote(entity)
            r4 = requests.get(sugg_url, headers=cls.HEADERS, timeout=1.5)
            if r4.status_code == 200:
                suggestions = r4.json()[1]
                if suggestions:
                    out = {
                        "entity_name": entity.title(),
                        "description": "Related search suggestions",
                        "detailed_description": f"Related search suggestions: {', '.join(suggestions[:4])}.",
                        "source": "Google Suggest"
                    }
                    remember(out)
                    return out
        except Exception:
            pass

        return {}

    @classmethod
    def get_hindi_knowledge(cls, query: str) -> str:
        """Retrieves native Hindi Knowledge Graph summary."""
        try:
            clean_q = re.sub(r"^(क्या है|कौन है|कहाँ है|के बारे में बताओ)\s+", "", query.strip())
            clean_q = clean_q.rstrip("?.! ") or query.strip()
            summary_url = "https://hi.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(clean_q.replace(" ", "_"))
            r = requests.get(summary_url, headers=cls.HEADERS, timeout=2.0)
            if r.status_code == 200:
                d = r.json()
                extract = d.get("extract", "")
                if extract:
                    sentences = re.split(r"(?<=[।!?])\s+", extract)
                    return " ".join(sentences[:3]).strip()
        except Exception as e:
            print(f"[GoogleKG] Hindi KG error: {e}")
        return ""

    @classmethod
    def get_web_intelligence(cls, query: str, max_results: int = 3) -> list[dict]:
        """Provides a retrieved entity summary as a reference excerpt."""
        kg_res = cls.query_knowledge_graph(query)
        clean_results = []
        if kg_res and kg_res.get("detailed_description"):
            clean_results.append({
                "title": f"Google Knowledge Graph: {kg_res.get('entity_name')}",
                "body": kg_res.get("detailed_description")[:350],
                "href": "https://www.google.com"
            })
        return clean_results

    @classmethod
    def get_wikipedia_extract(cls, query: str) -> str:
        """Retrieves Knowledge Graph overview extract."""
        kg_res = cls.query_knowledge_graph(query)
        if kg_res:
            desc = kg_res.get("description")
            body = kg_res.get("detailed_description")
            if desc and body:
                return f"{kg_res.get('entity_name')} ({desc}): {body}"
            return body or desc or ""
        return ""

    @classmethod
    def get_latest_news(cls, topic: str = "technology") -> str:
        """Retrieves breaking real-time news headlines via live Google RSS feed."""
        try:
            feed_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(topic)}&hl=en-IN&gl=IN&ceid=IN:en"
            r = requests.get(feed_url, headers=cls.HEADERS, timeout=3.0)
            if r.status_code == 200:
                titles = re.findall(r"<item>\s*<title>(.*?)</title>", r.text)
                if titles:
                    clean_titles = [re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", t).strip() for t in titles[:3]]
                    return f"Google News Intelligence feed regarding {topic}: " + " | ".join(clean_titles)
        except Exception as e:
            print(f"[GoogleKG] Google News error: {e}")
        return ""

    @classmethod
    def get_word_definition(cls, word: str) -> str:
        """Looks up dictionary definition, part of speech, and usage."""
        try:
            clean_word = re.sub(r"[^a-zA-Z]", "", word).lower()
            url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{clean_word}"
            r = requests.get(url, timeout=3.0)
            if r.status_code == 200:
                data = r.json()
                if data and isinstance(data, list):
                    first = data[0]
                    meanings = first.get("meanings", [])
                    if meanings:
                        part = meanings[0].get("partOfSpeech", "")
                        defs = meanings[0].get("definitions", [])
                        if defs:
                            definition = defs[0].get("definition", "")
                            example = defs[0].get("example", "")
                            res = f"'{clean_word.title()}' ({part}): {definition}"
                            if example:
                                res += f" Example: \"{example}\"."
                            return res
        except Exception as e:
            print(f"[GoogleKG] Dictionary error: {e}")
        return ""

    @classmethod
    def convert_currency(cls, amount: float, from_curr: str, to_curr: str) -> str:
        """Converts currency using live global exchange rates."""
        try:
            from_c = from_curr.upper()
            to_c = to_curr.upper()
            url = f"https://open.er-api.com/v6/latest/{from_c}"
            r = requests.get(url, timeout=3.0)
            if r.status_code == 200:
                rates = r.json().get("rates", {})
                if to_c in rates:
                    rate = rates[to_c]
                    converted = round(amount * rate, 2)
                    return f"{amount:,.2f} {from_c} is currently equivalent to {converted:,.2f} {to_c} (Exchange rate: 1 {from_c} = {rate:.4f} {to_c}), Sir."
        except Exception as e:
            print(f"[GoogleKG] Currency conversion error: {e}")
        return ""

    @classmethod
    def convert_units(cls, text: str) -> str:
        """Handles common metric/imperial conversions."""
        m = re.search(r"(\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s*(?:to|in|into)\s*([a-zA-Z]+)", text.lower())
        if not m:
            return ""

        val = float(m.group(1))
        u1 = m.group(2).strip()
        u2 = m.group(3).strip()

        # Distance
        if u1 in ["mile", "miles", "mi"] and u2 in ["km", "kilometer", "kilometers"]:
            return f"{val} miles is {round(val * 1.60934, 2)} kilometers, Sir."
        if u1 in ["km", "kilometer", "kilometers"] and u2 in ["mile", "miles", "mi"]:
            return f"{val} kilometers is {round(val / 1.60934, 2)} miles, Sir."
        if u1 in ["meter", "meters", "m"] and u2 in ["foot", "feet", "ft"]:
            return f"{val} meters is {round(val * 3.28084, 2)} feet, Sir."
        if u1 in ["foot", "feet", "ft"] and u2 in ["meter", "meters", "m"]:
            return f"{val} feet is {round(val / 3.28084, 2)} meters, Sir."
        if u1 in ["inch", "inches", "in"] and u2 in ["cm", "centimeter", "centimeters"]:
            return f"{val} inches is {round(val * 2.54, 2)} centimeters, Sir."
        if u1 in ["cm", "centimeter", "centimeters"] and u2 in ["inch", "inches", "in"]:
            return f"{val} centimeters is {round(val / 2.54, 2)} inches, Sir."

        # Weight
        if u1 in ["kg", "kilogram", "kilograms", "kilos"] and u2 in ["lb", "lbs", "pound", "pounds"]:
            return f"{val} kilograms is {round(val * 2.20462, 2)} pounds, Sir."
        if u1 in ["lb", "lbs", "pound", "pounds"] and u2 in ["kg", "kilogram", "kilograms", "kilos"]:
            return f"{val} pounds is {round(val / 2.20462, 2)} kilograms, Sir."

        # Temperature
        if u1 in ["c", "celsius"] and u2 in ["f", "fahrenheit"]:
            return f"{val}°C is {round((val * 9/5) + 32, 1)}°F, Sir."
        if u1 in ["f", "fahrenheit"] and u2 in ["c", "celsius"]:
            return f"{val}°F is {round((val - 32) * 5/9, 1)}°C, Sir."

        return ""

    @classmethod
    def synthesize_knowledge(cls, query: str, user_name: str = "Sir", lang: str = "en") -> str:
        """
        Synthesizes a response from available entity data and reference sources.
        """
        is_hindi = lang in ("hi", "hinglish")

        # 1. Native Hindi Knowledge Graph lookup if Hindi script detected
        if is_hindi and re.search(r'[\u0900-\u097F]', query):
            h_extract = cls.get_hindi_knowledge(query)
            if h_extract:
                if lang == "hi":
                    return f"Wikipedia के हिंदी लेख के अनुसार: {h_extract} क्या आप इसके बारे में और विस्तार से जानना चाहते हैं, {user_name}?"
                return f"Hindi Wikipedia ke mutabiq: {h_extract} Aur koi query hai, {user_name}?"

        # 2. Query Google Knowledge Graph
        kg_res = cls.query_knowledge_graph(query)
        base_text = ""
        entity_name = ""
        entity_desc = ""

        if kg_res and kg_res.get("detailed_description"):
            entity_name = kg_res.get("entity_name", "")
            entity_desc = kg_res.get("description", "")
            detailed = kg_res.get("detailed_description", "")
            # Pick first 2 crisp sentences for high spoken speed
            sentences = re.split(r"(?<=[.!?])\s+", detailed)
            base_text = " ".join(sentences[:2]).strip()
            if not base_text.endswith("."):
                base_text += "."

        if base_text:
            source_name = kg_res.get("source") or "retrieved reference source"
            if is_hindi:
                from core.voice_engine import translate_to_hindi
                hindi_text = translate_to_hindi(base_text)
                if lang == "hi" or re.search(r'[\u0900-\u097F]', query):
                    return f"उपलब्ध {source_name} के अनुसार: {hindi_text} क्या आप इसके बारे में और जानना चाहते हैं, {user_name}?"
                else:
                    return f"Available {source_name} ke mutabiq: {hindi_text} Aur koi jankari chahiye, {user_name}?"
            else:
                desc_tag = f" ({entity_desc})" if entity_desc else ""
                return f"According to {source_name} for {entity_name}{desc_tag}: {base_text} Standing by for further inquiries, {user_name}."

        if is_hindi:
            if lang == "hi":
                return f"'{query}' के लिए मुझे कोई विश्वसनीय स्रोत नहीं मिला, {user_name}। मैं पक्की जानकारी के बिना अनुमान नहीं लगाऊँगा।"
            else:
                return f"'{query}' ke liye mujhe reliable source nahi mila, {user_name}; main bina pakke data ke guess nahi karunga."

        return f"I couldn't find a reliable source to verify '{query}', {user_name}, so I won't guess."

# Backwards compatibility alias
OmniKnowledgeEngine = GoogleKnowledgeGraphEngine
