"""
Unified Configuration Manager for AntiHalu.
Handles loading and persisting settings in data/config.json with seamless fallbacks.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = DATA_DIR / "config.json"
HERMES_CONFIG_PATH = Path(os.getenv("HERMES_HOME", str(Path.home() / ".hermes"))) / "config.yaml"

DEFAULT_CONFIG: Dict[str, Any] = {
    "default_model": "anthropic/claude-3.5-sonnet",
    "base_url": "https://openrouter.ai/api/v1",
    "provider": "openrouter",
    "active_jailbreak": {
        "active": False,
        "strategy": None,
        "model": None,
        "system_prompt": None,
        "prefill": None,
        "updated_at": None,
    },
    "custom_models": [],
    "theme": "dark",
}


def load_config() -> Dict[str, Any]:
    """Load configuration from data/config.json with default fallback."""
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        # Merge with defaults for missing keys
        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        return merged
    except Exception:
        return dict(DEFAULT_CONFIG)


def save_config(cfg: Dict[str, Any]) -> None:
    """Save configuration to data/config.json."""
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def get_token(token_file: Path) -> str:
    """Read or create auth token."""
    if token_file.exists():
        token = token_file.read_text(encoding="utf-8").strip()
        if token:
            return token
    import secrets
    token = secrets.token_urlsafe(18)
    token_file.write_text(token + "\n", encoding="utf-8")
    return token
