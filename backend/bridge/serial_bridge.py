"""Read newline-delimited ESP32 JSON from a serial port and forward it to HydroInsight.

Example:
  py -3 backend/bridge/serial_bridge.py --port COM5 --baud 115200 \
    --endpoint http://127.0.0.1:8000/api/ingest/http --device-key local-device-key

The bridge intentionally does not overwrite firmware. It accepts the documented JSON
shape and reports malformed, duplicate or rejected messages without crashing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen


def parse_message(raw: str) -> dict:
    payload = json.loads(raw)
    required = {"device_id", "timestamp"}
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"missing fields: {', '.join(sorted(missing))}")
    # The ESP32 firmware uses its monotonic millis counter because it has no
    # network clock. Stamp it at bridge receipt while preserving all sensor
    # values exactly as emitted by the OLED packet.
    if isinstance(payload["timestamp"], (int, float)):
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()
    else:
        datetime.fromisoformat(str(payload["timestamp"]).replace("Z", "+00:00"))
    if all(payload.get(key) is None for key in ("distance_cm", "water_level_percent", "water_depth_cm")):
        raise ValueError("at least one groundwater measurement is required")
    return payload


def forward(endpoint: str, device_key: str, payload: dict) -> str:
    body = json.dumps(payload).encode()
    request = Request(endpoint, data=body, headers={"Content-Type": "application/json", "X-Device-Key": device_key}, method="POST")
    with urlopen(request, timeout=10) as response:
        return response.read().decode()


class LegacyTextParser:
    """Parse the human-readable lines emitted by the current OLED firmware."""

    distance_pattern = re.compile(r"^Sensor distance:\s*(-?\d+(?:\.\d+)?)\s*cm$", re.I)
    height_pattern = re.compile(r"^Water level:\s*(-?\d+(?:\.\d+)?)\s*cm$", re.I)
    percentage_pattern = re.compile(r"^Water percentage:\s*(-?\d+(?:\.\d+)?)\s*%$", re.I)

    def __init__(self, device_id: str) -> None:
        self.device_id = device_id
        self.distance_cm: float | None = None
        self.water_depth_cm: float | None = None

    def parse(self, raw: str) -> dict | None:
        line = raw.strip()
        match = self.distance_pattern.match(line)
        if match:
            self.distance_cm = float(match.group(1))
            return None

        match = self.height_pattern.match(line)
        if match:
            self.water_depth_cm = float(match.group(1))
            return None

        match = self.percentage_pattern.match(line)
        if not match:
            return None

        payload = {
            "device_id": self.device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "distance_cm": self.distance_cm,
            "water_level_percent": float(match.group(1)),
            "water_depth_cm": self.water_depth_cm,
            "temperature_c": None,
        }
        self.distance_cm = None
        self.water_depth_cm = None
        return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8000/api/ingest/http")
    parser.add_argument("--device-key", required=True, help="Device ingest key; never use a hardcoded production key")
    parser.add_argument("--device-id", default="ESP32-001")
    parser.add_argument("--min-interval", type=float, default=0.25, help="Minimum seconds between forwarded readings (250ms default)")
    args = parser.parse_args()
    try:
        import serial
    except ImportError:
        print("pyserial is required: py -3 -m pip install pyserial", file=sys.stderr)
        return 2
    print(f"Listening on {args.port} at {args.baud} baud; forwarding to {args.endpoint}")
    print(f"Input mode: auto (JSON or current OLED text firmware); forwarding at most once every {args.min_interval:g}s")
    legacy_parser = LegacyTextParser(args.device_id)
    last_forwarded_at = 0.0
    with serial.Serial(args.port, args.baud, timeout=1) as port:
        while True:
            raw = port.readline().decode("utf-8", errors="replace").strip()
            if not raw:
                continue
            try:
                try:
                    payload = parse_message(raw)
                except json.JSONDecodeError:
                    payload = legacy_parser.parse(raw)
                    if payload is None:
                        continue
                    parse_message(json.dumps(payload))
                now = time.monotonic()
                if now - last_forwarded_at < args.min_interval:
                    continue
                print(forward(args.endpoint, args.device_key, payload))
                last_forwarded_at = now
            except Exception as error:
                print(f"bridge rejected line: {error}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())

