# Handoff (更新於 2026-11-28)

## 1. 目標
1. **既有系統架構（`mp3-to-uncle` / AudioStudio 雙軌 + 類原生 PWA + 手機橋接）**：
   - **網頁版 + PWA（GitHub Pages 前端）**：單一 `main` 分支透過官方雙 Job GitHub Actions（`build` → `deploy`）部署至 `https://chun-chieh-chang.github.io/mp3-to-uncle/`；24 小時雲端後端為 Render US（`https://mp3-to-uncle-us.onrender.com`），支援 YouTube、TikTok 與小紅書影片（含 `xhslink.cn` / `rednote.com` 短網址與登入跳轉還原）。
   - **家用電腦橋接（`start_mobile_bridge.bat` + `mobile_bridge.py`）**：三層通道備援（Cloudflare Quick Tunnel → `localhost.run` SSH HTTPS → 家用 Wi-Fi 區網）、Secret GitHub Gist 永久固定 QR Code（`?bridge=<gist_id>`）、斷線自動重連看門狗，以及 Windows 連接埠衝突自動避讓。
   - **類原生 PWA 體驗（`sw.js` `audiostudio-v9`）** 與 **Windows 可攜單機版（`v1.1.0`）**。
2. **新增功能（已實作完成）**：
   - 下載小紅書圖文筆記。使用者已確認三項建議方案：Q1-A 格狀預覽＋勾選單張下載／分享＋一鍵 ZIP；Q2-A 預設以 FFmpeg 轉成高畫質 **PNG**，並保留原檔切換；Q3-A 第一階段僅處理靜態高畫質圖，實況圖動態 MP4 留待第二階段。

## 2. 目前進度
- **已完成並驗證**：
  - 上一輪清理工作已提交於本地 commit `3bc1a7c`（`chore: prune dead JS fields, remove duplicate dist artifact, and sync handoff/docs`），且與 `origin/main` 對齊。
  - **後端 `downloader.py`**：新增 CDN 白名單、 `_extract_xhs_note_state()`（以 yt-dlp 自身的下載器與 `js_to_json` 解析 `window.__INITIAL_STATE__`）、`_xhs_images_from_note()`、`get_xhs_images_info()`，並讓 `get_video_info()` 以 `media_type: "images" | "video"` 分流；新增 `fetch_xhs_image_bytes()`（20 MB 上限、Referer、禁止重新導向到外部 Host）、`convert_image_bytes_to_png()`（复用現有 FFmpeg）、`download_xhs_images()`（嚴格索引驗證、單張或 ZIP、30 張上限、逐張進度）。
  - **後端 `app.py`**：`POST /api/info` 簽發 30 分鐘有效的 `gallery_token`；新增 `GET /api/xhs-image/<token>/<int:index>` token 限定圖片代理（僅能讀取伺服器端已驗證的 CDN URL，拒絕任意 URL 代理）；`POST /api/download` 支援 `mode="images"` 與 `image_indices` / `image_format`；`serve_file()` 補齊 ZIP／PNG／WebP／JPEG MIME。
  - **前端**：`templates/index.html` 新增 `#imageGallerySection`（手機兩欄、桌面三欄、4px 間距、44px 觸控目標、`data-zh` / `data-en` 雙語）；`static/js/script.js` 加入格狀預覽、勾選、格式切換、單張下載／分享（含 iOS `NotAllowedError` 兩段式點擊）、批次 ZIP 任務與背景復原，並讓圖片代理與任務輪詢共用 `currentApiBaseOverride`；`static/css/style.css` 加入圖庫樣式；`static/sw.js` 升版至 `audiostudio-v9`。
  - **驗證結果**：`py_compile`、`node --check`、合成 `__INITIAL_STATE__` 解析與 CDN 白名單、真實 FFmpeg WebP→PNG、ZIP 內容與 MIME、Flask `test_client()` 的 token／索引／格式／404／400／202→ready 流程、影片流程迴歸與前端結構檢查全部通過（`ALL_XHS_IMAGE_VERIFICATIONS_PASSED`、`ALL_XHS_FRONTEND_CHECKS_PASSED`）。
- **尚未執行**：
  - `git commit` / `git push`（等待使用者許可）。
  - 以真實小紅書圖文連結做部署後端到端抽測。
  - 實況圖動態 MP4（Q3-A 第二階段）。

## 3. 待辦清單（依優先順序）
1. 取得使用者許可後提交並推送本次變更。
2. Render／GitHub Pages 部署完成後，用真實圖文筆記連結抽測分析、預覽、ZIP 與 iOS 分享；若遇到登入牆或驗證碼，再評估設定 Cookies 或改用家用橋接。
3. 第二階段再評估 Live Photo 動態 MP4 支援。

## 4. 已知問題與根因
1. **`yt-dlp` 拒絕小紅書純圖文筆記**：`XiaoHongShuIE` 僅從 `note.video.media.stream` 建立 `formats`，純圖文筆記因無影片串流而失敗，但所有圖片 URL 已存在於 `window.__INITIAL_STATE__ -> note.noteDetailMap[id].note.imageList`；本次改由共用解析器直接讀取該結構。
2. **台灣 ISP DNS 攔截小紅書網域**：本地網路可能觸發 `CERTIFICATE_VERIFY_FAILED` / 自簽憑證錯誤；前端既有自動切換至 Render 雲端（`currentApiBaseOverride`）已貫穿至圖片代理、單張下載與 ZIP 輪詢。
3. **跨網域防盜鏈與 Open Proxy 風險**：後端代理必須採用 `gallery_token` + 伺服器端索引映射，嚴禁任意 URL 參數代理；本次已加入 CDN Host 白名單、禁止重新導向與大小上限。
4. **Windows CLI Python 呼叫注意**：優先使用 `C:\Python314\python.exe` 或 `.venv\Scripts\python.exe`，避免 PyManager shim。
5. **文件格式決策差異**：原計畫書 artifact 內文寫 JPG；使用者於本次明確指定 Q2-A 為 **PNG**，因此程式碼、驗證與本文件一律以 PNG 為預設，原始檔（多為 WebP）可切換。
6. **驗證邊界**：本次以合成的 `__INITIAL_STATE__` 與本機 FFmpeg 驗證，未使用真實小紅書連結；小紅書反爬蟲／登入牆風險需在上線後抽測確認。

## 5. 環境與指令
- **GitHub Pages 前端**：`https://chun-chieh-chang.github.io/mp3-to-uncle/`
- **24 小時雲端後端（Render US）**：`https://mp3-to-uncle-us.onrender.com`
- **一鍵啟動手機橋接**：雙擊 `start_mobile_bridge.bat`（非互動檢查：`cmd /c start_mobile_bridge.bat --check`）
- **本機伺服器啟動**：`C:\Python314\python.exe app.py`（或 `.venv\Scripts\python.exe app.py`）
- **核心依賴**：`requirements.txt`（`flask`、`flask-cors`、`yt-dlp[default]`、`gunicorn`）與 `bin/ffmpeg.exe` / 系統 `ffmpeg`
- **圖文驗證腳本**：`C:\Python314\python.exe C:\Users\3kids\AppData\Local\Temp\verify_xhs_images.py`、`node C:\Users\3kids\AppData\Local\Temp\verify_xhs_frontend.js`（本機臨時腳本，不進版本庫）

## 6. 未提交變更
- `git status` 預期變更：`app.py`、`downloader.py`、`templates/index.html`、`static/css/style.css`、`static/js/script.js`、`static/sw.js`、`DEV_LOG.md`、`handoff.md`。
- **Push 許可狀態**：尚未向使用者請求或取得 `git push` 許可。
