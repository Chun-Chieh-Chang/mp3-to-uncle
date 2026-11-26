# Development Log - YouTube Downloader

## [2026-04-19] Initial Setup and Planning

### Requirement
Create a YouTube Downloader focusing on MP3 conversion with multiple quality options.

### Problem Analysis
- `yt-dlp` is available but `ffmpeg` is not installed on the system.
- Need a portable way to provide `ffmpeg` for audio conversion.
- UI needs to be premium and responsive.

### Plan
- Flask Backend.
- yt-dlp for extraction and downloading.
- Automatic portable ffmpeg downloader.
- Modern CSS/JS Frontend with high aesthetics.

### Root Cause Analysis (RCA) - Preliminary
- System lacks common media processing binaries.
- Solution: Bundle them or provide a script to pull them.

### Corrective and Preventive Actions (CAPA)
- Implementing `downloader.py` to check for `ffmpeg.exe` in the local path first.

### [2026-04-19] Implementation Finished
- Codebase generated. UI uses Design System guidelines.
- Automated FFmpeg download logic successfully created.
- Syntax checks passed.

## [2026-05-10] Repository Initialization and Verification

### Task
- Cloned repository from GitHub.
- Initial assessment of project structure and dependencies.

# Development Log - YouTube Downloader

## [2026-04-19] Initial Setup and Planning

### Requirement
Create a YouTube Downloader focusing on MP3 conversion with multiple quality options.

### Problem Analysis
- `yt-dlp` is available but `ffmpeg` is not installed on the system.
- Need a portable way to provide `ffmpeg` for audio conversion.
- UI needs to be premium and responsive.

### Plan
- Flask Backend.
- yt-dlp for extraction and downloading.
- Automatic portable ffmpeg downloader.
- Modern CSS/JS Frontend with high aesthetics.

### Root Cause Analysis (RCA) - Preliminary
- System lacks common media processing binaries.
- Solution: Bundle them or provide a script to pull them.

### Corrective and Preventive Actions (CAPA)
- Implementing `downloader.py` to check for `ffmpeg.exe` in the local path first.

### [2026-04-19] Implementation Finished
- Codebase generated. UI uses Design System guidelines.
- Automated FFmpeg download logic successfully created.
- Syntax checks passed.

## [2026-05-10] Repository Initialization and Verification

### Task
- Cloned repository from GitHub.
- Initial assessment of project structure and dependencies.

### Status
- Repository successfully cloned to local environment.
- Project structure verified: Flask backend with custom yt-dlp integration.
- Portable FFmpeg logic detected in `downloader.py`.

### Next Steps
- Install necessary Python dependencies (`flask`, `flask-cors`, `yt-dlp`).
- Run the application to verify functionality and UI aesthetics.
- Perform robustness tests on URL handling and download process.

## [2026-05-10] Implementation and Optimization

### Progress
- **Bilingual Support**: Implemented English and Traditional Chinese (zh-TW) toggle. All UI elements now support dual languages via `data-en` and `data-zh` attributes.
- **UI Aesthetics**: 
  - Corrected button colors to align with the "Color Master Palette" (Primary Action: Sky Blue, Success Action: Emerald).
  - Added glassmorphism effects and subtle animations for the language switcher.
  - Improved contrast for error messages.
- **FFmpeg Robustness**:
  - Refactored `downloader.py` to use a User-Agent in requests to avoid server blocks.
  - Optimized download to use chunked streaming (1MB chunks) for better memory management.
  - Added pre-check for existing `ffmpeg.zip` and streamlined extraction logic.

### Problem Analysis & RCA
- **Problem**: FFmpeg download was hanging/failing with 0-byte file.
- **RCA**: Default `urllib` headers were likely being blocked by the server. 0-byte file was created but never filled.
- **CAPA**: Added custom User-Agent headers and implemented chunked writing. Added logic to resume extraction if the zip is already present.

### Verification (PDCA)
- **UI Test**: Language toggle verified via browser subagent. Colors verified.
- **Functional Test**: Successfully analyzed "Big Buck Bunny" YouTube URL and simulated/started download process.
- **FFmpeg Test**: Extraction confirmed in logs (`Extraction complete`).

## [2026-05-22] Debugging yt-dlp Deno Runtime, Playlist Hangs, and Process Conflicts

### Requirement
- Fix the application freezing/hanging issue during video analysis and downloading.

### Problem Analysis & RCA
1. **yt-dlp (v2026.03.17+) JS Runtime Requirement**:
   - **RCA**: YouTube updated their player signature system. Newer versions of yt-dlp depend on a JavaScript runtime (like Deno) to evaluate challenge scripts. Lacking a local Deno installation causes yt-dlp to either fall back to unsupported slow APIs, log `WARNING: No supported JavaScript runtime could be found`, or hang indefinitely during extraction.
2. **Playlist Processing Overhead**:
   - **RCA**: When users paste playlist URLs (containing `&list=...`), yt-dlp defaults to parsing all metadata of the entire playlist rather than a single video, creating huge latency.
3. **Port 5000 Process Clashes (Flask Threading Block)**:
   - **RCA**: Flask's debug mode or aborted terminal runs left multiple zombie Python instances listening on Port 5000. Because Flask's dev server defaults to single-threaded operations unless configured, a slow blocking yt-dlp query totally locked up the backend socket.

### Corrective and Preventive Actions (CAPA)
1. **Bypassing JS Runtime**:
   - Configured `yt_dlp.YoutubeDL` with `extractor_args: {'youtube': {'player_client': ['android']}}`. The Android client does not enforce JS runtime solving on many streams and is significantly faster.
2. **Playlist Pruning**:
   - Implemented `_clean_url()` to strip away `&list=...` query components automatically.
   - Forced `noplaylist: True` and set `socket_timeout: 30` (or `60` during download) to guarantee timely recovery.
3. **Threading and Process Cleaning**:
   - Forced termination of stale Python PIDs using `taskkill`.
   - Enabled `threaded=True` on Flask's `app.run` to allow concurrent connection handling.

### Verification (PDCA)
- **Local Testing**: Process conflicts cleared. Flask running with `threaded=True`.
- **API Call Validation**: Executed PowerShell `Invoke-RestMethod` querying `http://127.0.0.1:5000/api/info` with a standard YouTube URL.
- **Result**: Server responded cleanly under 6 seconds, returning video meta (title, thumbnail, duration, options) successfully. Download verified.

## [2026-05-22] Extension Copy Conflict Troubleshooting & Re-packaging Executable

### Requirement
- Sync IDE extension folders from `~\.antigravity\extensions` to `~\.antigravity-ide\`.
- Rebuild the standalone executable `AudioStudio.exe` to incorporate the 2026-05-22 critical fixes.
- Perform MECE file cleaning and prepare repository for git push.

### Problem Analysis & RCA
1. **Extension Copy Failure (pyrefly.exe Locked)**:
   - **Problem**: Running `Copy-Item` failed with `IOException: file in use` for `pyrefly.exe`.
   - **RCA**: `pyrefly.exe` is actively managed by the IDE's process controller. Even after terminating it via `Stop-Process` or `taskkill`, the parent IDE process instantly spawns a new instance of it (e.g. from PID 11368 to 15492 within milliseconds).
   - **CAPA**: Instead of racing the auto-spawner, utilized `robocopy` with the `/XD` (Exclude Directory) flag to skip `meta.pyrefly-1.0.0-win32-x64` entirely, while successfully copying all other 33 extensions (totaling 1.18 GB).
2. **AudioStudio.exe Re-packaging**:
   - **Problem**: Executables compiled prior to 2026-05-22 did not contain the critical `yt-dlp` Deno bypass and Flask multithreading logic, making them prone to hanging on YouTube links.
   - **CAPA**: Ran PyInstaller to bundle the Flask web server, HTML templates, static assets, and FFmpeg/FFprobe binaries into a single, highly compressed 99.6MB executable:
     `python -m PyInstaller --onefile --noconsole --name="AudioStudio" --add-data "templates;templates" --add-data "static;static" --add-data "bin;bin" app.py`

### MECE File Verification & Cleanup
- **Temporary Build Artifacts**: Deleted the `build/` directory created during PyInstaller bundling to keep the workspace clean and adhere to the MECE principle.
- **Git Alignment**: Verified `.gitignore` correctly ignores the compiled executable (`dist/`), temporary specs, and FFmpeg binary files (`bin/`), ensuring zero bloated binary uploads.

### Status
- **Extensions**: Copied successfully.
- **Executable**: `dist/AudioStudio.exe` generated and ready for distribution.
- **Log**: Development log updated. Ready for git push.

## 2026-10-04 Multi-platform video support (TikTok) + MP4 output
- **Requirement**: Support non-YouTube platforms; output files directly (no ZIP). User later decided TikTok is video-only, no images.
- **Design**: yt-dlp only. Output format selector MP3 / MP4 (quality selector shown only for MP3). Filename title truncated to 80 chars (TikTok titles are very long).
- **Failed attempt / scope change**: Built a gallery-dl image fallback (save to downloads/<title>/). Removed entirely (YAGNI) after user declined images; gallery-dl has no Xiaohongshu extractor anyway. gallery-dl uninstalled, not in requirements.txt.
- **Verified**: real TikTok short link (vt.tiktok.com) -> info, MP4 (23 MB), MP3 (6.7 MB), file served via /api/files, invalid mode -> 400.
- **Xiaohongshu RCA**: xiaohongshu.com resolves via local DNS to 140.111.246.32 (not Xiaohongshu) -> self-signed cert -> yt-dlp SSL failure; with cert check off server returns HTTP 500. Cause is network-level DNS rewrite, not code. Disabling cert verification rejected (MITM risk). Retest after changing network/DNS.
- **Env note**: yt-dlp upgraded (was >90 days old); console print of Chinese titles needs PYTHONIOENCODING=utf-8 on cp950 terminals (test-harness only).
- **Executable Build**: Re-packaged `dist/AudioStudio.exe` (99.4 MB) via `python -m PyInstaller --clean AudioStudio.spec`. Temporary `build/` directory cleaned up (MECE).
## [2026-10-04] Full Project Refactor, MECE Audit & Release Packaging

### Requirement
1. Complete project refactor, dead code removal, and regression prevention.
2. Synchronize all development documentation with 100% precision.
3. Apply SSOT and MECE principles across resources.
4. Verify latest portable executable is cleanly packaged.
5. Establish Git baseline and prepare for remote push.

### Changes & MECE Audit
- **Dead Code & Import Removal**: Removed duplicate `import sys`, unused `import queue`, unused `import json`, unused `Response` from Flask, and duplicate `import webbrowser` / `Timer` in `app.py` and `downloader.py`.
- **SSOT Alignment**: Unified directory and FFmpeg check into a single `ensure_ffmpeg()` function in `downloader.py`.
- **PWA / SW Local Optimization**: Added dedicated `/sw.js` route to local Flask server, eliminating browser 404 console errors while maintaining GitHub Pages compatibility.
- **UI Metadata**: Updated `<title>` and `<meta name="description">` in `templates/index.html` and `static/manifest.json` to accurately reflect multi-platform audio/video capabilities.
- **Directory Cleanliness**: Removed empty directory `.vscode/`.
- **Executable Re-packaging**: Compiled clean single-file executable `dist/AudioStudio.exe` (99.4 MB) using `AudioStudio.spec` with latest dependencies.

### Local Runtime Verification
- Syntax check: `python -m py_compile app.py downloader.py` passed with zero errors.
- E2E API check: Video analysis, MP4/MP3 download, filename truncation (80 chars), and file serving verified.
- Status: Clean state, ready for commit and push.

## [2026-11-26] Route 3 Dual-Track Deployment Architecture (GitHub Pages PWA + Cloud Docker + Windows Portable Release)

### Requirement
- Deploy AudioStudio as a publicly accessible web app for desktop and mobile users (including iPhone iOS, macOS, Android) on GitHub Pages, paired with a portable Windows executable distribution (Route 3).

### Architecture & Problem Analysis (RCA / CAPA)
1. **Static Hosting vs Media Processing**:
   - **RCA**: GitHub Pages only serves static assets and cannot run Python, `yt-dlp`, or `FFmpeg`.
   - **CAPA**: Built a decoupled dual-track architecture: static PWA frontend on GitHub Pages (configurable via `static/js/config.js` + `vars.API_BASE_URL` or in-app Server Settings modal) + containerized Flask backend (`Dockerfile` with Python 3.12, `ffmpeg`, `deno`, `gunicorn`, non-root `user`, port `7860` for Hugging Face Spaces / Render) + automated GitHub Actions release pipeline (`release-windows.yml`) building `AudioStudio.exe` to GitHub Releases.
2. **Synchronous Timeout & Cross-User Isolation**:
   - **RCA**: Synchronous `POST /api/download` blocked connections until conversion finished (risking proxy/mobile timeouts), used `hash(url)` IDs, and never cleaned temporary files.
   - **CAPA**: Refactored `/api/download` to return HTTP `202` with a `uuid4` `job_id`, running bounded worker threads (`Semaphore`) with real-time progress polling (`/api/progress/<job_id>`), isolated per-job directories under `downloads/<job_id>/`, TTL auto-cleanup in cloud mode, SSRF/URL validation (`validate_url`), optional `MAX_DURATION_SECONDS` cap, and RFC 5987 UTF-8 `Content-Disposition` filenames via `send_file`.
3. **Mobile / iOS Safari UX & Service Worker**:
   - **RCA**: iOS Safari blocks programmatic `a.click()` after async polling; in-app browsers (LINE/FB/IG) block downloads; `sw.js` lacked `/api/` bypass and cache cleanup; `.duration-badge` had low contrast.
   - **CAPA**: Added explicit Emerald "點擊儲存檔案 / Tap to Save File" button + iOS Files app hint, in-app browser warning banner, one-tap Paste/Clear buttons, Light/Dark Color Master Palette tokens, `100dvh` safe-area layout, `manifest.json` relative `start_url`, and `sw.js` `audiostudio-v2` network-first with `/api/` bypass.

### Verification (PDCA Check)
- `py_compile` (`app.py`, `downloader.py`), `node --check` (`config.js`, `script.js`, `sw.js`), `manifest.json` JSON parse, and `deploy.yml` Jinja substitution check: all passed with 0 errors.
- Flask `test_client()` verification suite: `GET /`, `GET /sw.js`, `GET /api/health` (`ffmpeg: true`), SSRF & invalid input `400` checks (`file://`, `127.0.0.1`, `169.254.169.254`, invalid mode/quality), `404` checks for missing jobs/files, and RFC 5987 `filename*=UTF-8''` attachment response for Chinese-named MP3: all passed (`ALL_VERIFICATIONS_PASSED`).
- Local workspace clean; awaiting user permission before `git push`.

## [2026-11-26] Render Cloud YouTube Player Response Fix (yt-dlp[default] & Multi-Client Fallback)

### Problem
- After deploying to Render Free Docker, analyzing a YouTube URL failed with:
  `ERROR: [youtube] ...: Failed to extract any player response; please report this issue...`

### Root Cause Analysis (RCA)
1. `downloader.py` hardcoded `YTDLP_PLAYER_CLIENTS` default to `['android']` only. In `yt-dlp 2026.06.09`, `INNERTUBE_CLIENTS['android']` enforces `GVS_PO_TOKEN_POLICY.required = True` and `SUPPORTS_COOKIES = False`, causing cloud IPs without a PO token provider to fail with no fallback clients.
2. `requirements.txt` installed `yt-dlp` instead of `yt-dlp[default]`, omitting `yt-dlp-ejs` required by Deno to evaluate YouTube player JS challenges for `web`/`tv` clients.

### Corrective and Preventive Actions (CAPA)
1. Updated `requirements.txt` to `yt-dlp[default]`.
2. Replaced hardcoded `'android'` with `_resolve_player_clients()` in `downloader.py`:
   - Respects explicit `YTDLP_PLAYER_CLIENTS` override (`default` delegates natively to yt-dlp).
   - Uses `['web', 'tv']` when cookies are configured (`YTDLP_COOKIES_FILE` or new `YTDLP_COOKIES_B64`).
   - Uses `['android_vr', 'web', 'tv']` in cloud/Deno environments (`android_vr` requires neither JS player nor PO token; `web`/`tv` act as Deno+EJS fallbacks).
   - Uses `['android_vr', 'android']` on local environments without Deno.
3. Exposed `deno` and `yt_dlp_version` in `/api/health` (`app.py`) for instant cloud diagnostics, and updated `DEPLOY.md` to reflect Render Free + `YTDLP_COOKIES_B64`.

## [2026-11-26] Docker `/app/bin` Permission Denied Fix

### Problem
- TikTok URL analysis succeeded on Render, and downloading MP3 failed with `[Errno 13] Permission denied: '/app/bin'`.

### Root Cause Analysis (RCA)
1. `Dockerfile` created `WORKDIR /app` as `root` and only chowned `/app/downloads` (plus copied files), leaving `/app` owned by `root` when running as non-root `USER user`.
2. `downloader.py`'s `ensure_ffmpeg()` unconditionally called `ensure_dirs()`, which tried to `mkdir` `BIN_DIR` (`/app/bin`) even when system `ffmpeg` was already available on `PATH`.

### Corrective and Preventive Actions (CAPA)
1. Updated `ensure_dirs()` in `downloader.py` to only create `DOWNLOAD_DIR`, moving `BIN_DIR.mkdir(...)` inside Windows-only `download_ffmpeg()`.
2. Updated `Dockerfile` to `chown -R user:user /app`.
3. Added deterministic regression test in verification suite asserting `ensure_ffmpeg()` does not create `BIN_DIR` when system `ffmpeg` is present.
