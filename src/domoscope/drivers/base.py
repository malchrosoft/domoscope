from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Health statuses of a controllable device, as stored in `devices.check_status`.
READY = "ready"
UNREACHABLE = "unreachable"
INVALID_KEY = "invalid_key"


class DriverError(RuntimeError):
    """Raised when a driver cannot be loaded or a command fails."""


@dataclass(slots=True)
class CommandResult:
    ok: bool
    message: str
    state: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Health:
    status: str
    error: str | None = None
    state: dict[str, Any] = field(default_factory=dict)
