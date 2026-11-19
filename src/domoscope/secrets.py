from __future__ import annotations

import os
from functools import cached_property
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .config import settings


class SecretBox:
    """Encrypts local keys before they touch SQLite.

    The key is `DOMOSCOPE_SECRET_KEY` (a Fernet key, see `Fernet.generate_key()`) or a key file
    created on first use next to the database.
    """

    def __init__(self, key_path: Path | None = None, secret: str | None = None) -> None:
        self.key_path = key_path or settings.secret_path
        self.secret = secret or settings.secret_key

    @cached_property
    def _fernet(self) -> Fernet:
        if self.secret:
            try:
                return Fernet(self.secret)
            except ValueError as exc:
                raise RuntimeError("DOMOSCOPE_SECRET_KEY must be a Fernet key") from exc
        if not self.key_path.exists():
            self.key_path.parent.mkdir(parents=True, exist_ok=True)
            self.key_path.write_bytes(Fernet.generate_key())
            os.chmod(self.key_path, 0o600)
        return Fernet(self.key_path.read_bytes().strip())

    def encrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        return "fernet:" + self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        if not value.startswith("fernet:"):  # "plain:" values written by early versions
            return value.removeprefix("plain:")
        try:
            return self._fernet.decrypt(value[7:].encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise RuntimeError("Invalid secret key for this database") from exc


secret_box = SecretBox()
