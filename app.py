import io
import ipaddress
import math
import os
import re
import secrets
import shutil
import sys
import threading
import time
import urllib.parse
import uuid
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory
from flask_cors import CORS

from downloader import (
    ANSI_RE,
    DOWNLOAD_DIR,
    MAX_DURATION_SECONDS,
    VALID_MODES,
    VALID_QUALITIES,
    convert_image_bytes_to_png,
    download_media,
    download_xhs_images,
    ensure_ffmpeg,
    extract_media_url,
    fetch_xhs_image_bytes,
    get_diagnostics,
    get_js_runtimes,
    get_video_info,
    get_xhs_image_extension,
    get_ytdlp_version,
    has_deno,
    has_ffmpeg,
    validate_url,
    XHS_IMAGE_FORMATS,
)

if getattr(sys, "frozen", False):
    template_folder = os.path.join(sys._MEIPASS, "templates")
    static_folder = os.path.join(sys._MEIPASS, "static")
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__, static_folder="static", template_folder="templates")

CORS(app, expose_headers=["Content-Disposition", "Content-Length"])

IS_CLOUD = os.environ.get("DEPLOY_ENV", "").lower() == "cloud"
AUTO_CLEANUP = os.environ.get("AUTO_CLEANUP", "true" if IS_CLOUD else "false").lower() == "true"
FILE_TTL_SECONDS = int(os.environ.get("FILE_TTL_SECONDS", "900"))
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "3"))

LAN_URL_RE = re.compile(
    r"^http://(?:192\.168|10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}:\d{1,5}$"
)
GIST_ID_RE = re.compile(r"^[a-f0-9]{20,64}$", re.IGNORECASE)

# Ensure FFmpeg is available on startup only when missing
if not has_ffmpeg():
    threading.Thread(target=ensure_ffmpeg, daemon=True).start()

VALID_DOWNLOAD_MODES = VALID_MODES + ("images",)
GALLERY_TTL_SECONDS = 1800

# Thread-safe async job tracking
jobs = {}
jobs_lock = threading.Lock()
download_semaphore = threading.Semaphore(MAX_CONCURRENT_JOBS)

# Short-lived, token-scoped XHS image galleries. Never proxy arbitrary URLs.
galleries = {}
galleries_lock = threading.Lock()


def _issue_gallery_token(images):
    """Store a note's allowlisted image list behind an unguessable token."""
    token = secrets.token_urlsafe(24)
    with galleries_lock:
        galleries[token] = {"images": images, "created_at": time.time()}
        _prune_galleries_locked()
    return token


def _get_gallery_images(token):
    """Return a copy of the images bound to a live gallery token, or None."""
    if not isinstance(token, str) or not token:
        return None
    with galleries_lock:
        entry = galleries.get(token)
        if not entry:
            return None
        if time.time() - entry["created_at"] > GALLERY_TTL_SECONDS:
            galleries.pop(token, None)
            return None
        return [dict(image) for image in entry["images"]]


def _prune_galleries_locked():
    """Remove expired gallery tokens. Caller holds galleries_lock."""
    now = time.time()
    for token, entry in list(galleries.items()):
        if now - entry["created_at"] > GALLERY_TTL_SECONDS:
            galleries.pop(token, None)


def _extract_progress_metrics(d):
    """Extract numeric download progress metrics from a yt-dlp progress hook dict."""
    downloaded = d.get("downloaded_bytes")
    if isinstance(downloaded, bool) or not isinstance(downloaded, (int, float)) or downloaded < 0:
        downloaded = None
    else:
        downloaded = int(downloaded)

    total = d.get("total_bytes") or d.get("total_bytes_estimate")
    if isinstance(total, bool) or not isinstance(total, (int, float)) or total <= 0:
        total = None
    else:
        total = int(total)

    speed = d.get("speed")
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed <= 0:
        speed = None
    else:
        speed = float(speed)

    eta = d.get("eta")
    if isinstance(eta, bool) or not isinstance(eta, (int, float)) or not math.isfinite(eta) or eta < 0:
        eta = None
    else:
        eta = int(round(eta))

    progress = None
    if downloaded is not None and total:
        progress = max(0.0, min(100.0, (downloaded / total) * 100.0))
    else:
        frag_idx = d.get("fragment_index")
        frag_cnt = d.get("fragment_count")
        if (
            not isinstance(frag_idx, bool)
            and not isinstance(frag_cnt, bool)
            and isinstance(frag_idx, (int, float))
            and isinstance(frag_cnt, (int, float))
            and frag_cnt > 0
            and frag_idx >= 0
        ):
            progress = max(0.0, min(100.0, (frag_idx / frag_cnt) * 100.0))
        else:
            raw_percent = ANSI_RE.sub("", str(d.get("_percent_str") or "")).replace("%", "").strip()
            try:
                parsed_pct = float(raw_percent)
                if math.isfinite(parsed_pct):
                    progress = max(0.0, min(100.0, parsed_pct))
            except ValueError:
                pass

    metrics = {
        "downloaded_bytes": downloaded,
        "total_bytes": total,
        "speed": speed,
        "eta": eta,
    }
    if progress is not None:
        metrics["progress"] = progress
    return metrics


def _update_job(job_id, **fields):
    """Safely update fields on a tracked download job."""
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(fields)
            jobs[job_id]["updated_at"] = time.time()


def _cleanup_expired_jobs():
    """Periodically remove expired job records and isolated temp folders."""
    while True:
        time.sleep(300)
        now = time.time()
        expired_ids = []
        with jobs_lock:
            for jid, job in list(jobs.items()):
                age = now - job.get("updated_at", job.get("created_at", now))
                status = job.get("status")
                if (status in ("ready", "error") and age > FILE_TTL_SECONDS) or (age > FILE_TTL_SECONDS * 2):
                    expired_ids.append(jid)
                    jobs.pop(jid, None)

        for jid in expired_ids:
            job_dir = DOWNLOAD_DIR / jid
            if job_dir.exists() and job_dir.is_dir():
                shutil.rmtree(job_dir, ignore_errors=True)

        with galleries_lock:
            _prune_galleries_locked()


if AUTO_CLEANUP:
    threading.Thread(target=_cleanup_expired_jobs, daemon=True).start()


@app.route("/")
def serve_index():
    return render_template("index.html")


@app.route("/bridge")
def serve_bridge():
    raw_tunnel = (request.args.get("tunnel") or "").strip().rstrip("/")
    tunnel_url = ""
    if raw_tunnel.startswith("https://"):
        try:
            tunnel_url = validate_url(raw_tunnel)
        except ValueError:
            tunnel_url = ""

    raw_lan = (request.args.get("lan") or "").strip().rstrip("/")
    lan_url = ""
    if LAN_URL_RE.match(raw_lan):
        try:
            parsed_lan = urllib.parse.urlparse(raw_lan)
            ip_obj = ipaddress.ip_address(parsed_lan.hostname or "")
            if parsed_lan.port and 1 <= parsed_lan.port <= 65535 and ip_obj.is_private and not ip_obj.is_loopback:
                lan_url = raw_lan
        except ValueError:
            lan_url = ""

    raw_gist = (request.args.get("gist") or "").strip()
    gist_id = raw_gist if GIST_ID_RE.match(raw_gist) else ""

    pages_url = "https://chun-chieh-chang.github.io/mp3-to-uncle/"
    fixed_bridge_url = f"{pages_url}?bridge={gist_id}" if gist_id else ""
    mobile_connect_url = (
        f"{pages_url}?api={urllib.parse.quote(tunnel_url, safe='')}"
        if tunnel_url
        else ""
    )
    return render_template(
        "bridge.html",
        fixed_bridge_url=fixed_bridge_url,
        tunnel_url=tunnel_url,
        mobile_connect_url=mobile_connect_url,
        lan_url=lan_url,
    )


@app.route("/sw.js")
def service_worker():
    response = send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.static_folder, "icons"), "icon-512.png", mimetype="image/png")


@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({
        "status": "ok",
        "ffmpeg": has_ffmpeg(),
        "deno": has_deno(),
        "js_runtimes": get_js_runtimes(),
        "yt_dlp_version": get_ytdlp_version(),
        "mode": "cloud" if IS_CLOUD else "local",
        "max_duration_seconds": MAX_DURATION_SECONDS,
        **get_diagnostics(),
    })


@app.route("/api/info", methods=["POST"])
def api_get_info():
    data = request.get_json(silent=True) or {}
    url = data.get("url")
    try:
        validated_url = validate_url(extract_media_url(url))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    info = get_video_info(validated_url)
    if info.get("success") and info.get("media_type") == "images":
        info["gallery_token"] = _issue_gallery_token(info.get("images") or [])
        info["image_formats"] = list(XHS_IMAGE_FORMATS)
    status_code = 200 if info.get("success") else 500
    return jsonify(info), status_code


@app.route("/api/xhs-image/<gallery_token>/<int:index>", methods=["GET"])
def api_xhs_image(gallery_token, index):
    images = _get_gallery_images(gallery_token)
    if images is None:
        return jsonify({"success": False, "error": "Gallery token is invalid or expired."}), 404
    if index < 0 or index >= len(images):
        return jsonify({"success": False, "error": "Image index is out of range."}), 400

    image_format = (request.args.get("format") or "png").lower()
    if image_format not in XHS_IMAGE_FORMATS:
        return jsonify({"success": False, "error": "Invalid image format"}), 400

    try:
        payload = fetch_xhs_image_bytes(images[index]["url"])
        if image_format == "png":
            payload = convert_image_bytes_to_png(payload)
            ext = "png"
            mimetype = "image/png"
        else:
            ext = get_xhs_image_extension(images[index]["url"])
            mimetype = "image/webp" if ext == "webp" else ("image/png" if ext == "png" else "image/jpeg")
    except Exception as e:
        return jsonify({"success": False, "error": ANSI_RE.sub("", str(e))[:300]}), 502

    as_attachment = request.args.get("download") == "1"
    response = send_file(
        io.BytesIO(payload),
        mimetype=mimetype,
        as_attachment=as_attachment,
        download_name=f"image-{index + 1:02d}.{ext}",
    )
    response.headers["Cache-Control"] = "no-store" if as_attachment else "private, max-age=300"
    return response


@app.route("/api/download", methods=["POST"])
def api_download():
    data = request.get_json(silent=True) or {}
    url = data.get("url")
    quality = str(data.get("quality", "192"))
    mode = data.get("mode", "mp3")

    try:
        validated_url = validate_url(extract_media_url(url))
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    if mode not in VALID_DOWNLOAD_MODES:
        return jsonify({"success": False, "error": "Invalid mode"}), 400

    image_indices = None
    image_format = "png"
    if mode == "images":
        image_indices = data.get("image_indices")
        image_format = str(data.get("image_format") or "png").lower()
        gallery_images = _get_gallery_images(data.get("gallery_token"))
        if image_format not in XHS_IMAGE_FORMATS:
            return jsonify({"success": False, "error": "Invalid image format"}), 400
        if gallery_images is None:
            return jsonify({"success": False, "error": "Gallery token is invalid or expired"}), 400
        if not isinstance(image_indices, list) or not image_indices:
            return jsonify({"success": False, "error": "At least one image must be selected"}), 400
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0 or value >= len(gallery_images)
            for value in image_indices
        ):
            return jsonify({"success": False, "error": "Image index is out of range"}), 400
    elif quality not in VALID_QUALITIES:
        return jsonify({"success": False, "error": "Invalid quality"}), 400

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex
    now = time.time()

    with jobs_lock:
        jobs[job_id] = {
            "status": "queued",
            "mode": mode,
            "progress": None,
            "downloaded_bytes": 0,
            "total_bytes": None,
            "speed": None,
            "eta": None,
            "stage": "queued",
            "download_url": None,
            "filename": None,
            "file_path": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }

    def hook(d):
        if d.get("status") == "downloading":
            metrics = _extract_progress_metrics(d)
            _update_job(
                job_id,
                status="downloading",
                stage="downloading",
                progress=metrics.get("progress"),
                downloaded_bytes=metrics["downloaded_bytes"],
                total_bytes=metrics["total_bytes"],
                speed=metrics["speed"],
                eta=metrics["eta"],
            )
        elif d.get("status") == "finished":
            _update_job(
                job_id,
                status="processing",
                stage="converting",
                progress=100.0,
                speed=None,
                eta=0,
            )

    def pp_hook(d):
        if d.get("status") in ("started", "processing"):
            _update_job(
                job_id,
                status="processing",
                stage=d.get("postprocessor") or "converting",
                progress=100.0,
                speed=None,
                eta=0,
            )

    def worker():
        output_dir = (DOWNLOAD_DIR / job_id) if AUTO_CLEANUP else DOWNLOAD_DIR
        with download_semaphore:
            _update_job(job_id, status="downloading", stage="starting", progress=None)
            try:
                if mode == "images":
                    result = download_xhs_images(
                        validated_url,
                        image_indices=image_indices,
                        image_format=image_format,
                        progress_hook=hook,
                        output_dir=output_dir,
                    )
                else:
                    result = download_media(
                        validated_url,
                        mode=mode,
                        quality=quality,
                        progress_hook=hook,
                        output_dir=output_dir,
                        postprocessor_hook=pp_hook,
                    )
                if result.get("success"):
                    file_path = result["file_path"]
                    filename = os.path.basename(file_path)
                    _update_job(
                        job_id,
                        status="ready",
                        stage="ready",
                        progress=100.0,
                        speed=None,
                        eta=0,
                        file_path=file_path,
                        filename=filename,
                        download_url=f"/api/files/{job_id}",
                        error=None,
                    )
                else:
                    _update_job(job_id, status="error", stage="error", error=result.get("error", "Download failed"))
            except Exception as e:
                _update_job(job_id, status="error", stage="error", error=str(e))

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"success": True, "job_id": job_id, "status": "queued"}), 202


@app.route("/api/progress/<job_id>", methods=["GET"])
def api_progress(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return jsonify({"success": False, "status": "not_found", "error": "Job not found"}), 404
        is_local_req = (not IS_CLOUD) and request.remote_addr in ("127.0.0.1", "::1")
        payload = {
            "success": True,
            "job_id": job_id,
            "status": job["status"],
            "progress": job["progress"],
            "downloaded_bytes": job["downloaded_bytes"],
            "total_bytes": job["total_bytes"],
            "speed": job["speed"],
            "eta": job["eta"],
            "stage": job["stage"],
            "download_url": job["download_url"],
            "filename": job["filename"],
            "local_path": job["file_path"] if (is_local_req and job["status"] == "ready") else None,
            "error": job["error"],
        }
    return jsonify(payload)


@app.route("/api/files/<path:job_id_or_filename>", methods=["GET"])
def serve_file(job_id_or_filename):
    as_attachment = request.args.get("inline") != "1"
    with jobs_lock:
        job = jobs.get(job_id_or_filename)
        file_path = job.get("file_path") if job else None
        filename = job.get("filename") if job else None

    if file_path:
        resolved = Path(file_path)
        if resolved.is_file():
            ext = resolved.suffix.lower()
            mimetypes = {
                ".mp3": "audio/mpeg",
                ".mp4": "video/mp4",
                ".zip": "application/zip",
                ".png": "image/png",
                ".webp": "image/webp",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
            }
            mimetype = mimetypes.get(ext)
            return send_file(resolved, as_attachment=as_attachment, download_name=filename, mimetype=mimetype)
        return jsonify({"success": False, "error": "File no longer exists or has expired."}), 404

    return send_from_directory(DOWNLOAD_DIR, job_id_or_filename, as_attachment=as_attachment)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("HOST", "127.0.0.1")
    debug = os.environ.get("FLASK_DEBUG") == "1"

    if not IS_CLOUD and host in ("127.0.0.1", "localhost") and os.environ.get("NO_BROWSER") != "1":
        threading.Timer(1, lambda: webbrowser.open_new(f"http://127.0.0.1:{port}/")).start()

    app.run(host=host, port=port, debug=debug, use_reloader=False, threaded=True)
