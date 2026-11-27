# Handoff (更新於 2026-11-27)

## 目標
`mp3-to-uncle` (AudioStudio) 雙軌 + 手機橋接架構：
1. **網頁版 + PWA（GitHub Pages 前端）**：支援電腦桌面、iPhone (iOS Safari)、macOS、Android 免安裝使用。
   - **24 小時雲端後端（Render `https://mp3-to-uncle-us.onrender.com`）**：穩定支援 TikTok 等非機房封鎖平台。
   - **家用電腦橋接（`start_mobile_bridge.bat`）**：一鍵啟動本機 Flask + Cloudflare Tunnel + QR Code 掃碼直連（`?api=...`），讓 iPhone / Android 借用自家住宅 IP 100% 穩定抓 YouTube（免 Cookies、永不 403）。
2. **Windows 可攜單機版（GitHub Releases）**：已建立標籤 `v1.0.0` 自動建置 `AudioStudio.exe`。

## 已確認的決策與實測結論
- **Render 免費機房 IP 限制**：已於新加坡與美國 Oregon（搭配 `/robots.txt` 新匯出 Cookies）雙重實測，YouTube 對 `youtubei/v1/player` API 皆回傳 `HTTP Error 403: Forbidden`；TikTok 正常。
- **iOS 方案**：Apple 沙盒與 7 天重簽限制導致無法做永久免費獨立 `.ipa`，採用 **GitHub Pages PWA + `start_mobile_bridge.bat` 掃碼橋接**為最佳解法。

## 目前進度
已完成並驗證：
- 前端 `?api=` 安全解析與自動記憶連線（`static/js/script.js`）。
- 後端 `/bridge` QR Code 頁面與 XSS/Scheme 防護（`app.py`、`templates/bridge.html`）。
- 一鍵橋接腳本與自動下載 `cloudflared`（`mobile_bridge.py`、`start_mobile_bridge.bat`）。
- 文件同步更新（`DEPLOY.md`、`DEV_LOG.md`、`handoff.md`）。

## 待辦（依序）
1. 取得使用者許可後，`git commit` 並 `git push` 至 `origin/main`（讓 GitHub Pages 更新支援 `?api=` 自動連線）。
2. 確認 GitHub Repository Variable `API_BASE_URL` 已更新為 `https://mp3-to-uncle-us.onrender.com`（供平時無開電腦時雲端抓 TikTok）。
3. 雙擊 `start_mobile_bridge.bat` 並以 iPhone 相機掃碼實測 YouTube 下載與「加入主畫面」。

## 環境與指令
- 本機 Python（含 Flask / yt-dlp）：`C:\Users\USER\AppData\Local\Programs\Python\Python314\python.exe`
- 一鍵啟動手機橋接：雙擊 `start_mobile_bridge.bat`
- 本機啟動：`C:\Users\USER\AppData\Local\Programs\Python\Python314\python.exe app.py`
