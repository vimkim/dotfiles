import contextlib
import io
import os
import runpy
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = (
    Path(__file__).parents[1]
    / "private_dot_config"
    / "my-scripts"
    / "bin"
    / "executable_list-ports.py"
)
MODULE = runpy.run_path(str(SCRIPT))
SocketEntry = MODULE["SocketEntry"]


class ParseLocalEndpointTests(unittest.TestCase):
    def test_parses_ipv4_endpoint(self):
        self.assertEqual(
            MODULE["parse_local_endpoint"]("127.0.0.1:5432"),
            ("127.0.0.1", 5432),
        )

    def test_parses_ipv6_endpoint(self):
        self.assertEqual(MODULE["parse_local_endpoint"]("[::1]:323"), ("::1", 323))

    def test_rejects_non_numeric_port(self):
        self.assertIsNone(MODULE["parse_local_endpoint"]("0.0.0.0:http"))


class ParseSsLineTests(unittest.TestCase):
    def test_parses_tcp_process_metadata(self):
        entry = MODULE["parse_ss_line"](
            'tcp LISTEN 0 128 127.0.0.1:5432 0.0.0.0:* '
            'users:(("postgres",pid=321,fd=7))'
        )

        self.assertEqual(
            entry,
            SocketEntry("tcp", "LISTEN", "127.0.0.1", 5432, "321", "postgres"),
        )

    def test_parses_udp_without_process_metadata(self):
        entry = MODULE["parse_ss_line"]("udp UNCONN 0 0 [::1]:323 [::]:*")

        self.assertEqual(entry, SocketEntry("udp", "UNCONN", "::1", 323))

    def test_collects_unique_processes(self):
        pid, program = MODULE["parse_processes"](
            'users:(("nginx",pid=12,fd=5),("nginx",pid=11,fd=5))'
        )

        self.assertEqual(pid, "12,11")
        self.assertEqual(program, "nginx")


class DisplayTests(unittest.TestCase):
    def test_full_process_title_is_not_truncated_in_the_application_column(self):
        title = "dev2-baboon-rudd-gateway"
        row = MODULE["format_entry"](
            SocketEntry("tcp", "LISTEN", "127.0.0.1", 8443, "123", title)
        )
        self.assertTrue(row.endswith(title))

    def test_rows_begin_with_numeric_port(self):
        row = MODULE["format_entry"](
            SocketEntry("tcp", "LISTEN", "127.0.0.1", 80, "12", "nginx")
        )

        self.assertEqual(row.split()[0], "80")

    def test_fzf_preserves_input_order(self):
        command = MODULE["build_fzf_command"]("ngnx")

        self.assertIn("--no-sort", command)
        self.assertEqual(command[-2:], ["--query", "ngnx"])


class CollectEntriesTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(Path, "read_bytes", side_effect=FileNotFoundError).start()
        mock.patch.object(MODULE["shutil"], "which", return_value="/usr/sbin/ss").start()

    def collect(self, *processes):
        output = "\n".join(
            f'tcp LISTEN 0 128 127.0.0.1:{8000 + index} 0.0.0.0:* users:({process})'
            for index, process in enumerate(processes)
        )
        completed = subprocess.CompletedProcess(["ss"], 0, output, "")
        with mock.patch.object(MODULE["subprocess"], "run", return_value=completed):
            return MODULE["collect_entries"](tcp=True, udp=False)

    def test_reads_full_titles_once_per_pid_and_keeps_distinct_processes(self):
        with mock.patch.object(Path, "read_bytes", side_effect=[
            b"dev2-baboon-rudd-gateway\0--private-argument\0",
            b"dev2-baboon-rudd-docserve\0",
        ]) as read:
            entries = self.collect(
                '("python3",pid=321,fd=7),("python3",pid=322,fd=8)',
                '("python3",pid=321,fd=9)',
            )
        self.assertEqual(entries[0].pid, "321,322")
        self.assertEqual(entries[0].program,
                         "dev2-baboon-rudd-gateway,dev2-baboon-rudd-docserve")
        self.assertEqual(entries[1].program, "dev2-baboon-rudd-gateway")
        self.assertEqual(read.call_count, 2)

    def test_falls_back_when_process_exits_title_is_private_or_cmdline_is_empty(self):
        for outcome in (FileNotFoundError(), PermissionError(), b"", b"\0"):
            with self.subTest(outcome=outcome):
                kwargs = {"side_effect": outcome} if isinstance(outcome, OSError) else {"return_value": outcome}
                with mock.patch.object(Path, "read_bytes", **kwargs):
                    entry = self.collect('("python3",pid=321,fd=7)')[0]
                self.assertEqual(entry.program, "python3")

    def test_process_title_cannot_add_terminal_rows(self):
        with mock.patch.object(Path, "read_bytes", return_value=b"dev2\n\t gateway\0secret\0"):
            self.assertEqual(MODULE["process_title"]("321"), "dev2 gateway")

    def test_protocol_filters_handle_ss_omitting_the_protocol_column(self):
        for protocol, state in (("tcp", "LISTEN"), ("udp", "UNCONN")):
            with self.subTest(protocol=protocol):
                output = f'{state} 0 128 [::1]:8443 [::]:* users:(("python3",pid=321,fd=7))'
                completed = subprocess.CompletedProcess(["ss"], 0, output, "")
                with mock.patch.object(MODULE["subprocess"], "run", return_value=completed), \
                        mock.patch.object(Path, "read_bytes", return_value=b"dev2-baboon-rudd-gateway\0"):
                    entries = MODULE["collect_entries"](tcp=protocol == "tcp", udp=protocol == "udp")
                self.assertEqual(entries, [SocketEntry(protocol, state, "::1", 8443,
                                                      "321", "dev2-baboon-rudd-gateway")])

    def test_sorts_ports_numerically(self):
        ss_output = "\n".join(
            (
                "tcp LISTEN 0 128 127.0.0.1:10000 0.0.0.0:*",
                "udp UNCONN 0 0 127.0.0.1:53 0.0.0.0:*",
                "tcp LISTEN 0 128 127.0.0.1:800 0.0.0.0:*",
            )
        )
        completed = subprocess.CompletedProcess(
            ["ss"],
            returncode=0,
            stdout=ss_output,
            stderr="",
        )

        with mock.patch.object(MODULE["subprocess"], "run", return_value=completed):
            entries = MODULE["collect_entries"](tcp=True, udp=True)

        self.assertEqual([entry.port for entry in entries], [53, 800, 10000])

    def test_single_protocol_output_keeps_process_details(self):
        for tcp, udp, protocol, state in [
            (True, False, "tcp", "LISTEN"),
            (False, True, "udp", "UNCONN"),
        ]:
            with self.subTest(protocol=protocol):
                completed = subprocess.CompletedProcess(
                    ["ss"], 0,
                    f'{state} 0 4096 [::1]:8443 [::]:* '
                    'users:(("tailscaled",pid=2433,fd=8))\n', "",
                )
                with mock.patch.object(MODULE["subprocess"], "run", return_value=completed):
                    entries = MODULE["collect_entries"](tcp=tcp, udp=udp)
                self.assertEqual(
                    entries,
                    [SocketEntry(protocol, state, "::1", 8443, "2433", "tailscaled")],
                )


class ProcessDetailsTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(Path, "read_bytes", side_effect=FileNotFoundError).start()
        mock.patch("os.geteuid", return_value=1000).start()
        mock.patch.object(
            MODULE["shutil"], "which",
            side_effect=lambda name: {"ss": "/usr/sbin/ss", "fzf": "/usr/bin/fzf"}.get(name),
        ).start()
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
        self.calls = []
        self.picker_input = ""

    def run_command(self, command, **kwargs):
        self.calls.append(command)
        if command[0] == "fzf":
            self.picker_input = kwargs["input"]
            return subprocess.CompletedProcess(command, 0, self.picker_input.splitlines()[0] + "\n", "")

        privileged = command[0] == "sudo" or os.geteuid() == 0
        metadata = ' users:(("tailscaled",pid=2433,fd=8))' if privileged else ""
        return subprocess.CompletedProcess(
            command, 0,
            f"tcp LISTEN 0 4096 100.68.111.110:8443 0.0.0.0:*{metadata}\n", "",
        )

    def run_ports(self, *args):
        with contextlib.redirect_stdout(self.stdout), contextlib.redirect_stderr(self.stderr):
            with mock.patch.object(MODULE["subprocess"], "run", side_effect=self.run_command):
                return MODULE["main"](list(args))

    def test_default_shows_root_owned_process_in_unprivileged_picker(self):
        self.assertEqual(self.run_ports("8443"), 0)
        self.assertIn("tailscaled", self.picker_input)
        self.assertIn("2433", self.picker_input)
        self.assertEqual(self.stdout.getvalue(), "8443\n")
        self.assertEqual(self.stderr.getvalue(), "")
        self.assertEqual(self.calls[0][:3], ["sudo", "--", "/usr/sbin/ss"])
        self.assertEqual(self.calls[1][0], "fzf")

    def test_no_sudo_preserves_limited_details_without_elevation(self):
        self.assertEqual(self.run_ports("--no-sudo", "8443"), 0)
        self.assertNotIn("tailscaled", self.picker_input)
        self.assertEqual(self.calls[0][0], "/usr/sbin/ss")
        self.assertEqual(self.stdout.getvalue(), "8443\n")

    def test_root_does_not_invoke_sudo(self):
        with mock.patch("os.geteuid", return_value=0):
            self.assertEqual(self.run_ports("8443"), 0)
        self.assertIn("tailscaled", self.picker_input)
        self.assertEqual(self.calls[0][0], "/usr/sbin/ss")

    def test_failed_authentication_is_reported_before_picker(self):
        with contextlib.redirect_stdout(self.stdout), contextlib.redirect_stderr(self.stderr):
            with mock.patch.object(
                MODULE["subprocess"], "run",
                side_effect=subprocess.CalledProcessError(1, ["sudo"], stderr="sudo: authentication failed"),
            ) as run:
                result = MODULE["main"](["8443"])
        self.assertEqual(result, 1)
        self.assertEqual(self.stdout.getvalue(), "")
        self.assertIn("authentication failed", self.stderr.getvalue())
        self.assertIn("--no-sudo", self.stderr.getvalue())
        self.assertEqual(run.call_count, 1)

    def test_cancelled_authentication_exits_without_traceback(self):
        with contextlib.redirect_stdout(self.stdout), contextlib.redirect_stderr(self.stderr):
            with mock.patch.object(MODULE["subprocess"], "run", side_effect=KeyboardInterrupt):
                result = MODULE["main"]([])
        self.assertEqual(result, 130)
        self.assertEqual(self.stdout.getvalue(), "")
        self.assertEqual(self.stderr.getvalue(), "")

    def test_missing_sudo_explains_limited_details_option(self):
        with contextlib.redirect_stderr(self.stderr):
            with mock.patch.object(MODULE["subprocess"], "run", side_effect=FileNotFoundError):
                result = MODULE["main"]([])
        self.assertEqual(result, 1)
        self.assertIn("sudo", self.stderr.getvalue())
        self.assertIn("--no-sudo", self.stderr.getvalue())

    def test_missing_ss_reports_required_dependency(self):
        with contextlib.redirect_stderr(self.stderr):
            with mock.patch.object(MODULE["shutil"], "which", return_value=None):
                with mock.patch.object(MODULE["subprocess"], "run") as run:
                    result = MODULE["main"]([])
        self.assertEqual(result, 1)
        self.assertIn("ss is not installed", self.stderr.getvalue())
        run.assert_not_called()


@unittest.skipUnless(Path("/proc/self/cmdline").exists(), "Linux procfs is required")
class LiveProcessTitleTests(unittest.TestCase):
    def test_reads_long_argv_zero_from_a_real_process_without_arguments(self):
        title = "dev2-baboon-rudd-gateway"
        with subprocess.Popen(
            [title, "-c", "print('ready', flush=True); input()"],
            executable=sys.executable, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True,
        ) as child:
            try:
                self.assertEqual(child.stdout.readline().strip(), "ready")
                self.assertEqual(MODULE["process_title"](str(child.pid)), title)
            finally:
                child.communicate("\n", timeout=5)


if __name__ == "__main__":
    unittest.main()
