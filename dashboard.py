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

import yaml

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
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

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
        if not self._authed():
            self._json({"error": "Token tidak valid. Buka lewat URL lengkap dengan ?t=..."}, 403)
            return
        if path == "/":
            html = INDEX_FILE.read_text()
            self._send(200, html, "text/html; charset=utf-8")
            return
        if path == "/api/status":
            self._json(get_status())
            return
        if path.startswith("/api/job/"):
            name = path.rsplit("/", 1)[1]
            with JOBS_LOCK:
                job = JOBS.get(name)
                if job is None:
                    self._json({"status": "none"})
                    return
                out = {k: job[k] for k in ("status", "log", "result", "error")}
            self._json(out)
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
    load_godmode()
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
