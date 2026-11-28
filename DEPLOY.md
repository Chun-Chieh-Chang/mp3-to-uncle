# AudioStudio 雙軌部署指南（網頁版 + Windows 可攜單機版）

本專案採用**雙軌架構**：
- **網頁前端（GitHub Pages）**：電腦、iPhone（iOS Safari）、macOS、Android 手機免安裝打開即用，支援加入主畫面（PWA）。
- **雲端轉檔後端（Render Free Docker）**：免綁信用卡、綁定 GitHub 自動建置與部署，內含 FFmpeg、Deno 與 `yt-dlp[default]`。
- **Windows 可攜單機版（GitHub Releases）**：一鍵自動化打包 `AudioStudio.exe`，不限片長、走家用網路避免機房 IP 限制。

---

## 步驟一：3 分鐘免費部署雲端後端（Render Free）

> 註：Hugging Face Spaces 的 Docker SDK 目前為付費項目，因此免費雲端後端建議優先使用 **Render Free (Docker)**（免信用卡）。

1. 前往 [https://render.com/](https://render.com/) 並使用 **GitHub** 登入。
2. 點選右上角 **+ New → Web Service**，連結倉庫 `Chun-Chieh-Chang/mp3-to-uncle`。
3. 設定欄位：
   - **Region**：`Singapore (Southeast Asia)`
   - **Branch**：`main`
   - **Runtime**：`Docker`（自動讀取本專案 `Dockerfile`）
   - **Instance Type**：**Free（$0 / month）**
4. **Environment Variables（建議設定）**：
   - `MAX_DURATION_SECONDS` = `1800`（Render 免費版為 512 MB RAM，限制 30 分鐘內影音避免 OOM）
5. 點擊 **Deploy Web Service**，等待建置完成（約 3–5 分鐘）。
6. 打開 `<你的網址>/api/health`（例如 `https://<你的服務名稱>.onrender.com/api/health`），確認回傳 `"status": "ok"`、`"ffmpeg": true`、`"deno": true`。

---

## 步驟二：連結 GitHub Pages 前端

1. 前往 GitHub 專案倉庫的 **Settings → Pages → Build and deployment → Source**，確認設為 **GitHub Actions**（本專案使用官方 Actions 部署，無需保留 `gh-pages` 分支）。
2. 前往 GitHub 專案倉庫的 **Settings → Secrets and variables → Actions → Variables**。
3. 點選 **New repository variable**，新增：
   - **Name**：`API_BASE_URL`
   - **Value**：`https://<你的服務名稱>.onrender.com`（勿加結尾斜線）
4. 前往倉庫的 **Actions** 分頁，點選 **Deploy to GitHub Pages → Run workflow** 重新部署。
5. 部署完成後，打開：
   ```text
   https://chun-chieh-chang.github.io/mp3-to-uncle/
   ```
   網頁會自動連向你的雲端後端。用戶也可在網頁右上角「**伺服器設定（調音圖示）**」自行測試或切換後端網址。

---

## 步驟三：一鍵自動編譯釋出 Windows 可攜單機版 (`AudioStudio.exe`)

不需在自己電腦手動跑 PyInstaller，GitHub Actions 已內建自動化建置與發佈流程（[release-windows.yml](.github/workflows/release-windows.yml)）：

- **方法 A（推送版號標籤）**：
  ```bash
  git tag v1.0.0
  git push origin v1.0.0
  ```
- **方法 B（GitHub 網頁手動觸發）**：
  進入 GitHub **Actions → Build & Release Windows Portable → Run workflow**，填入 `release_tag`（例如 `v1.0.0`）後執行。

完成後，檔案 `AudioStudio.exe` 與 `AudioStudio.exe.sha256` 會自動上架到 GitHub **Releases (Latest)**，網頁上的「**下載 Windows 可攜版**」按鈕會自動指向最新版。

---

## 手機端（iPhone / macOS / Android）使用說明

- **iPhone / 手機抓 YouTube 一鍵家用橋接（推薦，免 Cookies、永不 403）**：
  1. 免費公有雲（Render）機房 IP 容易被 YouTube API 封鎖為 HTTP 403/429，此時可改用自家 Windows 電腦當私人後端。
  2. 直接雙擊專案根目錄的 **`start_mobile_bridge.bat`**（首次會自動下載官方 `cloudflared` 並啟動本機伺服器）。
  3. **三層通道自動備援**：優先建立 **Cloudflare Quick Tunnel**（遇到 429 限流自動重試）→ 失敗時自動切換 **localhost.run SSH HTTPS 通道** → 外部通道皆受阻時自動退回**家用同 Wi-Fi 區網直連**。
  4. **永久固定 QR Code（可選）**：若本機已登入 `gh auth login` 或設定環境變數 `GITHUB_GIST_TOKEN`，橋接程式會自動建立並更新同一個 Secret GitHub Gist（`?bridge=<gist_id>`），手機掃碼「加入主畫面」後，電腦重開機或重建通道皆免重新掃碼。
  5. **斷線自動重連看門狗**：`mobile_bridge.py` 會持續監控本機 Flask 與外部通道健康狀態（`/api/health`），遇到網路中斷、PPPoE 換 IP 或僵屍通道時自動重建並同步最新位址。
  6. 用畢後只要關閉電腦上的黑色橋接視窗即立即中斷連線（並將固定 Gist 狀態標記為 `offline`）。
- **iPhone (iOS Safari) 儲存、試聽與安裝提醒**：
  1. 請用 **Safari** 開啟網站（勿停留在 LINE / FB / IG 內建瀏覽器）。
  2. 轉檔完成後，畫面會顯示**檔案名稱**、**預設儲存位置**及**內嵌音訊／影片試聽播放器**。
  3. 點擊綠色 **「點擊儲存檔案」** 按鈕並選擇「下載」（存於「**檔案 App → 下載項目**」），或點擊 **「分享 / 存到檔案或相簿」** 透過 iOS 原生分享選單直接保存。
  4. 點擊 Safari 下方「分享 → 加入主畫面」即可安裝為桌面 App。
- **macOS / Android / 類原生分享與背景續接體驗**：
  - **Android 系統分享選單（Web Share Target）**：透過 Chrome「加入主畫面」安裝為 PWA 後，在 YouTube / TikTok / 小紅書 App 點選「分享」即可直接選擇 **AudioStudio** 自動帶入連結分析。
  - **iPhone 一鍵分享捷徑（iOS Shortcuts）**：於 iPhone「捷徑」App 建立新捷徑（勾選「在分享表單中顯示」、輸入類型選 URL 與文字）→ 加入「URL 編碼」動作 → 加入「打開 URL」動作，網址填 `https://chun-chieh-chang.github.io/mp3-to-uncle/?bridge=<你的GistID>&url=<URL 編碼後的輸入>`，即可在 YouTube / 小紅書按系統分享一鍵開抓。
  - **切背景自動續接進度**：下載轉檔期間切換至其他 App（如 LINE）或重新整理頁面，回到 PWA 時會自動恢復任務並繼續追蹤進度，無需重新轉檔。
  - 若僅需 24 小時在手機下載 **TikTok**（無需電腦開機），可將 GitHub Repository Variable `API_BASE_URL` 設為 `https://mp3-to-uncle-us.onrender.com`。

---

## YouTube 雲端機房 IP 風控備援說明

公有雲免費機房 IP 有時會遇到 YouTube `Sign in to confirm you're not a bot` 或 player response 驗證。若發生此狀況，有兩種解法：
1. **電腦用戶**：直接下載使用 **Windows 可攜單機版**（走家用網路 IP，不觸發機房風控）。
2. **雲端環境設定 Cookies / Player Client**：
   - **Secret File（Render）**：將 Netscape 格式的 `cookies.txt` 上傳到 Render **Secret Files**（路徑 `/etc/secrets/cookies.txt`），並設定環境變數 `YTDLP_COOKIES_FILE=/etc/secrets/cookies.txt`。
   - **Base64 環境變數（通用）**：將 `cookies.txt` 轉成單行 Base64 後設為環境變數 `YTDLP_COOKIES_B64`（後端會自動解碼為暫存 cookies 檔供 `yt-dlp` 使用）。
   - **Player Client 與 JS Runtime**：後端預設採用 `yt-dlp` 原生最新 client 策略，並自動偵測環境中的 `deno`、`node`、`bun`、`quickjs` 等 JS runtime；如遇特定環境需求，亦可透過 `YTDLP_PLAYER_CLIENTS` 手動覆寫（例如 `web,tv` 或 `default`）。
