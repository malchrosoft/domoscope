from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import __version__
from .db import database
from .drivers import DriverError, TuyaDriver
from .identify import describe, port_labels
from .network import choose_network
from .reporting import render_report
from .scanner import Scanner

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals.update(
    describe=describe,
    port_labels=port_labels,
    version=__version__,
)

app = FastAPI(title="Domoscope", version=__version__)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
database.init()


def _redirect(path: str, message: str) -> RedirectResponse:
    separator = "&" if "?" in path else "?"
    return RedirectResponse(f"{path}{separator}message={quote(message, safe='')}", status_code=303)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    devices = database.list_devices()
    latest = database.latest_scan()
    network = None
    try:
        network = choose_network()
    except (RuntimeError, ValueError):
        pass
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "devices": devices,
            "stats": database.stats(),
            "latest": latest,
            "network": network,
            "message": request.query_params.get("message"),
        },
    )


@app.post("/scan")
def scan() -> RedirectResponse:
    summary = Scanner().scan()
    message = (
        f"Scan terminé : {summary.devices_found} appareils "
        f"({summary.devices_new} nouveaux, {summary.devices_updated} mis à jour)."
    )
    return _redirect("/", message)


@app.get("/devices/{device_id}", response_class=HTMLResponse)
def device_detail(request: Request, device_id: int) -> HTMLResponse:
    device = database.get_device(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Appareil introuvable")
    labels: list[str] = []
    for item in device.services.get("ssdp", []):
        if item.get("server"):
            labels.append(f"UPnP : {item['server']}")
        if item.get("st"):
            labels.append(f"UPnP type : {item['st']}")
    for service in device.services.get("mdns", []):
        labels.append(f"mDNS : {service}")
    for key in ("tuya", "kasa", "wiz", "lifx", "miio", "yeelight"):
        if device.services.get(key):
            labels.append(key.upper())
    return templates.TemplateResponse(
        request=request,
        name="device.html",
        context={
            "device": device,
            "service_labels": sorted(set(labels)),
            "ports": port_labels(device.open_ports),
            "message": request.query_params.get("message"),
        },
    )


@app.post("/devices/{device_id}")
def update_device(
    device_id: int,
    hostname: str = Form(""),
    device_type: str = Form(""),
    notes: str = Form(""),
    tuya_device_id: str = Form(""),
    tuya_local_key: str = Form(""),
    tuya_version: str = Form(""),
    clear_tuya: bool = Form(False),
) -> RedirectResponse:
    device = database.get_device(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Appareil introuvable")
    database.update_device(
        device_id,
        hostname=hostname.strip() or None,
        device_type=device_type.strip() or None,
        notes=notes,
        tuya_device_id=tuya_device_id.strip() or None,
        tuya_local_key=tuya_local_key.strip() or None,
        tuya_version=tuya_version.strip() or None,
        clear_tuya=clear_tuya,
    )
    return _redirect(f"/devices/{device_id}", "Appareil mis à jour.")


@app.post("/devices/{device_id}/command")
def command(
    device_id: int,
    action: str = Form(...),
    brightness: int | None = Form(None),
    color_temp: int | None = Form(None),
    red: int | None = Form(None),
    green: int | None = Form(None),
    blue: int | None = Form(None),
) -> RedirectResponse:
    device = database.get_device(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Appareil introuvable")
    try:
        driver = TuyaDriver(device)
        result = driver.command(
            action,
            brightness=brightness,
            color_temp=color_temp,
            red=red,
            green=green,
            blue=blue,
        )
        message = result.message if result.ok else f"Échec : {result.message}"
    except DriverError as exc:
        message = f"Erreur : {exc}"
    except Exception as exc:  # noqa: BLE001 - surface driver errors in the UI
        message = f"Erreur inattendue : {exc}"
    return _redirect(f"/devices/{device_id}", message)


@app.get("/report", response_class=HTMLResponse)
def report() -> HTMLResponse:
    return HTMLResponse(render_report())


@app.get("/api/devices")
def api_devices() -> JSONResponse:
    return JSONResponse([device.to_dict() for device in database.list_devices()])


@app.get("/api/devices/{device_id}")
def api_device(device_id: int) -> JSONResponse:
    device = database.get_device(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Appareil introuvable")
    return JSONResponse(device.to_dict())


@app.post("/api/scan")
def api_scan() -> JSONResponse:
    summary = Scanner().scan()
    return JSONResponse(summary.to_dict())


@app.get("/api/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "version": __version__})
