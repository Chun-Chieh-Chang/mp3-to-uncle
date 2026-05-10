import os
import sys
import subprocess
import urllib.request
import zipfile
import yt_dlp
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import sys

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent.resolve()
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent.resolve()
    BUNDLE_DIR = BASE_DIR

BIN_DIR = BUNDLE_DIR / "bin"
DOWNLOAD_DIR = BASE_DIR / "downloads"
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

def ensure_dirs():
    """Ensure necessary directories exist."""
    BIN_DIR.mkdir(exist_ok=True)
    DOWNLOAD_DIR.mkdir(exist_ok=True)

def has_ffmpeg():
    """Check if ffmpeg is available in the bin directory or system path."""
    # Check bin dir first
    ffmpeg_exe = BIN_DIR / "ffmpeg.exe"
    if ffmpeg_exe.exists():
        return True
    
    # Check system path
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False

def download_ffmpeg():
    """Download portable ffmpeg for Windows."""
    if has_ffmpeg():
        logger.info("FFmpeg is already available.")
        return

    logger.info("Checking for FFmpeg...")
    ensure_dirs()
    zip_path = BIN_DIR / "ffmpeg.zip"
    
    if not zip_path.exists() or zip_path.stat().st_size == 0:
        logger.info("Downloading FFmpeg (this might take a minute)...")
        try:
            # Download with User-Agent to avoid being blocked
            req = urllib.request.Request(
                FFMPEG_URL, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            )
            with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
                chunk_size = 1024 * 1024  # 1MB
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
            
        except Exception as e:
            logger.error(f"Failed to download FFmpeg: {e}")
            if zip_path.exists():
                zip_path.unlink()
            raise

    if zip_path.exists():
        logger.info("Extracting FFmpeg...")
        try:
            # Extract
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # We only need ffmpeg.exe and ffprobe.exe
                for file_info in zip_ref.infolist():
                    if file_info.filename.endswith("ffmpeg.exe") or file_info.filename.endswith("ffprobe.exe"):
                        file_info.filename = os.path.basename(file_info.filename)
                        zip_ref.extract(file_info, BIN_DIR)
                        
            logger.info("Extraction complete.")
        except Exception as e:
            logger.error(f"Failed to extract FFmpeg: {e}")
            raise
        finally:
            if zip_path.exists():
                zip_path.unlink()

def get_video_info(url):
    """Get metadata about the YouTube video."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'ffmpeg_location': str(BIN_DIR) if (BIN_DIR / "ffmpeg.exe").exists() else None
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            
            # Extract basic info
            title = info_dict.get('title', 'Unknown Title')
            thumbnail = info_dict.get('thumbnail', '')
            duration = info_dict.get('duration_string', 'Unknown')
            
            return {
                'success': True,
                'title': title,
                'thumbnail': thumbnail,
                'duration': duration,
                'formats': ['128', '192', '256', '320'] # Standard MP3 kbps options
            }
    except Exception as e:
        logger.error(f"Failed to get video info: {e}")
        return {'success': False, 'error': str(e)}

def download_audio(url, quality='192', progress_hook=None):
    """Download the audio from the YouTube video."""
    ensure_directories_and_ffmpeg()

    output_template = str(DOWNLOAD_DIR / '%(title)s.%(ext)s')
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': quality,
        }],
        'outtmpl': output_template,
        'ffmpeg_location': str(BIN_DIR) if (BIN_DIR / "ffmpeg.exe").exists() else None,
        'quiet': True,
        'no_warnings': True,
    }
    
    if progress_hook:
        ydl_opts['progress_hooks'] = [progress_hook]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # Since postprocessor changes ext to mp3
            filename = os.path.splitext(filename)[0] + '.mp3'
            return {'success': True, 'file_path': filename, 'title': info.get('title')}
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return {'success': False, 'error': str(e)}

def ensure_directories_and_ffmpeg():
    ensure_dirs()
    if not has_ffmpeg():
        download_ffmpeg()

def ensure_ffmpeg():
    ensure_dirs()
    if not has_ffmpeg():
        download_ffmpeg()

if __name__ == "__main__":
    ensure_directories_and_ffmpeg()
    print("Environment is ready.")
