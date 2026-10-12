#!/usr/bin/env python3
"""
AntiHalu / Godmode Security Command Center.
Fully standalone red-teaming & LLM safety testing dashboard.
Zero external agent dependency — all core security engines embedded in ./core.

Jalankan:  python dashboard.py
Akses:     http://<IP>:8099/?t=<token>  (token ada di file ./token)
"""

import contextlib
import io
import json
import mimetypes
import os
import secrets
import shutil
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# UTF-8 fallback open for Windows
import builtins
_orig_open = builtins.open
def _utf8_fallback_open(*args, **kwargs):
    mode = kwargs.get("mode", args[1] if len(args) > 1 else "r")
    if "b" not in mode and "encoding" not in kwargs:
        kwargs["encoding"] = "utf-8"
        kwargs["errors"] = "replace"
    return _orig_open(*args, **kwargs)
builtins.open = _utf8_fallback_open

# ---------------------------------------------------------------- Paths & Setup
PORT = int(os.environ.get("PORT", 8099))
ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TOKEN_FILE = DATA_DIR / "token" if (DATA_DIR / "token").exists() else (ROOT_DIR / "token")
INDEX_FILE = ROOT_DIR / "index.html"
DASH_FILE = ROOT_DIR / "dashboard.html"
CONFIG_PATH = DATA_DIR / "config.yaml"
PREFILL_PATH = DATA_DIR / "prefill.json"
BACKUP_PATH = DATA_DIR / "config.yaml.bak"

# ---------------------------------------------------------------- Auth Token
if TOKEN_FILE.exists():
    TOKEN = TOKEN_FILE.read_text(encoding="utf-8").strip()
else:
    TOKEN = secrets.token_urlsafe(18)
    # Save to both for smooth compatibility
    (ROOT_DIR / "token").write_text(TOKEN + "\n", encoding="utf-8")
    (DATA_DIR / "token").write_text(TOKEN + "\n", encoding="utf-8")

# ---------------------------------------------------------------- .env Loader
def load_dotenv(path: Path):
    if not path.exists():
        return
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k:
            os.environ.setdefault(k, v)

# Load root .env first, then fallback locations if available
load_dotenv(ROOT_DIR / ".env")
load_dotenv(DATA_DIR / ".env")
load_dotenv(Path.home() / ".hermes" / ".env")
local_app = os.environ.get("LOCALAPPDATA")
if local_app:
    load_dotenv(Path(local_app) / "hermes" / ".env")

# ---------------------------------------------------------------- Core Security Engines
from core.config import load_config, save_config
from core.security import (
    generate_variants,
    detect_triggers,
    TRIGGER_WORDS,
    race_models,
    race_godmode_classic,
    classic_race,
    ULTRAPLINIAN_MODELS,
    auto_jailbreak,
    undo_jailbreak,
    _detect_model_family,
    _get_current_model,
)

# ---------------------------------------------------------------- Helpers
def json_safe(obj):
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return json.loads(json.dumps(obj, default=str))

def backup_config():
    if CONFIG_PATH.exists():
        shutil.copy2(CONFIG_PATH, BACKUP_PATH)

# ---------------------------------------------------------------- Job System
JOBS = {}
JOBS_LOCK = threading.Lock()

def any_running():
    with JOBS_LOCK:
        return any(j["status"] == "running" for j in JOBS.values())

class _LogWriter(io.TextIOBase):
    def __init__(self, job):
        self._job = job
    def write(self, s):
        with JOBS_LOCK:
            self._job["log"] += s
        return len(s)
    def flush(self):
        pass

def start_job(name, fn):
    with JOBS_LOCK:
        if any(j["status"] == "running" for j in JOBS.values()):
            return False, "Masih ada job yang sedang berjalan. Mohon tunggu hingga selesai."
        job = {"status": "running", "log": "", "result": None, "error": None, "t0": time.time()}
        JOBS[name] = job

    def run():
        try:
            buf = _LogWriter(job)
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                res = fn()
            job["result"] = json_safe(res)
            job["status"] = "done"
        except Exception:
            job["log"] += "\n" + traceback.format_exc()
            job["error"] = str(traceback.format_exc(limit=1))
            job["status"] = "error"
        job["t1"] = time.time()

    threading.Thread(target=run, daemon=True).start()
    return True, "started"

# ---------------------------------------------------------------- Status
def get_status():
    cfg = load_config()
    st = {
        "model": cfg.get("default_model"),
        "base_url": cfg.get("base_url"),
        "family": None,
        "jailbreak_active": cfg.get("active_jailbreak", {}).get("active", False),
        "system_prompt_set": bool(cfg.get("active_jailbreak", {}).get("system_prompt")),
        "prefill_set": bool(cfg.get("active_jailbreak", {}).get("prefill")),
        "prefill_exists": PREFILL_PATH.exists(),
        "config_backup_exists": BACKUP_PATH.exists(),
        "keys": {
            "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
            "deepseek": bool(os.getenv("DEEPSEEK_API_KEY")),
        },
        "running": any_running(),
        "skill_installed": True,  # Always embedded in core!
        "standalone_mode": True,
    }

    try:
        current_model, base_url = _get_current_model()
        if current_model:
            st["model"] = current_model
        if base_url:
            st["base_url"] = base_url
        if st["model"]:
            st["family"] = _detect_model_family(st["model"])
    except Exception as e:
        st["error"] = str(e)

    return st

# ---------------------------------------------------------------- Job Payloads
def job_auto_jailbreak(payload):
    backup_config()
    model = payload.get("model") or None
    base_url = payload.get("base_url") or None
    if not model:
        st = get_status()
        model = st.get("model") or None
        base_url = base_url or st.get("base_url") or None

    res = auto_jailbreak(
        model=model,
        base_url=base_url,
        api_key=payload.get("api_key")
               or os.getenv("OPENAI_API_KEY")
               or os.getenv("OPENROUTER_API_KEY")
               or os.getenv("ANTHROPIC_API_KEY")
               or None,
        canary=payload.get("canary") or None,
        dry_run=bool(payload.get("dry_run")),
        verbose=True,
    )
    if not isinstance(res, dict):
        res = {"success": False, "error": "Proses evaluasi selesai tanpa data kembalian.", "attempts": []}

    # API Error clarity
    try:
        att = res.get("attempts") or []
        if att and all(a.get("error") for a in att):
            res["success"] = False
            res["error"] = "Semua percobaan gagal karena Error API (periksa API key atau kuota endpoint)."
    except Exception:
        pass

    # Update local config state if success
    if res.get("success"):
        cfg = load_config()
        cfg["active_jailbreak"] = {
            "active": True,
            "strategy": res.get("strategy"),
            "model": model,
            "system_prompt": res.get("system_prompt"),
            "prefill": res.get("prefill"),
            "updated_at": time.time(),
        }
        save_config(cfg)

    return res

def job_undo(payload):
    backup_config()
    res = undo_jailbreak(verbose=True)
    cfg = load_config()
    cfg["active_jailbreak"] = {
        "active": False,
        "strategy": None,
        "model": None,
        "system_prompt": None,
        "prefill": None,
        "updated_at": time.time(),
    }
    save_config(cfg)
    return res

def job_race(payload):
    key = (payload.get("api_key") or "").strip() or os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY belum diset. Masukkan API key OpenRouter di form atau simpan di file .env.")
    return race_models(query=payload["query"], tier=payload.get("tier", "fast"), api_key=key)

def job_classic(payload):
    key = (payload.get("api_key") or "").strip() or os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY belum diset. Masukkan API key OpenRouter di form atau simpan di file .env.")
    return race_godmode_classic(query=payload["query"], api_key=key)

def api_obfuscate(payload):
    query = (payload.get("query") or "").strip()
    if not query:
        raise RuntimeError("Query prompt kosong.")
    triggers = detect_triggers(query)
    variants = generate_variants(query, tier=payload.get("tier", "standard"))
    return {"triggers": triggers, "variants": variants}

# ---------------------------------------------------------------- OpenCode Free Client
BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

def _opencode_session_id():
    t = int(time.time() * 1000)
    current = t * 0x1000 + 1
    val = ~current & 0xFFFFFFFFFFFFFFFF
    time_hex = hex(val)[2:].zfill(12)[:12]
    rand = "".join(secrets.choice(BASE62) for _ in range(14))
    return f"ses_{time_hex}{rand}"

def _opencode_request_id():
    t = int(time.time() * 1000)
    current = t * 0x1000 + 1
    time_hex = hex(current)[2:].zfill(12)[:12]
    rand = "".join(secrets.choice(BASE62) for _ in range(14))
    return f"msg_{time_hex}{rand}"

def test_opencode_free():
    import urllib.request
    req = urllib.request.Request(
        "https://opencode.ai/zen/v1/models",
        headers={
            "x-opencode-client": "desktop",
            "User-Agent": "opencode/1.18.31",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [
                m.get("id")
                for m in data.get("data", [])
                if "free" in m.get("id", "") or "contributor" in m.get("id", "") or "spark" in m.get("id", "")
            ]
            return {
                "ok": True,
                "status": "connected",
                "pool": "OpenCode Contributor Free Pool",
                "models_count": len(data.get("data", [])),
                "free_models": models or ["muse-spark-1.3-contributor-free", "muse-spark-1.2-contributor-free", "union-alpha"],
            }
    except Exception as e:
        return {"ok": False, "status": "error", "error": str(e)}

def chat_opencode_free(messages, model="muse-spark-1.3-contributor-free"):
    import urllib.request
    session_id = _opencode_session_id()
    req_id = _opencode_request_id()

    input_items = []
    for m in messages:
        role = m.get("role", "user")
        text = m.get("content", "")
        if isinstance(text, list):
            text = " ".join([item.get("text", "") for item in text if isinstance(item, dict)])
        input_items.append({
            "type": "message",
            "role": role,
            "content": [{"type": "input_text", "text": str(text)}],
        })

    payload = {
        "model": model,
        "input": input_items,
        "tools": [],
    }

    req = urllib.request.Request(
        "https://opencode.ai/zen/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-opencode-client": "desktop",
            "x-opencode-session": session_id,
            "x-opencode-request": req_id,
            "User-Agent": "opencode/1.18.31",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            choices = data.get("choices") or []
            if choices:
                return choices[0].get("message", {}).get("content", "")
            return raw
    except Exception as e:
        raise RuntimeError(f"OpenCode chat failed: {e}")

# ---------------------------------------------------------------- Provider Diagnostics
def test_provider_connection(payload):
    import urllib.request
    base_url = (payload.get("base_url") or "https://openrouter.ai/api/v1").rstrip("/")
    api_key = payload.get("api_key") or ""
    headers = {"User-Agent": "AntiHalu-Security-Test/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    target = f"{base_url}/models"
    req = urllib.request.Request(target, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            count = len(data.get("data", [])) if isinstance(data, dict) else len(data)
            return {"ok": True, "status": "connected", "models_count": count}
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return {"ok": False, "status": "auth_error", "error": "Autentikasi ditolak (HTTP 401). API Key salah."}
        if e.code in (404, 405):
            return {"ok": True, "status": "connected", "msg": f"Endpoint terjangkau (HTTP {e.code})"}
        return {"ok": False, "status": "http_error", "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"ok": False, "status": "network_error", "error": str(e)}

def detect_local_tokens():
    found = {}
    env_keys = {
        "openrouter": "OPENROUTER_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "groq": "GROQ_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "together": "TOGETHER_API_KEY",
        "cohere": "COHERE_API_KEY",
        "perplexity": "PERPLEXITY_API_KEY",
    }
    for p_id, env_var in env_keys.items():
        v = os.getenv(env_var)
        if v:
            found[p_id] = {"key": v, "source": f"ENV ({env_var})"}
    return found

# ---------------------------------------------------------------- HTTP Server Handler
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _authed(self):
        q = parse_qs(urlparse(self.path).query)
        cand = [
            (q.get("t") or [""])[0],
            self.headers.get("x-token", ""),
        ]
        ck = self.headers.get("cookie", "")
        for part in ck.split(";"):
            part = part.strip()
            if part.startswith("gm_t="):
                cand.append(part[5:])
        return any(c and c == TOKEN for c in cand)

    def _send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        if self._authed():
            self.send_header("Set-Cookie", f"gm_t={TOKEN}; Path=/; Max-Age=604800; SameSite=Lax")
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, x-token, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False, default=str))

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8") or "{}")

    # ---- GET
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        q = parse_qs(parsed.query)
        tq = (q.get("t") or [""])[0]
        SET_COOKIE = f"gm_t={TOKEN}; Path=/; Max-Age=31536000; SameSite=Lax"

        # Static assets
        if path.startswith("/assets/"):
            rel_asset = path.lstrip("/")
            asset_path = ROOT_DIR / rel_asset
            if asset_path.exists() and asset_path.is_file():
                mime, _ = mimetypes.guess_type(str(asset_path))
                mime = mime or "application/octet-stream"
                self._send(200, asset_path.read_bytes(), ctype=mime)
                return

        # Main Web Pages
        if path in ("/", "/dashboard", "/dashboard.html", "/index.html", "/landing"):
            if tq == TOKEN:
                self.send_response(302)
                self.send_header("Location", path)
                self.send_header("Set-Cookie", SET_COOKIE)
                self.send_header("Content-Length", "0")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return

            if path in ("/", "/dashboard", "/dashboard.html"):
                target = DASH_FILE if DASH_FILE.exists() else INDEX_FILE
            else:
                target = INDEX_FILE
            html = target.read_text(encoding="utf-8")
            self._send(200, html, "text/html; charset=utf-8", headers={"Set-Cookie": SET_COOKIE})
            return

        # API: tetap dikunci tanpa token (query/header) atau cookie
        if not self._authed():
            self._json({"error": "Token tidak valid. Silakan akses lewat URL lengkap dengan ?t=..."}, 403)
            return
        if path == "/api/status":
            self._json(get_status())
            return
        if path == "/api/config":
            self._json(load_config())
            return
        if path == "/api/provider/auto-detect":
            self._json(detect_local_tokens())
            return
        if path in ("/api/opencode/status", "/api/opencode/test"):
            self._json(test_opencode_free())
            return

        if path.startswith("/api/job/") or path.startswith("/api/log"):
            job_name = ""
            if path.startswith("/api/job/"):
                job_name = path[len("/api/job/"):].strip()
            if not job_name:
                q = parse_qs(parsed.query)
                job_name = (q.get("job") or [""])[0]

            with JOBS_LOCK:
                candidates = [job_name]
                if job_name == "auto":
                    candidates.append("auto_jailbreak")
                elif job_name == "auto_jailbreak":
                    candidates.append("auto")

                found_job = None
                for c in candidates:
                    if c in JOBS:
                        found_job = (c, JOBS[c])
                        break

                if found_job:
                    c_name, j = found_job
                    self._json({
                        "job": c_name,
                        "status": j["status"],
                        "log": j["log"],
                        "result": j["result"],
                        "error": j["error"],
                    })
                    return

                # Return newest job if no specific match
                if JOBS:
                    last_name = list(JOBS.keys())[-1]
                    j = JOBS[last_name]
                    self._json({
                        "job": last_name,
                        "status": j["status"],
                        "log": j["log"],
                        "result": j["result"],
                        "error": j["error"],
                    })
                    return
                self._json({"job": None, "status": "idle", "log": "", "result": None, "error": None})
            return

        self._json({"error": "Endpoint tidak ditemukan"}, 404)

    # ---- POST
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if not self._authed():
            self._json({"error": "Token tidak valid."}, 403)
            return

        payload = self._body()
        try:
            if path == "/api/config":
                cfg = load_config()
                cfg.update(payload)
                save_config(cfg)
                self._json({"ok": True, "config": cfg})
                return
            elif path in ("/api/auto", "/api/auto-jailbreak"):
                ok, msg = start_job("auto", lambda: job_auto_jailbreak(payload))
            elif path == "/api/undo":
                ok, msg = start_job("undo", lambda: job_undo(payload))
            elif path == "/api/race":
                if not (payload.get("query") or "").strip():
                    self._json({"error": "Query prompt tidak boleh kosong."}, 400)
                    return
                ok, msg = start_job("race", lambda: job_race(payload))
            elif path == "/api/classic":
                if not (payload.get("query") or "").strip():
                    self._json({"error": "Query prompt tidak boleh kosong."}, 400)
                    return
                ok, msg = start_job("classic", lambda: job_classic(payload))
            elif path in ("/api/parseltongue", "/api/obfuscate"):
                self._json(api_obfuscate(payload))
                return
            elif path == "/api/opencode/test":
                self._json(test_opencode_free())
                return
            elif path == "/api/provider/test":
                self._json(test_provider_connection(payload))
                return
            elif path == "/api/opencode/chat":
                messages = payload.get("messages") or [{"role": "user", "content": payload.get("prompt", "")}]
                model = payload.get("model", "muse-spark-1.3-contributor-free")
                res_text = chat_opencode_free(messages, model=model)
                self._json({"ok": True, "model": model, "content": res_text})
                return
            else:
                self._json({"error": "Endpoint tidak ditemukan"}, 404)
                return
        except RuntimeError as e:
            self._json({"error": str(e)}, 400)
            return
        except Exception:
            self._json({"error": traceback.format_exc(limit=2)}, 500)
            return

        if ok:
            self._json({"ok": True})
        else:
            self._json({"error": msg}, 409)

# ---------------------------------------------------------------- Main Entrypoint
def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        import socket
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = "<IP-VPS>"

    print("=" * 60, flush=True)
    print(f" AntiHalu Security Command Center (Standalone)", flush=True)
    print(f" Port  : {PORT}", flush=True)
    print(f" Local : http://127.0.0.1:{PORT}/?t={TOKEN}", flush=True)
    print(f" Public: http://{ip}:{PORT}/?t={TOKEN}", flush=True)
    print("=" * 60, flush=True)

    server.serve_forever()

if __name__ == "__main__":
    main()
