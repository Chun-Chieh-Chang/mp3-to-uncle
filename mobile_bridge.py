import logging
import os
import re
import shutil
import socket
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
TUNNEL_URL_RE = re.compile(
    r"https://[a-z0-9-]+\.(?:trycloudflare\.com|lhr\.life|lhr\.rocks)",
    re.IGNORECASE,
)
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
PAGES_URL = "https://chun-chieh-chang.github.io/mp3-to-uncle/"


def extract_tunnel_url(line):
    """Extract a supported HTTPS tunnel URL from a tunnel log line."""
    if not line:
        return None
    cleaned = ANSI_RE.sub("", line)
    match = TUNNEL_URL_RE.search(cleaned)
    return match.group(0) if match else None


def get_lan_ip():
    """Return this machine's local LAN IPv4 address without sending network traffic."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        return None
    finally:
        sock.close()
    return None


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
        return None

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
    except Exception as e:
        logger.warning("Failed to download cloudflared: %s", e)
        return None
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


def _read_until_tunnel_url(proc, timeout=25):
    """Read stdout lines from a tunnel process until a public HTTPS URL appears."""
    deadline = time.time() + timeout
    recent_lines = []
    while time.time() < deadline:
        if proc.poll() is not None:
            # Drain remaining buffered lines after early exit
            rest = proc.stdout.read() if proc.stdout else ""
            for extra in rest.splitlines():
                s = ANSI_RE.sub("", extra).strip()
                if s:
                    recent_lines.append(s)
                found = extract_tunnel_url(s)
                if found:
                    return found, recent_lines
            break

        line = proc.stdout.readline() if proc.stdout else ""
        if not line:
            time.sleep(0.1)
            continue
        stripped = ANSI_RE.sub("", line).strip()
        if stripped:
            recent_lines.append(stripped)
            if len(recent_lines) > 20:
                recent_lines.pop(0)
        found = extract_tunnel_url(stripped)
        if found:
            return found, recent_lines
    return None, recent_lines


def _start_cloudflared_tunnel(cloudflared_bin, port):
    """Tier 1: Try Cloudflare Quick Tunnel up to 2 times (retrying on 429)."""
    if not cloudflared_bin:
        return None, None

    for attempt in (1, 2):
        proc = subprocess.Popen(
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
        url, lines = _read_until_tunnel_url(proc, timeout=25)
        if url:
            return proc, url

        _terminate_proc(proc)
        saw_429 = any("429" in ln for ln in lines)
        if attempt == 1 and saw_429:
            print("[Mobile Bridge] Cloudflare Quick Tunnel 暫時限流 (429)，3 秒後重試...")
            time.sleep(3)
            continue
        if lines:
            print(f"[Mobile Bridge] Cloudflare 無法建立通道 ({lines[-1]})")
        break

    return None, None


def _start_localhost_run_tunnel(port):
    """Tier 2: Free zero-signup HTTPS SSH tunnel via localhost.run."""
    ssh_bin = shutil.which("ssh")
    if not ssh_bin:
        return None, None

    print("[Mobile Bridge] 正在切換備援通道 (localhost.run SSH HTTPS)...")
    proc = subprocess.Popen(
        [
            ssh_bin,
            "-T",
            "-o", "StrictHostKeyChecking=no",
            "-o", f"UserKnownHostsFile={os.devnull}",
            "-o", "ServerAliveInterval=30",
            "-o", "ConnectTimeout=15",
            "-R", f"80:127.0.0.1:{port}",
            "nokey@localhost.run",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    url, lines = _read_until_tunnel_url(proc, timeout=25)
    if url:
        return proc, url

    _terminate_proc(proc)
    if lines:
        print(f"[Mobile Bridge] 備援通道無法連線 ({lines[-1]})")
    return None, None


def main():
    if "--check" in sys.argv[1:]:
        print(f"MOBILE_BRIDGE_CHECK_OK python={sys.executable}")
        return 0

    port = int(os.environ.get("PORT", "5000"))
    cloudflared_bin = ensure_cloudflared()

    flask_proc = None
    tunnel_proc = None
    try:
        print(f"[Mobile Bridge] 正在啟動本機 AudioStudio 後端 (http://0.0.0.0:{port})...")
        flask_env = os.environ.copy()
        flask_env["HOST"] = "0.0.0.0"
        flask_env["PORT"] = str(port)
        flask_env["NO_BROWSER"] = "1"
        flask_proc = subprocess.Popen(
            [sys.executable, str(BASE_DIR / "app.py")],
            cwd=str(BASE_DIR),
            env=flask_env,
        )

        if not wait_for_local_server(port):
            raise RuntimeError("本機 Flask 伺服器啟動逾時，請確認連接埠未被佔用或依賴套件已安裝。")

        lan_ip = get_lan_ip()
        lan_url = f"http://{lan_ip}:{port}" if lan_ip else ""

        print("[Mobile Bridge] 正在建立免費 Cloudflare 加密通道...")
        tunnel_proc, tunnel_url = _start_cloudflared_tunnel(cloudflared_bin, port)

        if not tunnel_url:
            tunnel_proc, tunnel_url = _start_localhost_run_tunnel(port)

        if not tunnel_url and not lan_url:
            raise RuntimeError("無法建立外部 HTTPS 通道，且未偵測到區域網路 IP。")

        query = {}
        if tunnel_url:
            query["tunnel"] = tunnel_url
        if lan_url:
            query["lan"] = lan_url
        bridge_page_url = f"http://127.0.0.1:{port}/bridge?{urllib.parse.urlencode(query)}"

        print("\n" + "=" * 68)
        print("  AudioStudio 手機橋接已啟動！(iPhone / Android / Mac 皆可用)")
        print("=" * 68)
        if tunnel_url:
            mobile_connect_url = f"{PAGES_URL}?api={urllib.parse.quote(tunnel_url, safe='')}"
            print(f"  手機掃碼自動連線網址:\n  {mobile_connect_url}\n")
            print(f"  直連通道備用網址:\n  {tunnel_url}")
        else:
            print("  [提示] 外部免費通道暫時壅塞，已自動切換為「同 Wi-Fi 區網直連模式」！")
        if lan_url:
            print(f"  家用同 Wi-Fi 區網網址:\n  {lan_url}")
        print("=" * 68)
        print("  即將自動開啟 QR Code 視窗供 iPhone 相機掃描...")
        print("  使用期間請勿關閉此視窗；按 Ctrl+C 或直接關閉視窗即可停止服務。")
        print("=" * 68 + "\n")

        webbrowser.open_new(bridge_page_url)

        if tunnel_proc is not None:
            while tunnel_proc.poll() is None and flask_proc.poll() is None:
                line = tunnel_proc.stdout.readline()
                if not line:
                    time.sleep(0.2)
        else:
            while flask_proc.poll() is None:
                time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[Mobile Bridge] 正在關閉橋接服務...")
    finally:
        _terminate_proc(tunnel_proc)
        _terminate_proc(flask_proc)
        print("[Mobile Bridge] 已安全關閉。")


if __name__ == "__main__":
    main()
