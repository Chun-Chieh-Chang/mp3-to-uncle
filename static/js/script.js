document.addEventListener('DOMContentLoaded', () => {
    const urlInput = document.getElementById('urlInput');
    const fetchBtn = document.getElementById('fetchBtn');
    const downloadBtn = document.getElementById('downloadBtn');
    
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

    function showStatus(message, isError = false) {
        statusMessage.classList.remove('hidden', 'status-error', 'status-success');
        statusMessage.classList.add(isError ? 'status-error' : 'status-success');
        
        statusMessage.querySelector('.message-icon').textContent = isError ? 'error' : 'check_circle';
        statusText.textContent = message;
    }

    function hideStatus() {
        statusMessage.classList.add('hidden');
    }

    function setLoadingState(btn, isLoading) {
        if (isLoading) {
            btn.disabled = true;
            btn.dataset.originalText = btn.innerHTML;
            btn.innerHTML = `<span class="material-symbols-outlined animated-spin">sync</span> Loading...`;
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
            showStatus('Please enter a valid YouTube URL', true);
            return;
        }

        hideStatus();
        setLoadingState(fetchBtn, true);
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
                showStatus(data.error || 'Failed to fetch video information', true);
            }
        } catch (error) {
            showStatus('Network error occurred while fetching info', true);
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
        progressBar.style.width = '0%';
        progressPercentage.textContent = '0%';
        progressStatusText.textContent = 'Starting Download...';

        try {
            // First, get the hash identifier for progress tracking
            // Since Python hash() is not predictable from JS, we'll just poll, but wait!
            // Actually, in the backend, download blocks until finished. We need continuous polling.
            // Oh, since python blocks in the download api, fetch will wait until the download is fully done.
            // But we want progress. Let's start the download without waiting for the response, 
            // OR use a background task. Since app.py doesn't use background tasks for download, the fetch request
            // will hang until it's downloaded. The backend will update global progress dictionary.
            
            // To make it simple: Start polling immediately.
            const urlHashStr = currentUrl; // The backend uses hash(url)
            
            // Note: Since Python `hash()` is randomized per execution (for strings), 
            // the frontend won't know the exact ID unless we return it first.
            // Since we didn't do this in app.py, let's just make the download UI show a generic "Downloading..." state for now,
            // Then I will refactor app.py if needed. But for a minimal viable product with good UX, let's simulate a fake progress
            // or just use indeterminate loading.
            
            // For now, let's show an indeterminate loading bar since we can't reliably get the python string hash from JS.
            progressBar.style.width = '100%';
            progressBar.style.animation = 'pulse 2s infinite';
            progressStatusText.textContent = 'Downloading & Converting (this may take a minute)...';
            progressPercentage.textContent = '';
            
            const response = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: currentUrl, quality })
            });

            const data = await response.json();

            if (data.success) {
                showStatus('Download successful! Check your browser downloads.', false);
                progressStatusText.textContent = 'Finished!';
                progressBar.style.animation = 'none';
                
                // Trigger file download
                const a = document.createElement('a');
                a.href = data.download_url;
                a.setAttribute('download', '');
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                
            } else {
                showStatus(data.error || 'Failed to download file', true);
                progressStatusText.textContent = 'Failed!';
                progressBar.style.backgroundColor = 'var(--warning)';
                progressBar.style.animation = 'none';
            }
        } catch (error) {
            showStatus('Network error occurred during download', true);
            progressStatusText.textContent = 'Failed!';
            progressBar.style.backgroundColor = 'var(--warning)';
            progressBar.style.animation = 'none';
        } finally {
            setLoadingState(downloadBtn, false);
        }
    });
});

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
