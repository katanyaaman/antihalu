#!/usr/bin/env python3
"""
Godmode Dashboard — UI web untuk skill godmode (official/security/godmode).
Zero dependency: cukup python3 + pyyaml (sudah ada di venv Hermes).

Jalankan:  python3 dashboard.py
Akses:     http://<IP-VPS>:8099/?t=<token>   (token ada di file ./token)
"""
import contextlib
import io
import json
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

try:
    import yaml
except ImportError:
    yaml = None

PORT = 8099
HERE = Path(__file__).resolve().parent
TOKEN_FILE = HERE / "token"
INDEX_FILE = HERE / "index.html"
HERMES_HOME = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
SCRIPTS = HERMES_HOME / "skills" / "security" / "godmode" / "scripts"
CONFIG_PATH = HERMES_HOME / "config.yaml"
PREFILL_PATH = HERMES_HOME / "prefill.json"
BACKUP_PATH = HERMES_HOME / "config.yaml.gmdbak"

# ---------------------------------------------------------------- auth token
if TOKEN_FILE.exists():
    TOKEN = TOKEN_FILE.read_text().strip()
else:
    TOKEN = secrets.token_urlsafe(18)
    TOKEN_FILE.write_text(TOKEN + "\n")
    TOKEN_FILE.chmod(0o600)

# ---------------------------------------------------------------- .env loader
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

load_dotenv(HERMES_HOME / ".env")

# ---------------------------------------------------------------- godmode loader
GM = {}

def load_godmode():
    """Load parseltongue + godmode_race + auto_jailbreak ke satu namespace."""
    if GM.get("_loaded"):
        return GM
    if not SCRIPTS.exists():
        raise RuntimeError(f"Skill godmode belum terinstall ({SCRIPTS} tidak ada)")
    old_argv = sys.argv
    sys.argv = ["godmode_dash"]
    sys.path.insert(0, str(SCRIPTS))
    try:
        for f in ("parseltongue.py", "godmode_race.py", "auto_jailbreak.py"):
            p = SCRIPTS / f
            ns = {"__name__": "_godmode_module", "__file__": str(p)}
            exec(compile(p.read_text(), str(p), "exec"), ns)
            for k, v in ns.items():
                if not k.startswith("__"):
                    GM[k] = v
        GM["_loaded"] = True
    finally:
        sys.argv = old_argv
    return GM

def json_safe(obj):
    try:
        json.dumps(obj)
        return obj
    except Exception:
        return json.loads(json.dumps(obj, default=str))

def backup_config():
    if CONFIG_PATH.exists():
        shutil.copy2(CONFIG_PATH, BACKUP_PATH)

# ---------------------------------------------------------------- skill installer
def ensure_skill():
    """Auto-install skill godmode (official) kalau belum ada — biar clone+run cukup."""
    if SCRIPTS.exists():
        return
    print("Skill godmode belum terinstall — menginstall official/security/godmode ...", flush=True)
    import subprocess
    try:
        r = subprocess.run(
            ["hermes", "skills", "install", "official/security/godmode", "--force"],
            input="y\n", text=True, capture_output=True, timeout=180,
        )
        if SCRIPTS.exists():
            print("Skill godmode terinstall OK.", flush=True)
            return
        print("Install selesai tapi folder skill tidak ditemukan. Jalankan manual:", flush=True)
        print("  hermes skills install official/security/godmode --force", flush=True)
        print((r.stdout or "")[-400:], (r.stderr or "")[-200:], flush=True)
    except FileNotFoundError:
        print("Perintah 'hermes' tidak ditemukan. Install skill manual dulu:", flush=True)
        print("  hermes skills install official/security/godmode --force", flush=True)
    except Exception as e:
        print(f"Auto-install gagal ({e}). Install skill manual dulu:", flush=True)
        print("  hermes skills install official/security/godmode --force", flush=True)

# ---------------------------------------------------------------- job system
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
            return False, "Masih ada job yang sedang jalan — tunggu selesai dulu."
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

# ---------------------------------------------------------------- status
def get_status():
    st = {
        "model": None,
        "base_url": None,
        "family": None,
        "jailbreak_active": False,
        "system_prompt_set": False,
        "prefill_set": False,
        "prefill_exists": PREFILL_PATH.exists(),
        "config_backup_exists": BACKUP_PATH.exists(),
        "keys": {
            "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        },
        "running": any_running(),
        "skill_installed": SCRIPTS.exists(),
    }
    try:
        gm = load_godmode()
        model, base_url = gm["_get_current_model"]()
        st["model"] = model
        st["base_url"] = base_url
        st["family"] = gm["_detect_model_family"](model) if model else None
    except Exception as e:
        st["error"] = str(e)
    if CONFIG_PATH.exists():
        try:
            cfg = yaml.safe_load(CONFIG_PATH.read_text()) or {}
        except Exception:
            cfg = {}
        # config Hermes pakai model.default / model.provider (skill cuma baca name)
        mc = cfg.get("model") or {}
        if isinstance(mc, str):
            st["model"] = st["model"] or mc
        elif isinstance(mc, dict):
            st["model"] = st["model"] or mc.get("name") or mc.get("default")
            st["base_url"] = st["base_url"] if st["base_url"] and "openrouter" in str(st["base_url"]) else (mc.get("base_url") or st["base_url"])
            st["provider"] = mc.get("provider")
        if st["model"]:
            st["family"] = load_godmode()["_detect_model_family"](str(st["model"]))
        agent = cfg.get("agent") or {}
        sp = (agent.get("system_prompt") or "").strip()
        pf = cfg.get("prefill_messages_file") or agent.get("prefill_messages_file")
        st["system_prompt_set"] = bool(sp)
        st["prefill_set"] = bool(pf)
        st["jailbreak_active"] = bool(sp) or bool(pf)
    return st

# ---------------------------------------------------------------- job payloads
def job_auto_jailbreak(payload):
    backup_config()
    gm = load_godmode()
    model = payload.get("model") or None
    base_url = payload.get("base_url") or None
    if not model:  # skill cuma baca model.name; config Hermes pakai model.default
        st = get_status()
        model = st.get("model") or None
        base_url = base_url or st.get("base_url") or None
    res = gm["auto_jailbreak"](
        model=model,
        base_url=base_url,
        api_key=payload.get("api_key") or os.getenv("OPENAI_API_KEY")
               or os.getenv("OPENROUTER_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or None,
        canary=payload.get("canary") or None,
        dry_run=bool(payload.get("dry_run")),
        verbose=True,
    )
    # skill salah baca error API sebagai "refusal" — kasih peringatan jelas
    try:
        att = res.get("attempts") or []
        if att and all(a.get("error") for a in att):
            res["success"] = False
            res["error"] = "SEMUA attempt gagal karena ERROR API (kemungkinan model/key gak diakses) — ini BUKAN refusal model. Cek akses model di proxy/key dulu."
    except Exception:
        pass
    return res

def job_undo(payload):
    backup_config()
    gm = load_godmode()
    return gm["undo_jailbreak"](verbose=True)

def job_race(payload):
    gm = load_godmode()
    if not os.getenv("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY belum ada di ~/.hermes/.env — fitur race butuh OpenRouter.")
    return gm["race_models"](query=payload["query"], tier=payload.get("tier", "fast"))

def job_classic(payload):
    gm = load_godmode()
    if not os.getenv("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY belum ada di ~/.hermes/.env — fitur race butuh OpenRouter.")
    return gm["race_godmode_classic"](query=payload["query"])

def api_obfuscate(payload):
    gm = load_godmode()
    query = (payload.get("query") or "").strip()
    if not query:
        raise RuntimeError("Query kosong.")
    triggers = gm["detect_triggers"](query)
    variants = gm["generate_variants"](query, tier=payload.get("tier", "standard"))
    return {"triggers": triggers, "variants": variants}

# ---------------------------------------------------------------- opencode free native client
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
    """Test connection directly to OpenCode free contributor pool without API key."""
    import urllib.request
    req = urllib.request.Request(
        "https://opencode.ai/zen/v1/models",
        headers={
            "x-opencode-client": "desktop",
            "User-Agent": "opencode/1.18.31",
        },
        method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("id") for m in data.get("data", []) if "free" in m.get("id", "") or "contributor" in m.get("id", "") or "spark" in m.get("id", "")]
            return {
                "ok": True,
                "status": "connected",
                "pool": "OpenCode Contributor Free Pool",
                "models_count": len(data.get("data", [])),
                "free_models": models or ["muse-spark-1.3-contributor-free", "muse-spark-1.2-contributor-free", "union-alpha"]
            }
    except Exception as e:
        return {"ok": False, "status": "error", "error": str(e)}

def chat_opencode_free(messages, model="muse-spark-1.3-contributor-free"):
    """Send prompt to OpenCode Free pool and return text response."""
    import urllib.request
    session_id = _opencode_session_id()
    req_id = _opencode_request_id()

    # Format input for OpenAI Responses API schema expected by OpenCode
    input_items = []
    for m in messages:
        role = m.get("role", "user")
        text = m.get("content", "")
        if isinstance(text, list):
            text = " ".join([item.get("text", "") for item in text if isinstance(item, dict)])
        input_items.append({
            "type": "message",
            "role": role,
            "content": [{"type": "input_text", "text": str(text)}]
        })

    payload = {
        "model": model,
        "input": input_items,
        "tools": [
            {"type": "function", "name": "bash", "description": "unavailable", "parameters": {"type": "object", "properties": {}}},
            {"type": "function", "name": "glob", "description": "unavailable", "parameters": {"type": "object", "properties": {}}},
            {"type": "function", "name": "grep", "description": "unavailable", "parameters": {"type": "object", "properties": {}}},
            {"type": "function", "name": "read", "description": "unavailable", "parameters": {"type": "object", "properties": {}}},
        ],
        "tool_choice": "auto",
        "stream": True
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "opencode/1.18.31",
        "x-opencode-client": "desktop",
        "x-opencode-session": session_id,
        "x-opencode-request": req_id
    }

    req = urllib.request.Request(
        "https://opencode.ai/zen/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    full_text = ""
    with urllib.request.urlopen(req, timeout=30) as resp:
        for line in resp:
            line_str = line.decode("utf-8", errors="replace").strip()
            if line_str.startswith("data: "):
                raw_json = line_str[6:].strip()
                if raw_json and raw_json != "[DONE]":
                    try:
                        chunk = json.loads(raw_json)
                        if chunk.get("type") == "response.output_text.delta":
                            full_text += chunk.get("delta", "")
                    except Exception:
                        pass
    return full_text.strip()

# ---------------------------------------------------------------- generic provider tester
def test_provider_connection(payload):
    """Test connection to any LLM provider (API Key, OAuth, or Free Tier)."""
    p_id = payload.get("id", "")
    p_type = payload.get("type", "apikey")
    key = (payload.get("key") or "").strip()
    base_url = (payload.get("base_url") or "").strip().rstrip("/")

    # OpenCode Free special handler
    if p_id == "opencode_free":
        return test_opencode_free()

    # Local Ollama handler
    if "ollama" in p_id or "localhost:11434" in base_url or "127.0.0.1:11434" in base_url:
        target_url = base_url or "http://localhost:11434"
        try:
            import urllib.request
            req = urllib.request.Request(f"{target_url}/api/tags", headers={"User-Agent": "AntiHalu/1.0"}, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", [])]
                return {
                    "ok": True,
                    "status": "connected",
                    "provider": "Ollama Local",
                    "models_count": len(models),
                    "models": models[:10]
                }
        except Exception as e:
            return {"ok": False, "status": "error", "error": f"Ollama tidak merespon di {target_url} ({e})"}

    if not key and not base_url:
        return {"ok": False, "status": "missing_credentials", "error": "API Key atau Token belum diisi."}

    # Standard OpenAI / Anthropic format models check
    import urllib.request
    check_url = f"{base_url}/models" if base_url else "https://api.openai.com/v1/models"
    headers = {
        "User-Agent": "AntiHalu/1.0",
        "Accept": "application/json"
    }

    if "anthropic" in p_id or "anthropic" in base_url:
        headers["x-api-key"] = key
        headers["anthropic-version"] = "2023-06-01"
        check_url = f"{base_url}/models" if base_url else "https://api.anthropic.com/v1/models"
    else:
        headers["Authorization"] = f"Bearer {key}"

    try:
        req = urllib.request.Request(check_url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models_list = data.get("data") or data.get("models") or []
            count = len(models_list) if isinstance(models_list, list) else 1
            return {
                "ok": True,
                "status": "connected",
                "models_count": count,
                "msg": f"Berhasil terhubung ke endpoint {check_url}"
            }
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return {"ok": False, "status": "auth_error", "error": f"Autentikasi ditolak (HTTP {e.code}). Periksa kembali API Key / Token OAuth."}
        # Many proxy endpoints don't implement /models but accept chat completions
        if e.code in (404, 405):
            return {"ok": True, "status": "connected", "msg": f"Endpoint terjangkau (HTTP {e.code} /models bypass)"}
        return {"ok": False, "status": "http_error", "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"ok": False, "status": "network_error", "error": str(e)}

def detect_local_tokens():
    """Scan local environment and configs for active provider tokens."""
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

    # Check local Hermes config
    if CONFIG_PATH.exists():
        try:
            cfg = yaml.safe_load(CONFIG_PATH.read_text()) or {} if yaml else {}
            mc = cfg.get("model") or {}
            if isinstance(mc, dict) and mc.get("api_key"):
                found["hermes_default"] = {"key": mc.get("api_key"), "source": "Hermes config.yaml"}
        except Exception:
            pass

    return found

# ---------------------------------------------------------------- http
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
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, x-token, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        for k, v in (headers or {}).items():
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
        path = urlparse(self.path).path
        q = parse_qs(urlparse(self.path).query)
        tq = (q.get("t") or [""])[0]
        SET_COOKIE = f"gm_t={TOKEN}; Path=/; Max-Age=31536000; SameSite=Lax"

        # Halaman: selalu bisa dibuka. Token dipindahkan dari URL ke cookie
        # supaya address bar & link menu tetap bersih (gak nempel ?t=...)
        if path in ("/", "/index.html", "/dashboard", "/dashboard.html"):
            if tq == TOKEN:
                # ada token di URL -> simpan ke cookie, redirect ke URL bersih
                self.send_response(302)
                self.send_header("Location", path)
                self.send_header("Set-Cookie", SET_COOKIE)
                self.send_header("Content-Length", "0")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
            target = INDEX_FILE
            if path in ("/dashboard", "/dashboard.html"):
                dash_file = HERE / "dashboard.html"
                target = dash_file if dash_file.exists() else INDEX_FILE
            html = target.read_text(encoding="utf-8")
            self._send(200, html, "text/html; charset=utf-8",
                       headers={"Set-Cookie": SET_COOKIE})
            return

        # API: tetap dikunci tanpa token (query/header) atau cookie
        if not self._authed():
            self._json({"error": "Token tidak valid. Buka lewat URL lengkap dengan ?t=..."}, 403)
            return
        if path == "/api/status":
            self._json(get_status())
            return
        if path == "/api/provider/auto-detect":
            self._json(detect_local_tokens())
            return
        if path == "/api/opencode/status" or path == "/api/opencode/test":
            self._json(test_opencode_free())
            return
        if path.startswith("/api/job/"):
            name = path.rsplit("/", 1)[1]
            with JOBS_LOCK:
                job = JOBS.get(name)
                if job is None:
                    self._json({"status": "none"})
                    return
                out = {k: job[k] for k in ("status", "log", "result", "error")}
        if path.startswith("/assets/"):
            rel_file = HERE / path.lstrip("/")
            if rel_file.exists() and rel_file.is_file():
                content_type = "image/png" if path.endswith(".png") else "image/svg+xml" if path.endswith(".svg") else "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "public, max-age=86400")
                data = rel_file.read_bytes()
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
        self._json({"error": "not found"}, 404)

    # ---- POST
    def do_POST(self):
        if not self._authed():
            self._json({"error": "Token tidak valid."}, 403)
            return
        path = urlparse(self.path).path
        try:
            payload = self._body()
        except Exception:
            self._json({"error": "Body JSON tidak valid."}, 400)
            return
        try:
            if path == "/api/auto":
                ok, msg = start_job("auto", lambda: job_auto_jailbreak(payload))
            elif path == "/api/undo":
                ok, msg = start_job("undo", lambda: job_undo(payload))
            elif path == "/api/race":
                q = (payload.get("query") or "").strip()
                if not q:
                    self._json({"error": "Query kosong."}, 400)
                    return
                if not os.getenv("OPENROUTER_API_KEY"):
                    self._json({"error": "OPENROUTER_API_KEY belum ada di ~/.hermes/.env — fitur race butuh OpenRouter."}, 400)
                    return
                ok, msg = start_job("race", lambda: job_race(payload))
            elif path == "/api/classic":
                q = (payload.get("query") or "").strip()
                if not q:
                    self._json({"error": "Query kosong."}, 400)
                    return
                if not os.getenv("OPENROUTER_API_KEY"):
                    self._json({"error": "OPENROUTER_API_KEY belum ada di ~/.hermes/.env — fitur race butuh OpenRouter."}, 400)
                    return
                ok, msg = start_job("classic", lambda: job_classic(payload))
            elif path == "/api/obfuscate":
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
                self._json({"error": "not found"}, 404)
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

# ---------------------------------------------------------------- main
def main():
    ensure_skill()
    try:
        load_godmode()
    except Exception as e:
        # jangan crash — server tetap jalan, UI nunjukin badge "belum terinstall"
        print(f"Peringatan: skill godmode belum bisa dimuat ({e})", flush=True)
        print("  Install manual: hermes skills install official/security/godmode --force", flush=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        import socket
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = "<IP-VPS>"
    print(f"Godmode Dashboard jalan di port {PORT}", flush=True)
    print(f"  Local : http://127.0.0.1:{PORT}/?t={TOKEN}", flush=True)
    print(f"  Public: http://{ip}:{PORT}/?t={TOKEN}", flush=True)
    server.serve_forever()

if __name__ == "__main__":
    main()
