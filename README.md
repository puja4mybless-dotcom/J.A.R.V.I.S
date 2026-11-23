# J.A.R.V.I.S. (Just A Rather Very Intelligent System) - Mark VII

> **"Welcome back, Sir. All systems are online and operational."**

An Iron Man-inspired desktop AI assistant with a holographic Arc Reactor HUD, real-time Windows system telemetry, voice synthesis with MCU-authentic British neural voices, speech recognition, desktop automation, and multi-model AI reasoning (Google Gemini, Groq, OpenAI, or 100% offline intelligence).

---

## ⚡ Highlights & Capabilities

- 🌐 **Knowledge and Search Tools (`OmniKnowledgeEngine`)**:
  - Dictionary definitions, unit conversions, current currency rates and news feeds, encyclopedia references, and Groq browser search for factual questions when a Groq API key is configured.
  - **Dictionary Definitions**: Instant dictionary lexicon definitions and sentence examples (e.g. `"Define serendipity"`).
  - **Currency & Unit Conversions**: Real-time foreign exchange conversions (e.g. `"Convert 100 USD to EUR"`) and metric/imperial conversions (e.g. `"50 miles to km"`).
  - **Breaking Global News**: Real-time satellite news feeds on any topic (e.g. `"Latest news about artificial intelligence"`).
  - **Conversational Memory**: Retains multi-turn dialogue context so follow-up inquiries understand who or what you are referring to.
- 🌀 **Interactive Holographic Arc Reactor HUD**: Animated 60 FPS Canvas Arc Reactor with spinning mechanical rings, plasma particles, and audio-reactive waveform visualizer.
- 🗣️ **Iconic JARVIS Neural Voice**: Powered by Microsoft Edge Neural TTS with high-definition British male voice (`en-GB-RyanNeural` or `en-GB-ThomasNeural`), with instant audio cache and speech replay.
- 🎙️ **Real-Time Voice & Speech Recognition**: Continuous listening or push-to-talk microphone interface with instant transcription.
- 📊 **Live System Telemetry**: Real-time WebSocket monitoring of Central CPU load, RAM allocation, auxiliary battery reserves & charging state, Drive C: storage, and network I/O.
- 💻 **Complete Windows Automation**:
  - **App Launcher**: Open Chrome, Edge, Spotify, VS Code, Calculator, Notepad, Task Manager, Command Prompt, Explorer, etc.
  - **Master Volume**: Set exact volume percentage, volume up/down, mute/unmute.
  - **Power Controls**: Screen lock (`LockWorkStation`), sleep, timed shutdown, shutdown abort. Windows unlock requires entering the PIN/password at the PC.
  - **Screen Capture**: Instant desktop screenshots saved to `screenshots/`.
- 🧠 **Multi-Engine Intelligence**:
  - **Built-in Offline Intelligence**: Functions out of the box with zero setup, zero API keys, and offline MCU wit and command execution.
  - **Cloud LLM Support**: Configure Google Gemini (`gemini-3.8-flash`), Groq (`openai/gpt-oss-120b` with optional built-in browser search), or OpenAI (`gpt-4o-mini`). Stable repeat questions use a short-lived local cache; current information still needs a live network lookup.
- 📝 **Mission Notes & Reminders**: Save, review, and clear tasks and notes stored locally.
- 🔊 **Synthesized Sci-Fi Sound FX**: Web Audio API sound generator producing Stark bootup sweeps, confirmation chimes, and tactical radar pings.

Response time depends on the selected AI provider, internet connection, and whether live search is needed. The cache speeds up repeated stable questions; first-time answers cannot be guaranteed within one second.

---

## 🚀 Quick Start

### 1. One-Click Launch (Windows)
Double-click `start_jarvis.bat` in the project folder.

### 2. Manual Launch via Terminal
```bash
# Navigate to the folder
cd "c:\Users\IT SUPPORT\Downloads\J.A.R.V.I.S"

# Run the launcher
python main.py
```

The launcher will initialize the backend server at `http://127.0.0.1:8000` and automatically open J.A.R.V.I.S. in a clean, dedicated app window (using Microsoft Edge or Google Chrome app mode).

### Public link from anywhere (Cloudflare Quick Tunnel)

The public launcher uses the included `cloudflared.exe`; no Tailscale installation or account is needed. Run `start_jarvis_public.bat`. The random HTTPS URL is printed in the console and saved to `public_url.txt`. It changes when the tunnel restarts, and works only while this PC, J.A.R.V.I.S., and the tunnel stay running. This is a public, no-sign-in link: anyone who gets it can access the J.A.R.V.I.S. interface and its PC command controls. Only share it with people you trust. Google search does not create or host this link.

---

## 🗣️ Voice & Text Command Cheatsheet

| Category | Example Commands |
|---|---|
| **Diagnostics & Telemetry** | `"Run diagnostics"`, `"System status"`, `"How is the CPU?"`, `"Battery level"` |
| **App & Portal Launching** | `"Open Physics Wallah"`, `"Launch PW"`, `"Open Chrome"`, `"Launch Calculator"`, `"Start VS Code"`, `"Open Spotify"` |
| **Audio & Volume** | `"Set volume to 60"`, `"Volume up"`, `"Turn down volume"`, `"Mute"`, `"Unmute"` |
| **Atmospheric & Time** | `"What's the weather?"`, `"Weather in Tokyo"`, `"What time is it?"`, `"Current date"` |
| **Media & Web Search** | `"Search web for quantum computing"`, `"Play AC/DC on YouTube"`, `"Who is Tony Stark?"` |
| **Screen & Power** | `"Take a screenshot"`, `"Lock PC"`, `"Sleep computer"`, `"Shutdown in 5 minutes"`, `"Abort shutdown"` |
| **Mobile Uplink (Phone)** | `"Unlock my phone"`, `"Set phone PIN 1234"`, `"Lock phone"`, `"Phone battery"`, `"Phone status"` |
| **Real AI Images** | `"Create an image of a futuristic city at sunset"`, `"Generate a photo of a golden retriever puppy"`, `"Taj Mahal ki image banao"` |
| **Mission Notes** | `"Take a note: deploy satellite array"`, `"Read notes"`, `"Clear notes"` |
| **Computation** | `"Calculate 250 * 14"`, `"What is 15 percent of 800?"` |
| **Banter & Identity** | `"Who are you?"`, `"Tell me a joke"`, `"Avengers protocol"`, `"Good morning Jarvis"` |

---

## ⚙️ Configuration & API Keys (Optional)

J.A.R.V.I.S. is preconfigured to work immediately without any API keys using its built-in rule and offline knowledge matrix.

To unlock advanced conversational intelligence:
1. Open the HUD and click the **Gear icon** in the top-right header, or open `.env`.
2. Add your desired key:
   - **Google Gemini**: Get a free API key at [Google AI Studio](https://aistudio.google.com/)
   - **Groq**: Get a free ultra-fast key at [Groq Console](https://console.groq.com/)
   - **OpenAI**: Get an API key at [OpenAI Platform](https://platform.openai.com/)
3. Click **Save Configuration**.

---

## 📱 Mobile Uplink & Phone Unlocking (Android ADB)

J.A.R.V.I.S. includes built-in hardware automation to awaken, dismiss the lockscreen, and enter your security PIN/password to unlock your phone using ADB (Android Debug Bridge).

### 🛠️ One-Time Phone Setup:
1. **Enable Developer Options on your phone**:
   - Go to **Settings** > **About Phone**.
   - Tap **Build Number** 7 times until you see *"You are now a developer!"*.
2. **Enable USB Debugging**:
   - Go to **Settings** > **System / Additional Settings** > **Developer Options**.
   - Toggle **USB Debugging** to **ON**.
3. **Connect to PC**:
   - Plug your phone into your computer with a USB cable.
   - On your phone display, when prompted *"Allow USB debugging?"*, check **"Always allow from this computer"** and tap **Allow**.
4. **Configure Security PIN**:
   - **Directly on HUD**: Enter your PIN in the **LOCKSCREEN PIN** box on the left telemetry panel and click **Save**.
   - **Voice or Chat**: Say or type `"Set phone PIN 1234"` or `"My phone PIN is 1234"`.
   - **Settings Modal**: Click the **Gear icon** in the top header, enter your PIN under **Phone PIN / Passcode**, and click **Save Configuration**.

### 📶 Wireless Mode (Optional):
- Once connected via USB once, say or trigger `"enable wireless mode"`, then enter your phone's Wi-Fi IP address in settings. You can now unlock your phone completely wire-free over Wi-Fi!

---

## 🎨 Real AI Image Generation (Google Assistant style)

J.A.R.V.I.S. can synthesize a real, photorealistic AI image of **anything** you describe and display it live on the center panel.

### 🌟 Capabilities
- **Anything goes (safe content)**: `"Create an image of a futuristic city at sunset"`, `"Generate a photo of a golden retriever puppy"`, `"Draw a dragon over Tokyo"`.
- **Hindi / Hinglish prompts**: `"Taj Mahal ki image banao"`, `"sher ki photo banao"`.
- **Live viewer**: dedicated `IMAGE` tab with prompt title, download, fullscreen, and close controls.
- **Providers**: OpenAI DALL-E 3 when an `OPENAI_API_KEY` is configured, otherwise the free Pollinations classic endpoint (no key required).

### 🛡️ Content Safety
Every prompt is screened **before** any network request. Nudity, sexual, explicit, or suggestive-minor requests (in English, Hinglish, or Hindi) are refused with a safe-for-work alternative offer. Allowed prompts are automatically suffixed with `fully clothed, safe-for-work, non-explicit, respectful`.

### 🖼️ Render Archive (instant repeats)
Every successful render is stored in `data/generated_images/` and indexed in `cache_index.json`. Asking for the same subject again returns the stored image instantly instead of burning a render slot.

### ⏱️ Rate Limits
The free Pollinations tier allows roughly one image per minute per IP. J.A.R.V.I.S. serializes requests, persists the cooldown across restarts, retries once after the cooldown, and reports an honest "uplink busy, retry in Ns" message instead of a fake success. The HUD shows live elapsed seconds while a render is in flight.

For unlimited, instant generation add an `OPENAI_API_KEY` in settings — J.A.R.V.I.S. then uses DALL-E 3 automatically.

---

## 📁 Project Architecture

```
J.A.R.V.I.S/
├── static/
│   ├── index.html        # Stark Industries HUD + AI image viewer
│   ├── css/
│   │   └── style.css     # HUD styles, cyber glow, glassmorphic cards
│   ├── js/
│   │   ├── app.js        # Core controller, WebSocket & Speech Recognition
│   │   ├── arc_reactor.js# 60FPS Canvas Arc Reactor visualizer
│   │   └── sound_fx.js   # Web Audio API sci-fi sound effects
│   └── audio/            # Cached synthesized neural voice clips
├── core/
│   ├── brain.py          # AI logic (Cloud LLMs + offline NLP processor)
│   ├── image_engine.py   # Real AI image generation + content safety + rate limiting
│   ├── system_control.py # Master Windows hardware control (Volume, Apps, Power, Telemetry)
│   ├── voice_engine.py   # Edge Neural TTS engine + pyttsx3 fallback
│   ├── tools.py          # Web sweeps, Weather, Wikipedia, YouTube, Math
│   ├── memory.py         # Notes & interaction history manager
│   └── config.py         # Dynamic .env configuration manager
├── data/                 # Persistent storage (notes.json, history.json)
├── screenshots/          # Screen captures saved by J.A.R.V.I.S.
├── main.py               # Launcher script with auto browser window mode
├── server.py             # FastAPI REST & WebSocket server
├── start_jarvis.bat      # Windows batch double-click launcher
└── requirements.txt      # Project dependencies
```

---

*Engineered for Stark Industries Mark VII Protocol.*
