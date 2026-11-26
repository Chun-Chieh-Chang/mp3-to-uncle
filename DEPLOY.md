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
6. 打開 `<你的網址>/api/health`（例如 `https://mp3-to-uncle.onrender.com/api/health`），確認回傳 `"status": "ok"`、`"ffmpeg": true`、`"deno": true`。

---

## 步驟二：連結 GitHub Pages 前端

1. 前往 GitHub 專案倉庫的 **Settings → Secrets and variables → Actions → Variables**。
2. 點選 **New repository variable**，新增：
   - **Name**：`API_BASE_URL`
   - **Value**：`https://<你的服務名稱>.onrender.com`（勿加結尾斜線）
3. 前往倉庫的 **Actions** 分頁，點選 **Deploy to GitHub Pages → Run workflow** 重新部署。
4. 部署完成後，打開：
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

- **iPhone (iOS Safari)**：
  1. 請用 **Safari** 開啟網站（勿停留在 LINE / FB / IG 內建瀏覽器）。
  2. 轉檔完成後，點擊綠色 **「點擊儲存檔案」** 按鈕並選擇「下載」，檔案會存於「**檔案 App → 下載項目**」。
  3. 點擊 Safari 下方「分享 → 加入主畫面」即可安裝為桌面 App。
- **macOS / Android**：
  - 使用 Safari 或 Chrome 開啟並加入主畫面即可；Android Chrome 亦會顯示「立即安裝到主畫面」按鈕。

---

## YouTube 雲端機房 IP 風控備援說明

公有雲免費機房 IP 有時會遇到 YouTube `Sign in to confirm you're not a bot` 或 player response 驗證。若發生此狀況，有兩種解法：
1. **電腦用戶**：直接下載使用 **Windows 可攜單機版**（走家用網路 IP，不觸發機房風控）。
2. **雲端環境設定 Cookies / Player Client**：
   - **Secret File（Render）**：將 Netscape 格式的 `cookies.txt` 上傳到 Render **Secret Files**（路徑 `/etc/secrets/cookies.txt`），並設定環境變數 `YTDLP_COOKIES_FILE=/etc/secrets/cookies.txt`。
   - **Base64 環境變數（通用）**：將 `cookies.txt` 轉成單行 Base64 後設為環境變數 `YTDLP_COOKIES_B64`（後端會自動解碼為暫存 cookies 檔並切換為支援 Cookies 的 `web,tv` client）。
   - 或手動覆寫 `YTDLP_PLAYER_CLIENTS`（例如 `android_vr,web,tv` 或 `default`）。
