import re
import math
import requests
import urllib.parse
from datetime import datetime

class JarvisTools:
    @staticmethod
    def get_time_and_date() -> str:
        now = datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")
        time_str = now.strftime("%I:%M %p")
        return f"It is currently {time_str} on {date_str}, Sir."

    @staticmethod
    def get_weather(location: str = "") -> str:
        try:
            loc = location.strip()
            url = f"https://wttr.in/{urllib.parse.quote(loc)}?format=j1" if loc else "https://wttr.in/?format=j1"
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, headers=headers, timeout=6)
            if r.status_code == 200:
                data = r.json()
                current = data.get("current_condition", [{}])[0]
                temp_c = current.get("temp_C", "N/A")
                temp_f = current.get("temp_F", "N/A")
                desc = current.get("weatherDesc", [{}])[0].get("value", "Clear")
                humidity = current.get("humidity", "N/A")
                wind_kmph = current.get("windspeedKmph", "N/A")
                area = ""
                nearest_area = data.get("nearest_area", [{}])[0]
                area_name = nearest_area.get("areaName", [{}])[0].get("value", "")
                country = nearest_area.get("country", [{}])[0].get("value", "")
                if area_name:
                    area = f" for {area_name}, {country}"

                return (
                    f"Atmospheric telemetry{area}: Currently {temp_c}°C ({temp_f}°F) with {desc.lower()}. "
                    f"Humidity is at {humidity} percent and winds are clocking {wind_kmph} kilometers per hour, Sir."
                )
        except Exception as e:
            print(f"[Tools] Weather lookup error: {e}")
        return "I am currently unable to establish a telemetry downlink with atmospheric meteorological satellites, Sir."

    @staticmethod
    def search_wikipedia(query: str) -> str:
        try:
            clean_query = query.strip().replace(" ", "_")
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(clean_query)}"
            headers = {"User-Agent": "JarvisAI/2.0 (stark-industries@avengers.org)"}
            r = requests.get(url, headers=headers, timeout=6)
            if r.status_code == 200:
                data = r.json()
                extract = data.get("extract", "")
                if extract:
                    # Limit to two sentences for crisp speech
                    sentences = extract.split(". ")
                    short_extract = ". ".join(sentences[:2])
                    if not short_extract.endswith("."):
                        short_extract += "."
                    return f"According to archival records: {short_extract}"
        except Exception as e:
            print(f"[Tools] Wikipedia lookup error: {e}")
        return ""

    @staticmethod
    def search_web(query: str) -> str:
        try:
            from ddgs import DDGS
            results = list(DDGS().text(query, max_results=2))
            if results and len(results) > 0:
                first = results[0]
                title = first.get("title", "")
                body = first.get("body", "")
                return f"Global satellite sweep reports for '{query}': {body}"
        except Exception as e:
            print(f"[Tools] DDGS search error: {e}")
        
        # Fallback to wikipedia
        wiki_res = JarvisTools.search_wikipedia(query)
        if wiki_res:
            return wiki_res
            
        return f"I executed a web sweep for '{query}', Sir. You may review the active browser tab for complete results."

    @staticmethod
    def open_youtube_search(query: str) -> tuple[bool, str]:
        encoded = urllib.parse.quote_plus(query)
        import subprocess
        try:
            subprocess.Popen(f"start https://www.youtube.com/results?search_query={encoded}", shell=True)
            return True, f"Deploying audio-visual stream on YouTube for '{query}', Sir."
        except Exception as e:
            return False, f"Failed to access YouTube stream: {e}"

    @staticmethod
    def calculate_expression(expr: str) -> str:
        try:
            # Clean expression
            clean = expr.lower()
            clean = re.sub(r"[^\d\+\-\*\/\(\)\.\%\^x]", "", clean.replace("x", "*"))
            clean = clean.replace("^", "**")
            
            # Safe evaluation
            allowed_names = {"math": math, "sin": math.sin, "cos": math.cos, "sqrt": math.sqrt, "pi": math.pi}
            result = eval(clean, {"__builtins__": None}, allowed_names)
            return f"The computed solution is {result}, Sir."
        except Exception:
            return "My computational matrix was unable to parse that arithmetic expression, Sir."
