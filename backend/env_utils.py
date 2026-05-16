from __future__ import annotations

from pathlib import Path


def get_env(name: str, default: str = "") -> str:
    file_value = _read_secret_file(name)
    if file_value is not None:
        return file_value

    import os

    return os.getenv(name, default)


def get_list_env(name: str, default: list[str] | None = None) -> list[str]:
    raw = get_env(name, "")
    if not raw:
        return default or []
    return [item.strip() for item in raw.split(",") if item.strip()]


def get_bool_env(name: str, default: bool = False) -> bool:
    raw = get_env(name, "1" if default else "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def has_env(name: str) -> bool:
    return bool(get_env(name, "").strip())


def env_source(name: str) -> str:
    import os

    file_path = os.getenv(f"{name}_FILE", "").strip()
    if file_path:
        return "file"
    if os.getenv(name, "").strip():
        return "env"
    return "missing"


def _read_secret_file(name: str) -> str | None:
    import os

    file_path = os.getenv(f"{name}_FILE", "").strip()
    if not file_path:
        return None

    secret_file = Path(file_path)
    if not secret_file.exists():
        return None
    return secret_file.read_text(encoding="utf-8").strip()
