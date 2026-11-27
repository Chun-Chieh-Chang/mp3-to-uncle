document.addEventListener('DOMContentLoaded', () => {
    const STORAGE_API_KEY = 'audiostudio_api_base';
    const STORAGE_THEME_KEY = 'audiostudio_theme';
    const POLL_INTERVAL_MS = 1000;
    const MAX_POLL_ERRORS = 3;

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

    const progressSection = document.getElementById('progressSection');
    const progressBar = document.getElementById('progressBar');
    const progressPercentage = document.getElementById('progressPercentage');
    const progressStatusText = document.getElementById('progressStatusText');

    const saveFileSection = document.getElementById('saveFileSection');
    const saveFileLink = document.getElementById('saveFileLink');

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
    let currentLang = 'zh';
    let activePollTimer = null;
    let deferredInstallPrompt = null;

    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
        (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    const isInAppBrowser = /Line|FBAN|FBAV|Instagram|MicroMessenger/i.test(navigator.userAgent);

    const translations = {
        en: {
            placeholder: 'Paste a video link here...',
            loading: 'Loading...',
            analyzing: 'Analyzing...',
            queued: 'Queued for processing...',
            downloading: 'Downloading & Converting...',
            processing: 'Finalizing audio/video...',
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
            api_autoconnect: 'Connected to custom backend from link!'
        },
        zh: {
            placeholder: '在此貼上影片連結...',
            loading: '載入中...',
            analyzing: '分析中...',
            queued: '排隊處理中...',
            downloading: '正在下載與轉檔...',
            processing: '正在封裝檔案...',
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
            api_autoconnect: '已從專屬連結自動連線至後端伺服器！'
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
                    urlInput.value = text.trim();
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

    function updateLanguage() {
        document.documentElement.lang = currentLang === 'en' ? 'en' : 'zh-Hant';
        document.querySelectorAll('[data-en]').forEach((el) => {
            el.textContent = el.dataset[currentLang];
        });
        document.querySelectorAll('[data-en-placeholder]').forEach((el) => {
            el.placeholder = el.dataset[`${currentLang}Placeholder`];
        });
        langText.textContent = currentLang === 'en' ? '中文' : 'English';
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
            btn.disabled = true;
            btn.dataset.originalText = btn.innerHTML;
            const label = translations[currentLang][customLabelKey || 'loading'];
            btn.innerHTML = `<span class="material-symbols-outlined animated-spin">sync</span> ${label}`;
        } else {
            btn.disabled = false;
            if (btn.dataset.originalText) {
                btn.innerHTML = btn.dataset.originalText;
            }
        }
    }

    function stopPolling() {
        if (activePollTimer) {
            clearInterval(activePollTimer);
            activePollTimer = null;
        }
    }

    async function apiFetch(endpoint, options = {}) {
        const apiBase = getApiBaseUrl();
        if (apiBase === null) {
            showStatus('error_no_backend', true);
            refreshBackendNotice();
            throw new Error('NO_BACKEND');
        }
        return fetch(apiBase + endpoint, options);
    }

    urlInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            fetchBtn.click();
        }
    });

    fetchBtn.addEventListener('click', async () => {
        const url = urlInput.value.trim();
        if (!url) {
            showStatus('error_no_url', true);
            return;
        }

        stopPolling();
        hideStatus();
        setLoadingState(fetchBtn, true, 'analyzing');
        videoInfoSection.classList.add('hidden');
        progressSection.classList.add('hidden');
        saveFileSection.classList.add('hidden');
        durationLimitWarn.classList.add('hidden');

        try {
            const response = await apiFetch('/api/info', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            const data = await response.json();

            if (data.success) {
                currentUrl = url;
                videoTitle.textContent = data.title;
                videoThumb.src = data.thumbnail || '';
                videoDuration.textContent = data.duration || '--:--';
                durationLimitWarn.classList.toggle('hidden', !data.exceeds_limit);

                videoInfoSection.classList.remove('hidden');
                modeSelect.focus();
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

    downloadBtn.addEventListener('click', async () => {
        if (!currentUrl) return;

        stopPolling();
        const quality = qualitySelect.value;
        const mode = modeSelect.value;

        hideStatus();
        saveFileSection.classList.add('hidden');
        setLoadingState(downloadBtn, true);
        progressSection.classList.remove('hidden');

        progressBar.style.backgroundColor = 'var(--brand-accent)';
        progressBar.style.width = '5%';
        progressBar.style.animation = 'pulse 2s infinite';
        progressPercentage.textContent = '0%';
        progressStatusText.textContent = translations[currentLang].queued;

        try {
            const response = await apiFetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: currentUrl, quality, mode })
            });

            const startData = await response.json();
            if (!response.ok || !startData.success || !startData.job_id) {
                throw new Error(startData.error || translations[currentLang].error_download);
            }

            const jobId = startData.job_id;
            let transientErrors = 0;

            activePollTimer = setInterval(async () => {
                try {
                    const progResp = await apiFetch(`/api/progress/${jobId}`);
                    const prog = await progResp.json();
                    transientErrors = 0;

                    if (!progResp.ok || prog.status === 'not_found') {
                        stopPolling();
                        setLoadingState(downloadBtn, false);
                        showStatus(null, true, prog.error || translations[currentLang].error_download);
                        progressStatusText.textContent = translations[currentLang].failed;
                        progressBar.style.backgroundColor = 'var(--warning)';
                        progressBar.style.animation = 'none';
                        return;
                    }

                    const pct = Math.round(Number(prog.progress) || 0);
                    progressPercentage.textContent = `${pct}%`;
                    progressBar.style.width = `${Math.max(5, pct)}%`;

                    if (prog.status === 'queued') {
                        progressStatusText.textContent = translations[currentLang].queued;
                    } else if (prog.status === 'downloading') {
                        progressStatusText.textContent = translations[currentLang].downloading;
                    } else if (prog.status === 'processing') {
                        progressStatusText.textContent = translations[currentLang].processing;
                    } else if (prog.status === 'ready') {
                        stopPolling();
                        setLoadingState(downloadBtn, false);
                        progressBar.style.width = '100%';
                        progressBar.style.animation = 'none';
                        progressPercentage.textContent = '100%';
                        progressStatusText.textContent = translations[currentLang].finished;

                        const apiBase = getApiBaseUrl() || '';
                        const fileUrl = apiBase + prog.download_url;
                        saveFileLink.href = fileUrl;
                        if (prog.filename) {
                            saveFileLink.setAttribute('download', prog.filename);
                        } else {
                            saveFileLink.setAttribute('download', '');
                        }
                        saveFileSection.classList.remove('hidden');
                        showStatus('success_download', false);

                        if (!isIOS) {
                            const tempLink = document.createElement('a');
                            tempLink.href = fileUrl;
                            tempLink.setAttribute('download', prog.filename || '');
                            document.body.appendChild(tempLink);
                            tempLink.click();
                            document.body.removeChild(tempLink);
                        } else {
                            saveFileSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                        }
                    } else if (prog.status === 'error') {
                        stopPolling();
                        setLoadingState(downloadBtn, false);
                        showStatus(null, true, prog.error || translations[currentLang].error_download);
                        progressStatusText.textContent = translations[currentLang].failed;
                        progressBar.style.backgroundColor = 'var(--warning)';
                        progressBar.style.animation = 'none';
                    }
                } catch (pollErr) {
                    transientErrors += 1;
                    if (transientErrors >= MAX_POLL_ERRORS) {
                        stopPolling();
                        setLoadingState(downloadBtn, false);
                        const target = getApiBaseUrl() || window.location.origin;
                        showStatus(null, true, `${translations[currentLang].error_network_download} (${target})`);
                        progressStatusText.textContent = translations[currentLang].failed;
                        progressBar.style.backgroundColor = 'var(--warning)';
                        progressBar.style.animation = 'none';
                    }
                }
            }, POLL_INTERVAL_MS);
        } catch (error) {
            setLoadingState(downloadBtn, false);
            if (error.message !== 'NO_BACKEND') {
                const target = getApiBaseUrl() || window.location.origin;
                showStatus(null, true, error.message || `${translations[currentLang].error_network_download} (${target})`);
                progressStatusText.textContent = translations[currentLang].failed;
                progressBar.style.backgroundColor = 'var(--warning)';
                progressBar.style.animation = 'none';
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

        try {
            const parsed = new URL(apiParam.trim());
            const isLocalHttp = parsed.protocol === 'http:' && (parsed.hostname === 'localhost' || parsed.hostname === '127.0.0.1');
            if (parsed.protocol === 'https:' || isLocalHttp) {
                const cleaned = normalizeApiUrl(parsed.origin + parsed.pathname);
                localStorage.setItem(STORAGE_API_KEY, cleaned);
                currentPageUrl.searchParams.delete('api');
                window.history.replaceState({}, '', currentPageUrl.pathname + currentPageUrl.search + currentPageUrl.hash);
                return true;
            }
        } catch {
            // Ignore malformed ?api= param
        }
        return false;
    }

    // Initialize UI
    const didAutoConnect = applyApiParamFromUrl();
    updateLanguage();
    syncQualityVisibility();
    syncClearButton();
    refreshBackendNotice();
    if (didAutoConnect) {
        showStatus('api_autoconnect', false);
    }
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
