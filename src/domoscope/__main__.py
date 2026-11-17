from __future__ import annotations

import argparse
from pathlib import Path

from .config import settings
from .db import database
from .network import choose_network
from .reporting import write_report
from .scanner import Scanner


def _print_devices() -> None:
    devices = database.list_devices()
    if not devices:
        print("Aucun appareil. Lance: domoscope scan")
        return
    print(f"{'ID':>4}  {'IP':<15}  {'TYPE':<34}  {'FABRICANT':<28}  PORTS")
    print("-" * 110)
    for device in devices:
        ports = ",".join(str(port) for port in device.open_ports) or "-"
        print(
            f"{device.id or 0:>4}  {device.ip:<15}  {device.device_type[:34]:<34}  "
            f"{(device.vendor or '-')[:28]:<28}  {ports}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="domoscope", description="Scan and inventory your LAN.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create the SQLite database")

    scan_parser = sub.add_parser("scan", help="Scan the local network")
    scan_parser.add_argument("--subnet", help="Force a subnet, e.g. 192.168.0.0/24")

    sub.add_parser("devices", help="List known devices")

    report_parser = sub.add_parser("report", help="Write an inventory report")
    report_parser.add_argument("--format", choices=["html", "json", "csv"], default="html")
    report_parser.add_argument("--output", help="Output path (default: data/reports/...)")

    serve_parser = sub.add_parser("serve", help="Start the web interface")
    serve_parser.add_argument("--host", default=settings.host)
    serve_parser.add_argument("--port", type=int, default=settings.port)
    serve_parser.add_argument("--reload", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "init":
        database.init()
        print(f"Base initialisée: {settings.db_path}")
        print(f"Secret: {settings.secret_path}")
        return 0

    if args.command == "scan":
        scanner = Scanner(choose_network(args.subnet)) if args.subnet else Scanner()
        summary = scanner.scan()
        print(f"Scan terminé: {summary.subnet}")
        print(
            f"  {summary.hosts_alive} hôtes actifs, {summary.devices_found} appareils, "
            f"{summary.devices_new} nouveaux, {summary.devices_updated} mis à jour"
        )
        if summary.errors:
            print("  Avertissements:")
            for error in summary.errors:
                print(f"   - {error}")
        print()
        _print_devices()
        return 0

    if args.command == "devices":
        _print_devices()
        return 0

    if args.command == "report":
        output = Path(args.output) if args.output else None
        path = write_report(args.format, output)
        print(f"Rapport écrit: {path}")
        return 0

    if args.command == "serve":
        import uvicorn

        uvicorn.run(
            "domoscope.web:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
