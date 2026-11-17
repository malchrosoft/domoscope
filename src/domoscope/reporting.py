from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import REPORTS_DIR
from .db import database
from .models import Device

TEMPLATES_DIR = Path(__file__).parent / "templates"
env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_report(
    devices: Iterable[Device] | None = None,
    scans: list[dict[str, Any]] | None = None,
    summary: dict[str, Any] | None = None,
) -> str:
    devices = list(devices) if devices is not None else database.list_devices()
    scans = scans if scans is not None else database.list_scans(10)
    template = env.get_template("report.html")
    return template.render(
        devices=devices,
        scans=scans,
        summary=summary,
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )


def devices_as_json(devices: Iterable[Device] | None = None) -> str:
    devices = list(devices) if devices is not None else database.list_devices()
    return json.dumps([device.to_dict() for device in devices], indent=2, ensure_ascii=False)


def devices_as_csv(devices: Iterable[Device] | None = None) -> str:
    devices = list(devices) if devices is not None else database.list_devices()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "ip",
            "mac",
            "hostname",
            "vendor",
            "device_type",
            "open_ports",
            "first_seen",
            "last_seen",
            "notes",
            "controllable",
        ]
    )
    for device in devices:
        writer.writerow(
            [
                device.id,
                device.ip,
                device.mac or "",
                device.hostname or "",
                device.vendor or "",
                device.device_type,
                " ".join(str(port) for port in device.open_ports),
                device.first_seen,
                device.last_seen,
                device.notes,
                device.controllable,
            ]
        )
    return buffer.getvalue()


def write_report(fmt: str = "html", output: Path | str | None = None) -> Path:
    fmt = fmt.lower()
    if fmt not in {"html", "json", "csv"}:
        raise ValueError("format must be html, json or csv")
    if output is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = REPORTS_DIR / f"domoscope-{stamp}.{fmt}"
    else:
        output_path = Path(output)
        if not output_path.is_absolute():
            output_path = REPORTS_DIR / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "html":
        output_path.write_text(render_report(), encoding="utf-8")
    elif fmt == "json":
        output_path.write_text(devices_as_json(), encoding="utf-8")
    else:
        output_path.write_text(devices_as_csv(), encoding="utf-8")
    return output_path
