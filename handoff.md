# Handoff (更新於 2026-11-28)

## 目標
`mp3-to-uncle` (AudioStudio) 雙軌 + 類原生 PWA + 手機橋接架構：
1. **網頁版 + PWA（GitHub Pages 前端）**：以單一 `main` 分支透過官方雙 Job GitHub Actions（`build` → `deploy`）部署，支援電腦、iPhone（iOS Safari）、macOS、Android 安裝與使用。
   - **24 小時雲端後端（Render `https://mp3-to-uncle-us.onrender.com`）**：GitHub Variable `API_BASE_URL` 已指向此節點；支援 TikTok 與小紅書影片（含 `xhslink.cn` / `rednote.com` 短網址與登入跳轉自動還原）。
   - **家用電腦橋接（`start_mobile_bridge.bat` + `mobile_bridge.py`）**：支援三層通道備援（Cloudflare Quick Tunnel → `localhost.run` SSH HTTPS → 家用 Wi-Fi 區網）、Secret GitHub Gist 永久固定 QR Code（`?bridge=<gist_id>`）、斷線自動重連看門狗，以及 Windows 連接埠衝突自動避讓（偵測 `127.0.0.1` / `0.0.0.0` 佔用與 `/bridge` 就緒檢查）。
   - **類原生 PWA 體驗（`sw.js` `audiostudio-v8`）**：支援 Android `share_target` 與 iPhone 捷徑 `?url=`/`?text=` 自動分析、切背景自動續接 `/api/progress/<job_id>`、即時 MB／速度／ETA 與 FFmpeg 階段顯示、時長補抓，以及 iOS 分享手勢逾時 (`NotAllowedError`) 引導。
2. **Windows 可攜單機版（GitHub Releases）**：已更新 [`release-windows.yml`](.github/workflows/release-windows.yml) 納入 `--collect-all yt_dlp_ejs`，並發佈 `v1.1.0`（桌面 `C:\Users\3kids\Desktop\AudioStudio.exe` 已同步）。

## 目前進度
- 已完成無效 JS 欄位清理（`translations.*.processing`、`saveActiveJob` 未使用 `apiBase`）、移除過時 Render 範例網址、清除工作區重複的 `dist/` 副本（保留 `.bridge_config.json` 與 `bin/`）並通過本地驗證，已於本地建立清理 commit（待使用者許可後推送）。

## 待辦（依序）
1. 取得使用者明確許可後，執行 `git push origin main` 將最新清理與文件同步至遠端（觸發 GitHub Pages 更新至 `audiostudio-v8`）。

## 環境與指令
- 一鍵啟動手機橋接：雙擊 `start_mobile_bridge.bat`（非互動檢查：`cmd /c start_mobile_bridge.bat --check`）
- 本機伺服器啟動：`python app.py`（自動偵測 `bin/ffmpeg.exe` 與本機 JS runtime）
