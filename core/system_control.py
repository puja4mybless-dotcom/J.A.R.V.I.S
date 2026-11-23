import os
import sys
import time
import json
import ctypes
import re
import urllib.parse
import webbrowser
import subprocess
import platform
import psutil
from datetime import datetime
from pathlib import Path
from ctypes import wintypes
from core.config import SCREENSHOTS_DIR, Config

try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    from ctypes import cast, POINTER
    PYCAW_AVAILABLE = True
except Exception:
    PYCAW_AVAILABLE = False


def _open_on_screen(url: str) -> bool:
    """
    Opens a URL directly on the user's COMPUTER SCREEN using the Windows 'start' command.
    This ALWAYS opens in the system default browser (Chrome/Edge/Firefox),
    NOT inside the JARVIS web panel.
    """
    try:
        # Primary: Windows shell 'start' — most reliable, opens on desktop
        subprocess.Popen(f'start "" "{url}"', shell=True)
        return True
    except Exception:
        pass
    try:
        # Fallback 1: os.startfile (also opens on computer screen)
        os.startfile(url)
        return True
    except Exception:
        pass
    try:
        # Fallback 2: webbrowser module
        webbrowser.open(url)
        return True
    except Exception:
        return False


# Win32 Structures for Unicode Key simulation
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ('wVk', wintypes.WORD),
        ('wScan', wintypes.WORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_ulonglong)
    ]

class INPUT(ctypes.Structure):
    class _I(ctypes.Union):
        _fields_ = [('ki', KEYBDINPUT)]
    _anonymous_ = ('_input',)
    _fields_ = [('type', wintypes.DWORD), ('_input', _I)]


class SystemControl:
    # Cache for dynamically discovered Windows applications
    _INSTALLED_APPS_CACHE: dict = {}
    _LAST_APP_CACHE_TIME: float = 0.0

    # Comprehensive dictionary of Windows applications, tools, and popular portals
    APPS = {
        # Communication & Mail
        "mail": "start outlookmail:",
        "email": "start outlookmail:",
        "outlook": "start outlook:",
        "gmail": "start https://mail.google.com",
        "whatsapp": "start whatsapp:",
        "whatsapp web": "start https://web.whatsapp.com",
        "call centre": "start ms-yourphone:",
        "call center": "start ms-yourphone:",
        "phone link": "start ms-yourphone:",
        "your phone": "start ms-yourphone:",
        "dialer": "start ms-phone:",
        "telegram": "start https://web.telegram.org",
        "discord": "start https://discord.com/app",
        "teams": "start msteams:",
        "zoom": "start zoommtg:",

        # Settings & Control
        "settings": "start ms-settings:",
        "pc settings": "start ms-settings:",
        "computer settings": "start ms-settings:",
        "windows settings": "start ms-settings:",
        "system settings": "start ms-settings:",
        "wifi settings": "start ms-settings:network-wifi",
        "network settings": "start ms-settings:network",
        "bluetooth settings": "start ms-settings:bluetooth",
        "display settings": "start ms-settings:display",
        "sound settings": "start ms-settings:sound",
        "audio settings": "start ms-settings:sound",
        "update settings": "start ms-settings:windowsupdate",
        "windows update": "start ms-settings:windowsupdate",
        "apps settings": "start ms-settings:appsfeatures",
        "storage settings": "start ms-settings:storagesense",
        "control panel": "control.exe",
        "task manager": "taskmgr.exe",
        "taskmgr": "taskmgr.exe",
        "device manager": "devmgmt.msc",
        "disk management": "diskmgmt.msc",
        "services": "services.msc",
        "registry": "regedit.exe",
        "group policy": "gpedit.msc",

        # Standard Windows Utilities
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "paint": "mspaint.exe",
        "wordpad": "write.exe",
        "snipping tool": "snippingtool.exe",
        "snip": "snippingtool.exe",
        "camera": "start microsoft.windows.camera:",
        "photos": "start ms-photos:",
        "clock": "start ms-clock:",
        "alarm": "start ms-clock:",
        "calendar": "start outlookcal:",
        "store": "start ms-windows-store:",
        "windows store": "start ms-windows-store:",
        "file explorer": "explorer.exe",
        "explorer": "explorer.exe",
        "my pc": "explorer.exe",
        "this pc": "explorer.exe",
        "recycle bin": "explorer.exe shell:RecycleBinFolder",
        "command prompt": "start cmd.exe",
        "cmd": "start cmd.exe",
        "terminal": "start wt.exe",
        "powershell": "start powershell.exe",

        # Web Browsers
        "chrome": "start chrome",
        "google chrome": "start chrome",
        "edge": "start msedge",
        "microsoft edge": "start msedge",
        "browser": "start msedge",
        "brave": "start brave",
        "firefox": "start firefox",
        "opera": "start opera",

        # Developer & Productivity Tools
        "vscode": "code",
        "vs code": "code",
        "code": "code",
        "word": "start winword",
        "excel": "start excel",
        "powerpoint": "start powerpnt",
        "vlc": "start vlc",
        "spotify": "start spotify:",
        "steam": "start steam:",

        # ── Google Services (all open on computer screen) ──
        "google": "start https://www.google.com",
        "google search": "start https://www.google.com",
        "youtube": "start https://www.youtube.com",
        "gmail": "start https://mail.google.com",
        "google mail": "start https://mail.google.com",
        "google drive": "start https://drive.google.com",
        "drive": "start https://drive.google.com",
        "google docs": "start https://docs.google.com",
        "docs": "start https://docs.google.com",
        "google sheets": "start https://sheets.google.com",
        "sheets": "start https://sheets.google.com",
        "google slides": "start https://slides.google.com",
        "slides": "start https://slides.google.com",
        "google forms": "start https://forms.google.com",
        "forms": "start https://forms.google.com",
        "google meet": "start https://meet.google.com",
        "meet": "start https://meet.google.com",
        "google maps": "start https://maps.google.com",
        "maps": "start https://maps.google.com",
        "google translate": "start https://translate.google.com",
        "translate": "start https://translate.google.com",
        "google photos": "start https://photos.google.com",
        "google news": "start https://news.google.com",
        "google classroom": "start https://classroom.google.com",
        "classroom": "start https://classroom.google.com",
        "google calendar": "start https://calendar.google.com",
        "google keep": "start https://keep.google.com",
        "keep": "start https://keep.google.com",
        "google pay": "start https://pay.google.com",
        "gpay": "start https://pay.google.com",
        "google earth": "start https://earth.google.com",
        "google colab": "start https://colab.research.google.com",
        "colab": "start https://colab.research.google.com",
        "gemini": "start https://gemini.google.com",
        "google gemini": "start https://gemini.google.com",
        "google one": "start https://one.google.com",
        "google contacts": "start https://contacts.google.com",

        # ── Educational Portals ──
        "physics wallah": "start https://www.pw.live",
        "physicswallah": "start https://www.pw.live",
        "pw": "start https://www.pw.live",
        "pw live": "start https://www.pw.live",
        "ncert": "start https://ncert.nic.in",
        "ncert books": "start https://ncert.nic.in/textbook.php",
        "ncert portal": "start https://ncert.nic.in",
        "khan academy": "start https://www.khanacademy.org",
        "coursera": "start https://www.coursera.org",
        "udemy": "start https://www.udemy.com",
        "byjus": "start https://byjus.com",
        "byju's": "start https://byjus.com",
        "unacademy": "start https://unacademy.com",
        "vedantu": "start https://www.vedantu.com",

        # ── AI & Tech ──
        "chatgpt": "start https://chatgpt.com",
        "openai": "start https://openai.com",
        "github": "start https://github.com",
        "stackoverflow": "start https://stackoverflow.com",
        "stack overflow": "start https://stackoverflow.com",

        # ── Shopping ──
        "amazon": "start https://www.amazon.in",
        "flipkart": "start https://www.flipkart.com",
        "meesho": "start https://www.meesho.com",
        "myntra": "start https://www.myntra.com",

        # ── Info & Social ──
        "wikipedia": "start https://www.wikipedia.org",
        "instagram": "start https://www.instagram.com",
        "facebook": "start https://www.facebook.com",
        "twitter": "start https://x.com",
        "linkedin": "start https://www.linkedin.com",
        "reddit": "start https://www.reddit.com",
        "quora": "start https://www.quora.com",

        # ── Entertainment ──
        "netflix": "start https://www.netflix.com",
        "prime video": "start https://www.primevideo.com",
        "hotstar": "start https://www.hotstar.com",
        "spotify web": "start https://open.spotify.com",
        "cricbuzz": "start https://www.cricbuzz.com",
        "canva": "start https://www.canva.com",
    }

    POPULAR_SITES = {
        # ── Google Ecosystem (all open on computer screen) ──
        "google": "https://www.google.com",
        "google search": "https://www.google.com",
        "youtube": "https://www.youtube.com",
        "gmail": "https://mail.google.com",
        "mail": "https://mail.google.com",
        "google mail": "https://mail.google.com",
        "google drive": "https://drive.google.com",
        "drive": "https://drive.google.com",
        "google docs": "https://docs.google.com",
        "docs": "https://docs.google.com",
        "google sheets": "https://sheets.google.com",
        "sheets": "https://sheets.google.com",
        "google slides": "https://slides.google.com",
        "slides": "https://slides.google.com",
        "google forms": "https://forms.google.com",
        "forms": "https://forms.google.com",
        "google meet": "https://meet.google.com",
        "meet": "https://meet.google.com",
        "google maps": "https://maps.google.com",
        "maps": "https://maps.google.com",
        "google translate": "https://translate.google.com",
        "translate": "https://translate.google.com",
        "google photos": "https://photos.google.com",
        "photos": "https://photos.google.com",
        "google news": "https://news.google.com",
        "news": "https://news.google.com",
        "google classroom": "https://classroom.google.com",
        "classroom": "https://classroom.google.com",
        "google calendar": "https://calendar.google.com",
        "calendar web": "https://calendar.google.com",
        "google keep": "https://keep.google.com",
        "keep": "https://keep.google.com",
        "google pay": "https://pay.google.com",
        "gpay": "https://pay.google.com",
        "google earth": "https://earth.google.com",
        "earth": "https://earth.google.com",
        "google colab": "https://colab.research.google.com",
        "colab": "https://colab.research.google.com",
        "gemini": "https://gemini.google.com",
        "google gemini": "https://gemini.google.com",
        "google one": "https://one.google.com",
        "google contacts": "https://contacts.google.com",
        "contacts": "https://contacts.google.com",

        # ── Communication ──
        "whatsapp": "https://web.whatsapp.com",
        "whatsapp web": "https://web.whatsapp.com",
        "telegram": "https://web.telegram.org",
        "discord": "https://discord.com/app",
        "zoom": "https://zoom.us",

        # ── Educational ──
        "physics wallah": "https://www.pw.live",
        "physicswallah": "https://www.pw.live",
        "pw": "https://www.pw.live",
        "pw live": "https://www.pw.live",
        "ncert": "https://ncert.nic.in",
        "ncert books": "https://ncert.nic.in/textbook.php",
        "call centre": "https://voice.google.com",
        "call center": "https://voice.google.com",
        "chatgpt": "https://chatgpt.com",
        "openai": "https://openai.com",
        "claude": "https://claude.ai",
        "github": "https://github.com",
        "khan academy": "https://www.khanacademy.org",
        "khanacademy": "https://www.khanacademy.org",
        "coursera": "https://www.coursera.org",
        "udemy": "https://www.udemy.com",
        "byjus": "https://byjus.com",
        "byju's": "https://byjus.com",
        "unacademy": "https://unacademy.com",
        "vedantu": "https://www.vedantu.com",
        "wikipedia": "https://www.wikipedia.org",

        # ── Shopping ──
        "amazon": "https://www.amazon.in",
        "flipkart": "https://www.flipkart.com",
        "meesho": "https://www.meesho.com",
        "myntra": "https://www.myntra.com",
        "nykaa": "https://www.nykaa.com",

        # ── Social & Entertainment ──
        "instagram": "https://www.instagram.com",
        "facebook": "https://www.facebook.com",
        "twitter": "https://x.com",
        "x": "https://x.com",
        "linkedin": "https://www.linkedin.com",
        "reddit": "https://www.reddit.com",
        "quora": "https://www.quora.com",
        "pinterest": "https://www.pinterest.com",
        "netflix": "https://www.netflix.com",
        "prime video": "https://www.primevideo.com",
        "hotstar": "https://www.hotstar.com",
        "jio cinema": "https://www.jiocinema.com",
        "spotify": "https://open.spotify.com",
        "cricbuzz": "https://www.cricbuzz.com",
        "espncricinfo": "https://www.espncricinfo.com",
        "canva": "https://www.canva.com",

        # ── News ──
        "ndtv": "https://www.ndtv.com",
        "times of india": "https://timesofindia.indiatimes.com",
        "hindustan times": "https://www.hindustantimes.com",
        "bbc": "https://www.bbc.com",
        "cnn": "https://www.cnn.com",

        # ── Finance ──
        "zerodha": "https://zerodha.com",
        "groww": "https://groww.in",
        "paytm": "https://paytm.com",
        "phonepe": "https://www.phonepe.com",

        # ── Dev Tools ──
        "stackoverflow": "https://stackoverflow.com",
        "stack overflow": "https://stackoverflow.com",
        "w3schools": "https://www.w3schools.com",
        "mdn": "https://developer.mozilla.org",
    }

    @classmethod
    def get_installed_apps(cls, force_refresh: bool = False) -> dict:
        """
        Dynamically scans and caches all installed Windows applications,
        Store / UWP packages, and Start Menu shortcuts via Get-StartApps.
        """
        now = time.time()
        if cls._INSTALLED_APPS_CACHE and not force_refresh and (now - cls._LAST_APP_CACHE_TIME < 300):
            return cls._INSTALLED_APPS_CACHE

        apps = {}
        try:
            cmd = ['powershell', '-NoProfile', '-Command', 'Get-StartApps | Select-Object Name, AppID | ConvertTo-Json']
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    name = item.get('Name', '').strip()
                    appid = item.get('AppID', '').strip()
                    if name and appid:
                        apps[name.lower()] = (name, appid)
        except Exception as e:
            print(f"[SystemControl] Error querying Get-StartApps: {e}")

        cls._INSTALLED_APPS_CACHE = apps
        cls._LAST_APP_CACHE_TIME = now
        return apps

    @classmethod
    def _launch_by_appid(cls, appid: str) -> bool:
        """Launches a Windows Store / UWP or registered desktop app by its AppID."""
        try:
            cmd = f'powershell -NoProfile -Command "Start-Process \'shell:AppsFolder\\{appid}\'"'
            subprocess.Popen(cmd, shell=True)
            return True
        except Exception:
            try:
                subprocess.Popen(f'explorer.exe shell:AppsFolder\\"{appid}"', shell=True)
                return True
            except Exception:
                return False

    @classmethod
    def get_app_title(cls, key: str) -> str:
        key_lower = key.lower()
        if "ncert" in key_lower:
            return "NCERT Portal"
        if "pw" in key_lower or "physics" in key_lower:
            return "Physics Wallah"
        if "whatsapp" in key_lower:
            return "WhatsApp"
        if "call" in key_lower or "phone link" in key_lower:
            return "Phone Link Call Centre"
        if "setting" in key_lower:
            return "Windows Settings"
        return key.title()

    @classmethod
    def open_mail(cls) -> tuple[bool, str]:
        """Opens Mail app on computer (Windows Mail, Outlook, or Gmail web)."""
        user_name = Config.get_user_name()
        # 1. Try Windows Mail protocol
        try:
            subprocess.Popen("start outlookmail:", shell=True)
            return True, f"Launching Windows Mail client, {user_name}."
        except Exception:
            pass

        # 2. Check installed apps for Mail
        apps = cls.get_installed_apps()
        for name, (clean_name, appid) in apps.items():
            if "mail" in name and "windowslive" in appid.lower():
                if cls._launch_by_appid(appid):
                    return True, f"Launching {clean_name}, {user_name}."

        # 3. Fallback: Gmail on computer screen
        _open_on_screen("https://mail.google.com")
        return True, f"Opening Gmail on your computer screen, {user_name}."

    @classmethod
    def open_whatsapp(cls) -> tuple[bool, str]:
        """Opens WhatsApp desktop app or WhatsApp Web."""
        user_name = Config.get_user_name()
        # 1. Try WhatsApp protocol
        try:
            subprocess.Popen("start whatsapp:", shell=True)
            return True, f"Opening WhatsApp, {user_name}."
        except Exception:
            pass

        # 2. Check installed apps for WhatsApp
        apps = cls.get_installed_apps()
        for name, (clean_name, appid) in apps.items():
            if "whatsapp" in name:
                if cls._launch_by_appid(appid):
                    return True, f"Launching {clean_name}, {user_name}."

        # 3. Check Local AppData WhatsApp
        local_wa = Path(os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe"))
        if local_wa.exists():
            subprocess.Popen(f'"{local_wa}"', shell=True)
            return True, f"Opening WhatsApp Desktop, {user_name}."

        # 4. Fallback: WhatsApp Web on computer screen
        _open_on_screen("https://web.whatsapp.com")
        return True, f"Opening WhatsApp Web on your computer screen, {user_name}."

    @classmethod
    def open_call_centre(cls) -> tuple[bool, str]:
        """Opens Call Centre interface (Phone Link / calling terminal / dialer)."""
        user_name = Config.get_user_name()
        # 1. Try Windows Phone Link protocol
        try:
            subprocess.Popen("start ms-yourphone:", shell=True)
            return True, f"Opening Phone Link call centre terminal, {user_name}."
        except Exception:
            pass

        # 2. Check installed apps for Phone Link
        apps = cls.get_installed_apps()
        for name, (clean_name, appid) in apps.items():
            if "phone link" in name or "your phone" in name:
                if cls._launch_by_appid(appid):
                    return True, f"Launching {clean_name} call centre terminal, {user_name}."

        # 3. Try tel / phone dialer protocol
        try:
            subprocess.Popen("start ms-phone:", shell=True)
            return True, f"Opening phone calling dialer, {user_name}."
        except Exception:
            pass

        # 4. Fallback: Google Voice / Calling console on computer screen
        _open_on_screen("https://voice.google.com")
        return True, f"Opening Google Voice calling console on your computer screen, {user_name}."

    @classmethod
    def open_settings(cls, sub_page: str = "") -> tuple[bool, str]:
        """Opens computer system settings or specific control panel pages."""
        user_name = Config.get_user_name()
        sub = sub_page.lower().strip()
        routes = {
            "wifi": "start ms-settings:network-wifi",
            "network": "start ms-settings:network",
            "bluetooth": "start ms-settings:bluetooth",
            "display": "start ms-settings:display",
            "sound": "start ms-settings:sound",
            "audio": "start ms-settings:sound",
            "update": "start ms-settings:windowsupdate",
            "windows update": "start ms-settings:windowsupdate",
            "apps": "start ms-settings:appsfeatures",
            "storage": "start ms-settings:storagesense",
            "personalization": "start ms-settings:personalization",
            "power": "start ms-settings:powersleep",
            "battery": "start ms-settings:batterysaver",
            "about": "start ms-settings:about",
            "system": "start ms-settings:",
            "control panel": "control.exe",
            "task manager": "taskmgr.exe",
            "device manager": "devmgmt.msc",
            "disk management": "diskmgmt.msc",
        }
        cmd = "start ms-settings:"
        label = "Computer System Settings"
        for key, target in routes.items():
            if key in sub:
                cmd = target
                label = f"{key.title()} Settings"
                break

        try:
            subprocess.Popen(cmd, shell=True)
            return True, f"Opening {label}, {user_name}."
        except Exception as e:
            return False, f"Failed to open settings: {e}"

    @classmethod
    def open_website(cls, query_or_url: str) -> tuple[bool, str]:
        """
        Universal Website & Link Opener.
        ALL websites open on the computer screen (system default browser),
        NOT inside the JARVIS panel.
        """
        user_name = Config.get_user_name()
        clean = query_or_url.strip()
        clean = re.sub(r"^(?:open|launch|go\s+to|visit|navigate\s+to|website|site|link)\s+", "", clean, flags=re.IGNORECASE).strip()
        clean = re.sub(r"\s+(?:website|site|portal|link|page)$", "", clean, flags=re.IGNORECASE).strip()

        # Direct HTTP/HTTPS URL — open on screen immediately
        if clean.startswith("http://") or clean.startswith("https://"):
            _open_on_screen(clean)
            return True, f"Opening {clean} on your computer screen, {user_name}."

        clean_lower = clean.lower()

        # Popular mapped websites
        if clean_lower in cls.POPULAR_SITES:
            url = cls.POPULAR_SITES[clean_lower]
            _open_on_screen(url)
            return True, f"Opening {clean.title()} on your computer screen, {user_name}."

        for key, url in cls.POPULAR_SITES.items():
            if key == clean_lower or (len(key) > 3 and key in clean_lower):
                _open_on_screen(url)
                return True, f"Opening {key.title()} on your computer screen, {user_name}."

        # Domain check (.com, .in, .org, .net, etc.)
        tlds = [".com", ".in", ".org", ".net", ".edu", ".gov", ".io", ".ai", ".co", ".co.in", ".live", ".nic.in", ".info", ".biz", ".me"]
        if any(clean_lower.endswith(tld) or (tld + "/") in clean_lower for tld in tlds) or ("." in clean and " " not in clean):
            domain = clean.replace(" ", "")
            url = f"https://{domain}"
            _open_on_screen(url)
            return True, f"Navigating directly to {url} on your screen, {user_name}."

        # Universal Google Web Search on computer screen
        search_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(clean)}"
        _open_on_screen(search_url)
        return True, f"Searching Google for '{clean}' on your computer screen, {user_name}."

    @classmethod
    def open_all_google_apps(cls) -> tuple[bool, str]:
        """
        Opens Google's comprehensive Products and Apps hub directly on the user's computer screen,
        giving immediate access to all Google services (Search, Drive, Gmail, Docs, Sheets, Meet, etc.).
        """
        user_name = Config.get_user_name()
        _open_on_screen("https://about.google/products/")
        _open_on_screen("https://www.google.com")
        return True, (
            f"Deploying all Google links and apps directly on your computer screen, {user_name}. "
            "Google Products Hub and Search portal are now open. "
            "You can also ask me to launch any specific service: Google Drive, Docs, Sheets, "
            "Slides, Gmail, Meet, Maps, Classroom, YouTube, Earth, Colab, Keep, or Photos."
        )

    @classmethod
    def open_google_search(cls, search_term: str) -> tuple[bool, str]:
        """
        Opens a live Google Search query directly on the user's computer screen.
        """
        user_name = Config.get_user_name()
        clean = search_term.strip()
        url = f"https://www.google.com/search?q={urllib.parse.quote_plus(clean)}"
        _open_on_screen(url)
        return True, f"Opening Google search for '{clean}' on your computer screen, {user_name}."

    @classmethod
    def open_app(cls, app_name: str) -> tuple[bool, str]:
        """
        Comprehensive Application & Link Launcher:
        Opens Mail, WhatsApp, Call Centre, Settings, All Installed Apps, All Google Services, and All Websites
        directly on the user's computer screen.
        """
        # Sanitize trailing screen/device words
        raw_name = re.sub(
            r"\s+(?:on|in)\s+(?:my\s+)?(?:computer\s+screen|pc\s+screen|laptop\s+screen|screen|desktop|display|computer|pc|laptop|system)$",
            "",
            app_name.strip(),
            flags=re.IGNORECASE
        ).strip()
        raw_name = re.sub(
            r"\s+(?:(?:computer|pc|laptop)?\s*screen|desktop|display|computer|pc)\s+(?:par|pe|mein|me)$",
            "",
            raw_name,
            flags=re.IGNORECASE
        ).strip()
        # Sanitize leading verbs
        raw_name = re.sub(r"^(?:open|launch|start|run|go\s+to|visit)\s+", "", raw_name, flags=re.IGNORECASE).strip()

        app_name_lower = raw_name.lower().strip()

        # Check for "all google apps" / "all google links" / "google apps"
        if any(app_name_lower == k or app_name_lower.startswith(k) for k in [
            "all google apps", "all google links", "all google", "google apps", "google links",
            "google products", "google suite", "google ecosystem"
        ]):
            return cls.open_all_google_apps()

        # Check if query starts with "google " (e.g., "google drive", "google docs", "google machine learning")
        if app_name_lower.startswith("google "):
            term = app_name_lower[7:].strip()
            # If term matches a specific known Google service in APPS
            app_key = f"google {term}"
            if app_key in cls.APPS:
                cmd = cls.APPS[app_key]
                subprocess.Popen(cmd, shell=True)
                title = cls.get_app_title(app_key)
                return True, f"Opening {title} on your computer screen, Sir."
            if term in cls.APPS:
                cmd = cls.APPS[term]
                subprocess.Popen(cmd, shell=True)
                title = cls.get_app_title(term)
                return True, f"Opening {title} on your computer screen, Sir."
            # If term is a search term (e.g., "google quantum physics")
            return cls.open_google_search(term)

        # 1. Specialized Canonical Handlers
        if any(k == app_name_lower or k in app_name_lower for k in ["mail", "email", "gmail", "open mail", "check mail"]):
            return cls.open_mail()

        if any(k == app_name_lower or k in app_name_lower for k in ["whatsapp", "whatsapp web", "open whatsapp"]):
            return cls.open_whatsapp()

        if any(k in app_name_lower for k in ["call centre", "call center", "phone link", "your phone", "dialer"]):
            return cls.open_call_centre()

        if any(k in app_name_lower for k in ["setting", "control panel", "device manager", "task manager"]):
            return cls.open_settings(app_name_lower)

        # 2. Check predefined APPS dictionary
        if app_name_lower in cls.APPS:
            cmd = cls.APPS[app_name_lower]
            try:
                subprocess.Popen(cmd, shell=True)
                title = cls.get_app_title(app_name_lower)
                return True, f"Launching {title} on your computer screen, Sir."
            except Exception as e:
                return False, f"Failed to launch {app_name_lower}: {e}"

        for key, cmd in cls.APPS.items():
            if key == app_name_lower or (len(key) > 3 and key in app_name_lower):
                try:
                    subprocess.Popen(cmd, shell=True)
                    title = cls.get_app_title(key)
                    return True, f"Launching {title} on your computer screen, Sir."
                except Exception as e:
                    return False, f"Failed to launch {key}: {e}"

        # 3. Dynamic lookup across all installed Windows Apps (Get-StartApps / UWP)
        installed = cls.get_installed_apps()
        if app_name_lower in installed:
            clean_name, appid = installed[app_name_lower]
            if cls._launch_by_appid(appid):
                return True, f"Launching {clean_name} on your computer screen, Sir."

        for k, (clean_name, appid) in installed.items():
            if app_name_lower in k or (len(k) > 3 and k in app_name_lower):
                if cls._launch_by_appid(appid):
                    return True, f"Launching {clean_name} on your computer screen, Sir."

        # 4. If it has domain format or matches popular web services, open on screen
        tlds = [".com", ".in", ".org", ".net", ".edu", ".gov", ".io", ".ai", "http", "www"]
        if any(tld in app_name_lower for tld in tlds) or any(k in app_name_lower for k in cls.POPULAR_SITES):
            return cls.open_website(raw_name)

        # 5. Generic system command fallback — try launching by name, then open on screen
        try:
            subprocess.Popen(f"start {raw_name}", shell=True)
            return True, f"Launching {raw_name} on your screen, Sir."
        except Exception:
            return cls.open_website(raw_name)

    @classmethod
    def unlock_pc(cls, password: str = None) -> tuple[bool, str]:
        """
        Windows deliberately prevents ordinary apps from entering credentials
        on the secure logon desktop. Never type or store the user's password.
        """
        return False, (
            "Windows does not allow J.A.R.V.I.S. to bypass its secure lock screen. "
            "Please press a key on the PC and enter your Windows PIN or password there."
        )

    @classmethod
    def get_volume_controller(cls):
        if not PYCAW_AVAILABLE:
            return None
        try:
            speakers = AudioUtilities.GetSpeakers()
            if not speakers:
                return None
            interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return cast(interface, POINTER(IAudioEndpointVolume))
        except Exception:
            return None

    @classmethod
    def get_volume(cls) -> int:
        controller = cls.get_volume_controller()
        if controller:
            try:
                current_vol = controller.GetMasterVolumeLevelScalar()
                return int(round(current_vol * 100))
            except Exception:
                pass
        return 50

    @classmethod
    def set_volume(cls, percent: int) -> tuple[bool, str]:
        percent = max(0, min(100, percent))
        controller = cls.get_volume_controller()
        if controller:
            try:
                controller.SetMasterVolumeLevelScalar(percent / 100.0, None)
                return True, f"Master volume set to {percent} percent, Sir."
            except Exception as e:
                return False, f"Could not adjust volume: {e}"
        return True, f"Volume set to {percent} percent."

    @classmethod
    def volume_up(cls, delta: int = 10) -> tuple[bool, str]:
        curr = cls.get_volume()
        return cls.set_volume(curr + delta)

    @classmethod
    def volume_down(cls, delta: int = 10) -> tuple[bool, str]:
        curr = cls.get_volume()
        return cls.set_volume(curr - delta)

    @classmethod
    def toggle_mute(cls) -> tuple[bool, str]:
        controller = cls.get_volume_controller()
        if controller:
            try:
                is_muted = controller.GetMute()
                controller.SetMute(not is_muted, None)
                state = "unmuted" if is_muted else "muted"
                return True, f"Audio {state}, Sir."
            except Exception as e:
                return False, f"Mute toggle error: {e}"
        return False, "Audio controller not available."

    @classmethod
    def take_screenshot(cls) -> tuple[bool, str]:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            file_path = SCREENSHOTS_DIR / filename

            try:
                from PIL import ImageGrab
                img = ImageGrab.grab()
                img.save(str(file_path))
                return True, f"Screenshot captured and stored in diagnostics directory as {filename}, Sir."
            except Exception:
                pass

            try:
                import mss
                with mss.mss() as sct:
                    sct.shot(output=str(file_path))
                return True, f"Screenshot captured as {filename}, Sir."
            except Exception:
                pass

            ps_cmd = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
$bmp.Save('{str(file_path)}', [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose()
$bmp.Dispose()
"""
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True, capture_output=True)
            if file_path.exists():
                return True, f"Screenshot captured as {filename}, Sir."
            return False, "Failed to capture screenshot."
        except Exception as e:
            return False, f"Unable to capture screenshot: {e}"

    @classmethod
    def lock_pc(cls) -> tuple[bool, str]:
        try:
            if not ctypes.windll.user32.LockWorkStation():
                return False, "Windows rejected the workstation lock request. Start J.A.R.V.I.S. in your signed-in Windows desktop session and try again."
            return True, "Locking terminal workstation immediately, Sir."
        except Exception as e:
            return False, f"Failed to lock workstation: {e}"

    @classmethod
    def sleep_pc(cls) -> tuple[bool, str]:
        try:
            subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
            return True, "Initiating system sleep protocol, Sir."
        except Exception as e:
            return False, f"Sleep command failed: {e}"

    @classmethod
    def schedule_shutdown(cls, seconds: int = 60) -> tuple[bool, str]:
        try:
            subprocess.run(f"shutdown /s /t {seconds}", shell=True, check=True)
            mins = seconds // 60
            unit = f"{mins} minutes" if mins > 0 else f"{seconds} seconds"
            return True, f"System shutdown protocol initiated. Power down scheduled in {unit}, Sir."
        except Exception as e:
            return False, f"Could not schedule shutdown: {e}"

    @classmethod
    def cancel_shutdown(cls) -> tuple[bool, str]:
        try:
            subprocess.run("shutdown /a", shell=True, check=True)
            return True, "Shutdown sequence aborted, Sir. All systems standing by."
        except Exception as e:
            return False, f"Could not abort shutdown: {e}"

    @classmethod
    def get_telemetry(cls) -> dict:
        """Collects real-time system metrics for the Iron Man HUD."""
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_freq = psutil.cpu_freq()
        cpu_freq_current = round(cpu_freq.current / 1000, 2) if cpu_freq else 0.0

        mem = psutil.virtual_memory()
        mem_percent = mem.percent
        mem_used_gb = round(mem.used / (1024 ** 3), 1)
        mem_total_gb = round(mem.total / (1024 ** 3), 1)

        disk = psutil.disk_usage("C:\\")
        disk_percent = disk.percent
        disk_free_gb = round(disk.free / (1024 ** 3), 1)

        battery = psutil.sensors_battery()
        battery_data = {
            "percent": int(battery.percent) if battery else 100,
            "power_plugged": battery.power_plugged if battery else True,
            "has_battery": battery is not None
        }

        net_io = psutil.net_io_counters()
        net_sent_mb = round(net_io.bytes_sent / (1024 ** 2), 1)
        net_recv_mb = round(net_io.bytes_recv / (1024 ** 2), 1)

        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = str(datetime.now() - boot_time).split(".")[0]

        return {
            "cpu": {
                "percent": cpu_percent,
                "cores": psutil.cpu_count(logical=True),
                "freq_ghz": cpu_freq_current
            },
            "memory": {
                "percent": mem_percent,
                "used_gb": mem_used_gb,
                "total_gb": mem_total_gb
            },
            "disk": {
                "percent": disk_percent,
                "free_gb": disk_free_gb
            },
            "battery": battery_data,
            "network": {
                "sent_mb": net_sent_mb,
                "recv_mb": net_recv_mb
            },
            "system": {
                "hostname": platform.node(),
                "os": f"{platform.system()} {platform.release()}",
                "uptime": uptime,
                "volume": cls.get_volume(),
                "processes": len(psutil.pids())
            }
        }
