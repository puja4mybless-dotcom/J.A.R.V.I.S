# J.A.R.V.I.S. Android PC Companion

This is an Android Studio project for a phone companion. It connects to the existing Windows J.A.R.V.I.S. server over the same private Wi-Fi network; the PC remains responsible for AI processing, Windows apps, and telemetry.

## Pair it with the Windows PC

1. On the PC, create a long random token in PowerShell:

   ```powershell
   $bytes = New-Object byte[] 32
   $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
   $rng.GetBytes($bytes)
   $token = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
   $token
   ```

2. Put the printed value in the PC project’s `.env` file as `JARVIS_REMOTE_TOKEN=<token>`.
3. Run `start_jarvis_wifi.bat` on the PC. It prints the PC's private Wi-Fi IPv4 address. If Windows Firewall prompts, allow Python on **Private networks only**.
4. Keep the phone and PC on the same trusted Wi-Fi. Open the Android app and enter the printed PC address, port `8000`, and the token.

The token is required for API commands and telemetry. Do not forward port 8000 to the internet or share the token. This first companion uses local HTTP, so use it only on a trusted private Wi-Fi network; public release should move the PC connection behind HTTPS or a VPN.

## Build a Play Console bundle

Open this `android-app` folder in Android Studio (AGP 9.5 / Gradle 9.6 compatible) and sync Gradle. Install Android SDK Platform 36 and Build Tools 36.0.0 if prompted. If Android Studio asks for a Gradle wrapper, run `gradle wrapper --gradle-version 9.6.0` in this folder first. Then choose **Build > Generate Signed Bundle / APK > Android App Bundle** and create a release signing key. Keep that key and its passwords private; Google Play needs the signed `.aab` file.

The project targets Android API 36 and uses application ID `com.jarvis.pccompanion`. Pick and register the final package name before publishing; application IDs cannot be changed after release. This folder is a source project, not a built or signed AAB.

Before a public release, replace or license the J.A.R.V.I.S./Stark/Mark VII branding and Iron Man-inspired artwork. Google Play requires rights to third-party names, logos, and artwork. Prepare a privacy policy, data-safety disclosure, store assets, policy declarations for microphone access, and an in-app way to report or flag AI-generated responses.
