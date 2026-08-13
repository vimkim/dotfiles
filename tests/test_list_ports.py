import runpy
import subprocess
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


if __name__ == "__main__":
    unittest.main()
