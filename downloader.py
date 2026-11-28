import base64
import ipaddress
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import yt_dlp
from yt_dlp.utils import int_or_none, js_to_json, url_or_none
from yt_dlp.utils.traversal import traverse_obj

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
SHARE_URL_RE = re.compile(r"https?://[^\s<>\"'\u3000-\u303F\u4E00-\u9FFF\uFF00-\uFFEF]+", re.IGNORECASE)
XHS_SHORT_HOSTS = frozenset({"xhslink.cn", "www.xhslink.cn", "xhslink.com", "www.xhslink.com"})
XHS_WEB_HOSTS = frozenset({"xiaohongshu.com", "www.xiaohongshu.com", "rednote.com", "www.rednote.com"})
XHS_NOTE_PATH_RE = re.compile(r"^/(?P<path>(?:explore|discovery/item)/[\da-fA-F]+)(?:/|$)")
XHS_IMAGE_HOST_SUFFIXES = ("xhscdn.com", "ci.xiaohongshu.com")
XHS_IMAGE_MAX_COUNT = 30
XHS_IMAGE_MAX_BYTES = 20 * 1024 * 1024
XHS_IMAGE_FORMATS = ("png", "original")
IMAGE_EXTENSIONS = {"png", "webp", "jpg", "jpeg"}


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


def extract_media_url(raw):
    """Extract the first HTTP/HTTPS URL from pasted share text, preserving query tokens."""
    if not isinstance(raw, str):
        return raw
    cleaned = raw.strip()
    match = SHARE_URL_RE.search(cleaned)
    if match:
        return match.group(0).rstrip(".,;!?")
    return cleaned


def validate_url(url):
    """Validate an external HTTP/HTTPS media URL and block local/private SSRF targets."""
    if not isinstance(url, str):
        raise ValueError("URL must be a string.")
    cleaned = url.strip()
    if not cleaned:
        raise ValueError("URL is required.")
    if len(cleaned) > 2048:
        raise ValueError("URL exceeds maximum allowed length (2048 characters).")
    if any(ch.isspace() for ch in cleaned):
        raise ValueError("URL must not contain whitespace.")

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


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _canonicalize_xiaohongshu_url(url):
    """Normalize Xiaohongshu / Rednote web or login-redirect URLs to canonical xiaohongshu.com form."""
    parsed = urllib.parse.urlparse(url)
    hostname = (parsed.hostname or "").strip().lower()
    if hostname not in XHS_WEB_HOSTS:
        return None

    if parsed.path.rstrip("/") == "/login":
        query_params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        raw_redirect = (query_params.get("redirectPath") or [""])[0].strip()
        if not raw_redirect:
            return None
        redirect_url = urllib.parse.unquote(raw_redirect)
        redirect_parsed = urllib.parse.urlparse(redirect_url)
        redirect_host = (redirect_parsed.hostname or "").strip().lower()
        if redirect_parsed.scheme.lower() not in ("http", "https") or redirect_host not in XHS_WEB_HOSTS:
            return None
        parsed = redirect_parsed

    match = XHS_NOTE_PATH_RE.match(parsed.path)
    if not match:
        return None

    note_path = match.group("path")
    raw_params = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
    kept = [
        (key, raw_params[key][0])
        for key in ("xsec_token", "xsec_source")
        if key in raw_params and raw_params[key]
    ]
    query_str = urllib.parse.urlencode(kept, safe="=") if kept else ""
    base = f"https://www.xiaohongshu.com/{note_path}"
    return f"{base}?{query_str}" if query_str else base


def _resolve_xiaohongshu_url(url, max_hops=5, timeout=10):
    """Resolve xhslink short URLs and rednote login redirects safely with SSRF checks per hop."""
    canonical = _canonicalize_xiaohongshu_url(url)
    if canonical:
        return canonical

    hostname = (urllib.parse.urlparse(url).hostname or "").strip().lower()
    if hostname not in XHS_SHORT_HOSTS:
        return url

    handlers = [_NoRedirectHandler()]
    proxy = os.environ.get("YTDLP_PROXY", "").strip()
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)

    current = url
    try:
        for _ in range(max_hops):
            validate_url(current)
            req = urllib.request.Request(
                current,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                },
            )
            location = None
            try:
                with opener.open(req, timeout=timeout) as resp:
                    location = resp.headers.get("Location") if resp.headers else None
            except urllib.error.HTTPError as err:
                if 300 <= err.code < 400:
                    location = err.headers.get("Location") if err.headers else None
                err.close()

            if not location:
                return _canonicalize_xiaohongshu_url(current) or url

            next_url = urllib.parse.urljoin(current, location.strip())
            validate_url(next_url)
            canonical_next = _canonicalize_xiaohongshu_url(next_url)
            if canonical_next:
                return canonical_next
            current = next_url
    except Exception as e:
        logger.warning("Xiaohongshu short-link resolution fell back: %s", type(e).__name__)
        return url

    return url


def _clean_url(url):
    """Strip YouTube playlist params and canonicalize Xiaohongshu short/login-redirect URLs."""
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    if "youtube.com" in parsed.netloc and "v" in params:
        clean_query = urllib.parse.urlencode({"v": params["v"][0]})
        return urllib.parse.urlunparse(parsed._replace(query=clean_query))
    return _resolve_xiaohongshu_url(url)


def _xhs_note_id_from_url(url):
    """Return the note id from a canonical Xiaohongshu note URL, or None."""
    parsed = urllib.parse.urlparse(url)
    match = XHS_NOTE_PATH_RE.match(parsed.path)
    if not match:
        return None
    return match.group("path").rsplit("/", 1)[-1]


def validate_xhs_image_url(url):
    """Allow only Xiaohongshu CDN hosts and reject SSRF-style URL tricks."""
    cleaned = validate_url(url)
    parsed = urllib.parse.urlparse(cleaned)
    hostname = (parsed.hostname or "").lower()
    if not any(hostname == suffix or hostname.endswith("." + suffix) for suffix in XHS_IMAGE_HOST_SUFFIXES):
        raise ValueError("Image URL is not hosted on an allowed Xiaohongshu CDN.")
    if parsed.port and parsed.port not in (80, 443):
        raise ValueError("Image URL uses a disallowed port.")
    if parsed.username or parsed.password:
        raise ValueError("Image URL must not contain credentials.")
    return cleaned


def _extract_xhs_note_state(url):
    """Parse window.__INITIAL_STATE__ with yt-dlp's own downloader and JSON transform."""
    note_id = _xhs_note_id_from_url(url)
    if not note_id:
        raise ValueError("URL is not a Xiaohongshu note.")
    ydl_logger = _YdlCaptureLogger()
    ydl_opts = _build_ydl_opts({"skip_download": True, "socket_timeout": 30}, ydl_logger=ydl_logger)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            extractor = yt_dlp.extractor.get_info_extractor("XiaoHongShu")(ydl)
            webpage = extractor._download_webpage(url, note_id)
            state = extractor._search_json(
                r"window\.__INITIAL_STATE__\s*=",
                webpage,
                "initial state",
                note_id,
                transform_source=js_to_json,
            )
    except Exception as e:
        raise RuntimeError(_format_ydl_error(e, ydl_logger)) from e

    detail_map = traverse_obj(state, ("note", "noteDetailMap")) or {}
    entry = detail_map.get(note_id)
    if not isinstance(entry, dict):
        entry = next(
            (value for value in detail_map.values() if isinstance(value, dict) and value.get("note")),
            None,
        )
    note_info = traverse_obj(entry, ("note",)) if isinstance(entry, dict) else None
    if not isinstance(note_info, dict):
        raise RuntimeError("Unable to parse Xiaohongshu note state.")
    return note_id, note_info


def _xhs_images_from_note(note_info):
    """Build the ordered high-resolution image list from a parsed note."""
    if traverse_obj(note_info, ("video", "media", "stream", ...)):
        return []
    if str(note_info.get("type") or "").lower() == "video":
        return []

    images = []
    for item in traverse_obj(note_info, ("imageList", ...)) or []:
        if not isinstance(item, dict):
            continue
        candidates = traverse_obj(item, (("urlDefault", "urlPre"), {url_or_none})) or []
        candidate = candidates[0] if candidates else None
        if not candidate:
            continue
        try:
            candidate = validate_xhs_image_url(candidate)
        except ValueError:
            continue
        images.append({
            "index": len(images),
            "url": candidate,
            "width": traverse_obj(item, ("width", {int_or_none})),
            "height": traverse_obj(item, ("height", {int_or_none})),
            "is_live_photo": bool(item.get("livePhoto")),
        })
    if len(images) > XHS_IMAGE_MAX_COUNT:
        raise ValueError(f"Note has too many images (maximum {XHS_IMAGE_MAX_COUNT}).")
    return images


def get_xhs_images_info(url):
    """Return image-note metadata, or None when the note is a video note."""
    url = _clean_url(validate_url(extract_media_url(url)))
    note_id, note_info = _extract_xhs_note_state(url)
    images = _xhs_images_from_note(note_info)
    if not images:
        return None
    title = traverse_obj(note_info, ("title", {str})) or "Xiaohongshu Image Note"
    return {"note_id": note_id, "title": title, "images": images}


def get_xhs_image_extension(url):
    """Return a safe image extension derived from a validated CDN URL."""
    path = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1].lower()
    ext = path.rsplit(".", 1)[-1] if "." in path else ""
    return ext if ext in IMAGE_EXTENSIONS else "webp"


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


def _format_duration(seconds):
    """Format positive duration seconds as H:MM:SS or M:SS, or return None."""
    if seconds is None or isinstance(seconds, bool):
        return None
    try:
        val = float(seconds)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(val) or val <= 0:
        return None
    total = int(round(val))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _extract_duration(info_dict):
    """Extract (duration_seconds, formatted_duration) from top-level or format entries."""
    if not isinstance(info_dict, dict):
        return None, None

    candidates = [info_dict.get("duration")]
    for key in ("requested_formats", "formats"):
        entries = info_dict.get(key)
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict):
                    candidates.append(entry.get("duration"))

    duration_seconds = None
    for cand in candidates:
        if cand is None or isinstance(cand, bool):
            continue
        try:
            val = float(cand)
        except (TypeError, ValueError):
            continue
        if math.isfinite(val) and val > 0:
            duration_seconds = val
            break

    formatted = _format_duration(duration_seconds)
    if not formatted:
        raw_str = info_dict.get("duration_string")
        if isinstance(raw_str, str) and raw_str.strip() and raw_str.strip().lower() != "unknown":
            formatted = raw_str.strip()
    return duration_seconds, formatted


def get_video_info(url):
    """Get metadata for a video link (YouTube, TikTok, etc. via yt-dlp)."""
    url = _clean_url(validate_url(extract_media_url(url)))
    if _xhs_note_id_from_url(url):
        try:
            image_note = get_xhs_images_info(url)
        except Exception as e:
            logger.warning("Xiaohongshu image-state extraction failed: %s", e)
            image_note = None
        if image_note:
            images = image_note["images"]
            return {
                "success": True,
                "media_type": "images",
                "title": image_note["title"],
                "thumbnail": images[0]["url"],
                "duration": "--:--",
                "duration_seconds": None,
                "exceeds_limit": False,
                "max_duration_seconds": MAX_DURATION_SECONDS,
                "formats": [],
                "note_id": image_note["note_id"],
                "image_count": len(images),
                "images": images,
            }

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
            duration_seconds, duration = _extract_duration(info_dict)
            exceeds_limit = bool(
                MAX_DURATION_SECONDS and duration_seconds and duration_seconds > MAX_DURATION_SECONDS
            )

            return {
                "success": True,
                "media_type": "video",
                "title": title,
                "thumbnail": thumbnail,
                "duration": duration or "--:--",
                "duration_seconds": duration_seconds,
                "exceeds_limit": exceeds_limit,
                "max_duration_seconds": MAX_DURATION_SECONDS,
                "formats": list(VALID_QUALITIES),
            }
    except Exception as e:
        logger.error(f"Failed to get video info: {e}")
        return {"success": False, "error": _format_ydl_error(e, ydl_logger)}


def download_media(url, mode="mp3", quality="192", progress_hook=None, output_dir=None, postprocessor_hook=None):
    """Download as 'mp3' or 'mp4' via yt-dlp."""
    url = _clean_url(validate_url(extract_media_url(url)))
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
            duration, _ = _extract_duration(info_dict)
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
    if postprocessor_hook:
        ydl_opts["postprocessor_hooks"] = [postprocessor_hook]

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


def fetch_xhs_image_bytes(image_url, max_bytes=XHS_IMAGE_MAX_BYTES):
    """Stream one allowlisted Xiaohongshu CDN image into memory with a hard size cap."""
    validate_xhs_image_url(image_url)
    handlers = [_NoRedirectHandler()]
    proxy = os.environ.get("YTDLP_PROXY", "").strip()
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(
        image_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.xiaohongshu.com/",
        },
    )
    with opener.open(req, timeout=30) as resp:
        declared = resp.headers.get("Content-Length") if resp.headers else None
        if declared:
            try:
                if int(declared) > max_bytes:
                    raise ValueError("Image exceeds the allowed size limit.")
            except ValueError as exc:
                if "allowed size" in str(exc):
                    raise
        chunks = []
        total = 0
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("Image exceeds the allowed size limit.")
            chunks.append(chunk)
    if not chunks:
        raise ValueError("Image response was empty.")
    return b"".join(chunks)


def _ffmpeg_binary():
    """Return the bundled or system FFmpeg executable path."""
    local = BIN_DIR / FFMPEG_BIN
    if local.exists():
        return str(local)
    return shutil.which("ffmpeg") or FFMPEG_BIN


def convert_image_bytes_to_png(data):
    """Convert a downloaded WebP/JPEG image to PNG with the existing FFmpeg binary."""
    if not data:
        raise ValueError("Image data is empty.")
    ensure_ffmpeg()
    with tempfile.TemporaryDirectory() as tmp_dir:
        source = Path(tmp_dir) / "source.bin"
        target = Path(tmp_dir) / "output.png"
        source.write_bytes(data)
        cmd = [
            _ffmpeg_binary(), "-y", "-loglevel", "error",
            "-i", str(source), "-frames:v", "1", "-update", "1", str(target),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=90)
        stderr = ANSI_RE.sub("", proc.stderr or "").strip()
        if proc.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
            raise RuntimeError(f"FFmpeg PNG conversion failed: {stderr[:300] or 'unknown error'}")
        return target.read_bytes()


def _normalize_image_indices(image_indices, count):
    """Validate selected indices strictly and return them in request order."""
    if image_indices is None or image_indices == "":
        return list(range(count))
    if not isinstance(image_indices, (list, tuple)):
        raise ValueError("image_indices must be a list of integers.")
    result = []
    seen = set()
    for value in image_indices:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("image_indices must contain only integers.")
        if value < 0 or value >= count:
            raise ValueError(f"Image index {value} is out of range.")
        if value not in seen:
            seen.add(value)
            result.append(value)
    if not result:
        raise ValueError("At least one image must be selected.")
    if len(result) > XHS_IMAGE_MAX_COUNT:
        raise ValueError(f"Maximum {XHS_IMAGE_MAX_COUNT} images per download.")
    return result


def _safe_filename(raw, max_len=80):
    """Build a filesystem-safe, bounded output basename."""
    text = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", str(raw or "")).strip().strip(".")
    return (text or "xiaohongshu")[:max_len]


def download_xhs_images(url, image_indices=None, image_format="png", progress_hook=None, output_dir=None):
    """Download selected images as one PNG/image or a ZIP with bounded resources."""
    if image_format not in XHS_IMAGE_FORMATS:
        raise ValueError(f"Invalid image format '{image_format}'.")
    url = _clean_url(validate_url(extract_media_url(url)))
    note_id, note_info = _extract_xhs_note_state(url)
    images = _xhs_images_from_note(note_info)
    if not images:
        raise ValueError("This note has no downloadable images.")
    indices = _normalize_image_indices(image_indices, len(images))
    title = traverse_obj(note_info, ("title", {str})) or note_id

    target_dir = Path(output_dir) if output_dir else DOWNLOAD_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="xhs-", dir=str(target_dir)))
    try:
        saved = []
        final_ext = "png"
        for position, index in enumerate(indices, 1):
            item = images[index]
            if progress_hook:
                progress_hook({
                    "status": "downloading", "downloaded_bytes": 0, "total_bytes": None,
                    "image_index": index, "image_count": len(indices),
                })
            payload = fetch_xhs_image_bytes(item["url"])
            if image_format == "png":
                payload = convert_image_bytes_to_png(payload)
                ext = "png"
            else:
                ext = get_xhs_image_extension(item["url"])
            final_ext = ext
            path = work_dir / f"{position:02d}.{ext}"
            path.write_bytes(payload)
            saved.append(path)
            if progress_hook:
                progress_hook({
                    "status": "downloading", "downloaded_bytes": len(payload),
                    "total_bytes": len(payload), "image_index": index,
                    "image_count": len(indices),
                })

        base = f"{_safe_filename(title)}-{note_id[:8]}"
        if len(saved) == 1:
            final_path = target_dir / f"{base}.{final_ext}"
            shutil.move(str(saved[0]), str(final_path))
        else:
            final_path = target_dir / f"{base}.zip"
            with zipfile.ZipFile(final_path, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in saved:
                    archive.write(path, arcname=path.name)
        if not final_path.is_file() or final_path.stat().st_size == 0:
            raise RuntimeError("Output image file is empty.")
        if progress_hook:
            progress_hook({"status": "finished"})
        return {"success": True, "file_path": str(final_path), "title": title}
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def ensure_ffmpeg():
    """Ensure download/bin directories and FFmpeg binary are ready."""
    ensure_dirs()
    if not has_ffmpeg():
        download_ffmpeg()


if __name__ == "__main__":
    ensure_ffmpeg()
    print("Environment is ready.")
