import os
import re
import json
import shutil
import subprocess
import urllib.request
import urllib.parse
import urllib.error
import zipfile
import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from core.config import BASE_DIR, Config

# ─── ADB paths (kept for legacy fallback only) ───────────────────────────────
TOOLS_DIR = BASE_DIR / "tools"
PLATFORM_TOOLS_DIR = TOOLS_DIR / "platform-tools"
LOCAL_ADB_PATH = PLATFORM_TOOLS_DIR / "adb.exe"


class PhoneControl:
    """
    J.A.R.V.I.S. Mobile Uplink — Zero-Setup Android Controller
    ============================================================
    Unlocks and controls your Android phone WITHOUT ADB or Developer Options.

    Priority order (auto-selects best available method):
    ┌─────────────────────────────────────────────────────────────────────┐
    │ METHOD 1 · HTTP Webhook   ← MacroDroid / Tasker / Automate / IFTTT │
    │ METHOD 2 · KDE Connect    ← KDE Connect app (Wi-Fi, no dev options) │
    │ METHOD 3 · ADB (fallback) ← Requires Developer Options on phone    │
    └─────────────────────────────────────────────────────────────────────┘

    ── QUICK SETUP (Method 1 — Recommended) ─────────────────────────────
    1. Install "MacroDroid" from Google Play (free, no root needed)
    2. Open MacroDroid → Add Macro
    3. TRIGGER  → "Webhook" → note the webhook URL it generates
    4. ACTIONS  →
         a. "Device Actions" → "Wake Screen / Turn On Screen"
         b. (optional) "UI Interaction" → "Enter Text" → [your PIN]
         c. (optional) "UI Interaction" → "Simulate Key" → Enter/OK
    5. Save the macro as "jarvis_unlock" (or anything you like)
    6. In J.A.R.V.I.S. settings (or .env), save:
         JARVIS_PHONE_WEBHOOK_URL = <the webhook URL from step 3>
         JARVIS_PHONE_PIN         = <your PIN>  (optional, for display)

    ── QUICK SETUP (Method 2 — KDE Connect) ─────────────────────────────
    1. Install "KDE Connect" on Android (Google Play / F-Droid, free)
    2. Install "KDE Connect" on Windows  (https://kdeconnect.kde.org)
    3. Open both apps → pair your phone with your PC over Wi-Fi
    4. J.A.R.V.I.S. auto-detects paired devices — no extra config needed
    """

    _cached_status: Optional[Dict[str, Any]] = None
    _cached_time: float = 0.0

    # ═══════════════════════════════════════════════════════════════════════════
    # INTERNAL HELPERS
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _silent_startupinfo():
        """Returns a STARTUPINFO that hides any console window on Windows."""
        if os.name != "nt":
            return None
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        return si

    @staticmethod
    def _run_silent(cmd: list, timeout: int = 10) -> Tuple[bool, str]:
        """Run a subprocess silently and return (success, output)."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                startupinfo=PhoneControl._silent_startupinfo(),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            out = (result.stdout + result.stderr).strip()
            return result.returncode == 0, out
        except subprocess.TimeoutExpired:
            return False, "Command timed out."
        except Exception as e:
            return False, str(e)

    # ═══════════════════════════════════════════════════════════════════════════
    # METHOD DETECTION
    # ═══════════════════════════════════════════════════════════════════════════

    @classmethod
    def get_active_method(cls) -> str:
        """
        Returns the best available unlock method as a string:
        'webhook' | 'kde_connect' | 'adb' | 'none'
        """
        if Config.get("JARVIS_PHONE_WEBHOOK_URL", "").strip():
            return "webhook"
        if cls._kde_connect_path():
            return "kde_connect"
        if cls.get_adb_path():
            return "adb"
        return "none"

    @classmethod
    def get_method_label(cls) -> str:
        """Human-readable label for the active connection method."""
        labels = {
            "webhook":     "HTTP Webhook (MacroDroid / Tasker)",
            "kde_connect": "KDE Connect (Wi-Fi)",
            "adb":         "ADB Bridge (Developer Mode)",
            "none":        "Not Configured",
        }
        return labels.get(cls.get_active_method(), "Unknown")

    # ═══════════════════════════════════════════════════════════════════════════
    # METHOD 1 · HTTP WEBHOOK  (MacroDroid / Tasker / Automate / IFTTT)
    # ═══════════════════════════════════════════════════════════════════════════

    @classmethod
    def _webhook_request(cls, url: str, payload: dict, timeout: int = 8) -> Tuple[bool, int]:
        """
        Sends a POST request with JSON payload, falls back to GET with
        query-string parameters.  Returns (success, http_status_code).
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "JARVIS-Mobile-Uplink/2.0",
        }
        body = json.dumps(payload).encode("utf-8")

        # ── POST attempt ──────────────────────────────────────────────────────
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return True, resp.status
        except urllib.error.HTTPError as e:
            # 4xx / 5xx still means the server was reached
            if e.code < 500:
                return True, e.code
        except Exception:
            pass  # network error — try GET

        # ── GET fallback (some simple webhooks only accept GET) ────────────────
        try:
            qs = urllib.parse.urlencode({k: v for k, v in payload.items() if v})
            get_url = f"{url}?{qs}" if qs else url
            req = urllib.request.Request(
                get_url, headers={"User-Agent": "JARVIS-Mobile-Uplink/2.0"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return True, resp.status
        except urllib.error.HTTPError as e:
            return True, e.code
        except Exception as e:
            return False, 0

    @classmethod
    def _unlock_via_webhook(cls, pin: Optional[str] = None) -> Tuple[bool, str]:
        """
        Triggers unlock by calling the configured phone webhook.
        Supports MacroDroid, Tasker (HTTP Request plugin), Automate,
        IFTTT Webhooks, and any custom HTTP endpoint.
        """
        user_name = Config.get_user_name()
        webhook_url = Config.get("JARVIS_PHONE_WEBHOOK_URL", "").strip()

        if not webhook_url:
            return False, f"No phone webhook URL configured, {user_name}."

        passcode = pin or Config.get("JARVIS_PHONE_PIN", "").strip()
        payload = {
            "action": "unlock",
            "pin":    passcode,
            "value1": passcode,   # IFTTT compatibility key
        }

        success, status = cls._webhook_request(webhook_url, payload)

        if success and status in (200, 201, 202, 204):
            if passcode:
                return True, (
                    f"Unlock command dispatched to your mobile device, {user_name}. "
                    "Screen activating and PIN entered via your automation workflow."
                )
            return True, (
                f"Wake signal sent to your mobile device, {user_name}. "
                "Screen should be active momentarily."
            )

        if success and status != 0:
            return False, (
                f"Webhook responded with HTTP {status}, {user_name}. "
                "Check that your MacroDroid / Tasker macro is active and the URL is correct."
            )

        return False, (
            f"Could not reach your phone webhook, {user_name}. "
            "Ensure both your PC and phone are on the same Wi-Fi network "
            "and that the MacroDroid / Tasker server is running."
        )

    @classmethod
    def _lock_via_webhook(cls) -> Tuple[bool, str]:
        """Sends a lock action to the configured webhook."""
        user_name = Config.get_user_name()
        webhook_url = Config.get("JARVIS_PHONE_LOCK_WEBHOOK_URL",
                                 Config.get("JARVIS_PHONE_WEBHOOK_URL", "")).strip()

        if not webhook_url:
            return False, f"No phone webhook URL configured, {user_name}."

        payload = {"action": "lock", "value1": "lock"}
        success, status = cls._webhook_request(webhook_url, payload)

        if success and status in (200, 201, 202, 204):
            return True, f"Lock command dispatched to your mobile device, {user_name}."
        return False, (
            f"Could not send lock command to phone webhook (HTTP {status}), {user_name}."
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # METHOD 2 · KDE CONNECT  (no Developer Options required)
    # ═══════════════════════════════════════════════════════════════════════════

    @classmethod
    def _kde_connect_path(cls) -> Optional[str]:
        """
        Locates kdeconnect-cli on Windows.  KDE Connect for Windows can be
        downloaded from https://kdeconnect.kde.org/download.html
        """
        candidates = [
            shutil.which("kdeconnect-cli"),
            r"C:\Program Files\KDE Connect\kdeconnect-cli.exe",
            r"C:\Program Files (x86)\KDE Connect\kdeconnect-cli.exe",
            str(
                Path(os.environ.get("LOCALAPPDATA", ""))
                / "Programs"
                / "KDE Connect"
                / "kdeconnect-cli.exe"
            ),
            str(
                Path(os.environ.get("APPDATA", ""))
                / "KDE Connect"
                / "kdeconnect-cli.exe"
            ),
        ]
        for c in candidates:
            if c and Path(c).exists():
                return c
        return None

    @classmethod
    def _kde_run(cls, args: list, timeout: int = 10) -> Tuple[bool, str]:
        """Executes a kdeconnect-cli command."""
        cli = cls._kde_connect_path()
        if not cli:
            return False, "kdeconnect-cli not found."
        return cls._run_silent([cli] + args, timeout=timeout)

    @classmethod
    def _kde_get_device_id(cls) -> Optional[str]:
        """Returns the first reachable paired KDE Connect device ID."""
        # Prefer device explicitly set in config
        cfg_id = Config.get("JARVIS_KDE_DEVICE_ID", "").strip()
        if cfg_id:
            return cfg_id

        # Try available (reachable) devices first
        for flag in ("--list-available", "--list-devices"):
            ok, out = cls._kde_run([flag, "--id-only"])
            if ok and out.strip():
                first = out.strip().splitlines()[0].strip()
                if first:
                    return first
        return None

    @classmethod
    def _unlock_via_kde_connect(cls, pin: Optional[str] = None) -> Tuple[bool, str]:
        """
        Wakes and unlocks the phone via KDE Connect.

        Uses the "Run Command" plugin to execute a shell command on Android
        that wakes the screen.  If the "Remote Keyboard" plugin is enabled,
        it also types the PIN.

        NOTE: KDE Connect's "Run Command" plugin lets you pre-register shell
        commands on the phone side.  Register a command called 'unlock' that
        runs:  input keyevent 224 && input keyevent 82
        Then J.A.R.V.I.S. will call it automatically.
        """
        user_name = Config.get_user_name()
        dev_id = cls._kde_get_device_id()

        if not dev_id:
            return False, (
                f"No paired KDE Connect device found, {user_name}. "
                "Please open KDE Connect on your phone and PC and complete pairing."
            )

        passcode = pin or Config.get("JARVIS_PHONE_PIN", "").strip()
        d_arg = ["--device", dev_id]

        # ── 1. Try registered "unlock" remote command ─────────────────────────
        ok, _ = cls._kde_run(d_arg + ["--execute-command", "unlock"])

        # ── 2. Fallback: ring the phone (wakes screen as side-effect) ─────────
        if not ok:
            cls._kde_run(d_arg + ["--ring"])

        # ── 3. Send PIN keystrokes via Remote Keyboard plugin ─────────────────
        if passcode:
            time.sleep(1.8)   # wait for lockscreen to appear
            for ch in passcode:
                cls._kde_run(d_arg + ["--send-keys", ch])
                time.sleep(0.06)
            cls._kde_run(d_arg + ["--send-keys", "\n"])
            return True, (
                f"Wake signal and PIN dispatched via KDE Connect, {user_name}. "
                "Your mobile device should be unlocked."
            )

        return True, (
            f"Wake signal sent to your mobile device via KDE Connect, {user_name}. "
            "Swipe or enter your PIN to finish unlocking."
        )

    @classmethod
    def _lock_via_kde_connect(cls) -> Tuple[bool, str]:
        """Locks the phone screen via KDE Connect."""
        user_name = Config.get_user_name()
        dev_id = cls._kde_get_device_id()
        if not dev_id:
            return False, f"No paired KDE Connect device found, {user_name}."

        d_arg = ["--device", dev_id]
        # Try registered "lock" remote command, then KEYCODE_POWER via remote keyboard
        ok, _ = cls._kde_run(d_arg + ["--execute-command", "lock"])
        if not ok:
            cls._kde_run(d_arg + ["--send-keys", "\x1b"])   # best-effort

        return True, f"Lock command issued to your mobile device via KDE Connect, {user_name}."

    # ═══════════════════════════════════════════════════════════════════════════
    # METHOD 3 · ADB BRIDGE  (legacy fallback — requires Developer Options)
    # ═══════════════════════════════════════════════════════════════════════════

    @classmethod
    def get_adb_path(cls) -> Optional[str]:
        """Locates the ADB executable from local tools, PATH, or Android SDK."""
        custom_adb = Config.get("ADB_PATH", "").strip()
        if custom_adb and os.path.exists(custom_adb):
            return custom_adb
        if LOCAL_ADB_PATH.exists():
            return str(LOCAL_ADB_PATH)
        which_adb = shutil.which("adb")
        if which_adb:
            return which_adb
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            sdk = Path(local_app_data) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
            if sdk.exists():
                return str(sdk)
        prog_files = os.environ.get("ProgramFiles", "")
        if prog_files:
            sdk = Path(prog_files) / "Android" / "platform-tools" / "adb.exe"
            if sdk.exists():
                return str(sdk)
        return None

    @classmethod
    def ensure_adb(cls) -> Tuple[bool, str]:
        """Ensures ADB is available, downloading official Google binaries if missing."""
        adb_path = cls.get_adb_path()
        if adb_path:
            return True, adb_path
        try:
            TOOLS_DIR.mkdir(parents=True, exist_ok=True)
            zip_url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
            zip_path = TOOLS_DIR / "platform-tools.zip"
            print("[PhoneControl] Downloading official Android platform-tools...")
            urllib.request.urlretrieve(zip_url, str(zip_path))
            print("[PhoneControl] Extracting Android platform-tools...")
            with zipfile.ZipFile(str(zip_path), "r") as zf:
                zf.extractall(str(TOOLS_DIR))
            if zip_path.exists():
                zip_path.unlink()
            if LOCAL_ADB_PATH.exists():
                return True, str(LOCAL_ADB_PATH)
            return False, "ADB extraction finished but adb.exe was not found."
        except Exception as e:
            return False, f"Failed to auto-download Android platform-tools: {e}"

    @classmethod
    def run_adb(cls, args: list, timeout: int = 10) -> Tuple[bool, str]:
        """Executes an ADB command and returns (success, output)."""
        adb_path = cls.get_adb_path()
        if not adb_path:
            ok, msg = cls.ensure_adb()
            if not ok:
                return False, f"ADB not available: {msg}"
            adb_path = msg
        ok, out = cls._run_silent([adb_path] + args, timeout=timeout)
        return ok, out

    @classmethod
    def get_devices(cls) -> list:
        """Returns a list of connected ADB devices and their states."""
        success, out = cls.run_adb(["devices", "-l"])
        if not success:
            return []
        devices = []
        for line in out.splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                dev_id, status = parts[0], parts[1]
                model = "Unknown Device"
                for p in parts[2:]:
                    if p.startswith("model:"):
                        model = p.split(":", 1)[1].replace("_", " ")
                    elif p.startswith("device:") and model == "Unknown Device":
                        model = p.split(":", 1)[1]
                devices.append({"id": dev_id, "status": status, "model": model, "raw": line})
        return devices

    @classmethod
    def _unlock_via_adb(cls, pin: Optional[str] = None) -> Tuple[bool, str]:
        """Unlocks phone over ADB (requires USB Debugging / Developer Options)."""
        user_name = Config.get_user_name()
        devices = cls.get_devices()

        if not devices:
            phone_ip = Config.get("JARVIS_PHONE_IP", "").strip()
            if phone_ip:
                cls.connect_wireless(phone_ip)
                devices = cls.get_devices()

        if not devices:
            return False, (
                f"No mobile device detected via ADB bridge, {user_name}. "
                "ADB requires Developer Options and USB Debugging enabled on your phone. "
                "For a no-setup alternative, configure a MacroDroid webhook "
                "or install KDE Connect."
            )

        active = next((d for d in devices if d["status"] == "device"), None)
        if not active:
            unauth = next((d for d in devices if d["status"] == "unauthorized"), None)
            if unauth:
                return False, (
                    f"Device ({unauth['model']}) is connected but unauthorized, {user_name}. "
                    "Tap 'Always allow from this computer' on your phone screen."
                )
            return False, f"Mobile device is in '{devices[0]['status']}' state, {user_name}."

        dev_id = active["id"]
        d = ["-s", dev_id]

        # Adaptive swipe geometry
        width, height = 1080, 2400
        ok, dim = cls.run_adb(d + ["shell", "wm", "size"])
        if ok and dim:
            m = re.search(r"(\d+)x(\d+)", dim)
            if m:
                width, height = int(m.group(1)), int(m.group(2))
        cx = width // 2
        sy, ey = int(height * 0.82), int(height * 0.22)

        cls.run_adb(d + ["shell", "input", "keyevent", "224"])      # WAKEUP
        time.sleep(0.4)
        cls.run_adb(d + ["shell", "wm", "dismiss-keyguard"])
        time.sleep(0.3)
        cls.run_adb(d + ["shell", "input", "keyevent", "82"])        # MENU
        cls.run_adb(d + ["shell", "input", "swipe",
                         str(cx), str(sy), str(cx), str(ey), "280"]) # swipe up
        time.sleep(0.5)

        passcode = pin or Config.get("JARVIS_PHONE_PIN", "").strip()
        if passcode:
            cls.run_adb(d + ["shell", "input", "text", passcode])
            time.sleep(0.2)
            cls.run_adb(d + ["shell", "input", "keyevent", "66"])    # ENTER
            time.sleep(0.1)
            cls.run_adb(d + ["shell", "input", "keyevent", "160"])   # NUMPAD_ENTER
            return True, (
                f"Mobile security bypassed via ADB. Screen activated and PIN entered "
                f"for {active['model']}, {user_name}."
            )

        return True, (
            f"{active['model']} awakened and lockscreen dismissed via ADB, {user_name}. "
            "Enter your PIN if required."
        )

    @classmethod
    def _lock_via_adb(cls) -> Tuple[bool, str]:
        """Locks the phone via ADB (KEYCODE_POWER)."""
        user_name = Config.get_user_name()
        devices = cls.get_devices()
        active = next((d for d in devices if d["status"] == "device"), None)
        if not active:
            return False, f"No connected ADB device found to lock, {user_name}."
        cls.run_adb(["-s", active["id"], "shell", "input", "keyevent", "26"])
        return True, f"Mobile device locked and screen secured via ADB, {user_name}."

    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLIC API — UNIFIED UNLOCK / LOCK  (auto-selects best method)
    # ═══════════════════════════════════════════════════════════════════════════

    @classmethod
    def unlock_phone(cls, pin: Optional[str] = None) -> Tuple[bool, str]:
        """
        Wakes and unlocks the connected Android phone.
        Automatically uses the best available method (Webhook → KDE Connect → ADB).
        No ADB or Developer Options required when Webhook or KDE Connect is configured.
        """
        user_name = Config.get_user_name()
        method = cls.get_active_method()

        if method == "webhook":
            return cls._unlock_via_webhook(pin)

        if method == "kde_connect":
            return cls._unlock_via_kde_connect(pin)

        if method == "adb":
            return cls._unlock_via_adb(pin)

        # ── Nothing configured — give clear guidance ──────────────────────────
        return False, (
            f"No phone connection method is configured, {user_name}. "
            "To unlock your phone without ADB or Developer Options, choose one: "
            "Option 1 — Install MacroDroid on your phone, create an Unlock webhook macro, "
            "and save the webhook URL in J.A.R.V.I.S. settings as the Phone Webhook URL. "
            "Option 2 — Install KDE Connect on both your phone and this PC, then pair them."
        )

    @classmethod
    def lock_phone(cls) -> Tuple[bool, str]:
        """
        Locks the connected Android phone.
        Automatically uses the best available method (Webhook → KDE Connect → ADB).
        """
        user_name = Config.get_user_name()
        method = cls.get_active_method()

        if method == "webhook":
            return cls._lock_via_webhook()
        if method == "kde_connect":
            return cls._lock_via_kde_connect()
        if method == "adb":
            return cls._lock_via_adb()

        return False, f"No phone connection method is configured, {user_name}."

    # ═══════════════════════════════════════════════════════════════════════════
    # STATUS & TELEMETRY
    # ═══════════════════════════════════════════════════════════════════════════

    @classmethod
    def get_battery_level(cls, device_id: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves battery telemetry via ADB (requires ADB connection)."""
        cmd = []
        if device_id:
            cmd.extend(["-s", device_id])
        cmd.extend(["shell", "dumpsys", "battery"])
        success, out = cls.run_adb(cmd)
        if not success:
            return {"level": None, "charging": False}
        level, charging = None, False
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("level:"):
                try:
                    level = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("status:"):
                charging = line.split(":", 1)[1].strip() in ("2", "5")
            elif any(line.startswith(p) for p in ("AC powered:", "USB powered:", "Wireless powered:")):
                if "true" in line.lower():
                    charging = True
        return {"level": level, "charging": charging}

    @classmethod
    def get_status(cls, force: bool = False) -> Dict[str, Any]:
        """
        Returns the current connection status of the mobile uplink.
        Works for all methods; battery telemetry requires ADB.
        """
        if not force and cls._cached_status and (time.time() - cls._cached_time < 3.0):
            return cls._cached_status

        user_name = Config.get_user_name()
        method = cls.get_active_method()

        # ── Webhook / KDE Connect — report as "configured but unmonitored" ────
        if method == "webhook":
            res = {
                "installed": True,
                "connected": True,
                "device_id": None,
                "model": "Android Device (Webhook)",
                "status": "webhook",
                "battery": None,
                "charging": False,
                "message": (
                    f"Mobile uplink active via HTTP Webhook, {user_name}. "
                    "Battery telemetry is unavailable without ADB."
                ),
            }
            cls._cached_status = res
            cls._cached_time = time.time()
            return res

        if method == "kde_connect":
            dev_id = cls._kde_get_device_id()
            res = {
                "installed": True,
                "connected": bool(dev_id),
                "device_id": dev_id,
                "model": "Android Device (KDE Connect)",
                "status": "kde_connect",
                "battery": None,
                "charging": False,
                "message": (
                    f"Mobile uplink active via KDE Connect, {user_name}. "
                    "Battery telemetry is unavailable without ADB."
                ) if dev_id else f"KDE Connect is installed but no paired device found, {user_name}.",
            }
            cls._cached_status = res
            cls._cached_time = time.time()
            return res

        # ── ADB path ─────────────────────────────────────────────────────────
        if not cls.get_adb_path():
            res = {
                "installed": False, "connected": False,
                "device_id": None, "model": None, "status": "no_method",
                "message": (
                    f"No phone connection method configured, {user_name}. "
                    "Set up MacroDroid webhook or KDE Connect."
                ),
            }
            cls._cached_status = res
            cls._cached_time = time.time()
            return res

        devices = cls.get_devices()
        if not devices:
            res = {
                "installed": True, "connected": False,
                "device_id": None, "model": None, "status": "disconnected",
                "message": f"No mobile device detected via ADB, {user_name}.",
            }
            cls._cached_status = res
            cls._cached_time = time.time()
            return res

        active = next((d for d in devices if d["status"] == "device"), None)
        if not active:
            unauth = next((d for d in devices if d["status"] == "unauthorized"), None)
            if unauth:
                res = {
                    "installed": True, "connected": False,
                    "device_id": unauth["id"], "model": unauth["model"],
                    "status": "unauthorized",
                    "message": (
                        f"Device ({unauth['model']}) detected but unauthorized, {user_name}. "
                        "Tap 'Allow USB Debugging' on your phone."
                    ),
                }
            else:
                dev = devices[0]
                res = {
                    "installed": True, "connected": False,
                    "device_id": dev["id"], "model": dev["model"],
                    "status": dev["status"],
                    "message": f"Mobile device is in '{dev['status']}' state, {user_name}.",
                }
            cls._cached_status = res
            cls._cached_time = time.time()
            return res

        battery_info = cls.get_battery_level(active["id"])
        res = {
            "installed": True, "connected": True,
            "device_id": active["id"], "model": active["model"],
            "status": "connected",
            "battery": battery_info.get("level"),
            "charging": battery_info.get("charging", False),
            "message": f"{active['model']} is online and connected via ADB, {user_name}.",
        }
        cls._cached_status = res
        cls._cached_time = time.time()
        return res

    @classmethod
    def get_phone_battery_report(cls) -> Tuple[bool, str]:
        """Provides a spoken battery report."""
        user_name = Config.get_user_name()
        status = cls.get_status()
        if not status.get("connected"):
            return False, status.get("message", f"Phone is not connected, {user_name}.")
        bat = status.get("battery")
        charging = status.get("charging")
        model = status.get("model", "Your phone")
        if bat is not None:
            state = "currently charging" if charging else "running on battery reserves"
            return True, f"{model} battery is at {bat} percent and {state}, {user_name}."
        return True, (
            f"{model} is connected via {cls.get_method_label()}, "
            f"but battery telemetry requires ADB, {user_name}."
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # WIRELESS ADB (legacy helpers — kept for backward compatibility)
    # ═══════════════════════════════════════════════════════════════════════════

    @classmethod
    def connect_wireless(cls, ip: str, port: int = 5555) -> Tuple[bool, str]:
        """Connects to an Android phone over Wi-Fi via ADB (requires Developer Options)."""
        user_name = Config.get_user_name()
        target = f"{ip}:{port}" if ":" not in ip else ip
        success, out = cls.run_adb(["connect", target])
        if success and "connected to" in out.lower():
            Config.update_setting("JARVIS_PHONE_IP", ip.split(":")[0])
            return True, f"Wireless ADB uplink established with {target}, {user_name}."
        return False, f"Failed to connect to {target} via ADB: {out}"

    @classmethod
    def enable_tcpip(cls, port: int = 5555) -> Tuple[bool, str]:
        """Enables ADB TCP/IP mode on a currently USB-connected phone."""
        user_name = Config.get_user_name()
        success, out = cls.run_adb(["tcpip", str(port)])
        if success:
            return True, (
                f"ADB TCP/IP port {port} opened, {user_name}. "
                "You may now disconnect USB and connect wirelessly."
            )
        return False, f"Could not enable ADB TCP/IP mode: {out}"

    # ═══════════════════════════════════════════════════════════════════════════
    # WEBHOOK / KDE CONFIG HELPERS
    # ═══════════════════════════════════════════════════════════════════════════

    @classmethod
    def set_webhook_url(cls, url: str) -> Tuple[bool, str]:
        """Saves the phone unlock webhook URL to config."""
        user_name = Config.get_user_name()
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            return False, f"Invalid URL — must start with http:// or https://, {user_name}."
        Config.update_setting("JARVIS_PHONE_WEBHOOK_URL", url)
        return True, (
            f"Phone webhook URL saved successfully, {user_name}. "
            "J.A.R.V.I.S. will now use it to unlock your phone without ADB."
        )
