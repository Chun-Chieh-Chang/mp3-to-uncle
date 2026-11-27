import ipaddress
import os
import re
import shutil
import sys
import threading
import time
import urllib.parse
import uuid
import webbrowser
from pathlib import Path
from threading import Timer

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory
from flask_cors import CORS

from downloader import (
    DOWNLOAD_DIR,
    MAX_DURATION_SECONDS,
    VALID_MODES,
    VALID_QUALITIES,
    download_media,
    ensure_ffmpeg,
    get_diagnostics,
    get_js_runtimes,
    get_video_info,
    get_ytdlp_version,
    has_deno,
    has_ffmpeg,
    validate_url,
)

if getattr(sys, "frozen", False):
    template_folder = os.path.join(sys._MEIPASS, "templates")
    static_folder = os.path.join(sys._MEIPASS, "static")
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__, static_folder="static", template_folder="templates")

CORS(app, expose_headers=["Content-Disposition"])

IS_CLOUD = os.environ.get("DEPLOY_ENV", "").lower() == "cloud"
AUTO_CLEANUP = os.environ.get("AUTO_CLEANUP", "true" if IS_CLOUD else "false").lower() == "true"
FILE_TTL_SECONDS = int(os.environ.get("FILE_TTL_SECONDS", "900"))
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "3"))

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
LAN_URL_RE = re.compile(
    r"^http://(?:192\.168|10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}:\d{1,5}$"
)

# Ensure FFmpeg is available on startup only when missing
if not has_ffmpeg():
    threading.Thread(target=ensure_ffmpeg, daemon=True).start()

# Thread-safe async job tracking
jobs = {}
jobs_lock = threading.Lock()
download_semaphore = threading.Semaphore(MAX_CONCURRENT_JOBS)


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

    pages_url = "https://chun-chieh-chang.github.io/mp3-to-uncle/"
    mobile_connect_url = (
        f"{pages_url}?api={urllib.parse.quote(tunnel_url, safe='')}"
        if tunnel_url
        else ""
    )
    return render_template(
        "bridge.html",
        tunnel_url=tunnel_url,
        mobile_connect_url=mobile_connect_url,
        lan_url=lan_url,
        pages_url=pages_url,
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
        validated_url = validate_url(url)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    info = get_video_info(validated_url)
    status_code = 200 if info.get("success") else 500
    return jsonify(info), status_code


@app.route("/api/download", methods=["POST"])
def api_download():
    data = request.get_json(silent=True) or {}
    url = data.get("url")
    quality = str(data.get("quality", "192"))
    mode = data.get("mode", "mp3")

    try:
        validated_url = validate_url(url)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    if mode not in VALID_MODES:
        return jsonify({"success": False, "error": "Invalid mode"}), 400
    if quality not in VALID_QUALITIES:
        return jsonify({"success": False, "error": "Invalid quality"}), 400

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex
    now = time.time()

    with jobs_lock:
        jobs[job_id] = {
            "status": "queued",
            "progress": 0.0,
            "download_url": None,
            "filename": None,
            "file_path": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }

    def hook(d):
        if d.get("status") == "downloading":
            try:
                raw_percent = ANSI_RE.sub("", d.get("_percent_str", "")).replace("%", "").strip()
                percent = max(0.0, min(100.0, float(raw_percent)))
                _update_job(job_id, status="downloading", progress=percent)
            except Exception:
                _update_job(job_id, status="downloading")
        elif d.get("status") == "finished":
            _update_job(job_id, status="processing", progress=100.0)

    def worker():
        output_dir = (DOWNLOAD_DIR / job_id) if AUTO_CLEANUP else DOWNLOAD_DIR
        with download_semaphore:
            _update_job(job_id, status="downloading", progress=0.0)
            try:
                result = download_media(
                    validated_url,
                    mode=mode,
                    quality=quality,
                    progress_hook=hook,
                    output_dir=output_dir,
                )
                if result.get("success"):
                    file_path = result["file_path"]
                    filename = os.path.basename(file_path)
                    _update_job(
                        job_id,
                        status="ready",
                        progress=100.0,
                        file_path=file_path,
                        filename=filename,
                        download_url=f"/api/files/{job_id}",
                        error=None,
                    )
                else:
                    _update_job(job_id, status="error", error=result.get("error", "Download failed"))
            except Exception as e:
                _update_job(job_id, status="error", error=str(e))

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
            mimetype = "audio/mpeg" if ext == ".mp3" else ("video/mp4" if ext == ".mp4" else None)
            return send_file(resolved, as_attachment=as_attachment, download_name=filename, mimetype=mimetype)
        return jsonify({"success": False, "error": "File no longer exists or has expired."}), 404

    return send_from_directory(DOWNLOAD_DIR, job_id_or_filename, as_attachment=as_attachment)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("HOST", "127.0.0.1")
    debug = os.environ.get("FLASK_DEBUG") == "1"

    if not IS_CLOUD and host in ("127.0.0.1", "localhost") and os.environ.get("NO_BROWSER") != "1":
        Timer(1, lambda: webbrowser.open_new(f"http://127.0.0.1:{port}/")).start()

    app.run(host=host, port=port, debug=debug, use_reloader=False, threaded=True)
