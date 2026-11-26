# Handoff (更新於 2026-11-26)

## 目標
`mp3-to-uncle` (AudioStudio) 雙軌架構（路線 3）：
1. **網頁版 + PWA（GitHub Pages 前端 + Docker 雲端後端）**：支援電腦桌面、iPhone (iOS Safari)、macOS、Android 手機免安裝使用。
2. **Windows 可攜單機版（GitHub Releases）**：自動化建置 `AudioStudio.exe`，不限片長、走家用網路避免機房 IP 封鎖。

## 已確認的決策
- 採用 **路線 3（雙軌架構）**，目標裝置涵蓋 **iPhone (iOS) 與 macOS**，入口託管於 **GitHub Pages**。
- 前端維持零打包原生效能架構（Vanilla HTML/CSS/JS + Jinja `url_for`，相容 `.github/workflows/deploy.yml` 靜態替換）。
- 雲端後端改為非同步任務（`202` + `job_id` 輪詢）、每任務隔離資料夾、TTL 自動清理、SSRF 阻斷與 RFC 5987 中文檔名支援。

## 目前進度
已完成並驗證：
- 後端強化：`downloader.py`（跨平台 FFmpeg 檢查、SSRF `validate_url`、影片時長上限、環境變數支援）、`app.py`（非同步 `job_id` 佇列、`/api/health`、`/api/progress/<job_id>`、`/api/files/<job_id>` RFC 5987 下載、TTL 自動清檔）、`requirements.txt`（補上 `gunicorn`）。
- 容器化：`Dockerfile`（Python 3.12 + FFmpeg + Deno + Gunicorn + non-root `user`）、`.dockerignore`。
- 手機優先 PWA 前端：`templates/index.html`、`static/css/style.css`（Light/Dark 色彩規範與 375px 手機排版）、`static/js/config.js`、`static/js/script.js`（非同步輪詢、iOS 明確儲存按鈕、LINE/FB 內建瀏覽器提示、一鍵貼上、伺服器設定彈窗）、`static/manifest.json`、`static/sw.js`（`audiostudio-v2` 排除 `/api/`）。
- CI/CD 與文件：更新 `.github/workflows/deploy.yml`（注入 `vars.API_BASE_URL`）、新增 `.github/workflows/release-windows.yml`（自動編譯 `AudioStudio.exe` 上架 GitHub Releases）、新增 `DEPLOY.md`、更新 `DEV_LOG.md`。
- 自動化確效全數通過（Python `py_compile`、`node --check`、`manifest.json`、`deploy.yml` 模板替換模擬、Flask `test_client()` 全端點與 SSRF/RFC5987 檢查皆通過）。

尚未驗證（需推送與外部平台操作）：
- 實際將後端推上 Hugging Face Spaces Docker 並以真手機實測線上 YouTube/TikTok 下載（驗證機房 IP 風控狀況）。
- 觸發 GitHub Actions `Build & Release Windows Portable` 產出真實 GitHub Release。

## 待辦（依序）
1. 取得使用者許可後，執行 `git add`、`git commit` 與 `git push` 至 GitHub 遠端倉庫。
2. 依 `DEPLOY.md` 建立 Hugging Face Space (Docker) 並於 GitHub Repository Variables 設定 `API_BASE_URL`。
3. 推送 `v*` tag 或手動觸發 `release-windows.yml` 產出最新 `AudioStudio.exe` Release。

## 環境與指令
- 本機 Python（含 Flask / yt-dlp）：`C:\Users\USER\AppData\Local\Programs\Python\Python314\python.exe`
- 本機啟動：`C:\Users\USER\AppData\Local\Programs\Python\Python314\python.exe app.py`
- 部署與操作說明：見 `DEPLOY.md`

## 未提交變更
- 修改：`app.py`、`downloader.py`、`requirements.txt`、`templates/index.html`、`static/css/style.css`、`static/js/script.js`、`static/manifest.json`、`static/sw.js`、`.github/workflows/deploy.yml`、`DEV_LOG.md`、`handoff.md`
- 新增：`Dockerfile`、`.dockerignore`、`DEPLOY.md`、`static/js/config.js`、`.github/workflows/release-windows.yml`
- **尚未取得 `git push` 許可。**
