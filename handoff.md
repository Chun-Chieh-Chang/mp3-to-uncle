# Handoff (更新於 2026-10-04)

## 目標
`mp3-to-uncle` (AudioStudio)：本機 Flask 應用，貼上連結下載影音。
要支援 YouTube、TikTok、小紅書。**小紅書要同時支援影片與圖片**。輸出直接存檔，不打包 ZIP。

## 已確認的決策
- TikTok：**只要影片**，不要圖片。
- 圖片功能（含 gallery-dl）已全部移除，gallery-dl 已解除安裝。
- 小紅書圖文：自寫解析器，**只限小紅書**。圖片存到 `downloads/標題/標題_NN.ext`。
- 只支援公開內容，不處理 cookies。
- 輸出格式：影片可選 MP3 或 MP4；音質選單只在選 MP3 時顯示。

## 目前進度
已完成並驗證：
- TikTok 短連結 `https://vt.tiktok.com/ZSbu5f73w/`：分析、MP4（23 MB）、MP3（6.7 MB）、檔案取回、無效格式回 400，全部通過。
- 檔名標題截短到 80 字防禦 Windows 路徑限制。
- 程式碼重構與死碼清理：清理重複 import 與函式，補齊本機 `/sw.js` 路由，消滅控制台 404。
- 最新可攜式執行檔已重新編譯完成：`dist/AudioStudio.exe`（99.4 MB）。
- 本地 Python 與靜態檔語法確效通過，零紅色錯誤。

尚未驗證：
- 小紅書影片與圖文（因本地受內政部警政署 NPA 阻斷轉址與自簽憑證影響，需切換至不受限連線環境重測）。

## 待辦（依序）
1. 取得使用者許可後，將乾淨版本推送（git push）至 GitHub 遠端倉庫。
2. 小紅書若需支援：切換至不受阻斷網路環境後，重測小紅書影片與圖文抓取。

## 已知問題與根因
- 小紅書下載失敗：連線 `www.xiaohongshu.com` 時由 `OU=NPA, O=MOI`（內政部警政署）自簽憑證接管，此為網路防護阻斷政策，非程式瑕疵。
- yt-dlp 內建小紅書 extractor 僅支援影片，若需支援圖文需待網路連通後編寫專用 JSON 解析器。
- gallery-dl 因無小紅書支援且 TikTok 使用者已決策不要圖片，已徹底自依賴中移除。

## 環境與指令
- Python：`C:\Python314\python.exe`；相依：flask、flask-cors、yt-dlp（見 `requirements.txt`）。
- 本機啟動：`python app.py`（port 5000）。
- 打包腳本：`python -m PyInstaller --clean AudioStudio.spec`。

## 變更項目
- `app.py`、`downloader.py`、`templates/index.html`、`static/js/script.js`、`static/manifest.json`、`DEV_LOG.md`、`handoff.md`。
- 新增：`requirements.txt`、`.agents/rules/handoff.md`。
- 移除：無效目錄 `.vscode/` 與編譯暫存 `build/`。
