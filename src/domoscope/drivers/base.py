from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class DriverError(RuntimeError):
    """Raised when a driver cannot be loaded or a command fails."""


@dataclass(slots=True)
class CommandResult:
    ok: bool
    message: str
    state: dict[str, Any] = field(default_factory=dict)
