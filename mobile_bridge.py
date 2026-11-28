import datetime
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from downloader import ANSI_RE, BIN_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.resolve()
BRIDGE_CONFIG_PATH = BASE_DIR / ".bridge_config.json"
GIST_FILENAME = "audiostudio_bridge.json"
GITHUB_GISTS_API = "https://api.github.com/gists"
GIST_ID_RE = re.compile(r"^[a-f0-9]{20,64}$", re.IGNORECASE)
CLOUDFLARED_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
HEALTH_CHECK_INTERVAL = max(10, int(os.environ.get("BRIDGE_HEALTH_INTERVAL", "60")))
HEALTH_CHECK_TIMEOUT = 10
HEALTH_FAIL_THRESHOLD = 3
RECONNECT_BACKOFF_BASE = 5
RECONNECT_BACKOFF_MAX = 60
TUNNEL_URL_RE = re.compile(
    r"https://[a-z0-9-]+\.(?:trycloudflare\.com|lhr\.life|lhr\.rocks)",
    re.IGNORECASE,
)
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


def _is_port_available(port):
    """Return True only if neither 127.0.0.1 nor 0.0.0.0 has a conflicting listener."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return False
    except OSError:
        pass

    for bind_host in ("127.0.0.1", "0.0.0.0"):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind((bind_host, port))
        except OSError:
            return False
        finally:
            sock.close()
    return True


def select_available_port(preferred_port=5000, max_attempts=20):
    """Pick preferred_port if free on both loopback and wildcard, else next free port."""
    for candidate in range(preferred_port, preferred_port + max_attempts):
        if _is_port_available(candidate):
            return candidate
    raise RuntimeError(
        f"找不到可用的本機連接埠 ({preferred_port}-{preferred_port + max_attempts - 1})，請先關閉佔用程式。"
    )


def wait_for_local_server(port, timeout=25, proc=None):
    """Poll local Flask /api/health and /bridge until ready or timeout/exit."""
    health_url = f"http://127.0.0.1:{port}/api/health"
    bridge_url = f"http://127.0.0.1:{port}/bridge"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(health_url, timeout=2) as h_resp, urllib.request.urlopen(
                bridge_url, timeout=2
            ) as b_resp:
                if h_resp.status == 200 and b_resp.status == 200:
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


def _find_gh_binary():
    """Locate GitHub CLI (`gh`) binary on PATH or standard Windows install paths."""
    on_path = shutil.which("gh")
    if on_path:
        return on_path
    if os.name == "nt":
        candidates = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "GitHub CLI" / "gh.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "GitHub CLI" / "gh.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
    return None


def _load_bridge_config():
    """Load local `.bridge_config.json` safely, returning a dict."""
    if not BRIDGE_CONFIG_PATH.is_file():
        return {}
    try:
        data = json.loads(BRIDGE_CONFIG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("Failed to read %s: %s", BRIDGE_CONFIG_PATH.name, e)
        return {}


def _save_bridge_config(config):
    """Persist bridge configuration to `.bridge_config.json`."""
    try:
        BRIDGE_CONFIG_PATH.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning("Failed to write %s: %s", BRIDGE_CONFIG_PATH.name, e)


def _resolve_github_token(config):
    """Resolve GitHub token from env, config file, or local `gh auth token`."""
    env_token = (os.environ.get("GITHUB_GIST_TOKEN") or "").strip()
    if env_token:
        return env_token

    cfg_token = str(config.get("github_token") or "").strip()
    if cfg_token:
        return cfg_token

    gh_bin = _find_gh_binary()
    if not gh_bin:
        return None

    try:
        res = subprocess.run(
            [gh_bin, "auth", "token"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        token = (res.stdout or "").strip()
        if res.returncode == 0 and token:
            return token
    except Exception as e:
        logger.warning("Failed to obtain token from gh CLI: %s", e)
    return None


def _github_gist_request(method, url, token, payload, timeout=10):
    """Send a JSON request to the GitHub Gists API and return (status, dict_or_none)."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "AudioStudio-Bridge",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8", errors="replace") if err.fp else ""
        try:
            parsed = json.loads(raw) if raw else None
        except ValueError:
            parsed = None
        return err.code, parsed


def sync_fixed_bridge_gist(tunnel_url, status="online", timeout=10):
    """Create or update a Secret GitHub Gist pointing to the active tunnel URL."""
    try:
        config = _load_bridge_config()
        token = _resolve_github_token(config)
        if not token:
            return None

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        pointer_payload = {
            "api_url": tunnel_url,
            "status": status,
            "updated_at": now_iso,
        }
        content_str = json.dumps(pointer_payload, ensure_ascii=False, indent=2)

        raw_gist_id = str(config.get("gist_id") or "").strip()
        gist_id = raw_gist_id if GIST_ID_RE.match(raw_gist_id) else None

        if gist_id:
            code, resp_data = _github_gist_request(
                "PATCH",
                f"{GITHUB_GISTS_API}/{gist_id}",
                token,
                {"files": {GIST_FILENAME: {"content": content_str}}},
                timeout=timeout,
            )
            if code == 200:
                config["gist_id"] = gist_id
                config["updated_at"] = now_iso
                _save_bridge_config(config)
                return gist_id
            if code != 404:
                msg = (resp_data or {}).get("message", f"HTTP {code}")
                logger.warning("Failed to update Gist %s: %s", gist_id, msg)
                return None
            # Gist no longer exists on GitHub; recreate only when coming online
            gist_id = None
            config.pop("gist_id", None)

        if status != "online":
            return None

        code, resp_data = _github_gist_request(
            "POST",
            GITHUB_GISTS_API,
            token,
            {
                "description": "AudioStudio Fixed Mobile Bridge Pointer",
                "public": False,
                "files": {GIST_FILENAME: {"content": content_str}},
            },
            timeout=timeout,
        )
        new_id = str((resp_data or {}).get("id") or "").strip()
        if code in (200, 201) and GIST_ID_RE.match(new_id):
            config["gist_id"] = new_id
            config["updated_at"] = now_iso
            _save_bridge_config(config)
            return new_id

        msg = (resp_data or {}).get("message", f"HTTP {code}")
        logger.warning("Failed to create Secret Gist: %s", msg)
        return None
    except Exception as e:
        logger.warning("Unexpected error syncing fixed bridge Gist: %s", e)
        return None


def _drain_stream(stream):
    """Continuously drain subprocess stdout/stderr in a daemon thread to avoid pipe deadlock."""
    if stream is None:
        return
    try:
        for _ in iter(stream.readline, ""):
            pass
    except Exception:
        pass
    finally:
        try:
            stream.close()
        except Exception:
            pass


def check_endpoint_health(base_url, timeout=HEALTH_CHECK_TIMEOUT):
    """Verify the external tunnel URL responds HTTP 200 with JSON status=='ok'."""
    if not base_url:
        return False
    url = f"{base_url.rstrip('/')}/api/health"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AudioStudio-Bridge", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return False
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            return isinstance(data, dict) and data.get("status") == "ok"
    except Exception:
        return False


def has_internet_connectivity(timeout=3):
    """Check basic outbound internet TCP connectivity via public resolvers."""
    for host in ("1.1.1.1", "8.8.8.8"):
        try:
            with socket.create_connection((host, 443), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def _start_flask_server(port):
    """Start the local Flask server subprocess and wait until `/api/health` responds."""
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
    if not wait_for_local_server(port, proc=flask_proc):
        _terminate_proc(flask_proc)
        raise RuntimeError("本機 Flask 伺服器啟動逾時，請確認連接埠未被佔用或依賴套件已安裝。")
    return flask_proc


def _establish_tunnel(cloudflared_bin, port):
    """Establish Tier 1 Cloudflare or Tier 2 localhost.run tunnel and drain its stdout."""
    print("[Mobile Bridge] 正在建立免費 Cloudflare 加密通道...")
    tunnel_proc, tunnel_url = _start_cloudflared_tunnel(cloudflared_bin, port)
    if not tunnel_url:
        tunnel_proc, tunnel_url = _start_localhost_run_tunnel(port)

    if tunnel_proc is not None and tunnel_url:
        threading.Thread(target=_drain_stream, args=(tunnel_proc.stdout,), daemon=True).start()
        return tunnel_proc, tunnel_url

    _terminate_proc(tunnel_proc)
    return None, None


def _watchdog_step(state, cloudflared_bin, port, now=None):
    """Run one non-blocking watchdog cycle on `state`; returns status token string."""
    if now is None:
        now = time.time()

    flask_proc = state.get("flask_proc")
    if flask_proc is None or flask_proc.poll() is not None:
        logger.warning("本機 Flask 後端已停止，正在嘗試重新啟動...")
        try:
            state["flask_proc"] = _start_flask_server(port)
        except Exception as e:
            logger.warning("重啟本機 Flask 失敗: %s", e)

    tunnel_proc = state.get("tunnel_proc")
    tunnel_url = state.get("tunnel_url")
    proc_dead = tunnel_proc is not None and tunnel_proc.poll() is not None
    no_tunnel = not tunnel_url
    health_dead = state.get("consecutive_failures", 0) >= HEALTH_FAIL_THRESHOLD

    if proc_dead or health_dead or no_tunnel:
        if proc_dead or health_dead:
            reason = "通道進程已終止" if proc_dead else f"連續 {HEALTH_FAIL_THRESHOLD} 次健康檢查失敗"
            print(f"[Mobile Bridge Watchdog] {reason}，準備自動重連...")
            _terminate_proc(tunnel_proc)
            state["tunnel_proc"] = None
            state["tunnel_url"] = None
            state["consecutive_failures"] = 0

        if now < state.get("next_reconnect_at", 0):
            return "idle"

        if not has_internet_connectivity():
            if not state.get("waiting_for_net"):
                print("[Mobile Bridge Watchdog] 網路尚未恢復，等待自動重連...")
                state["waiting_for_net"] = True
            backoff = state.get("backoff", RECONNECT_BACKOFF_BASE)
            state["next_reconnect_at"] = now + backoff
            state["backoff"] = min(RECONNECT_BACKOFF_MAX, backoff * 2)
            return "waiting_network"

        state["waiting_for_net"] = False
        new_proc, new_url = _establish_tunnel(cloudflared_bin, port)
        if new_url:
            state["tunnel_proc"] = new_proc
            state["tunnel_url"] = new_url
            state["backoff"] = RECONNECT_BACKOFF_BASE
            state["consecutive_failures"] = 0
            state["last_health_check"] = now
            state["next_reconnect_at"] = 0
            gid = sync_fixed_bridge_gist(new_url, status="online")
            if gid:
                state["gist_id"] = gid
                state["last_synced_url"] = new_url
                print(f"[Mobile Bridge Watchdog] 通道已自動重連並同步固定網址: {new_url}")
            else:
                print(f"[Mobile Bridge Watchdog] 通道已自動重連: {new_url}")
            return "reconnected"

        backoff = state.get("backoff", RECONNECT_BACKOFF_BASE)
        state["next_reconnect_at"] = now + backoff
        state["backoff"] = min(RECONNECT_BACKOFF_MAX, backoff * 2)
        return "reconnect_failed"

    if now - state.get("last_health_check", 0) >= HEALTH_CHECK_INTERVAL:
        state["last_health_check"] = now
        if check_endpoint_health(tunnel_url):
            state["consecutive_failures"] = 0
            state["backoff"] = RECONNECT_BACKOFF_BASE
            if tunnel_url != state.get("last_synced_url"):
                gid = sync_fixed_bridge_gist(tunnel_url, status="online")
                if gid:
                    state["gist_id"] = gid
                    state["last_synced_url"] = tunnel_url
            return "healthy"

        failures = state.get("consecutive_failures", 0) + 1
        state["consecutive_failures"] = failures
        logger.warning(
            "通道健康檢查失敗 (%d/%d): %s",
            failures,
            HEALTH_FAIL_THRESHOLD,
            tunnel_url,
        )
        if failures >= HEALTH_FAIL_THRESHOLD:
            return "unhealthy_threshold"
        return "health_warn"

    return "idle"


def main():
    if "--check" in sys.argv[1:]:
        print(f"MOBILE_BRIDGE_CHECK_OK python={sys.executable}")
        return 0

    preferred_port = int(os.environ.get("PORT", "5000"))
    port = select_available_port(preferred_port)
    if port != preferred_port:
        print(f"[Mobile Bridge] 連接埠 {preferred_port} 已被其他程式佔用，自動改用連接埠 {port}。")
    cloudflared_bin = ensure_cloudflared()

    state = {
        "flask_proc": None,
        "tunnel_proc": None,
        "tunnel_url": None,
        "gist_id": None,
        "last_synced_url": None,
        "consecutive_failures": 0,
        "last_health_check": time.time(),
        "next_reconnect_at": 0,
        "backoff": RECONNECT_BACKOFF_BASE,
        "waiting_for_net": False,
    }
    try:
        state["flask_proc"] = _start_flask_server(port)

        lan_ip = get_lan_ip()
        lan_url = f"http://{lan_ip}:{port}" if lan_ip else ""

        tunnel_proc, tunnel_url = _establish_tunnel(cloudflared_bin, port)
        state["tunnel_proc"] = tunnel_proc
        state["tunnel_url"] = tunnel_url

        if not tunnel_url and not lan_url:
            raise RuntimeError("無法建立外部 HTTPS 通道，且未偵測到區域網路 IP。")

        if tunnel_url:
            gist_id = sync_fixed_bridge_gist(tunnel_url, status="online")
            if gist_id:
                state["gist_id"] = gist_id
                state["last_synced_url"] = tunnel_url
        else:
            state["next_reconnect_at"] = time.time() + RECONNECT_BACKOFF_BASE

        query = {}
        if tunnel_url:
            query["tunnel"] = tunnel_url
        if lan_url:
            query["lan"] = lan_url
        if state["gist_id"]:
            query["gist"] = state["gist_id"]
        bridge_page_url = f"http://127.0.0.1:{port}/bridge?{urllib.parse.urlencode(query)}"

        print("\n" + "=" * 68)
        print("  AudioStudio 手機橋接已啟動！(iPhone / Android / Mac 皆可用)")
        print("=" * 68)
        if state["gist_id"] and tunnel_url:
            fixed_bridge_url = f"{PAGES_URL}?bridge={state['gist_id']}"
            print(f"  [永久固定網址] 手機掃過一次永久不用重掃:\n  {fixed_bridge_url}\n")
            print(f"  本次通道位址 (已自動同步至上述固定網址):\n  {tunnel_url}")
        elif tunnel_url:
            mobile_connect_url = f"{PAGES_URL}?api={urllib.parse.quote(tunnel_url, safe='')}"
            print(f"  手機掃碼自動連線網址 (本次有效):\n  {mobile_connect_url}\n")
            print(f"  直連通道備用網址:\n  {tunnel_url}")
            print("  [提示] 若要啟用永久固定 QR Code，請先執行 `gh auth login` 或設定 GITHUB_GIST_TOKEN。")
        else:
            print("  [提示] 外部免費通道暫時壅塞，已自動切換為「同 Wi-Fi 區網直連模式」！")
        if lan_url:
            print(f"  家用同 Wi-Fi 區網網址:\n  {lan_url}")
        print(f"  [看門狗] 已啟用斷線自動重連（每 {HEALTH_CHECK_INTERVAL} 秒檢查，斷線後自動重建通道並更新固定網址）")
        print("=" * 68)
        print("  即將自動開啟 QR Code 視窗供 iPhone 相機掃描...")
        print("  使用期間請勿關閉此視窗；按 Ctrl+C 或直接關閉視窗即可停止服務。")
        print("=" * 68 + "\n")

        webbrowser.open_new(bridge_page_url)

        while True:
            _watchdog_step(state, cloudflared_bin, port)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Mobile Bridge] 正在關閉橋接服務...")
    finally:
        if state.get("gist_id") and state.get("tunnel_url"):
            sync_fixed_bridge_gist(state["tunnel_url"], status="offline", timeout=3)
        _terminate_proc(state.get("tunnel_proc"))
        _terminate_proc(state.get("flask_proc"))
        print("[Mobile Bridge] 已安全關閉。")


if __name__ == "__main__":
    main()
