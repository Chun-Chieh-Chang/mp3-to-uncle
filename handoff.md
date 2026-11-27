# Handoff (更新於 2026-11-27)

## 目標
`mp3-to-uncle` (AudioStudio) 雙軌 + 手機橋接架構：
1. **網頁版 + PWA（GitHub Pages 前端）**：支援電腦桌面、iPhone (iOS Safari)、macOS、Android 免安裝使用。
   - **24 小時雲端後端（Render `https://mp3-to-uncle-us.onrender.com`）**：穩定支援 TikTok 等非機房封鎖平台。
   - **家用電腦橋接（`start_mobile_bridge.bat` + `mobile_bridge.py`）**：支援三層通道備援（Cloudflare Quick Tunnel → `localhost.run` SSH HTTPS → 家用 Wi-Fi 區網）、Secret GitHub Gist 永久固定 QR Code（`?bridge=<gist_id>`）及斷線自動重連看門狗，讓手機借用住宅 IP 穩定下載 YouTube。
2. **Windows 可攜單機版（GitHub Releases）**：已透過 `release-windows.yml`（標籤 `v1.0.0`）自動建置 `AudioStudio.exe`。

## 已確認的決策與現況
- **Render 免費機房 IP 限制**：新加坡與美國 Oregon 機房對 YouTube `youtubei/v1/player` 會觸發 HTTP 403；TikTok 正常。YouTube 手機下載由家用橋接處理。
- **iOS 方案**：採用 GitHub Pages PWA（`sw.js` `audiostudio-v4`）+ 內嵌音訊／影片試聽 + 原生 `navigator.share` 儲存 + 家用橋接 QR Code。
- **代碼與檔案清理（MECE）**：已移除死碼（`_resolve_cookies_file`）、重複常數與匯入（`ANSI_RE`、`Timer`、未用模板參數）、未用 CSS/JS 欄位、`.gitignore`/`.dockerignore` 重複與遺漏項目、過時 Hugging Face 文案、重複 `DEV_LOG.md` 區塊，以及過時本機建置產物（`AudioStudio.spec`、`dist/`、`__pycache__/`）。

## 目前進度
- 所有清理修改已完成並通過本地語法與 Flask 運行確效測試，已於本地建立 Git commit（待使用者許可後推送）。

## 待辦（依序）
1. 取得使用者明確許可後，執行 `git push origin main` 將最新清理與文件同步至遠端（觸發 GitHub Pages 更新）。
2. 確認 GitHub Repository Variable `API_BASE_URL` 與實際雲端後端設定一致（若需 24 小時雲端下載 TikTok）。

## 環境與指令
- 一鍵啟動手機橋接：雙擊 `start_mobile_bridge.bat`（非互動檢查：`cmd /c start_mobile_bridge.bat --check`）
- 本機伺服器啟動：`python app.py`（自動偵測 `bin/ffmpeg.exe` 與本機 JS runtime）
