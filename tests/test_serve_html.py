"""Verify discovery and the foreground CLI's actual HTTP lifecycle."""

from contextlib import contextmanager
from datetime import datetime, timezone
import errno
from html import unescape
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import call, patch
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import ProxyHandler, Request, build_opener


SCRIPT = (Path(__file__).resolve().parents[1] / "private_dot_config/my-scripts/bin"
          / "executable_serve-html.py")
WRAPPER = SCRIPT.with_name("executable_html-serve")
ASSETS = SCRIPT.parent.parent / "share" / "serve-html"
SPEC = importlib.util.spec_from_file_location("serve_html", SCRIPT)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


def interface(name, address, **extra):
    return {"ifname": name, "flags": ["UP"], "operstate": "UP",
            "addr_info": [{"family": "inet", "local": address, "scope": "global"}],
            **extra}


class ServeHTML(unittest.TestCase):
    def listing_links(self, body):
        return [(unescape(href), unescape(label)) for href, label in re.findall(
            r'<tr><td><a href="([^"]+)">([^<]*)</a>', body,
        )]

    def test_directory_sorting_dates_navigation_and_special_filenames(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            names = ['-', '.hidden', 'Alpha.md', 'alpha.md', 'report10.md', 'report2.md',
                     '한글 <tag> & "quote"\n.md']
            for index, name in enumerate(names):
                (root / name).write_text(name)
                os.utime(root / name, ns=(1_700_000_000_000_000_000 + index,) * 2)
            (root / 'nested').mkdir()
            os.utime(root / 'nested', ns=(1_600_000_000_000_000_000,) * 2)
            (root / 'broken').symlink_to('missing')
            client = build_opener(ProxyHandler({}))
            with self.server(root, '--bind', '127.0.0.1') as (_, urls, _):
                for query in ('', '?sort=modified', '?sort=garbage', '?sort=',
                              '?sort=title&sort=', '?sort=title&sort=title'):
                    with self.subTest(query=query), client.open(urls[0] + query) as response:
                        body = response.read().decode()
                    labels = [label for _, label in self.listing_links(body)]
                    self.assertEqual(labels, list(reversed(names)) + ['nested/', 'broken@'])
                    self.assertIn('<th scope="col">Created</th>', body)
                    self.assertIn('aria-sort="descending"', body)
                    self.assertIn('<time datetime=', body)
                    self.assertIn('Unavailable', body)
                    self.assertNotIn('<tag>', body)
                    self.assertNotIn('href="../', body)
                with client.open(urls[0] + '?sort=title') as response:
                    body = response.read().decode()
                labels = [label for _, label in self.listing_links(body)]
                expected = sorted(names + ['nested', 'broken'], key=lambda name: (name.casefold(), name))
                self.assertEqual(labels, [name + ('/' if name == 'nested' else '@' if name == 'broken' else '') for name in expected])
                self.assertIn('aria-sort="ascending"', body)
                self.assertIn(('nested/?sort=title', 'nested/'), self.listing_links(body))
                for name in names:
                    self.assertIn((quote(name, safe=''), name), self.listing_links(body))
                with client.open(urls[0] + 'nested?sort=title') as response:
                    self.assertTrue(response.url.endswith('/nested/?sort=title'))
                    self.assertEqual(self.listing_links(response.read().decode()), [('../?sort=title', '../')])

    def test_directory_metadata_follows_links_without_ctime_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'target').write_text('body')
            os.utime(root / 'target', ns=(123_456_789,) * 2)
            (root / 'link').symlink_to('target')
            (root / 'broken').symlink_to('absent')
            with patch.object(helper, 'birth_times', return_value={}):
                rows = {entry.name: entry for entry in helper.directory_entries(root)}
            self.assertEqual(rows['link'].modified_ns, rows['target'].modified_ns)
            self.assertTrue(rows['link'].is_symlink)
            self.assertIsNone(rows['broken'].modified_ns)
            self.assertIsNone(rows['link'].created)
            self.assertIsNone(rows['target'].created)
            rendered = helper.render_directory(list(rows.values()), '/', 'modified').decode()
            self.assertEqual([label for _, label in self.listing_links(rendered)], ['link@', 'target', 'broken@'])

    def test_native_birth_dates_accept_epoch_zero_and_negative_times(self):
        for born in (0, -1):
            metadata = SimpleNamespace(st_mode=0o100644, st_mtime_ns=42, st_birthtime=born)
            child = SimpleNamespace(name='native', is_symlink=lambda: False, stat=lambda: metadata)
            with patch.object(helper.os, 'scandir') as scan, patch.object(helper, 'birth_times') as fallback:
                scan.return_value.__enter__.return_value = iter([child])
                rows = helper.directory_entries('.')
            self.assertEqual(rows[0].created, datetime.fromtimestamp(born, timezone.utc))
            fallback.assert_not_called()

    def test_birth_dates_keep_partial_records_by_name_and_parse_epoch_zero(self):
        output = (b'./quote\nname\0' b'1970-01-01 00:00:00.123456789 +0000\0'
                  b'./-\0' b'1970-01-01 00:00:00.000000000 +0000\0'
                  b'./unknown\0-\0./bad\0not a date\0./truncated\0')
        diagnostics = []
        result = subprocess.CompletedProcess([], 1, output, b'one file disappeared')
        names = ['unknown', '-', 'quote\nname', 'bad', 'missing']
        with patch.object(helper.subprocess, 'run', return_value=result) as run:
            found = helper.birth_times('.', names, diagnostics.append)
        self.assertEqual(set(found), {'-', 'quote\nname'})
        self.assertEqual(found['-'].timestamp(), 0)
        self.assertEqual(found['quote\nname'].microsecond, 123456)
        self.assertEqual(run.call_args.args[0][-len(names):], ['./' + name for name in names])
        self.assertEqual(run.call_args.kwargs['env']['TZ'], 'UTC0')
        self.assertTrue(diagnostics)

    def test_birth_lookup_failure_does_not_repeat_for_every_batch(self):
        for error in (FileNotFoundError(), subprocess.TimeoutExpired('stat', 2)):
            with self.subTest(error=error), patch.object(helper.subprocess, 'run', side_effect=error) as run:
                self.assertEqual(helper.birth_times('.', [str(i) for i in range(300)]), {})
                self.assertEqual(run.call_count, 1)

    def test_birth_lookup_bounds_batches_and_splits_e2big(self):
        empty = subprocess.CompletedProcess([], 0, b'', b'')
        names = [f'{i:03d}' + 'x' * 252 for i in range(300)]
        with patch.object(helper.subprocess, 'run', return_value=empty) as run:
            helper.birth_times('.', names)
        self.assertGreater(run.call_count, 1)
        for invocation in run.call_args_list:
            operands = invocation.args[0][4:]
            self.assertLessEqual(len(operands), 128)
            self.assertLessEqual(sum(len(os.fsencode(name)) + 1 for name in operands), 32768)
        first = subprocess.CompletedProcess([], 0, b'./a\0' b'1970-01-01 00:00:00 +0000\0', b'')
        second = subprocess.CompletedProcess([], 0, b'./b\0' b'1970-01-02 00:00:00 +0000\0', b'')
        with patch.object(helper.subprocess, 'run', side_effect=[OSError(errno.E2BIG, 'too large'), first, second]):
            self.assertEqual(set(helper.birth_times('.', ['a', 'b'])), {'a', 'b'})

    def test_birth_lookup_deadline_preserves_completed_batches(self):
        result = subprocess.CompletedProcess([], 0, b'./0\0' b'1970-01-01 00:00:00 +0000\0', b'')
        with patch.object(helper.time, 'monotonic', side_effect=[0, 0.1, 1.9, 2.1]), \
                patch.object(helper.subprocess, 'run', return_value=result) as run:
            found = helper.birth_times('.', [str(i) for i in range(300)])
        self.assertEqual(set(found), {'0'})
        self.assertEqual(run.call_count, 2)
        self.assertAlmostEqual(run.call_args_list[1].kwargs['timeout'], 0.1)

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

    def test_preferred_ports_follow_memorable_patterns_without_blocked_ports(self):
        ports = helper.preferred_ports()
        self.assertEqual(ports[0], 7777)
        self.assertEqual(len(ports), len(set(ports)))
        self.assertTrue(all(1024 <= port <= 9999 for port in ports))
        examples = [7777, 8888, 1111, 2233, 2223, 5678, 2255,
                    8080, 1221, 7000, 2500, 4329]
        positions = [ports.index(port) for port in examples]
        self.assertEqual(positions, sorted(positions))
        for port in (4190, 6000, 6566, 6665, 6666, 6667, 6668, 6669, 6679, 6697):
            self.assertNotIn(port, ports)

    def test_auto_port_skips_busy_or_permission_denied_candidates(self):
        handler = helper.PreviewHTTPRequestHandler
        selected = object()
        for code in (errno.EADDRINUSE, errno.EACCES):
            with self.subTest(errno=code):
                with patch.object(helper, "preferred_ports", return_value=[7777, 8888]), \
                        patch.object(helper, "ThreadingHTTPServer", side_effect=[
                            OSError(code, "unavailable"), selected]) as constructor:
                    self.assertIs(helper.create_server("127.0.0.1", 0, handler), selected)
                    self.assertEqual(constructor.call_args_list, [
                        call(("127.0.0.1", 7777), handler),
                        call(("127.0.0.1", 8888), handler),
                    ])

    def test_auto_port_fallback_retains_a_reserved_socket(self):
        handler = helper.PreviewHTTPRequestHandler
        # Simulate unavailable preferred choices without occupying real services.
        constructor = helper.ThreadingHTTPServer

        def unavailable_preferred(address, selected_handler):
            if address[1] != 0:
                raise OSError(errno.EADDRINUSE, "occupied")
            return constructor(address, selected_handler)

        with patch.object(helper, "preferred_ports", return_value=[7777, 8888]), \
                patch.object(helper, "ThreadingHTTPServer", side_effect=unavailable_preferred) as attempted:
            with helper.create_server("127.0.0.1", 0, handler) as server:
                self.assertGreater(server.server_port, 0)
                self.assertEqual(attempted.call_args_list, [
                    call(("127.0.0.1", 7777), handler),
                    call(("127.0.0.1", 8888), handler),
                    call(("127.0.0.1", 0), handler),
                ])
                with socket.socket() as probe:
                    with self.assertRaises(OSError):
                        probe.bind(("127.0.0.1", server.server_port))

    def test_auto_port_reports_unrelated_bind_errors_without_retrying(self):
        handler = helper.PreviewHTTPRequestHandler
        error = OSError(errno.EADDRNOTAVAIL, "bind address unavailable")
        with patch.object(helper, "ThreadingHTTPServer", side_effect=error) as constructor:
            with self.assertRaises(OSError) as caught:
                helper.create_server("192.0.2.1", 0, handler)
            self.assertIs(caught.exception, error)
            constructor.assert_called_once_with(("192.0.2.1", 7777), handler)

    @contextmanager
    def server(self, directory, *args, env=None, command=None):
        if command is None:
            command = [sys.executable, str(SCRIPT), "--directory", str(directory)]
        with tempfile.TemporaryDirectory(prefix="serve-html-output-") as temp:
            output_path = Path(temp) / "stdout"
            error_path = Path(temp) / "stderr"
            with output_path.open("w") as stdout, error_path.open("w") as stderr:
                process = subprocess.Popen(
                    [*command, *args], cwd=directory, env=env,
                    stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                )
                try:
                    deadline = time.monotonic() + 5
                    while "Ctrl+C" not in (output := output_path.read_text()):
                        if process.poll() is not None or time.monotonic() >= deadline:
                            self.fail(f"server did not start: {error_path.read_text()}")
                        time.sleep(0.02)
                    urls = re.findall(r"^- (http://\S+) — ", output, re.MULTILINE)
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
                self.assertEqual(
                    [line for line in output.splitlines() if line.startswith("- ")],
                    [f"- {url} — {label}"
                     for url, label in zip(urls, ("Tailscale", "LAN"))],
                )
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

    def test_directories_list_index_pages_until_explicitly_requested(self):
        with tempfile.TemporaryDirectory(prefix="serve-html-test-") as temp:
            directory = Path(temp)
            nested = directory / "nested directory"
            nested.mkdir()
            for folder in (directory, nested):
                (folder / "index.html").write_bytes(b"<h1>Chosen index.html</h1>")
                (folder / "index.htm").write_bytes(b"<h1>Chosen index.htm</h1>")
            client = build_opener(ProxyHandler({}))
            with self.server(directory, "--bind", "127.0.0.1") as (_, urls, _):
                root = urls[0]
                for path in ("", "nested%20directory/", "nested%20directory?sort=name"):
                    with self.subTest(path=path):
                        with client.open(root + path, timeout=2) as response:
                            listing = response.read()
                            self.assertIn(b"Directory listing for", listing)
                            self.assertIn(b'href="index.html"', listing)
                            self.assertIn(b'href="index.htm"', listing)
                            self.assertNotIn(b"<h1>Chosen", listing)
                            listing_url = response.url
                            redirected = urlsplit(listing_url)
                            self.assertTrue(redirected.path.endswith("/"))
                            self.assertEqual(redirected.query, urlsplit(path).query)
                        with client.open(Request(listing_url, method="HEAD"), timeout=2) as response:
                            self.assertEqual(int(response.headers["Content-Length"]), len(listing))
                            self.assertEqual(response.read(), b"")
                for prefix in ("", "nested%20directory/"):
                    for name in ("index.html", "index.htm"):
                        with client.open(root + prefix + name, timeout=2) as response:
                            self.assertEqual(response.read(), f"<h1>Chosen {name}</h1>".encode())
                # index.htm must not become an implicit page when index.html is absent.
                (nested / "index.html").unlink()
                with client.open(root + "nested%20directory/", timeout=2) as response:
                    self.assertIn(b'href="index.htm"', response.read())

    def test_wrapper_serves_current_directory_and_forwards_options(self):
        with tempfile.TemporaryDirectory(prefix="html-serve-test-") as temp:
            home = Path(temp) / "test home's config"
            scripts = home / ".config/my-scripts/bin"
            scripts.mkdir(parents=True)
            (scripts / "serve-html.py").write_bytes(SCRIPT.read_bytes())
            shutil.copytree(ASSETS, scripts.parent / "share" / "serve-html")
            wrapper = scripts / "html-serve"
            wrapper.write_bytes(WRAPPER.read_bytes())
            wrapper.chmod(0o755)

            directory = Path(temp) / "current directory"
            directory.mkdir()
            (directory / "notes.txt").write_text("notes")
            (directory / "notes.md").write_text("# Preview from the wrapper")
            (directory / "index.html").write_text("explicit index page")
            other = home / "another output directory"
            other.mkdir()
            html = other / "한글 review #1's ?.html"
            html.write_text("forwarded options")

            fake_ip = scripts / "ip"
            fixture = json.dumps([interface("tailscale0", "100.68.111.110")])
            fake_ip.write_text(f"#!{sys.executable}\nprint({fixture!r})\n")
            fake_ip.chmod(0o755)
            env = {**os.environ, "HOME": str(home),
                   "PATH": str(scripts) + os.pathsep + os.environ.get("PATH", "")}

            cases = [
                ([], "/", b"notes.txt"),
                (["."], "/", b"notes.txt"),
                ([str(other)], "/", html.name.encode()),
                ([os.path.relpath(other, directory)], "/", html.name.encode()),
                (["~/another output directory"], "/", html.name.encode()),
                (["notes.md"], "/notes.md", b"Markdown preview"),
                ([str(html)], "/" + quote(html.name, safe=""), b"forwarded options"),
                ([os.path.relpath(html, directory)],
                 "/" + quote(html.name, safe=""), b"forwarded options"),
                (["-d", str(other)], "/", html.name.encode()),
                ([str(other), "-f", html.name],
                 "/" + quote(html.name, safe=""), b"forwarded options"),
                (["-d", str(other), "-f", html.name],
                 "/" + quote(html.name, safe=""), b"forwarded options"),
                (["-f", "notes.txt"], "/notes.txt", b"notes"),
                (["index.html"], "/index.html", b"explicit index page"),
                (["--file", "notes.md", "--bind", "127.0.0.1"],
                 "/notes.md", b"Markdown preview"),
                (["--directory", str(other), "--file", html.name,
                  "--bind", "127.0.0.1", "--port", "0"],
                 "/" + quote(html.name, safe=""), b"forwarded options"),
            ]
            for args, expected_path, content in cases:
                with self.subTest(args=args):
                    with self.server(directory, *args, env=env,
                                     command=[str(wrapper)]) as (process, urls, output):
                        parsed = urlsplit(urls[0])
                        self.assertEqual(parsed.path, expected_path)
                        client = build_opener(ProxyHandler({}))
                        url = f"http://127.0.0.1:{parsed.port}{parsed.path}"
                        with client.open(url, timeout=2) as response:
                            self.assertIn(content, response.read())
                        process.send_signal(signal.SIGINT)
                        self.assertEqual(process.wait(timeout=5), 0)

    def test_python_cli_defaults_and_positional_files(self):
        with tempfile.TemporaryDirectory(prefix="serve-html-test-") as temp:
            directory = Path(temp)
            nested = directory / "nested"
            nested.mkdir()
            (nested / "page.html").write_text("chosen page")
            (nested / "style.css").write_text("adjacent asset")
            client = build_opener(ProxyHandler({}))
            for args, expected_path, content in (
                ([], "/", b"nested/"),
                (["nested"], "/", b"page.html"),
                (["nested/page.html"], "/page.html", b"chosen page"),
                (["-d", ".", "-f", "nested/page.html"], "/nested/page.html", b"chosen page"),
                (["nested/style.css"], "/style.css", b"adjacent asset"),
            ):
                with self.subTest(args=args), self.server(
                    directory, "--bind", "127.0.0.1", *args,
                    command=[sys.executable, str(SCRIPT)],
                ) as (_, urls, output):
                    parsed = urlsplit(urls[0])
                    self.assertEqual(parsed.path, expected_path)
                    with client.open(urls[0], timeout=2) as response:
                        self.assertIn(content, response.read())
                    if expected_path == "/page.html":
                        self.assertIn(f"Serving {nested} on port", output)
                        with client.open(urls[0].replace("page.html", "style.css"), timeout=2) as response:
                            self.assertEqual(response.read(), b"adjacent asset")

    @unittest.skipUnless(shutil.which("git"), "Git is unavailable")
    def test_positional_file_serves_git_root_from_another_directory(self):
        with tempfile.TemporaryDirectory(prefix="serve-html-git-test-") as temp:
            directory = Path(temp) / "repository with spaces"
            directory.mkdir()
            subprocess.run(["git", "init", "--quiet", str(directory)], check=True)
            nested = directory / "docs/nested folder"
            nested.mkdir(parents=True)
            document = nested / "한글 review #1's ?.md"
            markdown = "# Review\n\n![Diagram](../../assets/drawing.svg)\n"
            document.write_text(markdown)
            (directory / "assets").mkdir()
            drawing = b'<svg xmlns="http://www.w3.org/2000/svg"/>'
            (directory / "assets/drawing.svg").write_bytes(drawing)
            client = build_opener(ProxyHandler({}))
            for path in (str(document), os.path.relpath(document, temp),
                         str(nested / ".." / nested.name / document.name)):
                with self.subTest(path=path), self.server(
                    temp, path, "--bind", "127.0.0.1",
                    command=[sys.executable, str(SCRIPT)],
                ) as (_, urls, output):
                    expected_path = "/" + quote(document.relative_to(directory).as_posix(), safe="/")
                    self.assertEqual(urlsplit(urls[0]).path, expected_path)
                    self.assertIn(f"Serving {directory} on port", output)
                    with client.open(urls[0], timeout=2) as response:
                        self.assertIn(b"Markdown preview", response.read())
                    with client.open(urls[0] + "?raw=1", timeout=2) as response:
                        self.assertEqual(response.read().decode(), markdown)
                    origin = urls[0].removesuffix(expected_path)
                    with client.open(origin + "/assets/drawing.svg", timeout=2) as response:
                        self.assertEqual(response.read(), drawing)
                    with client.open(origin + "/", timeout=2) as response:
                        self.assertIn(('docs/?sort=modified', 'docs/'),
                                      self.listing_links(response.read().decode()))

            # Explicit roots and --file retain their requested directory inside Git.
            for args in ([str(nested), "-f", document.name],
                         ["-d", str(nested), "-f", document.name],
                         ["-f", document.name]):
                with self.subTest(args=args), self.server(
                    nested, *args, "--bind", "127.0.0.1",
                    command=[sys.executable, str(SCRIPT)],
                ) as (_, urls, output):
                    self.assertEqual(urlsplit(urls[0]).path, "/" + quote(document.name, safe=""))
                    self.assertIn(f"Serving {nested} on port", output)
                    with client.open(urls[0] + "?raw=1", timeout=2) as response:
                        self.assertEqual(response.read().decode(), markdown)

    @unittest.skipUnless(shutil.which("git"), "Git is unavailable")
    def test_nested_repositories_and_worktrees_use_their_own_roots(self):
        with tempfile.TemporaryDirectory(prefix="serve-html-git-test-") as temp:
            repository = Path(temp) / "repository"
            repository.mkdir()
            subprocess.run(["git", "init", "--quiet", str(repository)], check=True)
            nested = repository / "nested repository"
            nested.mkdir()
            subprocess.run(["git", "init", "--quiet", str(nested)], check=True)
            subprocess.run(
                ["git", "-C", str(repository), "-c", "user.name=Serve HTML test",
                 "-c", "user.email=serve-html@example.invalid", "-c", "commit.gpgsign=false",
                 "-c", "core.hooksPath=/dev/null", "commit", "--quiet", "--allow-empty", "-m", "fixture"],
                check=True, capture_output=True, text=True,
            )
            worktree = Path(temp) / "linked worktree"
            subprocess.run(
                ["git", "-C", str(repository), "worktree", "add", "--quiet", "--detach", str(worktree)],
                check=True, capture_output=True, text=True,
            )
            self.assertTrue((worktree / ".git").is_file())
            for root in (nested, worktree):
                with self.subTest(root=root):
                    document = root / "docs/review.md"
                    document.parent.mkdir()
                    document.write_text("# Review")
                    self.assertEqual(helper.serving_target(document), (root, "docs/review.md"))

    @unittest.skipUnless(shutil.which("git"), "Git is unavailable")
    def test_git_file_paths_preserve_file_symlinks_and_resolve_directory_aliases(self):
        with tempfile.TemporaryDirectory(prefix="serve-html-git-test-") as temp:
            repository = Path(temp) / "repository"
            repository.mkdir()
            subprocess.run(["git", "init", "--quiet", str(repository)], check=True)
            nested = repository / "docs"
            nested.mkdir()
            document = nested / "review.md"
            document.write_text("# Review")
            alias = Path(temp) / "directory alias"
            alias.symlink_to(nested, target_is_directory=True)
            self.assertEqual(helper.serving_target(alias / document.name), (repository, "docs/review.md"))
            outside = Path(temp) / "outside.md"
            outside.write_text("# Linked document")
            linked_document = nested / "linked.md"
            linked_document.symlink_to(outside)
            self.assertEqual(helper.serving_target(linked_document), (repository, "docs/linked.md"))

    def test_git_discovery_failures_fall_back_to_the_file_parent(self):
        with tempfile.TemporaryDirectory(prefix="serve-html-git-test-") as temp:
            directory = Path(temp) / "nested"
            directory.mkdir()
            document = directory / "review #1.md"
            document.write_text("# Review")
            for error in (FileNotFoundError(), PermissionError(),
                          subprocess.CalledProcessError(128, "git"),
                          subprocess.TimeoutExpired("git", 5)):
                with self.subTest(error=error), patch.object(helper.subprocess, "run", side_effect=error):
                    self.assertEqual(helper.serving_target(document),
                                     (directory, quote(document.name, safe="")))

    def test_markdown_urls_render_by_default_with_raw_and_head_support(self):
        with tempfile.TemporaryDirectory(prefix="serve-markdown-test-") as temp:
            directory = Path(temp)
            nested = directory / "nested"
            nested.mkdir()
            name = "한글 notes #1's ?.MD"
            markdown = "# Hello\n\n![SVG](drawing.svg)\n"
            (nested / name).write_text(markdown)
            (directory / "other.markdown").write_text("# Another document")
            (nested / "drawing.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
            client = build_opener(ProxyHandler({}))
            for options in ([], ["--verbose"]):
                with self.subTest(options=options), self.server(
                    directory, "--bind", "127.0.0.1", *options,
                ) as (_, urls, _):
                    root = urls[0]
                    url = root + "nested/" + quote(name, safe="")
                    with client.open(root + "nested/", timeout=2) as response:
                        self.assertIn(quote(name).encode(), response.read())
                    with client.open(url + "?other=1", timeout=2) as response:
                        self.assertEqual(response.headers.get_content_type(), "text/html")
                        viewer = response.read()
                        self.assertIn(b"/__serve_html__/viewer.js", viewer)
                    with client.open(Request(url, method="HEAD"), timeout=2) as response:
                        self.assertEqual(response.headers.get_content_type(), "text/html")
                        self.assertEqual(int(response.headers["Content-Length"]), len(viewer))
                        self.assertEqual(response.read(), b"")
                    with client.open(url + "?raw=1", timeout=2) as response:
                        self.assertEqual(response.headers.get_content_type(), "text/plain")
                        self.assertEqual(response.headers.get_content_charset(), "utf-8")
                        self.assertEqual(response.read().decode(), markdown)
                    with client.open(root + "other.markdown", timeout=2) as response:
                        self.assertEqual(response.headers.get_content_type(), "text/html")
                    with client.open(root + "nested/drawing.svg", timeout=2) as response:
                        self.assertEqual(response.headers.get_content_type(), "image/svg+xml")
                    for asset in ("viewer.js", "vendor/markdown.js", "vendor/mermaid.js",
                                  "vendor/math.js", "vendor/katex.css", "vendor/github-markdown.css"):
                        with client.open(root + "__serve_html__/" + asset, timeout=2) as response:
                            self.assertGreater(len(response.read()), 0)
                    for path in ("missing.md", "other.markdown/", "__serve_html__/../viewer.html",
                                 "__serve_html__/%2e%2e/viewer.html", "__serve_html__//etc/passwd"):
                        with self.assertRaises(HTTPError) as error:
                            client.open(root + path, timeout=2)
                        self.assertEqual(error.exception.code, 404)
                        error.exception.close()

    def test_file_option_accepts_markdown_with_an_encoded_link(self):
        with tempfile.TemporaryDirectory(prefix="serve-markdown-test-") as temp:
            name = "한글 review #1.md"
            (Path(temp) / name).write_text("# Direct Markdown")
            with self.server(temp, "--bind", "127.0.0.1", "--file", name) as (_, urls, _):
                self.assertEqual(urlsplit(urls[0]).path, "/" + quote(name, safe=""))

    def test_missing_preview_assets_report_an_actionable_error(self):
        with tempfile.TemporaryDirectory(prefix="serve-markdown-test-") as temp:
            directory = Path(temp)
            (directory / "notes.md").write_text("# Notes")
            # A standalone copied script has no adjacent managed assets.
            (directory / "bin").mkdir()
            script = directory / "bin" / "serve-html.py"
            script.write_bytes(SCRIPT.read_bytes())
            client = build_opener(ProxyHandler({}))
            with self.server(directory, "--bind", "127.0.0.1",
                             command=[sys.executable, str(script), "--directory", temp]) as (_, urls, _):
                with self.assertRaises(HTTPError) as error:
                    client.open(urls[0] + "notes.md", timeout=2)
                self.assertEqual(error.exception.code, 500)
                self.assertIn(b"preview assets are missing", error.exception.read())
                error.exception.close()
                with client.open(urls[0] + "notes.md?raw=1", timeout=2) as response:
                    self.assertEqual(response.read(), b"# Notes")

    def test_concurrent_servers_keep_distinct_free_ports(self):
        with tempfile.TemporaryDirectory(prefix="serve-html-test-") as temp:
            (Path(temp) / "index.html").write_text("index")
            with self.server(temp, "--bind", "127.0.0.1") as (_, first, _):
                with self.server(temp, "--bind", "127.0.0.1") as (_, second, _):
                    self.assertNotEqual(urlsplit(first[0]).port, urlsplit(second[0]).port)
                    for url in (first[0], second[0]):
                        self.assertEqual(urlsplit(url).path, "/")
                        with build_opener(ProxyHandler({})).open(url, timeout=2) as response:
                            self.assertIn(b'href="index.html"', response.read())

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
                         ["missing.html"],
                         [str(Path(temp) / "index.html"), "--file", "index.html"],
                         [temp, "--directory", temp],
                         ["--directory", temp, temp],
                         [temp, temp],
                         ["--directory", str(Path(temp) / "index.html")],
                         ["--directory", temp, "--file", "missing.html"],
                         ["--directory", temp, "--file", "../outside.html"],
                         ["--directory", temp, "--file", "/tmp/page.html"],
                         ["--directory", temp, "--file", "file.txt"],
                         ["--directory", temp, "--file", ""],
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
