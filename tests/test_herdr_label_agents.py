import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import unittest
from unittest import mock


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "private_dot_config/my-scripts/bin/executable_herdr-label-agents"
)


class HerdrLabelAgentsTest(unittest.TestCase):
    def test_labels_only_unnamed_panes_and_repeated_runs_make_no_changes(self):
        agents = [
            {"pane_id": "w1:p1", "name": "r6-engine"},
            {"pane_id": "w1:p2", "name": "skillfix"},
            {"pane_id": "w1:p3", "name": "panelabel"},
            {"pane_id": "w1:p4"},
            {"pane_id": "w1:p5", "name": None},
            {"pane_id": "w1:p6", "name": ""},
            {"pane_id": "w1:p7", "name": "empty"},
        ]
        labels = {"w1:p1": None, "w1:p2": "skillfix", "w1:p3": "my custom label", "w1:p7": ""}
        renamed = []

        def read(command, **kwargs):
            if command == ["herdr", "agent", "list"]:
                result = {"agents": agents}
            else:
                self.assertEqual(command[:3], ["herdr", "pane", "get"])
                pane_id = command[3]
                label = labels[pane_id]
                result = {"pane": {} if label is None else {"label": label}}
            return json.dumps({"result": result})

        def rename(command, **kwargs):
            self.assertEqual(command[:3], ["herdr", "pane", "rename"])
            self.assertTrue(kwargs["check"])
            pane_id, name = command[3:]
            renamed.append((pane_id, name))
            labels[pane_id] = name

        output = io.StringIO()
        with mock.patch.dict(os.environ, HERDR_ENV="1"), \
             mock.patch("subprocess.check_output", side_effect=read), \
             mock.patch("subprocess.run", side_effect=rename), \
             contextlib.redirect_stdout(output):
            runpy.run_path(str(SCRIPT), run_name="__main__")
            self.assertEqual(renamed, [("w1:p1", "r6-engine"), ("w1:p7", "empty")])
            renamed.clear()
            runpy.run_path(str(SCRIPT), run_name="__main__")
            self.assertEqual(renamed, [])
        self.assertEqual(labels["w1:p3"], "my custom label")
        self.assertIn("labeled w1:p1 -> r6-engine", output.getvalue())
        self.assertIn("unchanged w1:p2 -> skillfix", output.getvalue())
        self.assertIn("skipped w1:p3: keeping 'my custom label'", output.getvalue())

    def test_failed_pane_read_does_not_rename_any_pane(self):
        agents = {"result": {"agents": [{"pane_id": "w1:p1", "name": "r6-engine"}]}}
        with mock.patch.dict(os.environ, HERDR_ENV="1"), \
             mock.patch("subprocess.check_output", side_effect=[
                 json.dumps(agents), subprocess.CalledProcessError(1, ["herdr"]),
             ]), \
             mock.patch("subprocess.run") as rename:
            with self.assertRaises(subprocess.CalledProcessError):
                runpy.run_path(str(SCRIPT), run_name="__main__")
            rename.assert_not_called()

    def test_requires_a_herdr_pane(self):
        with mock.patch.dict(os.environ, HERDR_ENV=""), \
             mock.patch("subprocess.check_output") as read:
            with self.assertRaisesRegex(SystemExit, "run this command inside Herdr"):
                runpy.run_path(str(SCRIPT), run_name="__main__")
            read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
