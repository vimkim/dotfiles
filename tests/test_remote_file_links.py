"""Check remote file clicks without launching WezTerm or a browser."""

import re
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RemoteFileLinksTest(unittest.TestCase):
    def test_file_destinations_and_mouse_bindings(self):
        lua = shutil.which("lua") or shutil.which("luajit")
        if not lua:
            self.skipTest("requires Lua or LuaJIT")
        subprocess.run(
            [lua, "tests/verify_remote_file_links.lua"], cwd=ROOT, check=True
        )

    def test_visible_absolute_paths(self):
        source = (ROOT / "dot_wezterm.lua").read_text()
        # The configured rule uses the common Rust/Python regex subset.
        pattern = re.compile(source.split("regex = [=[", 1)[1].split("]=]", 1)[0])
        cases = {
            "/home/vimkim/arst.txt": "/home/vimkim/arst.txt",
            "See (/home/vimkim/a.txt).": "/home/vimkim/a.txt",
            "`/home/vimkim/code.rs:42:3`": "/home/vimkim/code.rs:42:3",
            "[/tmp/a.md#L42]": "/tmp/a.md#L42",
            "/tmp/한국어.txt": "/tmp/한국어.txt",
            "https://example.com/home/vimkim/a.txt": None,
            "relative/path.txt": None,
            "../src/file.rs": None,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                match = pattern.search(text)
                self.assertEqual(match.group(1) if match else None, expected)


if __name__ == "__main__":
    unittest.main()
