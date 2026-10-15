#!/usr/bin/env python3
"""Serve a directory with Markdown previews and print PC access links until Ctrl+C."""

import argparse
import errno
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import parse_qs, quote, unquote, urlsplit


VPN_PREFIXES = ("tailscale", "tun", "tap", "wg", "ppp", "vpn", "zt")
CONTAINER_PREFIXES = (
    "docker", "podman", "veth", "virbr", "br-", "cni", "flannel", "cali", "lxc",
)
REPEATED_PORTS = (7777, 8888, 9999, 5555, 4444, 3333, 2222, 1111)
# Four-digit entries from https://fetch.spec.whatwg.org/#port-blocking.
BLOCKED_HTTP_PORTS = frozenset({
    1719, 1720, 1723, 2049, 3659, 4045, 4190, 5060, 5061, 6000, 6566,
    6665, 6666, 6667, 6668, 6669, 6679, 6697,
})
MARKDOWN_SUFFIXES = (".md", ".markdown")
PREVIEW_PREFIX = "/__serve_html__/"
PREVIEW_ASSETS = Path(__file__).resolve().parent.parent / "share" / "serve-html"


class PreviewHTTPRequestHandler(SimpleHTTPRequestHandler):
    """List directories and render Markdown at its original URL."""

    def __init__(self, *args, verbose=False, **kwargs):
        self.verbose = verbose
        super().__init__(*args, **kwargs)

    def log_request(self, code="-", size="-"):
        if self.verbose:
            super().log_request(code, size)

    def preview_file(self, path, content_type=None):
        """Share response headers and file opening between GET and HEAD."""
        try:
            stream = path.open("rb")
        except OSError:
            self.send_error(404, "File not found")
            return None
        try:
            self.send_response(200)
            self.send_header("Content-Type", content_type or self.guess_type(str(path)))
            self.send_header("Content-Length", str(os.fstat(stream.fileno()).st_size))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            return stream
        except BaseException:
            stream.close()
            raise

    def send_head(self):
        request = urlsplit(self.path)
        if request.path.startswith(PREVIEW_PREFIX):
            relative = Path(unquote(request.path[len(PREVIEW_PREFIX):]))
            assets = PREVIEW_ASSETS.resolve()
            path = (assets / relative).resolve()
            if (relative.is_absolute() or ".." in relative.parts
                    or not path.is_relative_to(assets) or not path.is_file()):
                self.send_error(404, "Preview asset not found")
                return None
            return self.preview_file(path)

        path = Path(self.translate_path(self.path))
        if path.is_dir():
            if not request.path.endswith(("/", "%2f", "%2F")):
                self.send_response(301)
                self.send_header("Location", request._replace(path=request.path + "/").geturl())
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None
            # Bypass SimpleHTTPRequestHandler's implicit index.html/index.htm lookup.
            return self.list_directory(str(path))
        if (not request.path.endswith("/") and path.suffix.lower() in MARKDOWN_SUFFIXES
                and path.is_file()):
            if parse_qs(request.query).get("raw") == ["1"]:
                return self.preview_file(path, "text/plain; charset=utf-8")
            # Check readability before returning a viewer for an unreadable document.
            try:
                with path.open("rb"):
                    pass
            except OSError:
                self.send_error(404, "File not found")
                return None
            if not (PREVIEW_ASSETS / "viewer.html").is_file():
                self.send_error(500, "Markdown preview assets are missing; reinstall serve-html assets")
                return None
            return self.preview_file(PREVIEW_ASSETS / "viewer.html", "text/html; charset=utf-8")
        return super().send_head()


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
    if filename is None:
        return directory, ""
    relative = Path(filename)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("--file must be a relative path inside --directory")
    document = directory / relative
    if not document.is_file():
        raise ValueError(f"file does not exist or is not a regular file: {document}")
    with document.open("rb"):
        pass
    return directory, quote(relative.as_posix(), safe="/")


def serving_target(path=None, directory=None, filename=None):
    """Resolve a positional file/directory or an explicit root and relative file."""
    if path is not None:
        if directory is not None:
            raise ValueError("PATH and --directory/-d cannot be used together; choose one serving root")
        target = Path(path).expanduser().absolute()
        if target.is_dir():
            directory = target
        elif target.is_file():
            if filename is not None:
                raise ValueError("a positional file and --file/-f cannot be used together; choose one file")
            directory, filename = target.parent, target.name
        else:
            raise ValueError(f"path does not exist or is not a regular file or directory: {target}")
    return review_file(directory if directory is not None else ".", filename)


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
        print(f"- {url} — {label}")
    print("\nPress **Ctrl+C** in the SSH terminal when finished.", flush=True)


def port_preference(port):
    """Rank four-digit ports by patterns that are easy to remember and type."""
    a, b, c, d = map(int, str(port))
    if port in REPEATED_PORTS:
        return 0, REPEATED_PORTS.index(port)
    if a == b and c == d and abs(a - c) == 1:  # 2233, 3322
        return 1, port
    if (a == b == c or b == c == d) and abs(a - d) == 1:  # 2223, 2333
        return 2, port
    if b - a == c - b == d - c and abs(b - a) == 1:  # 5678, 8765
        return 3, port
    if a == b and c == d:  # 2255, 5577
        return 4, port
    if a == c and b == d:  # 1212, 8080
        return 5, port
    if a == d and b == c:  # 1221, 8008
        return 6, port
    if port % 1000 == 0:  # 7000, 8000
        return 7, port
    if port % 100 == 0:  # 2500, 8100
        return 8, port
    return 9, port


def preferred_ports():
    """Try memorable patterns, then the remaining unprivileged four-digit ports."""
    return sorted((port for port in range(1024, 10000)
                   if port not in BLOCKED_HTTP_PORTS), key=port_preference)


def create_server(bind, port, handler):
    """Reserve a requested port or the first available preferred port."""
    if port:
        return ThreadingHTTPServer((bind, port), handler)
    for candidate in preferred_ports():
        try:
            # Bind the actual server; retain its socket instead of probing ports.
            return ThreadingHTTPServer((bind, candidate), handler)
        except OSError as error:
            if error.errno not in (errno.EADDRINUSE, errno.EACCES):
                raise
    # Exhausted four-digit choices: let the kernel reserve an available port.
    return ThreadingHTTPServer((bind, 0), handler)


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
    parser.add_argument("path", nargs="?", metavar="PATH",
                        help="directory to list or file to link to (serves its parent); default: current directory")
    parser.add_argument("--bind", type=ipv4_address, default="0.0.0.0",
                        help="IPv4 bind address (default: 0.0.0.0)")
    parser.add_argument("-d", "--directory",
                        help="directory to serve instead of PATH (default: current directory)")
    parser.add_argument("-f", "--file",
                        help="file relative to the serving directory; may accompany a directory PATH (default: listing)")
    parser.add_argument("--port", type=port_number, default=0,
                        help="use a fixed port; 0 prefers memorable four-digit ports (default: 0)")
    parser.add_argument("--interface", help="print links for only this active interface")
    parser.add_argument("--verbose", action="store_true",
                        help="print HTTP request logs (disabled by default)")
    args = parser.parse_args()
    try:
        directory, filename = serving_target(args.path, args.directory, args.file)
        addresses = addresses_for_bind(args.bind, args.interface)
        handler = partial(PreviewHTTPRequestHandler, directory=str(directory), verbose=args.verbose)
        with create_server(args.bind, args.port, handler) as server:
            print_links(directory, server.server_port, filename, addresses)
            server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.", flush=True)
    except (ValueError, OSError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
