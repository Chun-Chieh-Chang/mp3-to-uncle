import logging
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from downloader import BIN_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.resolve()
CLOUDFLARED_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
TUNNEL_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.IGNORECASE)
PAGES_URL = "https://chun-chieh-chang.github.io/mp3-to-uncle/"


def extract_tunnel_url(line):
    """Extract a trycloudflare.com HTTPS URL from a cloudflared output line."""
    if not line:
        return None
    match = TUNNEL_URL_RE.search(line)
    return match.group(0) if match else None


def ensure_cloudflared():
    """Return path to cloudflared executable, downloading it on Windows if missing."""
    on_path = shutil.which("cloudflared")
    if on_path:
        return on_path

    bin_name = "cloudflared.exe" if os.name == "nt" else "cloudflared"
    local_bin = BIN_DIR / bin_name
    if local_bin.is_file() and local_bin.stat().st_size > 0:
        return str(local_bin)

    if os.name != "nt":
        raise RuntimeError(
            "cloudflared not found on PATH. Please install cloudflared via your package manager."
        )

    BIN_DIR.mkdir(parents=True, exist_ok=True)
    tmp_bin = BIN_DIR / f"{bin_name}.tmp"
    print("[Mobile Bridge] 首次使用，正在下載官方 cloudflared 通道程式...")
    req = urllib.request.Request(
        CLOUDFLARED_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp, open(tmp_bin, "wb") as out_f:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out_f.write(chunk)
        os.replace(tmp_bin, local_bin)
        print("[Mobile Bridge] cloudflared 下載完成。")
        return str(local_bin)
    finally:
        if tmp_bin.exists():
            tmp_bin.unlink(missing_ok=True)


def wait_for_local_server(port, timeout=25):
    """Poll local Flask /api/health until ready or timeout expires."""
    health_url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def _terminate_proc(proc):
    """Best-effort clean termination of a child process."""
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def main():
    if "--check" in sys.argv[1:]:
        print(f"MOBILE_BRIDGE_CHECK_OK python={sys.executable}")
        return 0

    port = int(os.environ.get("PORT", "5000"))
    cloudflared_bin = ensure_cloudflared()

    flask_proc = None
    tunnel_proc = None
    try:
        print(f"[Mobile Bridge] 正在啟動本機 AudioStudio 後端 (http://127.0.0.1:{port})...")
        flask_env = os.environ.copy()
        flask_env["HOST"] = "127.0.0.1"
        flask_env["PORT"] = str(port)
        flask_env["NO_BROWSER"] = "1"
        flask_proc = subprocess.Popen(
            [sys.executable, str(BASE_DIR / "app.py")],
            cwd=str(BASE_DIR),
            env=flask_env,
        )

        if not wait_for_local_server(port):
            raise RuntimeError("本機 Flask 伺服器啟動逾時，請確認連接埠未被佔用或依賴套件已安裝。")

        print("[Mobile Bridge] 正在建立免費 Cloudflare 加密通道...")
        tunnel_proc = subprocess.Popen(
            [
                cloudflared_bin,
                "tunnel",
                "--url",
                f"http://127.0.0.1:{port}",
                "--no-autoupdate",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        tunnel_url = None
        deadline = time.time() + 45
        recent_lines = []
        while time.time() < deadline:
            if tunnel_proc.poll() is not None:
                break
            line = tunnel_proc.stdout.readline()
            if not line:
                time.sleep(0.1)
                continue
            stripped = line.strip()
            if stripped:
                recent_lines.append(stripped)
                if len(recent_lines) > 15:
                    recent_lines.pop(0)
            found = extract_tunnel_url(stripped)
            if found:
                tunnel_url = found
                break

        if not tunnel_url:
            tail = "\n".join(recent_lines[-5:])
            raise RuntimeError(f"無法取得 Cloudflare Tunnel 網址，請確認網路連線正常。\n{tail}")

        mobile_connect_url = f"{PAGES_URL}?api={urllib.parse.quote(tunnel_url, safe='')}"
        bridge_page_url = f"http://127.0.0.1:{port}/bridge?tunnel={urllib.parse.quote(tunnel_url, safe='')}"

        print("\n" + "=" * 68)
        print("  AudioStudio 手機橋接已啟動！(iPhone / Android / Mac 皆可用)")
        print("=" * 68)
        print(f"  手機掃碼自動連線網址:\n  {mobile_connect_url}\n")
        print(f"  直連通道備用網址:\n  {tunnel_url}")
        print("=" * 68)
        print("  即將自動開啟 QR Code 視窗供 iPhone 相機掃描...")
        print("  使用期間請勿關閉此視窗；按 Ctrl+C 或直接關閉視窗即可停止服務。")
        print("=" * 68 + "\n")

        webbrowser.open_new(bridge_page_url)

        # Drain cloudflared output until exit or Ctrl+C
        while tunnel_proc.poll() is None and flask_proc.poll() is None:
            line = tunnel_proc.stdout.readline()
            if not line:
                time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n[Mobile Bridge] 正在關閉橋接服務...")
    finally:
        _terminate_proc(tunnel_proc)
        _terminate_proc(flask_proc)
        print("[Mobile Bridge] 已安全關閉。")


if __name__ == "__main__":
    main()
