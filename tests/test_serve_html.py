"""Verify discovery and the foreground CLI's actual HTTP lifecycle."""

from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import ProxyHandler, build_opener


SCRIPT = (Path(__file__).resolve().parents[1] / "private_dot_config/my-scripts/bin"
          / "executable_serve-html.py")
SPEC = importlib.util.spec_from_file_location("serve_html", SCRIPT)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


def interface(name, address, **extra):
    return {"ifname": name, "flags": ["UP"], "operstate": "UP",
            "addr_info": [{"family": "inet", "local": address, "scope": "global"}],
            **extra}


class ServeHTML(unittest.TestCase):
    def addresses(self, entries, selected=None):
        result = subprocess.CompletedProcess([], 0, json.dumps(entries), "")
        with patch.object(helper.subprocess, "run", return_value=result):
            return helper.network_addresses(selected)

    def test_vpn_preferred_and_non_remote_addresses_excluded(self):
        found = self.addresses([
            interface("lo", "127.0.0.1"),
            interface("eno1", "192.168.4.2"),
            interface("docker0", "172.17.0.1"),
            interface("podman0", "10.88.0.1"),
            interface("br-container", "172.18.0.1"),
            interface("eno2", "192.168.5.2", operstate="DOWN"),
            interface("wg0", "10.1.0.2", operstate="UNKNOWN"),
            interface("eno3", "169.254.1.2"),
            interface("eno4", "0.0.0.0"),
        ])
        self.assertEqual(found, [
            {"interface": "wg0", "address": "10.1.0.2"},
            {"interface": "eno1", "address": "192.168.4.2"},
        ])

    def test_interface_selection_and_missing_address(self):
        entries = [interface("eno1", "192.168.4.2"), interface("tailscale0", "100.68.111.110")]
        self.assertEqual(self.addresses(entries, "eno1"),
                         [{"interface": "eno1", "address": "192.168.4.2"}])
        with self.assertRaisesRegex(ValueError, "no active"):
            self.addresses(entries, "missing")
        with self.assertRaisesRegex(ValueError, "no active"):
            self.addresses([interface("lo", "127.0.0.1")])

    def test_duplicate_address_keeps_vpn_interface(self):
        found = self.addresses([interface("eno1", "10.1.0.2"), interface("tun0", "10.1.0.2")])
        self.assertEqual(found, [{"interface": "tun0", "address": "10.1.0.2"}])

    def test_ip_command_failures_are_actionable(self):
        for error in (FileNotFoundError(), subprocess.TimeoutExpired("ip", 5)):
            with self.subTest(error=error), patch.object(helper.subprocess, "run", side_effect=error):
                with self.assertRaisesRegex(ValueError, "ip"):
                    helper.network_addresses()
        with patch.object(helper.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "invalid", "")):
            with self.assertRaisesRegex(ValueError, "could not read"):
                helper.network_addresses()

    def test_specific_bind_only_advertises_matching_addresses(self):
        entries = self.addresses([interface("eno1", "192.168.4.2"), interface("tailscale0", "100.68.111.110")])
        with patch.object(helper, "network_addresses", return_value=entries):
            self.assertEqual(helper.addresses_for_bind("192.168.4.2"),
                             [{"interface": "eno1", "address": "192.168.4.2"}])
            with self.assertRaisesRegex(ValueError, "no active address"):
                helper.addresses_for_bind("192.168.99.99")
        with patch.object(helper, "network_addresses", side_effect=AssertionError("unneeded discovery")):
            self.assertEqual(helper.addresses_for_bind("127.0.0.1"),
                             [{"interface": "lo", "address": "127.0.0.1"}])

    @contextmanager
    def server(self, directory, *args, env=None):
        with tempfile.TemporaryDirectory(prefix="serve-html-output-") as temp:
            output_path = Path(temp) / "stdout"
            error_path = Path(temp) / "stderr"
            with output_path.open("w") as stdout, error_path.open("w") as stderr:
                process = subprocess.Popen(
                    [sys.executable, str(SCRIPT), "--directory", str(directory), *args],
                    env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                )
                try:
                    deadline = time.monotonic() + 5
                    while "Ctrl+C" not in (output := output_path.read_text()):
                        if process.poll() is not None or time.monotonic() >= deadline:
                            self.fail(f"server did not start: {error_path.read_text()}")
                        time.sleep(0.02)
                    urls = re.findall(r"\]\(<(http://[^>]+)>\)", output)
                    self.assertTrue(urls, output)
                    yield process, urls, output
                finally:
                    if process.poll() is None:
                        process.send_signal(signal.SIGINT)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                        raise

    def test_default_cli_serves_encoded_html_and_adjacent_assets(self):
        with tempfile.TemporaryDirectory(prefix="serve-html-test-") as temp:
            directory = Path(temp) / "review's $(touch SHOULD_NOT_EXIST) files"
            directory.mkdir()
            html = directory / "한글 review #1's ?.html"
            content = b'<html><link rel="stylesheet" href="style.css">Review</html>'
            html.write_bytes(content)
            (directory / "style.css").write_bytes(b"body { color: navy; }")
            (directory.parent / "outside.txt").write_text("outside serving directory")
            fake_bin = Path(temp) / "bin"
            fake_bin.mkdir()
            fake_ip = fake_bin / "ip"
            fixture = json.dumps([interface("eno1", "192.168.4.2"), interface("tailscale0", "100.68.111.110")])
            fake_ip.write_text(f"#!{sys.executable}\nprint({fixture!r})\n")
            fake_ip.chmod(0o755)
            env = {**os.environ, "PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", "")}
            with self.server(directory, "--file", html.name, env=env) as (process, urls, output):
                parsed = [urlsplit(url) for url in urls]
                port = parsed[0].port
                self.assertEqual([item.hostname for item in parsed], ["100.68.111.110", "192.168.4.2"])
                self.assertEqual([item.port for item in parsed], [port, port])
                self.assertEqual(parsed[0].path, "/" + quote(html.name, safe=""))
                self.assertIn("Tailscale — tailscale0", output)
                self.assertIn("LAN — eno1", output)
                with socket.socket() as probe:
                    with self.assertRaises(OSError):
                        probe.bind(("0.0.0.0", port))
                client = build_opener(ProxyHandler({}))
                with client.open(f"http://127.0.0.1:{port}{parsed[0].path}", timeout=2) as response:
                    self.assertEqual(response.read(), content)
                with client.open(f"http://127.0.0.1:{port}/style.css", timeout=2) as response:
                    self.assertEqual(response.read(), b"body { color: navy; }")
                with self.assertRaises(HTTPError) as error:
                    client.open(f"http://127.0.0.1:{port}/../outside.txt", timeout=2)
                self.assertEqual(error.exception.code, 404)
                error.exception.close()
                process.send_signal(signal.SIGINT)
                self.assertEqual(process.wait(timeout=5), 0)
                with self.assertRaises(OSError):
                    socket.create_connection(("127.0.0.1", port), timeout=1)
                self.assertFalse((Path(temp) / "SHOULD_NOT_EXIST").exists())

    def test_concurrent_servers_keep_distinct_free_ports(self):
        with tempfile.TemporaryDirectory(prefix="serve-html-test-") as temp:
            (Path(temp) / "index.html").write_text("index")
            with self.server(temp, "--bind", "127.0.0.1") as (_, first, _):
                with self.server(temp, "--bind", "127.0.0.1") as (_, second, _):
                    self.assertNotEqual(urlsplit(first[0]).port, urlsplit(second[0]).port)
                    for url in (first[0], second[0]):
                        with build_opener(ProxyHandler({})).open(url, timeout=2) as response:
                            self.assertEqual(response.read(), b"index")

    def test_occupied_explicit_port_fails_without_advertising_links(self):
        with tempfile.TemporaryDirectory(prefix="serve-html-test-") as temp:
            (Path(temp) / "index.html").write_text("index")
            with socket.socket() as busy:
                busy.bind(("127.0.0.1", 0))
                busy.listen()
                run = subprocess.run(
                    [sys.executable, str(SCRIPT), "--directory", temp,
                     "--bind", "127.0.0.1", "--port", str(busy.getsockname()[1])],
                    text=True, capture_output=True, timeout=5,
                )
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(run.stdout, "")
            self.assertIn("error:", run.stderr)

    def test_invalid_paths_and_arguments_fail_without_advertising_links(self):
        with tempfile.TemporaryDirectory(prefix="serve-html-test-") as temp:
            (Path(temp) / "index.html").write_text("index")
            for args in (["--directory", "/nonexistent"],
                         ["--directory", temp, "--file", "missing.html"],
                         ["--directory", temp, "--file", "../outside.html"],
                         ["--directory", temp, "--file", "/tmp/page.html"],
                         ["--directory", temp, "--file", "file.txt"],
                         ["--directory", temp, "--port", "-1"],
                         ["--directory", temp, "--port", "65536"],
                         ["--directory", temp, "--bind", "::1"]):
                with self.subTest(args=args):
                    run = subprocess.run([sys.executable, str(SCRIPT), *args],
                                         text=True, capture_output=True, timeout=5)
                    self.assertNotEqual(run.returncode, 0)
                    self.assertEqual(run.stdout, "")
                    self.assertIn("error:", run.stderr)


if __name__ == "__main__":
    unittest.main()
