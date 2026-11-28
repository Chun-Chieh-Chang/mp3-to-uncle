document.addEventListener('DOMContentLoaded', () => {
    const STORAGE_API_KEY = 'audiostudio_api_base';
    const STORAGE_BRIDGE_GIST_KEY = 'audiostudio_bridge_gist';
    const STORAGE_ACTIVE_JOB_KEY = 'audiostudio_active_job';
    const STORAGE_THEME_KEY = 'audiostudio_theme';
    const GIST_ID_RE = /^[a-f0-9]{20,64}$/i;
    const BRIDGE_REFRESH_COOLDOWN_MS = 10000;
    const ACTIVE_JOB_MAX_AGE_MS = 20 * 60 * 1000;
    const POLL_INTERVAL_MS = 1500;
    const MAX_POLL_ERRORS = 8;

    const urlInput = document.getElementById('urlInput');
    const pasteBtn = document.getElementById('pasteBtn');
    const clearBtn = document.getElementById('clearBtn');
    const fetchBtn = document.getElementById('fetchBtn');
    const downloadBtn = document.getElementById('downloadBtn');

    const langToggle = document.getElementById('langToggle');
    const langText = document.getElementById('langText');
    const themeToggle = document.getElementById('themeToggle');
    const themeIcon = document.getElementById('themeIcon');

    const inAppBanner = document.getElementById('inAppBanner');
    const backendNotice = document.getElementById('backendNotice');
    const openSettingsFromNotice = document.getElementById('openSettingsFromNotice');
    const jumpToPortableBtn = document.getElementById('jumpToPortableBtn');
    const distributionCard = document.getElementById('distributionCard');

    const videoInfoSection = document.getElementById('videoInfoSection');
    const videoThumb = document.getElementById('videoThumb');
    const videoTitle = document.getElementById('videoTitle');
    const videoDuration = document.getElementById('videoDuration');
    const durationLimitWarn = document.getElementById('durationLimitWarn');
    const qualitySelect = document.getElementById('qualitySelect');
    const modeSelect = document.getElementById('modeSelect');
    const qualityGroup = document.getElementById('qualityGroup');
    const videoControlsGrid = document.getElementById('videoControlsGrid');
    const imageGallerySection = document.getElementById('imageGallerySection');
    const imageGalleryGrid = document.getElementById('imageGalleryGrid');
    const imageCountText = document.getElementById('imageCountText');
    const imageFormatSelect = document.getElementById('imageFormatSelect');
    const selectAllImagesBtn = document.getElementById('selectAllImagesBtn');
    const clearSelectionImagesBtn = document.getElementById('clearSelectionImagesBtn');
    const downloadSelectedImagesBtn = document.getElementById('downloadSelectedImagesBtn');
    const shareSelectedImagesBtn = document.getElementById('shareSelectedImagesBtn');
    const zipAllImagesBtn = document.getElementById('zipAllImagesBtn');

    const progressSection = document.getElementById('progressSection');
    const progressBar = document.getElementById('progressBar');
    const progressPercentage = document.getElementById('progressPercentage');
    const progressStatusText = document.getElementById('progressStatusText');

    const saveFileSection = document.getElementById('saveFileSection');
    const saveFileLink = document.getElementById('saveFileLink');
    const savedFileName = document.getElementById('savedFileName');
    const savedLocationText = document.getElementById('savedLocationText');
    const mediaPreviewWrap = document.getElementById('mediaPreviewWrap');
    const audioPreview = document.getElementById('audioPreview');
    const videoPreview = document.getElementById('videoPreview');
    const shareFileBtn = document.getElementById('shareFileBtn');

    const statusMessage = document.getElementById('statusMessage');
    const statusText = document.getElementById('statusText');

    const winDownloadBtn = document.getElementById('winDownloadBtn');
    const pwaInstallBtn = document.getElementById('pwaInstallBtn');

    // Settings modal elements
    const serverSettingsBtn = document.getElementById('serverSettingsBtn');
    const settingsModal = document.getElementById('settingsModal');
    const closeSettingsBtn = document.getElementById('closeSettingsBtn');
    const apiBaseInput = document.getElementById('apiBaseInput');
    const testConnBtn = document.getElementById('testConnBtn');
    const resetSettingsBtn = document.getElementById('resetSettingsBtn');
    const saveSettingsBtn = document.getElementById('saveSettingsBtn');
    const settingsStatus = document.getElementById('settingsStatus');
    const settingsStatusText = document.getElementById('settingsStatusText');

    let currentUrl = '';
    let currentApiBaseOverride = null;
    let currentLang = 'zh';
    let activePollTimer = null;
    let activePollFn = null;
    let activeJobState = null;
    let pollInFlight = false;
    let deferredInstallPrompt = null;
    let lastSavedLocalPath = null;
    let lastReadyFileUrl = '';
    let lastReadyFilename = '';
    let lastReadyMimeType = '';
    let lastReadyFile = null;
    let lastBridgeRefreshAt = 0;

    let currentMediaType = 'video';
    let currentGalleryToken = '';
    let currentImages = [];
    let currentSelectedImages = new Set();
    let currentImageCount = 0;
    let pendingBatchShare = null;
    const pendingImageShares = new Map();

    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
        (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    const isAndroid = /Android/i.test(navigator.userAgent);
    const isMac = /Macintosh|Mac OS X/i.test(navigator.userAgent) && !isIOS;
    const isInAppBrowser = /Line|FBAN|FBAV|Instagram|MicroMessenger/i.test(navigator.userAgent);

    const translations = {
        en: {
            loading: 'Loading...',
            analyzing: 'Analyzing...',
            queued: 'Queued for processing...',
            starting_download: 'Connecting to media server...',
            downloading: 'Downloading & Converting...',
            converting: 'Converting / Packaging (FFmpeg)...',
            poll_retrying: 'Network hiccup, retrying',
            cloud_fallback_retry: 'Local DNS blocked Xiaohongshu; switching to cloud server (may take ~30s to wake)...',
            error_no_url: 'Please enter a valid URL',
            error_no_backend: 'Cloud backend URL is not configured. Open Server Settings or use the Windows Portable App.',
            error_fetch_info: 'Failed to fetch video information',
            error_network: 'Network error occurred while fetching info',
            error_download: 'Failed to download file',
            error_network_download: 'Network error occurred during download',
            error_clipboard: 'Unable to read clipboard automatically. Please paste manually.',
            success_download: 'Ready! Tap "Tap to Save File" below if download did not start automatically.',
            finished: 'Ready to save!',
            failed: 'Failed!',
            conn_ok: 'Connected! Backend & FFmpeg ready.',
            conn_no_ffmpeg: 'Backend reachable, but FFmpeg is missing.',
            conn_fail: 'Connection failed. Check URL and CORS/HTTPS.',
            settings_saved: 'Server settings saved.',
            settings_reset: 'Server settings cleared.',
            api_autoconnect: 'Connected to custom backend from link!',
            share_btn_default: 'Share / Save to Files or Photos',
            share_preparing: 'Preparing file',
            share_tap_again: 'File Ready — Tap Again to Share',
            share_ready_hint: 'File downloaded to browser memory. Tap "File Ready — Tap Again to Share" now to open the iOS Share Sheet.',
            share_fetch_fail: 'Failed to fetch file for sharing. Please tap "Tap to Save File" above.',
            share_unsupported: 'Your browser does not support direct file sharing. Please use "Tap to Save File" above.',
            resuming_job: 'Resuming background download progress...',
            job_expired: 'Previous background job expired. Tap "Start Convert & Download" to run again.',
            share_url_received: 'Shared link detected — analyzing automatically...',
            bridge_connecting: 'Connecting to your fixed home PC server...',
            bridge_connected: 'Connected to your fixed home PC server!',
            bridge_offline: 'Home PC server is currently offline. Please run start_mobile_bridge.bat on your PC.',
            bridge_fetch_fail: 'Unable to look up latest home server address. Check your network and try again.',
            image_note: 'Image note',
            image_no_selection: 'Select at least one image first.',
            image_downloading: 'Downloading images...',
            image_zipping: 'Packaging images into ZIP...',
            image_share_preparing: 'Preparing image',
            image_share_tap_again: 'Image Ready — Tap Again to Share',
            image_share_hint: 'Image is ready in memory. Tap the button again to open the share sheet.',
            image_share_unsupported: 'This browser cannot share files directly. Use the download button instead.'
        },
        zh: {
            loading: '載入中...',
            analyzing: '分析中...',
            queued: '排隊處理中...',
            starting_download: '正在連線取得影音串流...',
            downloading: '正在下載與轉檔...',
            converting: '正在轉檔與封裝檔案 (FFmpeg)...',
            poll_retrying: '網路波動，重試中',
            cloud_fallback_retry: '偵測到本地 DNS 攔截小紅書，自動切換雲端後端重試中（喚醒約需 30 秒）...',
            error_no_url: '請輸入有效的連結',
            error_no_backend: '尚未設定雲端後端網址，請點擊右上「伺服器設定」或改用下方 Windows 可攜版。',
            error_fetch_info: '獲取影片資訊失敗',
            error_network: '獲取資訊時發生網路錯誤',
            error_download: '下載檔案失敗',
            error_network_download: '下載過程發生網路錯誤',
            error_clipboard: '無法自動讀取剪貼簿，請長按輸入框手動貼上。',
            success_download: '轉檔完成！若未自動下載，請點擊下方「點擊儲存檔案」按鈕。',
            finished: '已完成，請儲存！',
            failed: '失敗！',
            conn_ok: '連線成功！後端與 FFmpeg 已就緒。',
            conn_no_ffmpeg: '後端可連線，但缺少 FFmpeg。',
            conn_fail: '連線失敗，請確認網址正確且支援 HTTPS。',
            settings_saved: '已儲存伺服器設定。',
            settings_reset: '已清除自訂伺服器設定。',
            api_autoconnect: '已從專屬連結自動連線至後端伺服器！',
            share_btn_default: '分享 / 存到檔案或相簿',
            share_preparing: '準備分享中',
            share_tap_again: '檔案已就緒，再點一次立即分享',
            share_ready_hint: '檔案已下載至暫存，請再點一次上方「檔案已就緒，再點一次立即分享」開啟系統分享選單！',
            share_fetch_fail: '讀取檔案失敗，請改用上方「點擊儲存檔案」。',
            share_unsupported: '此瀏覽器不支援直接分享檔案，請點擊上方「點擊儲存檔案」。',
            resuming_job: '正在恢復背景下載進度...',
            job_expired: '先前的背景下載任務已過期，請重新點擊「開始轉換並下載」。',
            share_url_received: '已收到分享連結，正在自動分析...',
            bridge_connecting: '正在連線至固定家用電腦伺服器...',
            bridge_connected: '已自動連線至最新家用電腦伺服器！',
            bridge_offline: '家用電腦伺服器目前未開機，請先在電腦啟動 start_mobile_bridge.bat。',
            bridge_fetch_fail: '無法取得最新家用伺服器位址，請確認網路後再試。',
            image_note: '圖文筆記',
            image_no_selection: '請先勾選至少一張圖片。',
            image_downloading: '正在下載圖片...',
            image_zipping: '正在打包 ZIP...',
            image_share_preparing: '準備分享圖片中',
            image_share_tap_again: '圖片已就緒，再點一次立即分享',
            image_share_hint: '圖片已下載至暫存，請再點一次按鈕開啟系統分享選單！',
            image_share_unsupported: '此瀏覽器不支援直接分享圖片，請改用下載按鈕。'
        }
    };

    // Apply releases URL from config
    const cfg = window.AUDIOSTUDIO_CONFIG || {};
    if (cfg.releasesUrl && winDownloadBtn) {
        winDownloadBtn.href = cfg.releasesUrl;
    }

    // Calculate base path for same-origin deployment
    const pathSegments = window.location.pathname.split('/');
    if (pathSegments[pathSegments.length - 1].includes('.')) pathSegments.pop();
    const basePath = pathSegments.join('/').replace(/\/$/, '');

    function normalizeApiUrl(raw) {
        return (raw || '').trim().replace(/\/+$/, '');
    }

    function isValidBackendUrl(raw) {
        try {
            const parsed = new URL((raw || '').trim());
            const isLocalHttp = parsed.protocol === 'http:' &&
                (parsed.hostname === 'localhost' || parsed.hostname === '127.0.0.1');
            if (parsed.protocol === 'https:' || isLocalHttp) {
                return normalizeApiUrl(parsed.origin + parsed.pathname);
            }
        } catch {
            // Ignore malformed URL
        }
        return null;
    }

    function getSavedBridgeGistId() {
        try {
            const currentPageUrl = new URL(window.location.href);
            const urlGist = (currentPageUrl.searchParams.get('bridge') || '').trim();
            if (GIST_ID_RE.test(urlGist)) {
                localStorage.setItem(STORAGE_BRIDGE_GIST_KEY, urlGist);
                return urlGist;
            }
        } catch {
            // Ignore URL parse failures
        }
        const stored = (localStorage.getItem(STORAGE_BRIDGE_GIST_KEY) || '').trim();
        return GIST_ID_RE.test(stored) ? stored : null;
    }

    async function resolveBridgeFromGist(gistId, { silent = false } = {}) {
        if (!gistId || !GIST_ID_RE.test(gistId)) {
            return { ok: false, offline: false, apiUrl: null };
        }
        try {
            const resp = await fetch(`https://api.github.com/gists/${gistId}`, {
                cache: 'no-store',
                headers: { Accept: 'application/vnd.github+json' }
            });
            if (!resp.ok) {
                throw new Error(`HTTP ${resp.status}`);
            }
            const gistData = await resp.json();
            const fileObj = gistData && gistData.files && gistData.files['audiostudio_bridge.json'];
            if (!fileObj || !fileObj.content) {
                throw new Error('Missing bridge pointer file');
            }
            const payload = JSON.parse(fileObj.content);
            const validUrl = isValidBackendUrl(payload.api_url);
            if (payload.status === 'offline') {
                if (!silent) {
                    showStatus('bridge_offline', true);
                }
                return { ok: false, offline: true, apiUrl: validUrl };
            }
            if (!validUrl) {
                throw new Error('Invalid api_url in bridge pointer');
            }
            localStorage.setItem(STORAGE_API_KEY, validUrl);
            refreshBackendNotice();
            if (!silent) {
                showStatus('bridge_connected', false);
            }
            return { ok: true, offline: false, apiUrl: validUrl };
        } catch {
            if (!silent) {
                showStatus('bridge_fetch_fail', true);
            }
            return { ok: false, offline: false, apiUrl: null };
        }
    }

    function getApiBaseUrl() {
        const stored = normalizeApiUrl(localStorage.getItem(STORAGE_API_KEY));
        if (stored) return stored;

        const configured = normalizeApiUrl(cfg.apiBaseUrl);
        if (configured) return configured;

        if (window.location.hostname.includes('github.io')) {
            return null;
        }
        return basePath;
    }

    function refreshBackendNotice() {
        const apiBase = getApiBaseUrl();
        backendNotice.classList.toggle('hidden', apiBase !== null);
    }

    // Theme management
    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem(STORAGE_THEME_KEY, theme);
        themeIcon.textContent = theme === 'dark' ? 'light_mode' : 'dark_mode';
    }

    const savedTheme = localStorage.getItem(STORAGE_THEME_KEY) ||
        (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    applyTheme(savedTheme);

    themeToggle.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme') || 'light';
        applyTheme(current === 'dark' ? 'light' : 'dark');
    });

    // Show in-app browser warning if applicable
    if (isInAppBrowser && inAppBanner) {
        inAppBanner.classList.remove('hidden');
    }

    function syncQualityVisibility() {
        qualityGroup.classList.toggle('hidden', modeSelect.value !== 'mp3');
    }
    modeSelect.addEventListener('change', syncQualityVisibility);

    function syncClearButton() {
        clearBtn.classList.toggle('hidden', urlInput.value.trim().length === 0);
    }
    urlInput.addEventListener('input', syncClearButton);

    pasteBtn.addEventListener('click', async () => {
        try {
            if (navigator.clipboard && navigator.clipboard.readText) {
                const text = await navigator.clipboard.readText();
                if (text) {
                    urlInput.value = extractFirstUrl(text);
                    syncClearButton();
                    urlInput.focus();
                    return;
                }
            }
            showStatus('error_clipboard', true);
        } catch {
            showStatus('error_clipboard', true);
        }
    });

    clearBtn.addEventListener('click', () => {
        urlInput.value = '';
        syncClearButton();
        urlInput.focus();
    });

    function getDefaultSaveLocation(localPath = null) {
        const isZh = currentLang === 'zh';
        let baseLocation = '';
        if (isIOS) {
            baseLocation = isZh
                ? '「檔案」App →「下載項目」（可能在「iCloud 雲碟」或「我的 iPhone」內），或點 Safari 網址列藍色「↓」圖示直接開啟'
                : 'Files app -> Downloads (under iCloud Drive or On My iPhone), or tap the blue "↓" icon in Safari\'s address bar';
        } else if (isAndroid) {
            baseLocation = isZh
                ? '「檔案」App → 內部儲存空間 / Download（下載），或 Chrome「⋮ → 下載內容」'
                : 'Files app -> Internal Storage / Download, or Chrome menu -> Downloads';
        } else if (isMac) {
            baseLocation = isZh
                ? 'Finder →「下載項目 (Downloads)」'
                : 'Finder -> Downloads';
        } else {
            baseLocation = isZh
                ? '瀏覽器預設「下載 (Downloads)」資料夾（按 Ctrl+J 可開啟）'
                : 'Browser Downloads folder (press Ctrl+J to open)';
        }

        if (localPath) {
            const sep = isZh ? ' ｜ 本機伺服器備份：' : ' | Local server copy: ';
            return `${baseLocation}${sep}${localPath}`;
        }
        return baseLocation;
    }

    function setShareButtonDefault() {
        shareFileBtn.disabled = false;
        shareFileBtn.innerHTML =
            `<span class="material-symbols-outlined">ios_share</span> ` +
            `<span data-en="${translations.en.share_btn_default}" data-zh="${translations.zh.share_btn_default}">${translations[currentLang].share_btn_default}</span>`;
    }

    function resetSavePreview() {
        saveFileSection.classList.add('hidden');
        mediaPreviewWrap.classList.add('hidden');
        audioPreview.pause();
        audioPreview.removeAttribute('src');
        audioPreview.classList.add('hidden');
        videoPreview.pause();
        videoPreview.removeAttribute('src');
        videoPreview.classList.add('hidden');
        shareFileBtn.classList.add('hidden');
        setShareButtonDefault();
        lastSavedLocalPath = null;
        lastReadyFileUrl = '';
        lastReadyFilename = '';
        lastReadyMimeType = '';
        lastReadyFile = null;
    }

    function formatBytes(bytes) {
        if (!Number.isFinite(bytes) || bytes < 0) return '';
        if (bytes < 1024) return `${Math.round(bytes)} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    function formatEta(seconds) {
        if (!Number.isFinite(seconds) || seconds <= 0) return '';
        const total = Math.round(seconds);
        const mins = Math.floor(total / 60);
        const secs = total % 60;
        if (mins > 0) return `${mins}m ${secs}s`;
        return `${secs}s`;
    }

    function formatSecondsAsClock(seconds) {
        if (!Number.isFinite(seconds) || seconds <= 0) return '--:--';
        const total = Math.round(seconds);
        const hours = Math.floor(total / 3600);
        const mins = Math.floor((total % 3600) / 60);
        const secs = total % 60;
        const pad = (n) => String(n).padStart(2, '0');
        return hours > 0 ? `${hours}:${pad(mins)}:${pad(secs)}` : `${mins}:${pad(secs)}`;
    }

    function buildDownloadDetail(prog) {
        const parts = [];
        const dl = Number(prog && prog.downloaded_bytes);
        const tot = Number(prog && prog.total_bytes);
        if (Number.isFinite(dl) && dl > 0) {
            if (Number.isFinite(tot) && tot > 0) {
                parts.push(`${formatBytes(dl)} / ${formatBytes(tot)}`);
            } else {
                parts.push(formatBytes(dl));
            }
        }
        const spd = Number(prog && prog.speed);
        if (Number.isFinite(spd) && spd > 0) {
            parts.push(`${formatBytes(spd)}/s`);
        }
        const eta = Number(prog && prog.eta);
        if (Number.isFinite(eta) && eta > 0) {
            parts.push(`ETA ${formatEta(eta)}`);
        }
        return parts.join(' · ');
    }

    function backfillDurationFromMedia(el) {
        if (!el || !Number.isFinite(el.duration) || el.duration <= 0) return;
        const currentText = (videoDuration.textContent || '').trim();
        if (!currentText || currentText === '--:--' || currentText === 'Unknown') {
            videoDuration.textContent = formatSecondsAsClock(el.duration);
        }
    }
    audioPreview.addEventListener('loadedmetadata', () => backfillDurationFromMedia(audioPreview));
    videoPreview.addEventListener('loadedmetadata', () => backfillDurationFromMedia(videoPreview));

    function updateLanguage() {
        document.documentElement.lang = currentLang === 'en' ? 'en' : 'zh-Hant';
        document.querySelectorAll('[data-en]').forEach((el) => {
            el.textContent = el.dataset[currentLang];
        });
        document.querySelectorAll('[data-en-placeholder]').forEach((el) => {
            el.placeholder = el.dataset[`${currentLang}Placeholder`];
        });
        langText.textContent = currentLang === 'en' ? '中文' : 'English';
        if (!saveFileSection.classList.contains('hidden')) {
            savedLocationText.textContent = getDefaultSaveLocation(lastSavedLocalPath);
        }
        if (currentMediaType === 'images') updateImageCountText();
    }

    langToggle.addEventListener('click', () => {
        currentLang = currentLang === 'en' ? 'zh' : 'en';
        updateLanguage();
    });

    function showStatus(key, isError = false, directMessage = null) {
        statusMessage.classList.remove('hidden', 'status-error', 'status-success');
        statusMessage.classList.add(isError ? 'status-error' : 'status-success');
        statusMessage.querySelector('.message-icon').textContent = isError ? 'error' : 'check_circle';
        statusText.textContent = directMessage || translations[currentLang][key] || '';
    }

    function hideStatus() {
        statusMessage.classList.add('hidden');
    }

    function showSettingsStatus(message, isError = false) {
        settingsStatus.classList.remove('hidden', 'status-error', 'status-success');
        settingsStatus.classList.add(isError ? 'status-error' : 'status-success');
        settingsStatus.querySelector('.message-icon').textContent = isError ? 'error' : 'check_circle';
        settingsStatusText.textContent = message;
    }

    function setLoadingState(btn, isLoading, customLabelKey = null) {
        if (isLoading) {
            if (!btn.disabled) {
                btn.dataset.originalText = btn.innerHTML;
            }
            btn.disabled = true;
            const label = translations[currentLang][customLabelKey || 'loading'];
            btn.innerHTML = `<span class="material-symbols-outlined animated-spin">sync</span> ${label}`;
        } else {
            btn.disabled = false;
            if (btn.dataset.originalText) {
                btn.innerHTML = btn.dataset.originalText;
                delete btn.dataset.originalText;
            }
        }
    }

    function saveActiveJob(jobObj) {
        if (!jobObj || !jobObj.jobId) return;
        const normalized = {
            jobId: String(jobObj.jobId),
            url: jobObj.url || '',
            mode: jobObj.mode || 'mp3',
            quality: jobObj.quality || '192',
            title: jobObj.title || '',
            thumbnail: jobObj.thumbnail || '',
            duration: jobObj.duration || '--:--',
            apiBaseOverride: jobObj.apiBaseOverride || null,
            media_type: jobObj.media_type || 'video',
            gallery_token: jobObj.gallery_token || '',
            images: Array.isArray(jobObj.images) ? jobObj.images : [],
            image_format: jobObj.image_format || 'png',
            selected_indices: Array.isArray(jobObj.selected_indices) ? jobObj.selected_indices : [],
            startedAt: Number(jobObj.startedAt) || Date.now()
        };
        activeJobState = normalized;
        try {
            localStorage.setItem(STORAGE_ACTIVE_JOB_KEY, JSON.stringify(normalized));
        } catch {
            // Ignore storage quota errors
        }
    }

    function clearActiveJob() {
        activeJobState = null;
        try {
            localStorage.removeItem(STORAGE_ACTIVE_JOB_KEY);
        } catch {
            // Ignore storage errors
        }
    }

    function loadActiveJob() {
        try {
            const raw = localStorage.getItem(STORAGE_ACTIVE_JOB_KEY);
            if (!raw) return null;
            const parsed = JSON.parse(raw);
            if (!parsed || typeof parsed !== 'object' || !parsed.jobId) {
                clearActiveJob();
                return null;
            }
            const age = Date.now() - Number(parsed.startedAt || 0);
            if (!Number.isFinite(age) || age < 0 || age > ACTIVE_JOB_MAX_AGE_MS) {
                clearActiveJob();
                return null;
            }
            activeJobState = parsed;
            return parsed;
        } catch {
            clearActiveJob();
            return null;
        }
    }

    function stopPolling() {
        if (activePollTimer) {
            clearInterval(activePollTimer);
            activePollTimer = null;
        }
        activePollFn = null;
        pollInFlight = false;
    }

    const XHS_HOST_RE = /(?:^|\.)(?:xiaohongshu\.com|xhslink\.cn|xhslink\.com|rednote\.com)$/i;

    function extractFirstUrl(raw) {
        const text = (raw || '').trim();
        const match = text.match(/https?:\/\/[^\s<>"'\u3000-\u303F\u4E00-\u9FFF\uFF00-\uFFEF]+/i);
        return match ? match[0].replace(/[.,;!?]+$/, '') : text;
    }

    function isXiaohongshuUrl(raw) {
        try {
            const parsed = new URL((raw || '').trim());
            return XHS_HOST_RE.test(parsed.hostname);
        } catch {
            return false;
        }
    }

    function isSslDnsInterceptError(msg) {
        return Boolean(msg && /CERTIFICATE_VERIFY_FAILED|self-signed certificate/i.test(msg));
    }

    function getGalleryApiBase() {
        return currentApiBaseOverride || getApiBaseUrl() || '';
    }

    function buildImageProxyUrl(token, index, format = 'png', download = false) {
        const query = `?format=${encodeURIComponent(format)}${download ? '&download=1' : ''}`;
        return `${getGalleryApiBase()}/api/xhs-image/${encodeURIComponent(token)}/${index}${query}`;
    }

    function updateImageCountText() {
        if (!currentImageCount) return;
        const suffix = currentLang === 'en'
            ? `${currentImageCount} images`
            : `${currentImageCount} 張圖片`;
        imageCountText.textContent = `${translations[currentLang].image_note} · ${suffix}`;
    }

    function syncImageDownloadLinks() {
        imageGalleryGrid.querySelectorAll('a.btn-image-action').forEach((link) => {
            const card = link.closest('.image-card');
            if (!card) return;
            const index = Number(card.dataset.index);
            const format = imageFormatSelect.value || 'png';
            const ext = format === 'png' ? 'png' : 'webp';
            link.href = buildImageProxyUrl(currentGalleryToken, index, format, true);
            link.setAttribute('download', `image-${index + 1}.${ext}`);
        });
    }

    function syncImageSelectionUI() {
        imageGalleryGrid.querySelectorAll('.image-card').forEach((card) => {
            const index = Number(card.dataset.index);
            card.classList.toggle('is-selected', currentSelectedImages.has(index));
            const box = card.querySelector('input[type="checkbox"]');
            if (box) box.checked = currentSelectedImages.has(index);
        });
        const empty = currentSelectedImages.size === 0;
        downloadSelectedImagesBtn.disabled = empty;
        shareSelectedImagesBtn.disabled = empty;
    }

    function renderImageGallery(data) {
        currentGalleryToken = data.gallery_token || '';
        currentImages = Array.isArray(data.images) ? data.images : [];
        currentImageCount = Number(data.image_count || currentImages.length) || currentImages.length;
        const requested = Array.isArray(data.selected_indices) ? data.selected_indices : null;
        const selected = requested && requested.length
            ? requested.filter((i) => Number.isInteger(i) && i >= 0 && i < currentImages.length)
            : currentImages.map((_, index) => index);
        currentSelectedImages = new Set(selected);
        imageGalleryGrid.innerHTML = '';

        currentImages.forEach((image, index) => {
            const card = document.createElement('div');
            card.className = 'image-card';
            card.dataset.index = String(index);

            const label = document.createElement('label');
            label.className = 'image-card-label';
            const previewUrl = buildImageProxyUrl(currentGalleryToken, index, 'png');
            label.innerHTML =
                `<input type="checkbox" data-image-index="${index}" ${currentSelectedImages.has(index) ? 'checked' : ''}>` +
                `<img src="${previewUrl}" alt="Image ${index + 1}" loading="lazy">`;

            const actions = document.createElement('div');
            actions.className = 'image-card-actions';
            actions.innerHTML =
                `<a class="btn-image-action" href="#" data-en="Save" data-zh="下載">下載</a>` +
                `<button type="button" class="btn-image-action" data-share-index="${index}" data-en="Share" data-zh="分享">分享</button>`;

            card.appendChild(label);
            card.appendChild(actions);
            imageGalleryGrid.appendChild(card);
        });

        syncImageDownloadLinks();
        syncImageSelectionUI();
        updateImageCountText();
    }

    function resetShareButton(button, originalLabel) {
        button.disabled = false;
        if (originalLabel) {
            button.innerHTML = originalLabel;
        } else {
            button.innerHTML =
                `<span class="material-symbols-outlined">ios_share</span> ` +
                `<span data-en="Share" data-zh="分享">${currentLang === 'en' ? 'Share' : '分享'}</span>`;
        }
    }

    async function invokeNativeShareNamed(file, filename) {
        if (navigator.canShare && navigator.canShare({ files: [file] })) {
            await navigator.share({ files: [file], title: filename });
            return;
        }
        throw new DOMException('Share unsupported', 'NotAllowedError');
    }

    function handleImageShareError(err, button, originalLabel) {
        if (err && err.name === 'AbortError') {
            resetShareButton(button, originalLabel);
            return;
        }
        if (err && err.name === 'NotAllowedError') {
            button.disabled = false;
            button.innerHTML =
                `<span class="material-symbols-outlined">ios_share</span> ${translations[currentLang].image_share_tap_again}`;
            showStatus('image_share_hint', false);
            return;
        }
        resetShareButton(button, originalLabel);
        showStatus('image_share_unsupported', true);
    }

    async function shareImageAt(index, button) {
        if (!currentGalleryToken) return;
        const format = imageFormatSelect.value || 'png';
        const ext = format === 'png' ? 'png' : 'webp';
        const filename = `image-${index + 1}.${ext}`;
        const cached = pendingImageShares.get(index);

        if (cached && cached.format === format) {
            try {
                await invokeNativeShareNamed(cached.file, filename);
                pendingImageShares.delete(index);
                resetShareButton(button, cached.label);
            } catch (err) {
                handleImageShareError(err, button, cached.label);
            }
            return;
        }

        const originalLabel = button.innerHTML;
        button.disabled = true;
        button.innerHTML =
            `<span class="material-symbols-outlined animated-spin">sync</span> ${translations[currentLang].image_share_preparing}...`;
        try {
            const resp = await fetch(buildImageProxyUrl(currentGalleryToken, index, format));
            if (!resp.ok) throw new Error('HTTP_ERROR');
            const blob = await resp.blob();
            const file = new File([blob], filename, { type: blob.type || 'image/png' });
            pendingImageShares.set(index, { file, format, label: originalLabel });
            try {
                await invokeNativeShareNamed(file, filename);
                pendingImageShares.delete(index);
                resetShareButton(button, originalLabel);
            } catch (err) {
                handleImageShareError(err, button, originalLabel);
            }
        } catch {
            resetShareButton(button, originalLabel);
            showStatus('share_fetch_fail', true);
        }
    }

    async function startImageDownload(useAll = false) {
        if (!currentUrl || !currentGalleryToken) return;
        const indices = useAll
            ? currentImages.map((_, index) => index)
            : [...currentSelectedImages].sort((a, b) => a - b);
        if (!indices.length) {
            showStatus('image_no_selection', true);
            return;
        }

        hideStatus();
        resetSavePreview();
        setLoadingState(downloadSelectedImagesBtn, true, 'image_downloading');
        setLoadingState(zipAllImagesBtn, true, 'image_zipping');
        progressSection.classList.remove('hidden');
        progressSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        progressBar.style.backgroundColor = 'var(--brand-accent)';
        progressBar.style.width = '5%';
        progressBar.style.animation = 'pulse 2s infinite';
        progressPercentage.textContent = '...';
        progressStatusText.textContent = translations[currentLang].image_downloading;

        try {
            const response = await apiFetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: currentUrl,
                    mode: 'images',
                    image_indices: indices,
                    image_format: imageFormatSelect.value || 'png',
                    gallery_token: currentGalleryToken
                }),
                apiBaseOverride: currentApiBaseOverride
            });
            const startData = await response.json();
            if (!response.ok || !startData.success || !startData.job_id) {
                throw new Error(startData.error || translations[currentLang].error_download);
            }
            saveActiveJob({
                jobId: startData.job_id,
                url: currentUrl,
                mode: 'images',
                media_type: 'images',
                gallery_token: currentGalleryToken,
                images: currentImages,
                selected_indices: indices,
                image_format: imageFormatSelect.value || 'png',
                title: videoTitle.textContent,
                thumbnail: videoThumb.src,
                duration: videoDuration.textContent,
                apiBaseOverride: currentApiBaseOverride,
                startedAt: Date.now()
            });
            startJobPolling(startData.job_id, {
                mode: 'images',
                apiBaseOverride: currentApiBaseOverride,
                isResume: false
            });
        } catch (error) {
            showStatus(null, true, error.message || translations[currentLang].error_download);
            progressStatusText.textContent = translations[currentLang].failed;
            progressBar.style.backgroundColor = 'var(--warning)';
            progressBar.style.animation = 'none';
        } finally {
            setLoadingState(downloadSelectedImagesBtn, false);
            setLoadingState(zipAllImagesBtn, false);
        }
    }

    function resetBatchShareButton() {
        shareSelectedImagesBtn.innerHTML =
            `<span class="material-symbols-outlined">ios_share</span> ` +
            `<span data-en="Share selected" data-zh="分享勾選圖片">${currentLang === 'en' ? 'Share selected' : '分享勾選圖片'}</span>`;
    }

    async function shareSelectedImages() {
        if (!currentGalleryToken) return;
        const indices = [...currentSelectedImages].sort((a, b) => a - b);
        if (!indices.length) {
            showStatus('image_no_selection', true);
            return;
        }
        if (typeof navigator.share !== 'function') {
            showStatus('image_share_unsupported', true);
            return;
        }
        if (pendingBatchShare && pendingBatchShare.key === indices.join(',')) {
            try {
                await navigator.share(pendingBatchShare.payload);
                hideStatus();
            } catch (err) {
                if (err && err.name !== 'AbortError') showStatus('image_share_unsupported', true);
            }
            pendingBatchShare = null;
            resetBatchShareButton();
            return;
        }

        showStatus('image_share_preparing', false);
        try {
            const format = imageFormatSelect.value || 'png';
            const ext = format === 'png' ? 'png' : 'webp';
            const files = [];
            for (const index of indices) {
                const resp = await fetch(buildImageProxyUrl(currentGalleryToken, index, format));
                if (!resp.ok) throw new Error('HTTP_ERROR');
                const blob = await resp.blob();
                files.push(new File([blob], `image-${index + 1}.${ext}`, { type: blob.type || 'image/png' }));
            }
            if (navigator.canShare && !navigator.canShare({ files })) {
                showStatus('image_share_unsupported', true);
                return;
            }
            const payload = { files, title: videoTitle.textContent || translations[currentLang].image_note };
            try {
                await navigator.share(payload);
                hideStatus();
            } catch (err) {
                if (err && err.name === 'NotAllowedError') {
                    pendingBatchShare = { key: indices.join(','), payload };
                    shareSelectedImagesBtn.innerHTML =
                        `<span class="material-symbols-outlined">ios_share</span> ${translations[currentLang].image_share_tap_again}`;
                    showStatus('image_share_hint', false);
                } else if (err && err.name !== 'AbortError') {
                    showStatus('image_share_unsupported', true);
                    resetBatchShareButton();
                }
            }
        } catch {
            showStatus('share_fetch_fail', true);
        }
    }

    imageGalleryGrid.addEventListener('change', (event) => {
        const box = event.target.closest('input[data-image-index]');
        if (!box) return;
        const index = Number(box.dataset.imageIndex);
        if (box.checked) currentSelectedImages.add(index);
        else currentSelectedImages.delete(index);
        syncImageSelectionUI();
    });

    imageGalleryGrid.addEventListener('click', (event) => {
        const button = event.target.closest('button[data-share-index]');
        if (button) shareImageAt(Number(button.dataset.shareIndex), button);
    });

    selectAllImagesBtn.addEventListener('click', () => {
        currentSelectedImages = new Set(currentImages.map((_, index) => index));
        syncImageSelectionUI();
    });

    clearSelectionImagesBtn.addEventListener('click', () => {
        currentSelectedImages.clear();
        syncImageSelectionUI();
    });

    imageFormatSelect.addEventListener('change', () => {
        pendingImageShares.clear();
        pendingBatchShare = null;
        syncImageDownloadLinks();
    });

    downloadSelectedImagesBtn.addEventListener('click', () => startImageDownload(false));
    zipAllImagesBtn.addEventListener('click', () => startImageDownload(true));
    shareSelectedImagesBtn.addEventListener('click', shareSelectedImages);

    async function apiFetch(endpoint, options = {}) {
        const { allowBridgeRefresh = true, apiBaseOverride = null, ...fetchOptions } = options;
        let apiBase = apiBaseOverride !== null ? apiBaseOverride : getApiBaseUrl();
        const gistId = getSavedBridgeGistId();

        if (apiBase === null && allowBridgeRefresh && gistId) {
            lastBridgeRefreshAt = Date.now();
            const initRes = await resolveBridgeFromGist(gistId, { silent: true });
            if (initRes.ok && initRes.apiUrl) {
                apiBase = initRes.apiUrl;
            } else if (initRes.offline) {
                showStatus('bridge_offline', true);
                throw new Error('NO_BACKEND');
            }
        }

        if (apiBase === null) {
            showStatus('error_no_backend', true);
            refreshBackendNotice();
            throw new Error('NO_BACKEND');
        }
        try {
            return await fetch(apiBase + endpoint, fetchOptions);
        } catch (err) {
            if (apiBaseOverride === null && allowBridgeRefresh && gistId && (Date.now() - lastBridgeRefreshAt > BRIDGE_REFRESH_COOLDOWN_MS)) {
                lastBridgeRefreshAt = Date.now();
                const res = await resolveBridgeFromGist(gistId, { silent: true });
                if (res.ok && res.apiUrl && res.apiUrl !== apiBase) {
                    return await fetch(res.apiUrl + endpoint, fetchOptions);
                }
                if (res.offline) {
                    showStatus('bridge_offline', true);
                }
            }
            throw err;
        }
    }

    urlInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            fetchBtn.click();
        }
    });

    fetchBtn.addEventListener('click', async () => {
        const url = extractFirstUrl(urlInput.value);
        if (url !== urlInput.value) {
            urlInput.value = url;
            syncClearButton();
        }
        if (!url) {
            showStatus('error_no_url', true);
            return;
        }

        currentApiBaseOverride = null;
        currentMediaType = 'video';
        currentGalleryToken = '';
        currentImages = [];
        currentSelectedImages = new Set();
        currentImageCount = 0;
        pendingImageShares.clear();
        pendingBatchShare = null;
        clearActiveJob();
        stopPolling();
        hideStatus();
        setLoadingState(fetchBtn, true, 'analyzing');
        videoInfoSection.classList.add('hidden');
        imageGallerySection.classList.add('hidden');
        videoControlsGrid.classList.remove('hidden');
        downloadBtn.classList.remove('hidden');
        progressSection.classList.add('hidden');
        resetSavePreview();
        durationLimitWarn.classList.add('hidden');

        try {
            const response = await apiFetch('/api/info', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            let data = await response.json();

            if (!data.success && isXiaohongshuUrl(url) && isSslDnsInterceptError(data.error)) {
                const cloudFallback = normalizeApiUrl(cfg.apiBaseUrl);
                const activeBase = getApiBaseUrl();
                if (cloudFallback && cloudFallback !== activeBase) {
                    showStatus('cloud_fallback_retry', false);
                    try {
                        const retryResp = await apiFetch('/api/info', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ url }),
                            apiBaseOverride: cloudFallback
                        });
                        const retryData = await retryResp.json();
                        if (retryData && retryData.success) {
                            currentApiBaseOverride = cloudFallback;
                            data = retryData;
                            hideStatus();
                        }
                    } catch {
                        // Preserve original error if cloud fallback is unreachable
                    }
                }
            }

            if (data.success) {
                currentUrl = url;
                videoTitle.textContent = data.title;
                videoThumb.src = data.thumbnail || '';
                const safeDuration = (!data.duration || data.duration === 'Unknown') ? '--:--' : data.duration;
                if (data.media_type === 'images') {
                    currentMediaType = 'images';
                    videoDuration.textContent = currentLang === 'en'
                        ? `${data.image_count} images`
                        : `${data.image_count} 張圖片`;
                    durationLimitWarn.classList.add('hidden');
                    videoControlsGrid.classList.add('hidden');
                    downloadBtn.classList.add('hidden');
                    imageGallerySection.classList.remove('hidden');
                    renderImageGallery(data);
                    if (currentGalleryToken && currentImages.length) {
                        videoThumb.src = buildImageProxyUrl(currentGalleryToken, 0, 'png');
                    }
                } else {
                    currentMediaType = 'video';
                    videoDuration.textContent = safeDuration;
                    durationLimitWarn.classList.toggle('hidden', !data.exceeds_limit);
                    videoControlsGrid.classList.remove('hidden');
                    downloadBtn.classList.remove('hidden');
                    imageGallerySection.classList.add('hidden');
                }

                videoInfoSection.classList.remove('hidden');
                if (currentMediaType === 'video') modeSelect.focus();
            } else {
                showStatus(null, true, data.error || translations[currentLang].error_fetch_info);
            }
        } catch (error) {
            if (error.message !== 'NO_BACKEND') {
                const target = getApiBaseUrl() || window.location.origin;
                showStatus(null, true, `${translations[currentLang].error_network} (${target})`);
            }
        } finally {
            setLoadingState(fetchBtn, false);
        }
    });

    function startJobPolling(jobId, { mode = 'mp3', apiBaseOverride = null, isResume = false } = {}) {
        stopPolling();
        let transientErrors = 0;

        async function pollOnce(resetErrors = false) {
            if (resetErrors) transientErrors = 0;
            if (pollInFlight) return;
            pollInFlight = true;
            try {
                const progResp = await apiFetch(`/api/progress/${jobId}`, {
                    allowBridgeRefresh: false,
                    apiBaseOverride
                });
                const prog = await progResp.json();
                transientErrors = 0;

                if (!progResp.ok || prog.status === 'not_found') {
                    stopPolling();
                    clearActiveJob();
                    setLoadingState(downloadBtn, false);
                    if (isResume && progResp.status === 404) {
                        progressSection.classList.add('hidden');
                        showStatus('job_expired', true);
                    } else {
                        showStatus(null, true, prog.error || translations[currentLang].error_download);
                        progressStatusText.textContent = translations[currentLang].failed;
                        progressBar.style.backgroundColor = 'var(--warning)';
                        progressBar.style.animation = 'none';
                    }
                    return;
                }

                const hasPct = prog.progress !== null && prog.progress !== undefined && Number.isFinite(Number(prog.progress));

                if (prog.status === 'queued') {
                    progressPercentage.textContent = '0%';
                    progressBar.style.width = '5%';
                    progressStatusText.textContent = translations[currentLang].queued;
                } else if (prog.status === 'downloading') {
                    const baseLabel = prog.stage === 'starting'
                        ? translations[currentLang].starting_download
                        : translations[currentLang].downloading;
                    const detail = buildDownloadDetail(prog);
                    progressStatusText.textContent = detail ? `${baseLabel} (${detail})` : baseLabel;
                    if (hasPct) {
                        const pct = Math.round(Number(prog.progress));
                        progressPercentage.textContent = `${pct}%`;
                        progressBar.style.width = `${Math.max(5, pct)}%`;
                    } else {
                        const dlText = formatBytes(Number(prog.downloaded_bytes));
                        progressPercentage.textContent = dlText || '...';
                        progressBar.style.width = '35%';
                    }
                } else if (prog.status === 'processing') {
                    progressPercentage.textContent = '100%';
                    progressBar.style.width = '100%';
                    progressStatusText.textContent = translations[currentLang].converting;
                } else if (prog.status === 'ready') {
                    stopPolling();
                    clearActiveJob();
                    setLoadingState(downloadBtn, false);
                    progressBar.style.width = '100%';
                    progressBar.style.animation = 'none';
                    progressPercentage.textContent = '100%';
                    progressStatusText.textContent = translations[currentLang].finished;

                    const apiBase = apiBaseOverride || getApiBaseUrl() || '';
                    const fileUrl = apiBase + prog.download_url;
                    const fallbackName = mode === 'images' ? 'download.zip' : (mode === 'mp4' ? 'download.mp4' : 'download.mp3');
                    const filename = prog.filename || fallbackName;
                    const extension = (filename.toLowerCase().split('.').pop() || '').trim();
                    const isMp4 = extension === 'mp4' || (mode === 'mp4' && extension !== 'zip');
                    const isImagesJob = mode === 'images' || currentMediaType === 'images';
                    lastSavedLocalPath = prog.local_path || null;
                    lastReadyFileUrl = fileUrl;
                    lastReadyFilename = filename;
                    lastReadyMimeType = extension === 'zip' ? 'application/zip'
                        : extension === 'png' ? 'image/png'
                        : extension === 'webp' ? 'image/webp'
                        : isMp4 ? 'video/mp4' : 'audio/mpeg';

                    savedFileName.textContent = filename;
                    savedLocationText.textContent = getDefaultSaveLocation(lastSavedLocalPath);

                    if (isImagesJob) {
                        audioPreview.pause();
                        audioPreview.removeAttribute('src');
                        audioPreview.classList.add('hidden');
                        videoPreview.pause();
                        videoPreview.removeAttribute('src');
                        videoPreview.classList.add('hidden');
                        mediaPreviewWrap.classList.add('hidden');
                    } else {
                        const inlineUrl = `${fileUrl}?inline=1`;
                        mediaPreviewWrap.classList.remove('hidden');
                        if (isMp4) {
                            videoPreview.src = inlineUrl;
                            videoPreview.classList.remove('hidden');
                        } else {
                            audioPreview.src = inlineUrl;
                            audioPreview.classList.remove('hidden');
                        }
                    }

                    saveFileLink.href = fileUrl;
                    saveFileLink.setAttribute('download', filename);
                    if (typeof navigator.share === 'function') {
                        shareFileBtn.classList.remove('hidden');
                    }
                    saveFileSection.classList.remove('hidden');
                    showStatus('success_download', false);

                    if (!isIOS && !isResume) {
                        const tempLink = document.createElement('a');
                        tempLink.href = fileUrl;
                        tempLink.setAttribute('download', filename);
                        document.body.appendChild(tempLink);
                        tempLink.click();
                        document.body.removeChild(tempLink);
                    } else {
                        saveFileSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    }
                } else if (prog.status === 'error') {
                    stopPolling();
                    clearActiveJob();
                    setLoadingState(downloadBtn, false);
                    showStatus(null, true, prog.error || translations[currentLang].error_download);
                    progressStatusText.textContent = translations[currentLang].failed;
                    progressBar.style.backgroundColor = 'var(--warning)';
                    progressBar.style.animation = 'none';
                }
            } catch {
                transientErrors += 1;
                progressStatusText.textContent =
                    `${translations[currentLang].poll_retrying} (${transientErrors}/${MAX_POLL_ERRORS})...`;
                if (transientErrors >= MAX_POLL_ERRORS) {
                    stopPolling();
                    clearActiveJob();
                    setLoadingState(downloadBtn, false);
                    const target = apiBaseOverride || getApiBaseUrl() || window.location.origin;
                    showStatus(null, true, `${translations[currentLang].error_network_download} (${target})`);
                    progressStatusText.textContent = translations[currentLang].failed;
                    progressBar.style.backgroundColor = 'var(--warning)';
                    progressBar.style.animation = 'none';
                }
            } finally {
                pollInFlight = false;
            }
        }

        activePollFn = pollOnce;
        pollOnce();
        activePollTimer = setInterval(pollOnce, POLL_INTERVAL_MS);
    }

    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState !== 'visible' || !activeJobState) return;
        if (activePollFn) {
            activePollFn(true);
        } else {
            startJobPolling(activeJobState.jobId, {
                mode: activeJobState.mode || 'mp3',
                apiBaseOverride: activeJobState.apiBaseOverride || null,
                isResume: true
            });
        }
    });

    downloadBtn.addEventListener('click', async () => {
        if (!currentUrl) return;

        stopPolling();
        clearActiveJob();
        const quality = qualitySelect.value;
        const mode = modeSelect.value;

        hideStatus();
        resetSavePreview();
        setLoadingState(downloadBtn, true);
        progressSection.classList.remove('hidden');
        progressSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        progressBar.style.backgroundColor = 'var(--brand-accent)';
        progressBar.style.width = '5%';
        progressBar.style.animation = 'pulse 2s infinite';
        progressPercentage.textContent = '...';
        progressStatusText.textContent = translations[currentLang].queued;

        try {
            const response = await apiFetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: currentUrl, quality, mode }),
                apiBaseOverride: currentApiBaseOverride
            });

            const startData = await response.json();
            if (!response.ok || !startData.success || !startData.job_id) {
                throw new Error(startData.error || translations[currentLang].error_download);
            }

            const jobId = startData.job_id;
            saveActiveJob({
                jobId,
                url: currentUrl,
                mode,
                quality,
                title: videoTitle.textContent,
                thumbnail: videoThumb.src,
                duration: videoDuration.textContent,
                apiBaseOverride: currentApiBaseOverride,
                startedAt: Date.now()
            });
            startJobPolling(jobId, {
                mode,
                apiBaseOverride: currentApiBaseOverride,
                isResume: false
            });
        } catch (error) {
            setLoadingState(downloadBtn, false);
            if (error.message !== 'NO_BACKEND') {
                const target = currentApiBaseOverride || getApiBaseUrl() || window.location.origin;
                showStatus(null, true, error.message || `${translations[currentLang].error_network_download} (${target})`);
                progressStatusText.textContent = translations[currentLang].failed;
                progressBar.style.backgroundColor = 'var(--warning)';
                progressBar.style.animation = 'none';
            }
        }
    });

    async function invokeNativeShare(file) {
        if (navigator.canShare && navigator.canShare({ files: [file] })) {
            await navigator.share({ files: [file], title: lastReadyFilename });
            return true;
        }
        return false;
    }

    // Native Share / Save to Files or Photos (iOS & Android)
    shareFileBtn.addEventListener('click', async () => {
        if (!lastReadyFileUrl) return;

        if (lastReadyFile) {
            try {
                const shared = await invokeNativeShare(lastReadyFile);
                if (!shared) showStatus('share_unsupported', true);
            } catch (err) {
                if (err && err.name !== 'AbortError') {
                    showStatus('share_unsupported', true);
                }
            }
            return;
        }

        shareFileBtn.disabled = true;
        shareFileBtn.innerHTML =
            `<span class="material-symbols-outlined animated-spin">sync</span> ${translations[currentLang].share_preparing}...`;

        let fetchedFile = null;
        try {
            const resp = await fetch(lastReadyFileUrl);
            if (!resp.ok) throw new Error('HTTP_ERROR');

            const contentLength = Number(resp.headers.get('Content-Length') || 0);
            let blob;
            if (resp.body && typeof resp.body.getReader === 'function') {
                const reader = resp.body.getReader();
                const chunks = [];
                let received = 0;
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    chunks.push(value);
                    received += value.byteLength;
                    const progressText = contentLength > 0
                        ? `${Math.min(100, Math.round((received / contentLength) * 100))}% (${formatBytes(received)} / ${formatBytes(contentLength)})`
                        : formatBytes(received);
                    shareFileBtn.innerHTML =
                        `<span class="material-symbols-outlined animated-spin">sync</span> ${translations[currentLang].share_preparing}... ${progressText}`;
                }
                blob = new Blob(chunks, { type: lastReadyMimeType || resp.headers.get('Content-Type') || 'application/octet-stream' });
            } else {
                blob = await resp.blob();
            }

            fetchedFile = new File([blob], lastReadyFilename || 'audiostudio.mp3', {
                type: lastReadyMimeType || blob.type || 'application/octet-stream'
            });
            lastReadyFile = fetchedFile;
        } catch {
            setShareButtonDefault();
            showStatus('share_fetch_fail', true);
            return;
        }

        try {
            const shared = await invokeNativeShare(fetchedFile);
            setShareButtonDefault();
            if (!shared) {
                showStatus('share_unsupported', true);
            }
        } catch (err) {
            if (err && err.name === 'AbortError') {
                setShareButtonDefault();
            } else if (err && err.name === 'NotAllowedError') {
                shareFileBtn.disabled = false;
                shareFileBtn.innerHTML =
                    `<span class="material-symbols-outlined">ios_share</span> ${translations[currentLang].share_tap_again}`;
                showStatus('share_ready_hint', false);
            } else {
                setShareButtonDefault();
                showStatus('share_unsupported', true);
            }
        }
    });

    // Server Settings Modal handlers
    function openSettingsModal() {
        apiBaseInput.value = localStorage.getItem(STORAGE_API_KEY) || normalizeApiUrl(cfg.apiBaseUrl);
        settingsStatus.classList.add('hidden');
        settingsModal.classList.remove('hidden');
    }

    function closeSettingsModal() {
        settingsModal.classList.add('hidden');
    }

    serverSettingsBtn.addEventListener('click', openSettingsModal);
    openSettingsFromNotice.addEventListener('click', openSettingsModal);
    closeSettingsBtn.addEventListener('click', closeSettingsModal);
    settingsModal.addEventListener('click', (e) => {
        if (e.target === settingsModal) closeSettingsModal();
    });

    jumpToPortableBtn.addEventListener('click', () => {
        distributionCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    testConnBtn.addEventListener('click', async () => {
        const candidate = normalizeApiUrl(apiBaseInput.value) || basePath;
        setLoadingState(testConnBtn, true, 'loading');
        try {
            const resp = await fetch(`${candidate}/api/health`);
            const data = await resp.json();
            if (resp.ok && data.status === 'ok') {
                showSettingsStatus(
                    data.ffmpeg ? translations[currentLang].conn_ok : translations[currentLang].conn_no_ffmpeg,
                    !data.ffmpeg
                );
            } else {
                showSettingsStatus(translations[currentLang].conn_fail, true);
            }
        } catch {
            showSettingsStatus(translations[currentLang].conn_fail, true);
        } finally {
            setLoadingState(testConnBtn, false);
        }
    });

    saveSettingsBtn.addEventListener('click', () => {
        const cleaned = normalizeApiUrl(apiBaseInput.value);
        localStorage.removeItem(STORAGE_BRIDGE_GIST_KEY);
        if (cleaned) {
            localStorage.setItem(STORAGE_API_KEY, cleaned);
        } else {
            localStorage.removeItem(STORAGE_API_KEY);
        }
        refreshBackendNotice();
        showSettingsStatus(translations[currentLang].settings_saved, false);
    });

    resetSettingsBtn.addEventListener('click', () => {
        localStorage.removeItem(STORAGE_API_KEY);
        localStorage.removeItem(STORAGE_BRIDGE_GIST_KEY);
        try {
            const currentPageUrl = new URL(window.location.href);
            if (currentPageUrl.searchParams.has('bridge')) {
                currentPageUrl.searchParams.delete('bridge');
                window.history.replaceState({}, '', currentPageUrl.pathname + currentPageUrl.search + currentPageUrl.hash);
            }
        } catch {
            // Ignore URL history cleanup failure
        }
        apiBaseInput.value = normalizeApiUrl(cfg.apiBaseUrl);
        refreshBackendNotice();
        showSettingsStatus(translations[currentLang].settings_reset, false);
    });

    // PWA install prompt (Android Chrome / Desktop Edge & Chrome)
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredInstallPrompt = e;
        pwaInstallBtn.classList.remove('hidden');
    });

    pwaInstallBtn.addEventListener('click', async () => {
        if (!deferredInstallPrompt) return;
        deferredInstallPrompt.prompt();
        await deferredInstallPrompt.userChoice;
        deferredInstallPrompt = null;
        pwaInstallBtn.classList.add('hidden');
    });

    function applyApiParamFromUrl() {
        const currentPageUrl = new URL(window.location.href);
        const apiParam = currentPageUrl.searchParams.get('api');
        if (!apiParam) return false;

        const cleaned = isValidBackendUrl(apiParam);
        if (cleaned) {
            localStorage.setItem(STORAGE_API_KEY, cleaned);
            currentPageUrl.searchParams.delete('api');
            window.history.replaceState({}, '', currentPageUrl.pathname + currentPageUrl.search + currentPageUrl.hash);
            return true;
        }
        return false;
    }

    function consumeSharedUrlFromQuery() {
        try {
            const currentPageUrl = new URL(window.location.href);
            const shareKeys = ['url', 'text', 'title'];
            let sharedUrl = null;
            let touched = false;

            for (const key of shareKeys) {
                if (!currentPageUrl.searchParams.has(key)) continue;
                touched = true;
                const rawVal = currentPageUrl.searchParams.get(key) || '';
                if (!sharedUrl && rawVal.trim()) {
                    const candidate = extractFirstUrl(rawVal);
                    if (/^https?:\/\//i.test(candidate)) {
                        sharedUrl = candidate;
                    }
                }
                currentPageUrl.searchParams.delete(key);
            }

            if (touched) {
                window.history.replaceState({}, '', currentPageUrl.pathname + currentPageUrl.search + currentPageUrl.hash);
            }
            return sharedUrl;
        } catch {
            return null;
        }
    }

    async function initApp() {
        const didAutoConnect = applyApiParamFromUrl();
        const bridgeGistId = getSavedBridgeGistId();
        const sharedUrl = consumeSharedUrlFromQuery();
        updateLanguage();
        syncQualityVisibility();
        syncClearButton();
        refreshBackendNotice();

        if (didAutoConnect) {
            showStatus('api_autoconnect', false);
        } else if (bridgeGistId) {
            showStatus('bridge_connecting', false);
            await resolveBridgeFromGist(bridgeGistId);
        }

        if (sharedUrl) {
            clearActiveJob();
            urlInput.value = sharedUrl;
            syncClearButton();
            showStatus('share_url_received', false);
            fetchBtn.click();
            return;
        }

        const pendingJob = loadActiveJob();
        if (pendingJob) {
            currentUrl = pendingJob.url || '';
            currentApiBaseOverride = pendingJob.apiBaseOverride || null;
            urlInput.value = currentUrl;
            syncClearButton();
            videoTitle.textContent = pendingJob.title || '';
            videoThumb.src = pendingJob.thumbnail || '';
            videoDuration.textContent = pendingJob.duration || '--:--';
            modeSelect.value = pendingJob.mode === 'images' ? 'mp3' : (pendingJob.mode || 'mp3');
            qualitySelect.value = pendingJob.quality || '192';
            syncQualityVisibility();
            if (pendingJob.media_type === 'images') {
                currentMediaType = 'images';
                currentGalleryToken = pendingJob.gallery_token || '';
                videoControlsGrid.classList.add('hidden');
                downloadBtn.classList.add('hidden');
                imageGallerySection.classList.remove('hidden');
                imageFormatSelect.value = pendingJob.image_format || 'png';
                renderImageGallery({
                    gallery_token: currentGalleryToken,
                    images: pendingJob.images || [],
                    image_count: (pendingJob.images || []).length,
                    selected_indices: pendingJob.selected_indices || []
                });
                if (currentGalleryToken && (pendingJob.images || []).length) {
                    videoThumb.src = buildImageProxyUrl(currentGalleryToken, 0, 'png');
                }
            } else {
                currentMediaType = 'video';
                imageGallerySection.classList.add('hidden');
                videoControlsGrid.classList.remove('hidden');
                downloadBtn.classList.remove('hidden');
            }
            videoInfoSection.classList.remove('hidden');
            progressSection.classList.remove('hidden');
            progressBar.style.backgroundColor = 'var(--brand-accent)';
            progressBar.style.width = '5%';
            progressBar.style.animation = 'pulse 2s infinite';
            progressPercentage.textContent = '...';
            progressStatusText.textContent = translations[currentLang].resuming_job;
            setLoadingState(downloadBtn, true);
            startJobPolling(pendingJob.jobId, {
                mode: pendingJob.mode || 'mp3',
                apiBaseOverride: pendingJob.apiBaseOverride || null,
                isResume: true
            });
        }
    }

    initApp();
});

// Register Service Worker for PWA
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        const pathSegments = window.location.pathname.split('/');
        if (pathSegments[pathSegments.length - 1].includes('.')) pathSegments.pop();
        const base = pathSegments.join('/').replace(/\/$/, '');
        const swUrl = base + '/sw.js';

        navigator.serviceWorker.register(swUrl)
            .then((reg) => console.log('Service Worker registered with scope:', reg.scope))
            .catch((err) => console.log('Service Worker registration failed:', err));
    });
}
