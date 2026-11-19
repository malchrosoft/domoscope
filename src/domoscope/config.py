from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_data_path

_SOURCE_ROOT = Path(__file__).resolve().parents[2]


def _data_dir() -> Path:
    """`DOMOSCOPE_HOME`, else `./data` in a source checkout, else the per-user data directory."""
    if home := os.getenv("DOMOSCOPE_HOME"):
        return Path(home)
    if (_SOURCE_ROOT / "pyproject.toml").exists():
        return _SOURCE_ROOT / "data"
    return user_data_path("domoscope", appauthor=False)


DATA_DIR = _data_dir()
REPORTS_DIR = DATA_DIR / "reports"


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    db_path: Path = field(default_factory=lambda: Path(os.getenv("DOMOSCOPE_DB", DATA_DIR / "domoscope.db")))
    subnet: str | None = field(default_factory=lambda: os.getenv("DOMOSCOPE_SUBNET") or None)
    host: str = field(default_factory=lambda: os.getenv("DOMOSCOPE_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("DOMOSCOPE_PORT", "8765")))
    online_lookup: bool = field(default_factory=lambda: _env_bool("DOMOSCOPE_ONLINE_LOOKUP"))
    tuya_version: str = field(default_factory=lambda: os.getenv("DOMOSCOPE_TUYA_VERSION", "3.3"))
    secret_key: str | None = field(default_factory=lambda: os.getenv("DOMOSCOPE_SECRET_KEY") or None)

    @property
    def secret_path(self) -> Path:
        return self.db_path.parent / "secret.key"


settings = Settings()
