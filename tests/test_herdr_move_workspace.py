#!/usr/bin/env python3

import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import unittest


HELPER = (
    Path(__file__).resolve().parents[1]
    / "private_dot_local/bin/executable_herdr-move-workspace"
)


class OneRequestHerdrServer:
    def __init__(self, socket_path: Path, workspace_ids: list[str]) -> None:
        self.socket_path = socket_path
        self.workspace_ids = workspace_ids
        self.errors: list[Exception] = []
        self.stop = threading.Event()
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(str(socket_path))
        self.listener.settimeout(0.05)
        self.listener.listen()
        self.thread = threading.Thread(target=self.serve, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.stop.set()
        self.thread.join(timeout=1)
        self.listener.close()
        if self.errors:
            raise self.errors[0]

    def serve(self) -> None:
        while not self.stop.is_set():
            try:
                connection, _ = self.listener.accept()
            except TimeoutError:
                continue

            try:
                with connection, connection.makefile("rwb") as stream:
                    request = json.loads(stream.readline())
                    response = {
                        "id": request["id"],
                        "result": self.handle(request["method"], request["params"]),
                    }
                    stream.write(json.dumps(response).encode() + b"\n")
                    stream.flush()
            except Exception as error:
                self.errors.append(error)
                return

    def handle(self, method: str, params: dict) -> dict:
        if method == "session.snapshot":
            return {
                "type": "session_snapshot",
                "snapshot": {
                    "workspaces": [
                        {"workspace_id": workspace_id}
                        for workspace_id in self.workspace_ids
                    ]
                },
            }

        if method == "workspace.move":
            workspace_id = params["workspace_id"]
            source_index = self.workspace_ids.index(workspace_id)
            insert_index = params["insert_index"]
            workspace = self.workspace_ids.pop(source_index)
            if insert_index > source_index:
                insert_index -= 1
            self.workspace_ids.insert(insert_index, workspace)
            return {"type": "workspace_list"}

        raise AssertionError(f"unexpected method: {method}")


class HerdrMoveWorkspaceTest(unittest.TestCase):
    def run_helper(self, workspace_ids: list[str], active_id: str, direction: str):
        with tempfile.TemporaryDirectory() as temporary_directory:
            socket_path = Path(temporary_directory) / "herdr.sock"
            with OneRequestHerdrServer(socket_path, workspace_ids) as server:
                environment = os.environ.copy()
                environment.update(
                    {
                        "HERDR_SOCKET_PATH": str(socket_path),
                        "HERDR_ACTIVE_WORKSPACE_ID": active_id,
                    }
                )
                result = subprocess.run(
                    ["python3", HELPER, direction],
                    capture_output=True,
                    check=False,
                    env=environment,
                    text=True,
                )
            return result, server.workspace_ids

    def test_moves_workspace_up_one_position(self) -> None:
        result, workspace_ids = self.run_helper(["w1", "w2", "w3"], "w2", "up")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(workspace_ids, ["w2", "w1", "w3"])

    def test_moves_workspace_down_one_position(self) -> None:
        result, workspace_ids = self.run_helper(
            ["w1", "w2", "w3"], "w2", "down"
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(workspace_ids, ["w1", "w3", "w2"])

    def test_does_nothing_at_workspace_boundaries(self) -> None:
        up_result, up_workspace_ids = self.run_helper(
            ["w1", "w2", "w3"], "w1", "up"
        )
        down_result, down_workspace_ids = self.run_helper(
            ["w1", "w2", "w3"], "w3", "down"
        )

        self.assertEqual(up_result.returncode, 0, up_result.stderr)
        self.assertEqual(down_result.returncode, 0, down_result.stderr)
        self.assertEqual(up_workspace_ids, ["w1", "w2", "w3"])
        self.assertEqual(down_workspace_ids, ["w1", "w2", "w3"])


if __name__ == "__main__":
    unittest.main()
