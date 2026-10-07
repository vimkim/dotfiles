#!/usr/bin/env python3
"""Serve an HTML directory and print PC access links until Ctrl+C."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
from pathlib import Path
import subprocess
from urllib.parse import quote


VPN_PREFIXES = ("tailscale", "tun", "tap", "wg", "ppp", "vpn", "zt")
CONTAINER_PREFIXES = (
    "docker", "podman", "veth", "virbr", "br-", "cni", "flannel", "cali", "lxc",
)


def network_addresses(interface=None):
    """Find active IPv4 addresses, preferring VPN interfaces."""
    try:
        result = subprocess.run(
            ["ip", "-j", "address", "show"],
            check=True, capture_output=True, text=True, timeout=5,
        )
        interfaces = json.loads(result.stdout)
    except FileNotFoundError as error:
        raise ValueError("'ip' is required; install the Linux iproute2 tools") from error
    except (subprocess.SubprocessError, json.JSONDecodeError) as error:
        raise ValueError(f"could not read network addresses from 'ip': {error}") from error
    if not isinstance(interfaces, list):
        raise ValueError("'ip' returned an unexpected address list")

    addresses = []
    for entry in interfaces:
        name = entry["ifname"]
        if interface is not None and name != interface:
            continue
        if "UP" not in entry.get("flags", []) or entry.get("operstate") == "DOWN":
            continue
        if "LOOPBACK" in entry.get("flags", []) or name == "lo":
            continue
        if interface is None and name.startswith(CONTAINER_PREFIXES):
            continue
        for info in entry.get("addr_info", []):
            if info.get("family") != "inet" or info.get("scope") != "global":
                continue
            address = ipaddress.IPv4Address(info["local"])
            if (address.is_loopback or address.is_link_local or address.is_unspecified
                    or address.is_multicast):
                continue
            addresses.append({"interface": name, "address": str(address)})

    addresses.sort(key=lambda item: not item["interface"].startswith(VPN_PREFIXES))
    seen = set()
    unique = []
    for item in addresses:
        if item["address"] not in seen:
            unique.append(item)
            seen.add(item["address"])
    if not unique:
        target = f" on interface {interface!r}" if interface else ""
        raise ValueError(f"no active VPN/LAN IPv4 address found{target}")
    return unique


def review_file(directory, filename):
    directory = Path(directory).expanduser().absolute()
    if not directory.is_dir():
        raise ValueError(f"serving directory does not exist: {directory}")
    relative = Path(filename)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("--file must be a relative path inside --directory")
    if relative.suffix.lower() not in (".html", ".htm"):
        raise ValueError("--file must name an .html or .htm file")
    html = directory / relative
    if not html.is_file():
        raise ValueError(f"HTML file does not exist or is not a regular file: {html}")
    with html.open("rb"):
        pass
    return directory, quote(relative.as_posix(), safe="/")


def addresses_for_bind(bind, interface=None):
    if ipaddress.IPv4Address(bind).is_loopback:
        if interface is not None:
            raise ValueError("--interface requires a VPN/LAN bind address")
        return [{"interface": "lo", "address": bind}]
    addresses = network_addresses(interface)
    if bind != "0.0.0.0":
        addresses = [item for item in addresses if item["address"] == bind]
        if not addresses:
            raise ValueError(f"no active address matches --bind {bind}")
    return addresses


def print_links(directory, port, filename, addresses):
    print(f"Serving {directory} on port {port}\n\nThen open from your PC:\n")
    for item in addresses:
        name = item["interface"]
        if name.startswith("tailscale"):
            label = "Tailscale"
        elif name.startswith(VPN_PREFIXES):
            label = "VPN"
        elif name == "lo":
            label = "Local"
        else:
            label = "LAN"
        url = f"http://{item['address']}:{port}/{filename}"
        print(f"- [{label} — {name} ({url})](<{url}>)")
    print("\nPress **Ctrl+C** in the SSH terminal when finished.", flush=True)


def port_number(value):
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("port must be an integer") from error
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 0 and 65535")
    return port


def ipv4_address(value):
    try:
        return str(ipaddress.IPv4Address(value))
    except ipaddress.AddressValueError as error:
        raise argparse.ArgumentTypeError("--bind must be an IPv4 address") from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", type=ipv4_address, default="0.0.0.0",
                        help="IPv4 bind address (default: 0.0.0.0)")
    parser.add_argument("--directory", required=True, help="directory to serve, including adjacent assets")
    parser.add_argument("--file", default="index.html", help="HTML path relative to --directory (default: index.html)")
    parser.add_argument("--port", type=port_number, default=0,
                        help="use a fixed port; 0 chooses a free port automatically (default: 0)")
    parser.add_argument("--interface", help="print links for only this active interface")
    args = parser.parse_args()
    try:
        directory, filename = review_file(args.directory, args.file)
        addresses = addresses_for_bind(args.bind, args.interface)
        handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
        # Port 0 lets the kernel allocate and retain a free port on this server.
        with ThreadingHTTPServer((args.bind, args.port), handler) as server:
            print_links(directory, server.server_port, filename, addresses)
            server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.", flush=True)
    except (ValueError, OSError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
