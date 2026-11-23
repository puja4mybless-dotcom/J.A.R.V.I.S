"""
J.A.R.V.I.S. (Just A Rather Very Intelligent System) - Desktop Launcher
Starts the FastAPI backend and launches the futuristic HUD in dedicated App mode.
"""

import os
import sys
import time
import webbrowser
import subprocess
import uvicorn
from threading import Thread
from pathlib import Path
from core.config import Config

BANNER = r"""
       __      ___      .______     ____    ____  __       _______.
      |  |    /   \     |   _  \    \   \  /   / |  |     /       |
      |  |   /  ^  \    |  |_)  |    \   \/   /  |  |    |   (----`
.--.  |  |  /  /_\  \   |      /      \      /   |  |     \   \    
|  `--'  | /  _____  \  |  |\  \----.  \    /    |  | .----)   |   
 \______/ /__/     \__\ | _| `._____|   \__/     |__| |_______/    
 
              [ STARK INDUSTRIES - MARK VII ONLINE ]
"""

def find_browser_app_cmd(url: str):
    """
    Looks for Microsoft Edge or Google Chrome to launch in clean frameless --app mode.
    """
    candidates = [
        # Microsoft Edge (Standard on Windows 10/11)
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        # Google Chrome
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]

    for exe in candidates:
        if os.path.exists(exe):
            return f'"{exe}" --app={url}'
    
    return None

def launch_browser(url: str):
    time.sleep(1.2)  # Give server a moment to bind
    app_cmd = find_browser_app_cmd(url)
    if app_cmd:
        try:
            print(f"[JARVIS Launcher] Opening HUD in dedicated window mode...")
            subprocess.Popen(app_cmd, shell=True)
            return
        except Exception as e:
            print(f"[JARVIS Launcher] App-mode launch failed: {e}")

    # Fallback to default browser
    print(f"[JARVIS Launcher] Opening in default web browser: {url}")
    webbrowser.open(url)

def main():
    print(BANNER)
    host = Config.get_host()
    port = Config.get_port()
    url = f"http://{host}:{port}"

    print(f"[JARVIS] Initializing core neural systems...")
    print(f"[JARVIS] User Honorific: {Config.get_user_name()}")
    print(f"[JARVIS] Voice Persona: {Config.get_voice()}")

    from core.tunnel_manager import get_local_ip, start_public_tunnel
    local_ip = get_local_ip()
    print("-" * 65)
    print("🌐 J.A.R.V.I.S. MULTI-DEVICE ACCESS LINKS:")
    print(f"  1. This PC:                http://localhost:{port}")
    print(f"  2. Any PC on Same Wi-Fi:   http://{local_ip}:{port}")
    print("  3. Public link:             Preparing Cloudflare Quick Tunnel...")
    print("-" * 65)

    # Launch the temporary Cloudflare Quick Tunnel in background.
    start_public_tunnel(port)

    print("[JARVIS] Press CTRL+C at any time in this console to shut down.\n")

    # Start browser launcher thread
    browser_thread = Thread(target=launch_browser, args=(url,), daemon=True)
    browser_thread.start()

    # Start Uvicorn Server
    try:
        uvicorn.run("server:app", host=host, port=port, log_level="info", reload=True)
    except KeyboardInterrupt:
        print("\n[JARVIS] Powering down Mark VII subroutines. Goodbye, Sir.")

if __name__ == "__main__":
    main()
