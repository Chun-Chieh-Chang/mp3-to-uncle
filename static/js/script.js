document.addEventListener('DOMContentLoaded', () => {
    const urlInput = document.getElementById('urlInput');
    const fetchBtn = document.getElementById('fetchBtn');
    const downloadBtn = document.getElementById('downloadBtn');
    const langToggle = document.getElementById('langToggle');
    const langText = document.getElementById('langText');
    
    const videoInfoSection = document.getElementById('videoInfoSection');
    const videoThumb = document.getElementById('videoThumb');
    const videoTitle = document.getElementById('videoTitle');
    const videoDuration = document.getElementById('videoDuration');
    const qualitySelect = document.getElementById('qualitySelect');
    
    const progressSection = document.getElementById('progressSection');
    const progressBar = document.getElementById('progressBar');
    const progressPercentage = document.getElementById('progressPercentage');
    const progressStatusText = document.getElementById('progressStatusText');
    
    const statusMessage = document.getElementById('statusMessage');
    const statusText = document.getElementById('statusText');

    let currentUrl = '';
    let currentLang = 'zh'; // Default to Chinese

    const translations = {
        en: {
            placeholder: "Paste YouTube link here...",
            loading: "Loading...",
            analyzing: "Analyzing...",
            downloading: "Downloading & Converting (this may take a minute)...",
            error_no_url: "Please enter a valid YouTube URL",
            error_fetch_info: "Failed to fetch video information",
            error_network: "Network error occurred while fetching info",
            error_download: "Failed to download file",
            error_network_download: "Network error occurred during download",
            success_download: "Download successful! Check your browser downloads.",
            finished: "Finished!",
            failed: "Failed!",
            starting_download: "Starting Download..."
        },
        zh: {
            placeholder: "在此貼上 YouTube 連結...",
            loading: "載入中...",
            analyzing: "分析中...",
            downloading: "正在下載並轉換（這可能需要一分鐘）...",
            error_no_url: "請輸入有效的 YouTube 連結",
            error_fetch_info: "獲取影片資訊失敗",
            error_network: "獲取資訊時發生網路錯誤",
            error_download: "下載檔案失敗",
            error_network_download: "下載時發生網路錯誤",
            success_download: "下載成功！請查看瀏覽器的下載項目。",
            finished: "完成！",
            failed: "失敗！",
            starting_download: "開始下載..."
        }
    };

    function updateLanguage() {
        document.querySelectorAll('[data-en]').forEach(el => {
            el.textContent = el.dataset[currentLang];
        });

        // Update placeholders
        document.querySelectorAll('[data-en-placeholder]').forEach(el => {
            el.placeholder = el.dataset[`${currentLang}Placeholder`];
        });

        // Update language toggle button text
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
        
        if (directMessage) {
            statusText.textContent = directMessage;
        } else {
            statusText.textContent = translations[currentLang][key];
        }
    }

    function hideStatus() {
        statusMessage.classList.add('hidden');
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

        hideStatus();
        setLoadingState(fetchBtn, true, 'analyzing');
        videoInfoSection.classList.add('hidden');
        progressSection.classList.add('hidden');

        try {
            const response = await fetch('/api/info', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            const data = await response.json();

            if (data.success) {
                currentUrl = url;
                videoTitle.textContent = data.title;
                videoThumb.src = data.thumbnail || 'https://via.placeholder.com/640x360.png?text=No+Thumbnail';
                videoDuration.textContent = data.duration;
                
                // Show info section
                videoInfoSection.classList.remove('hidden');
                qualitySelect.focus();
            } else {
                showStatus(null, true, data.error || translations[currentLang].error_fetch_info);
            }
        } catch (error) {
            showStatus('error_network', true);
        } finally {
            setLoadingState(fetchBtn, false);
        }
    });

    downloadBtn.addEventListener('click', async () => {
        if (!currentUrl) return;

        const quality = qualitySelect.value;
        
        hideStatus();
        setLoadingState(downloadBtn, true);
        progressSection.classList.remove('hidden');
        
        // Reset progress UI
        progressBar.style.width = '100%';
        progressBar.style.animation = 'pulse 2s infinite';
        progressPercentage.textContent = '';
        progressStatusText.textContent = translations[currentLang].downloading;

        try {
            const response = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: currentUrl, quality })
            });

            const data = await response.json();

            if (data.success) {
                showStatus('success_download', false);
                progressStatusText.textContent = translations[currentLang].finished;
                progressBar.style.animation = 'none';
                
                // Trigger file download
                const a = document.createElement('a');
                a.href = data.download_url;
                a.setAttribute('download', '');
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                
            } else {
                showStatus(null, true, data.error || translations[currentLang].error_download);
                progressStatusText.textContent = translations[currentLang].failed;
                progressBar.style.backgroundColor = 'var(--warning)';
                progressBar.style.animation = 'none';
            }
        } catch (error) {
            showStatus('error_network_download', true);
            progressStatusText.textContent = translations[currentLang].failed;
            progressBar.style.backgroundColor = 'var(--warning)';
            progressBar.style.animation = 'none';
        } finally {
            setLoadingState(downloadBtn, false);
        }
    });

    // Detect if running on GitHub Pages (Static Demo)
    if (window.location.hostname.includes('github.io')) {
        const warningMsg = currentLang === 'zh' 
            ? '💡 此頁面目前為前端展示模式。下載功能需要本地 Python 後端支援。' 
            : '💡 This page is currently in Front-end Demo mode. Download functionality requires a local Python backend.';
        showStatus(null, false, warningMsg);
    }

    // Initialize the UI with the default language
    updateLanguage();
});

// Register Service Worker for PWA
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        // Build base path for SW (it's now at the root of the project)
        const pathSegments = window.location.pathname.split('/');
        // Remove 'index.html' or empty string if it ends with /
        if (pathSegments[pathSegments.length - 1].includes('.')) pathSegments.pop();
        const base = pathSegments.join('/').replace(/\/$/, '');
        const swUrl = base + '/sw.js';

        navigator.serviceWorker.register(swUrl)
            .then(reg => console.log('Service Worker registered with scope:', reg.scope))
            .catch(err => console.log('Service Worker registration failed:', err));
    });
}

/* Add basic css animation dynamically for pulse */
const style = document.createElement('style');
style.textContent = `
    @keyframes pulse {
        0% { opacity: 0.6; }
        50% { opacity: 1; }
        100% { opacity: 0.6; }
    }
    .animated-spin {
        animation: spin 1s linear infinite;
    }
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);
