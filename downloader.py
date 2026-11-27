import base64
import ipaddress
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import yt_dlp

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent.resolve()
    BUNDLE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent.resolve()
    BUNDLE_DIR = BASE_DIR

BIN_DIR = BUNDLE_DIR / "bin"
DOWNLOAD_DIR = BASE_DIR / "downloads"
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_BIN = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"

IS_CLOUD = os.environ.get("DEPLOY_ENV", "").lower() == "cloud"
MAX_DURATION_SECONDS = int(os.environ.get("MAX_DURATION_SECONDS", "3600" if IS_CLOUD else "0"))
YTDLP_COOKIES_FILE = os.environ.get("YTDLP_COOKIES_FILE", "").strip()
YTDLP_COOKIES_B64 = os.environ.get("YTDLP_COOKIES_B64", "").strip()

VALID_MODES = ("mp3", "mp4")
VALID_QUALITIES = ("128", "192", "256", "320")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


JS_RUNTIME_BINARIES = (
    ("deno", ("deno",)),
    ("node", ("node",)),
    ("bun", ("bun",)),
    ("quickjs", ("qjs", "quickjs")),
)


def has_deno():
    """Check if Deno JS runtime is available on PATH."""
    return shutil.which("deno") is not None


def get_js_runtimes():
    """Return list of available JS runtimes on PATH for yt-dlp EJS solving."""
    return [
        name
        for name, binaries in JS_RUNTIME_BINARIES
        if any(shutil.which(binary) is not None for binary in binaries)
    ]


def get_ytdlp_version():
    """Return installed yt-dlp version string."""
    return getattr(yt_dlp.version, "__version__", "unknown")


def ensure_dirs():
    """Ensure download directory exists."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def has_ffmpeg():
    """Check if ffmpeg is available in the bin directory or system path."""
    if (BIN_DIR / FFMPEG_BIN).exists():
        return True
    if shutil.which("ffmpeg") is not None:
        return True
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def download_ffmpeg():
    """Download portable ffmpeg for Windows; require system ffmpeg on Linux/macOS."""
    if has_ffmpeg():
        logger.info("FFmpeg is already available.")
        return

    if os.name != "nt":
        raise RuntimeError("FFmpeg is required on Linux/macOS. Please install ffmpeg via your package manager.")

    logger.info("Checking for FFmpeg...")
    ensure_dirs()
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = BIN_DIR / "ffmpeg.zip"

    if not zip_path.exists() or zip_path.stat().st_size == 0:
        logger.info("Downloading FFmpeg (this might take a minute)...")
        try:
            req = urllib.request.Request(
                FFMPEG_URL,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    )
                },
            )
            with urllib.request.urlopen(req) as response, open(zip_path, "wb") as out_file:
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
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
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


def validate_url(url):
    """Validate an external HTTP/HTTPS media URL and block local/private SSRF targets."""
    if not isinstance(url, str):
        raise ValueError("URL must be a string.")
    cleaned = url.strip()
    if not cleaned:
        raise ValueError("URL is required.")
    if len(cleaned) > 2048:
        raise ValueError("URL exceeds maximum allowed length (2048 characters).")

    parsed = urllib.parse.urlparse(cleaned)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError("Only http and https URLs are supported.")

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname or any(ch.isspace() for ch in hostname):
        raise ValueError("URL must contain a valid hostname.")

    if hostname == "localhost" or hostname.endswith(".local") or hostname.endswith(".internal"):
        raise ValueError("Local or internal network addresses are not allowed.")

    # Reject empty DNS labels or trailing-dot abuse
    labels = hostname.rstrip(".").split(".")
    if any(not label for label in labels):
        raise ValueError("URL hostname is malformed.")

    # Block private, loopback, link-local, multicast, and reserved IP literals
    try:
        ip_obj = ipaddress.ip_address(hostname.strip("[]"))
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
        ):
            raise ValueError("Private or reserved IP addresses are not allowed.")
    except ValueError as exc:
        # Re-raise our explicit SSRF error; ignore ValueError from ip_address() for domain names
        if "not allowed" in str(exc):
            raise

    return cleaned


def _clean_url(url):
    """Strip playlist/index params so yt-dlp only fetches a single video."""
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    if "youtube.com" in parsed.netloc and "v" in params:
        clean_query = urllib.parse.urlencode({"v": params["v"][0]})
        return urllib.parse.urlunparse(parsed._replace(query=clean_query))
    return url


def _get_ffmpeg_location():
    """Return ffmpeg location string if local binary exists, else None."""
    local_ffmpeg = BIN_DIR / FFMPEG_BIN
    return str(BIN_DIR) if local_ffmpeg.exists() else None


class _YdlCaptureLogger:
    """Capture sanitized yt-dlp warnings so cloud failures expose root causes."""

    def __init__(self, max_warnings=5):
        self.max_warnings = max_warnings
        self.warnings = []

    @staticmethod
    def _sanitize(msg):
        text = ANSI_RE.sub("", str(msg)).strip()
        tmp_dir = str(Path(tempfile.gettempdir()))
        if tmp_dir:
            text = text.replace(tmp_dir, "[tmp]")
        text = text.replace("audiostudio_cookies.txt", "[cookies]")
        return text

    def debug(self, msg):
        pass

    def warning(self, msg):
        cleaned = self._sanitize(msg)
        if not cleaned:
            return
        logger.warning("[yt-dlp] %s", cleaned)
        if cleaned not in self.warnings and len(self.warnings) < self.max_warnings:
            self.warnings.append(cleaned)

    def error(self, msg):
        logger.error("[yt-dlp] %s", self._sanitize(msg))

    def format_diagnostics(self):
        return " | ".join(self.warnings)


def _format_ydl_error(err, ydl_logger):
    """Combine exception message with captured yt-dlp warnings without duplication."""
    base = ANSI_RE.sub("", str(err)).strip()
    diag = ydl_logger.format_diagnostics() if ydl_logger else ""
    if diag and diag not in base:
        return f"{base} [Diagnostics: {diag}]"
    return base


def _resolve_cookies_status():
    """Validate and resolve cookies.txt path and safe diagnostic status."""
    cookies_file = os.environ.get("YTDLP_COOKIES_FILE", YTDLP_COOKIES_FILE).strip()
    if cookies_file:
        if Path(cookies_file).is_file():
            return {"path": cookies_file, "loaded": True, "source": "file", "error": None}
        return {"path": None, "loaded": False, "source": "file", "error": "Configured cookies file was not found."}

    cookies_b64 = os.environ.get("YTDLP_COOKIES_B64", YTDLP_COOKIES_B64).strip()
    if cookies_b64:
        try:
            compact_b64 = "".join(cookies_b64.split())
            raw_bytes = base64.b64decode(compact_b64, validate=True)
            decoded_text = raw_bytes.decode("utf-8-sig", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
            has_cookie_entry = any(
                line.strip() and not line.lstrip().startswith("#") and "\t" in line
                for line in decoded_text.splitlines()
            )
            if not has_cookie_entry:
                return {
                    "path": None,
                    "loaded": False,
                    "source": "b64",
                    "error": "YTDLP_COOKIES_B64 does not contain valid Netscape tab-separated cookies.",
                }
            target = Path(tempfile.gettempdir()) / "audiostudio_cookies.txt"
            target.write_text(decoded_text, encoding="utf-8")
            if os.name != "nt":
                os.chmod(target, 0o600)
            return {"path": str(target), "loaded": True, "source": "b64", "error": None}
        except Exception as e:
            logger.warning("Failed to decode YTDLP_COOKIES_B64: %s", type(e).__name__)
            return {
                "path": None,
                "loaded": False,
                "source": "b64",
                "error": f"Failed to decode YTDLP_COOKIES_B64 ({type(e).__name__}).",
            }

    return {"path": None, "loaded": False, "source": "none", "error": None}


def _resolve_cookies_file():
    """Return a valid cookies.txt path from YTDLP_COOKIES_FILE or decoded YTDLP_COOKIES_B64."""
    return _resolve_cookies_status()["path"]


def _resolve_player_clients():
    """Return optional YTDLP_PLAYER_CLIENTS override, or None to use yt-dlp native defaults."""
    override = os.environ.get("YTDLP_PLAYER_CLIENTS", "").strip()
    if override and override.lower() != "default":
        clients = [c.strip() for c in override.split(",") if c.strip()]
        return clients or None
    return None


def get_diagnostics():
    """Return non-secret runtime diagnostics for /api/health."""
    cookie_status = _resolve_cookies_status()
    clients = _resolve_player_clients()
    proxy_configured = bool(os.environ.get("YTDLP_PROXY", "").strip())
    return {
        "cookies_loaded": cookie_status["loaded"],
        "cookies_source": cookie_status["source"],
        "cookies_error": cookie_status["error"],
        "player_clients": clients if clients is not None else "default",
        "proxy_configured": proxy_configured,
    }


def _build_ydl_opts(extra_opts=None, ydl_logger=None):
    """Build shared yt-dlp options across info extraction and download."""
    cookie_status = _resolve_cookies_status()
    cookies_file = cookie_status["path"]
    clients = _resolve_player_clients()
    proxy = os.environ.get("YTDLP_PROXY", "").strip()

    opts = {
        "quiet": ydl_logger is None,
        "no_warnings": ydl_logger is None,
        "noplaylist": True,
        "ffmpeg_location": _get_ffmpeg_location(),
        "js_runtimes": {"deno": {}, "node": {}, "bun": {}, "quickjs": {}},
    }
    if ydl_logger is not None:
        opts["logger"] = ydl_logger
    if clients:
        opts["extractor_args"] = {"youtube": {"player_client": clients}}
    if cookies_file:
        opts["cookiefile"] = cookies_file
    if proxy:
        opts["proxy"] = proxy
    if extra_opts:
        opts.update(extra_opts)
    return opts


def get_video_info(url):
    """Get metadata for a video link (YouTube, TikTok, etc. via yt-dlp)."""
    url = _clean_url(validate_url(url))
    ydl_logger = _YdlCaptureLogger()
    ydl_opts = _build_ydl_opts({
        "skip_download": True,
        "socket_timeout": 30,
    }, ydl_logger=ydl_logger)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            if not info_dict:
                return {"success": False, "error": _format_ydl_error("Unable to extract video metadata.", ydl_logger)}

            title = info_dict.get("title", "Unknown Title")
            thumbnail = info_dict.get("thumbnail", "")
            duration = info_dict.get("duration_string", "Unknown")
            duration_seconds = info_dict.get("duration")
            exceeds_limit = bool(
                MAX_DURATION_SECONDS and duration_seconds and duration_seconds > MAX_DURATION_SECONDS
            )

            return {
                "success": True,
                "title": title,
                "thumbnail": thumbnail,
                "duration": duration,
                "duration_seconds": duration_seconds,
                "exceeds_limit": exceeds_limit,
                "max_duration_seconds": MAX_DURATION_SECONDS,
                "formats": list(VALID_QUALITIES),
            }
    except Exception as e:
        logger.error(f"Failed to get video info: {e}")
        return {"success": False, "error": _format_ydl_error(e, ydl_logger)}


def download_media(url, mode="mp3", quality="192", progress_hook=None, output_dir=None):
    """Download as 'mp3' or 'mp4' via yt-dlp."""
    url = _clean_url(validate_url(url))
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode '{mode}'. Must be one of {VALID_MODES}.")
    quality_str = str(quality)
    if quality_str not in VALID_QUALITIES:
        raise ValueError(f"Invalid quality '{quality}'. Must be one of {VALID_QUALITIES}.")

    ensure_ffmpeg()

    target_dir = Path(output_dir) if output_dir else DOWNLOAD_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    ydl_logger = _YdlCaptureLogger()
    ydl_opts = _build_ydl_opts({
        "outtmpl": str(target_dir / "%(title).80s.%(ext)s"),
        "socket_timeout": 60,
    }, ydl_logger=ydl_logger)

    if MAX_DURATION_SECONDS > 0:
        def _duration_filter(info_dict, *, incomplete=False):
            duration = info_dict.get("duration")
            if duration and duration > MAX_DURATION_SECONDS:
                return (
                    f"Video duration ({int(duration)}s) exceeds cloud limit ({MAX_DURATION_SECONDS}s). "
                    "Please use the Windows portable version."
                )
            return None

        ydl_opts["match_filter"] = _duration_filter

    if mode == "mp4":
        ydl_opts.update({"format": "bv*+ba/b", "merge_output_format": "mp4"})
        out_ext = "mp4"
    else:
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": quality_str,
            }],
            "postprocessor_args": {
                "extractaudio": ["-id3v2_version", "3", "-write_id3v1", "1"],
            },
        })
        out_ext = "mp3"

    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return {
                    "success": False,
                    "error": (
                        f"Download skipped (video may exceed the {MAX_DURATION_SECONDS}s cloud limit)."
                        if MAX_DURATION_SECONDS > 0
                        else "Unable to extract or download media."
                    ),
                }

            filename = os.path.splitext(ydl.prepare_filename(info))[0] + "." + out_ext
            if not os.path.exists(filename):
                candidates = sorted(
                    target_dir.glob(f"*.{out_ext}"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if candidates:
                    filename = str(candidates[0])
                else:
                    return {"success": False, "error": "Output file was not created."}

            if os.path.getsize(filename) == 0:
                return {"success": False, "error": "Output file is empty."}

            return {"success": True, "file_path": filename, "title": info.get("title")}
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return {"success": False, "error": _format_ydl_error(e, ydl_logger)}


def ensure_ffmpeg():
    """Ensure download/bin directories and FFmpeg binary are ready."""
    ensure_dirs()
    if not has_ffmpeg():
        download_ffmpeg()


if __name__ == "__main__":
    ensure_ffmpeg()
    print("Environment is ready.")
