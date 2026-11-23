"""Manage J.A.R.V.I.S. local and optional public access links."""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def get_local_ip() -> str:
    """Return the preferred LAN address, falling back to loopback."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("1.1.1.1", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def _tailscale_exe() -> str | None:
    located = shutil.which("tailscale")
    if located:
        return located
    for candidate in (
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tailscale" / "tailscale.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Tailscale" / "tailscale.exe",
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def _run_tailscale(exe: str, *args: str, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout, check=False)


def _save_public_url(url: str) -> None:
    (ROOT / "public_url.txt").write_text(url + "\n", encoding="utf-8")
    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    path = data_dir / "public_links.json"
    try:
        contents = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        contents = {}
    contents["public_url"] = url
    contents["provider"] = "cloudflare-quick"
    path.write_text(json.dumps(contents, indent=2), encoding="utf-8")


def get_active_links() -> dict[str, str]:
    """Return current local and public links for the HUD settings panel."""
    from core.config import Config

    port = Config.get_port()
    public_url = ""
    path = ROOT / "data" / "public_links.json"
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved.get("provider") == "cloudflare-quick":
            public_url = str(saved.get("public_url", ""))
    except (OSError, json.JSONDecodeError):
        pass
    return {
        "localhost": f"http://localhost:{port}",
        "local_network": f"http://{get_local_ip()}:{port}",
        "public_url": public_url,
    }


def _start_cloudflare_tunnel(port: int) -> None:
    exe = ROOT / "cloudflared.exe"
    if not exe.is_file():
        print("[JARVIS] Public link unavailable: cloudflared.exe is missing from the J.A.R.V.I.S. folder.")
        return
    try:
        process = subprocess.Popen(
            [str(exe), "tunnel", "--url", f"http://127.0.0.1:{port}"],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        for line in process.stdout or ():
            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
            if match:
                url = match.group(0)
                _save_public_url(url)
                print(f"[JARVIS] Temporary public link: {url}")
                print("[JARVIS] This random link works while this PC, J.A.R.V.I.S., and the tunnel stay running.")
                # Continue draining output so the tunnel process remains healthy.
                for _ in process.stdout:
                    pass
                return
            if line.strip():
                print(f"[Cloudflare] {line.strip()}")
        if process.poll() is not None:
            print(f"[JARVIS] Cloudflare tunnel exited with code {process.returncode}.")
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"[JARVIS] Could not start Cloudflare tunnel: {exc}")


def start_public_tunnel(port: int) -> None:
    """Start a no-account Cloudflare Quick Tunnel in the background."""
    threading.Thread(target=_start_cloudflare_tunnel, args=(port,), daemon=True, name="jarvis-cloudflare-tunnel").start()
