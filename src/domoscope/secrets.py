from __future__ import annotations

import base64
import os
from pathlib import Path

from .config import settings

try:  # pragma: no cover - depends on optional package state
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover
    Fernet = None  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[assignment]


class SecretBox:
    """Small helper that encrypts local keys before they touch SQLite.

    If ``cryptography`` is unavailable the value is stored as plain text with a
    ``plain:`` prefix. That keeps the MVP usable, but the UI shows a warning.
    """

    def __init__(self, key_path: Path | None = None, secret: str | None = None) -> None:
        self.key_path = key_path or settings.secret_path
        self._fernet = None
        if Fernet is None:
            return
        key = self._load_or_create_key(secret)
        self._fernet = Fernet(key)

    def _load_or_create_key(self, secret: str | None) -> bytes:
        if secret:
            raw = secret.encode("utf-8")
            if len(raw) == 44:
                return raw
            return base64.urlsafe_b64encode(raw.ljust(32, b"0")[:32])
        if self.key_path.exists():
            return self.key_path.read_bytes().strip()
        key = Fernet.generate_key()
        self.key_path.write_bytes(key)
        try:
            os.chmod(self.key_path, 0o600)
        except OSError:
            pass
        return key

    @property
    def encrypted(self) -> bool:
        return self._fernet is not None

    def encrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        if self._fernet is None:
            return "plain:" + value
        return "fernet:" + self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        if value.startswith("plain:"):
            return value[6:]
        if value.startswith("fernet:"):
            if self._fernet is None:
                raise RuntimeError("cryptography is required to decrypt this value")
            try:
                return self._fernet.decrypt(value[7:].encode("ascii")).decode("utf-8")
            except InvalidToken as exc:  # pragma: no cover
                raise RuntimeError("Invalid secret key for this database") from exc
        return value


secret_box = SecretBox()
