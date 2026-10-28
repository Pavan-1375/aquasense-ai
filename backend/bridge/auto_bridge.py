"""Reconnect-safe ESP32 serial bridge.

The watcher detects CP210x, CH340/CH341, FTDI and native Espressif USB serial
adapters, starts the normal bridge on the detected port, and restarts it after
USB disconnect/reconnect. It never flashes firmware unless --upload is passed.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from serial.tools import list_ports


KNOWN_USB_IDS = {
    (0x10C4, 0xEA60),  # Silicon Labs CP210x
    (0x1A86, 0x7523),  # CH340/CH341
    (0x0403, 0x6001),  # FTDI
    (0x303A, None),    # Espressif native USB
}


def matching_ports() -> list[str]:
    ports: list[str] = []
    for port in list_ports.comports():
        identity = (port.vid, port.pid)
        description = (port.description or '').lower()
        if identity in KNOWN_USB_IDS or any(token in description for token in ('cp210', 'ch340', 'ch341', 'esp32', 'usb serial', 'ftdi')):
            ports.append(port.device)
    return ports


def main() -> int:
    parser = argparse.ArgumentParser(description='Automatically reconnect an ESP32 serial bridge')
    parser.add_argument('--endpoint', default='http://127.0.0.1:8000/api/ingest/http')
    parser.add_argument('--device-key', default='local-device-key')
    parser.add_argument('--device-id', default='ESP32-001')
    parser.add_argument('--baud', type=int, default=115200)
    parser.add_argument('--min-interval', type=float, default=0.25)
    parser.add_argument('--poll-seconds', type=float, default=1.0)
    parser.add_argument('--upload', action='store_true', help='Opt in to Arduino CLI compile/upload on a newly detected port')
    parser.add_argument('--firmware', type=Path, help='Arduino sketch directory or .ino file used with --upload')
    parser.add_argument('--fqbn', default='esp32:esp32:esp32', help='Arduino CLI board identifier used with --upload')
    args = parser.parse_args()
    if args.upload and not args.firmware:
        parser.error('--upload requires --firmware so the target code is explicit')

    bridge = Path(__file__).with_name('serial_bridge.py')
    current_port: str | None = None
    process: subprocess.Popen[str] | None = None
    print('ESP32 auto-bridge watching for USB reconnects. Press Ctrl+C to stop.')
    try:
        while True:
            detected = matching_ports()
            port = current_port if current_port in detected else (detected[0] if detected else None)
            if port and process is None:
                if args.upload:
                    command = ['arduino-cli', 'compile', '--upload', '--fqbn', args.fqbn, '--port', port, str(args.firmware)]
                    print(f'Uploading explicit firmware to {port} using {args.fqbn}...')
                    subprocess.run(command, check=True)
                command = [sys.executable, str(bridge), '--port', port, '--baud', str(args.baud), '--endpoint', args.endpoint, '--device-key', args.device_key, '--device-id', args.device_id, '--min-interval', str(args.min_interval)]
                print(f'ESP32 detected on {port}; starting live bridge.')
                process = subprocess.Popen(command, text=True)
                current_port = port
            if process and process.poll() is not None:
                print(f'Bridge stopped on {current_port}; waiting for reconnect.')
                process = None
                current_port = None
            if current_port and current_port not in detected and process:
                process.terminate()
                process = None
                print(f'{current_port} disconnected; waiting for ESP32 reconnect.')
                current_port = None
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        if process and process.poll() is None:
            process.terminate()
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
