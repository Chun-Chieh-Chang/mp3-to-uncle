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

## [2026-11-26] TikTok MP3 Playback Investigation & Lean Compatibility Hardening

### Problem
- Downloaded TikTok `.mp3` (3.45 MB, valid MPEG audio per `ffprobe`) failed to play in local PotPlayer with "未知的檔案格式".

### Root Cause Analysis (RCA)
- Re-encoding the downloaded file locally via FFmpeg into a fresh standard 192 kbps ID3v2.3 `libmp3lame` MP3 succeeded cleanly (5,058 KiB, 3m35s, 0 errors), yet PotPlayer still reported "未知的檔案格式" on the re-encoded file as well. This confirmed the downloaded MP3 itself was intact and the issue was local PotPlayer decoder/splitter state rather than backend output corruption.

### Corrective and Preventive Actions (CAPA)
1. Removed the extra post-download MP3 re-encoding pass (YAGNI, avoids wasting cloud CPU and double-compressing audio).
2. Retained lightweight, zero-overhead improvements: `postprocessor_args: {"extractaudio": ["-id3v2_version", "3", "-write_id3v1", "1"]}` in `downloader.py`, non-empty output file check (`> 0 bytes`), and explicit `audio/mpeg` / `video/mp4` MIME types in `app.py`'s `serve_file()`.

## [2026-11-26] YouTube Download HTTP 403 Forbidden Fix (Native Player Client & JS Runtime Auto-Detection)

### Problem
- Local YouTube video analysis (`POST /api/info`) succeeded, but downloading (`POST /api/download` on `https://youtu.be/-gQUPWstYDI`) failed at 0% with:
  `ERROR: unable to download video data: HTTP Error 403: Forbidden`.

### Root Cause Analysis (RCA)
1. `_resolve_player_clients()` in `downloader.py` hardcoded `extractor_args.youtube.player_client` to `["android_vr", "android"]` when Deno was absent locally (or `["android_vr", "web", "tv"]` with Deno/cloud).
2. YouTube now enforces GVS PO Token / SABR restrictions on `android_vr` and `android` clients, causing `yt-dlp` to skip all audio-only HTTPS formats and leave only format `18` (`360p, ANDR-V`), whose media download returned `HTTP Error 403: Forbidden`.
3. `downloader.py` only checked for `deno` (`has_deno()`) and did not pass `js_runtimes` to `yt-dlp`, leaving locally installed Node.js (`v26.7.0`) unused. Additionally, the local Python environment had an outdated `yt-dlp` (`2026.08.19`) without `yt-dlp-ejs`.

### Corrective and Preventive Actions (CAPA)
1. **Use `yt-dlp` Native Client Strategy by Default**: Updated `_resolve_player_clients()` in `downloader.py` to return `None` unless `YTDLP_PLAYER_CLIENTS` is explicitly set (and not `default`), removing brittle hardcoded `player_client` lists.
2. **Multi-Runtime JS Detection**: Added `JS_RUNTIME_BINARIES` and `get_js_runtimes()` in `downloader.py`, configured `js_runtimes` (`deno`, `node`, `bun`, `quickjs`) in `_build_ydl_opts()`, and exposed `js_runtimes` in `GET /api/health` (`app.py`).
3. **Documentation & Dependency Sync**: Updated `DEPLOY.md` to document native client selection and multi-runtime detection, and upgraded local `yt-dlp[default]` to `2026.11.23` (`yt-dlp-ejs 0.8.0`).

### Verification (PDCA Check)
- `py_compile` (`app.py`, `downloader.py`) and unit assertions (`_resolve_player_clients()`, `_build_ydl_opts()`, Flask `test_client().get('/api/health')` returning `js_runtimes: ['node']`, `yt_dlp_version: '2026.11.23'`) passed.
- Real E2E `downloader.download_media("https://youtu.be/-gQUPWstYDI", mode="mp3", quality="128")` succeeded and produced a valid `.mp3` file (`4,532,013` bytes).

## [2026-11-27] Cloud YouTube Diagnostics, Cookies Validation & Proxy Support

### Problem
- On Render cloud deployment, YouTube extraction returned only `Failed to extract any player response`, hiding underlying per-client warnings (`report_warning` in `yt-dlp`'s `_video.py`) and offering no visibility into whether `YTDLP_COOKIES_B64` loaded properly.

### Root Cause Analysis (RCA)
1. `downloader.py` set `no_warnings: True` and `quiet: True` with no logger hook, suppressing `yt-dlp`'s per-client warnings (cookie expiration, bot challenge, or PO token notices).
2. `YTDLP_COOKIES_B64` decoding lacked whitespace/BOM sanitization and Netscape format validation, and `/api/health` did not surface `cookies_loaded` or active `player_clients`.

### Corrective and Preventive Actions (CAPA)
1. Added `_YdlCaptureLogger` in `downloader.py` (sanitizing temp/cookie paths) and attached it to `get_video_info` and `download_media` so real `yt-dlp` warnings appear in both Render logs and API error responses.
2. Hardened `_resolve_cookies_status()` to strip whitespace/UTF-8 BOM, validate Netscape tab-separated cookie lines, and report safe status via `get_diagnostics()` in `/api/health` (plus `YTDLP_PROXY` support).
3. Preserved `94aa0a8`'s native `yt-dlp` client default and multi-JS runtime detection (`deno`, `node`, `bun`, `quickjs`).

## [2026-11-27] Option B: One-Click Cloudflare Mobile Bridge & QR Auto-Connect

### Problem
- Verified across both Render Singapore and Render Oregon (`mp3-to-uncle-us`) even with fresh `/robots.txt` cookies: YouTube consistently rejects `youtubei/v1/player` from Render datacenter IPs with `HTTP Error 403: Forbidden`, while local residential IP succeeds 100%.
- iPhone users cannot sideload a permanent free standalone `yt-dlp` app due to iOS sandbox & App Store 5.2.3 rules.

### Corrective and Preventive Actions (CAPA)
1. **Frontend `?api=` Auto-Connect (`static/js/script.js`)**: Added `applyApiParamFromUrl()` validating `https:` (or `http://localhost`/`127.0.0.1`) query params, persisting into `localStorage`, and cleaning the URL bar via `history.replaceState`.
2. **Bridge QR UI (`app.py`, `templates/bridge.html`)**: Added `/bridge` route validating `https://` tunnel URLs via `validate_url()` and rendering a local client-side QR Code + one-click copy links + iPhone Safari instructions.
3. **One-Click Launcher (`mobile_bridge.py`, `start_mobile_bridge.bat`)**: Automated Python detection, auto-download of official `cloudflared-windows-amd64.exe` into `bin/`, local Flask startup, quick Cloudflare Tunnel creation, and automatic browser QR launch.
4. **Docs (`DEPLOY.md`, `handoff.md`)**: Documented mobile bridge usage and Render `mp3-to-uncle-us` 24/7 TikTok configuration.

## [2026-11-27] Fix `start_mobile_bridge.bat` `cmd.exe` Parsing Error (CRLF & Pure ASCII)

### Problem
- Double-clicking `start_mobile_bridge.bat` failed in `cmd.exe` with `'"PY_CMD="' is not recognized`, `Unknown option: -%`, and `']' is not recognized`.

### Root Cause Analysis (RCA)
- `start_mobile_bridge.bat` was saved with Unix LF (`\n`) line endings, UTF-8 multi-byte Chinese characters, and parenthesized `if`/`for` blocks. Windows `cmd.exe` miscalculates batch file byte-seek offsets when LF is used with parenthesized blocks / multi-byte encodings, jumping mid-line on resumption.

### Corrective and Preventive Actions (CAPA)
1. Added `.gitattributes` (`*.bat text eol=crlf`) to enforce CRLF on all batch scripts permanently.
2. Rewrote `start_mobile_bridge.bat` using pure ASCII, flat `goto` labels (no parenthesized blocks), and strict CRLF (`\r\n`) line endings, with `--check` passthrough for non-interactive testing.
3. Added `--check` fast-path to `mobile_bridge.py` and verified directly via `cmd /c start_mobile_bridge.bat --check`.

## [2026-11-27] 3-Tier Mobile Bridge Tunnel Fallback (Cloudflare -> localhost.run -> Home Wi-Fi LAN)

### Problem
- Running `start_mobile_bridge.bat` succeeded on Python/Flask startup, then hit Cloudflare Quick Tunnel rate-limiting:
  `quick tunnel provisioning failed with status 429: [10000] Tunnelstore request failed`.

### Root Cause Analysis (RCA)
- `mobile_bridge.py` relied exclusively on Cloudflare Quick Tunnels (unauthenticated shared `trycloudflare.com` provisioning endpoint), crashing completely on transient `429` throttling.

### Corrective and Preventive Actions (CAPA)
1. Implemented a 3-tier fallback chain in `mobile_bridge.py`:
   - Tier 1: Cloudflare Quick Tunnel (`cloudflared`), with 1 retry after 3s on `429`.
   - Tier 2: Zero-signup HTTPS SSH tunnel via Windows built-in OpenSSH (`nokey@localhost.run` -> `lhr.life` / `lhr.rocks`).
   - Tier 3: Home Wi-Fi LAN direct access (`http://<LAN_IP>:5000`, binding Flask to `0.0.0.0`).
2. Updated `/bridge` (`app.py`) and `templates/bridge.html` with strict private-IP `LAN_URL_RE` validation and automatic LAN QR code fallback rendering.

## [2026-11-27] Local `.venv` (`yt-dlp[default]`) & ANSI/Network Error UX Polish

### Problem
- Desktop YouTube download hit `HTTP Error 403: Forbidden` (with raw ANSI escape codes `[0;31mERROR:[0m`), while iPhone on 4G reported `獲取資訊時發生網路錯誤` without showing which backend URL failed.

### Root Cause Analysis (RCA)
1. System Python 3.14 ran outdated `yt-dlp 2026.06.09` without `yt-dlp-ejs` (`yt_dlp[default]`), leaving Node.js unused for YouTube `n`-challenge solving.
2. `downloader.py` returned raw `str(err)` containing ANSI escape codes.
3. `script.js` hid the target backend URL on network errors, making it unclear whether mobile was calling a home LAN IP over 4G or a deleted cloud host.

### Corrective and Preventive Actions (CAPA)
1. Created project `.venv` and installed latest `yt-dlp[default]` (including `yt-dlp-ejs`) so `start_mobile_bridge.bat` automatically runs with up-to-date YouTube extractors and EJS support.
2. Added `ANSI_RE` stripping to `_YdlCaptureLogger._sanitize()` and `_format_ydl_error()` in `downloader.py`.
3. Updated `static/js/script.js` network error handlers to include the target backend URL.

## [2026-11-27] Save-Location Display, Inline Media Preview & Native Share UX

### Problem
- Mobile/desktop users could not see where downloaded files were saved on their device or easily locate/play downloaded MP3/MP4 files on iOS Safari.

### Corrective and Preventive Actions (CAPA)
1. **`app.py`**: Added `local_path` in `/api/progress/<job_id>` exclusively for localhost requests (`127.0.0.1` / `::1` in local mode) and added `?inline=1` support in `/api/files/<job_id>` for browser `<audio>`/`<video>` preview playback.
2. **`templates/index.html`, `static/css/style.css`, `static/js/script.js`**: Added `.save-meta-box` showing exact filename and OS-specific save path (iPhone/iPad Files app, Android Download, macOS Finder, Windows Downloads + localhost path), inline HTML5 audio/video preview player, and Web Share API (`navigator.share` with `files`) button to save directly into iOS Files / Photos.

## [2026-11-27] Fixed QR Code / URL via Secret GitHub Gist Dynamic Pointer (Route A)

### Problem
- Free Cloudflare Quick Tunnels (`*.trycloudflare.com`) and `localhost.run` assign a fresh random HTTPS subdomain on every restart of `start_mobile_bridge.bat`, forcing iPhone/Android users to re-scan a new QR code every time the PC restarts.

### Root Cause Analysis (RCA)
- Home broadband lacks a static public IP + trusted TLS certificate by default, while embedding transient tunnel origins in `?api=` ties the QR code lifetime to a single tunnel process.

### Corrective and Preventive Actions (CAPA)
1. **`mobile_bridge.py`, `.gitignore`**: Added `sync_fixed_bridge_gist()` using a Secret GitHub Gist (`audiostudio_bridge.json`, resolved via `GITHUB_GIST_TOKEN`, `.bridge_config.json`, or `gh auth token`). On startup it creates or `PATCH`es the same Gist with the active tunnel URL (`status: "online"`), and marks `status: "offline"` on clean shutdown; ignored `.bridge_config.json` in `.gitignore`.
2. **`app.py`, `templates/bridge.html`**: Validated `gist` query param against `GIST_ID_RE` and prioritized the permanent URL (`?bridge=<gist_id>`) for QR rendering.
3. **`static/js/script.js`, `static/sw.js`**: Added `getSavedBridgeGistId()` (retaining `?bridge=` in the URL so iOS "Add to Home Screen" PWAs preserve the fixed pointer across isolated Safari/PWA storage), `resolveBridgeFromGist()`, automatic self-healing reconnection inside `apiFetch()` (with 10s cooldown and polling opt-out), offline detection, and bumped Service Worker cache to `audiostudio-v3`.

## [2026-11-27] Auto-Reconnect Watchdog for Host Outages & Zombie Tunnels

### Problem
- Previously `mobile_bridge.py` blocked on `tunnel_proc.stdout.readline()` and exited as soon as the tunnel process died during prolonged internet outages or PPPoE IP changes, leaving the host server offline without recovery until manual restart.

### Corrective and Preventive Actions (CAPA)
1. **`mobile_bridge.py`**: Added daemon stdout draining (`_drain_stream`), external tunnel probe (`check_endpoint_health` checking `/api/health`), internet pre-check (`has_internet_connectivity`), and `_watchdog_step()` in `main()`:
   - Monitors both Flask and tunnel processes in a 1s non-blocking loop; automatically restarts Flask if crashed and rebuilds the tunnel immediately when `tunnel_proc` exits.
   - Runs a periodic `/api/health` probe (`HEALTH_CHECK_INTERVAL = 60s`); 3 consecutive failures trigger zombie tunnel termination and automatic rebuild.
   - Uses exponential backoff (`5s` up to `60s`) while offline, re-syncs the recovered tunnel URL to the same Secret GitHub Gist once online, and never re-opens duplicate browser tabs.
