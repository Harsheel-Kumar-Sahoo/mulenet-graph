"""Config loader: YAML file -> plain dict, with dotted-key access helper."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent

def load_config(path=None) -> dict:
    p = Path(path) if path else ROOT / "config.yaml"
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get(cfg: dict, dotted: str, default=None):
    cur = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur
