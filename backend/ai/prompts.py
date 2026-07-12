import re
from pathlib import Path

import yaml

_PATH = Path(__file__).resolve().parents[1] / "config" / "prompts.yaml"
_cache = None


def load() -> dict:
    global _cache
    if _cache is None:
        with open(_PATH, "r", encoding="utf-8") as f:
            _cache = yaml.safe_load(f)
    return _cache


def reload():
    global _cache
    _cache = None
    return load()


def _substitute(text: str, vars: dict) -> str:
    def repl(m):
        return str(vars.get(m.group(1), m.group(0)))

    return re.sub(r"\{\{\s*(\w+)\s*\}\}", repl, text)


def render(section: str, vars: dict) -> list:
    tpl = load()[section]
    return [
        {"role": "system", "content": _substitute(tpl["system"], vars)},
        {"role": "user", "content": _substitute(tpl["user"], vars)},
    ]
