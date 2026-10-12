"""Verify native Codex prompt rejection with a disposable thread and local provider.

No OpenAI inference: all provider requests go to a localhost sink, and the guard
reads a synthetic quota snapshot. Run explicitly; this requires installed Codex.
"""

import importlib.machinery
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time

SOURCE = Path(__file__).resolve().parents[1] / "dot_codex/hooks/executable_daily-usage.py"
loader = importlib.machinery.SourceFileLoader("native_guard_verification", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
guard = importlib.util.module_from_spec(spec)
loader.exec_module(guard)


def main():
    binary = shutil.which("codex")
    if binary is None:
        raise SystemExit("Codex is required for native-hook verification")
    posts = []

    class Sink(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b'{"models":[],"data":[]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            posts.append(self.path)
            self.send_response(503)
            self.end_headers()

        def log_message(self, *unused):
            pass

    with tempfile.TemporaryDirectory(prefix="codex-native-guard-") as temporary:
        root = Path(temporary)
        fixture = root / "quota.json"
        observed = time.time()
        fixture.write_text(json.dumps({
            "account_key": "a" * 64, "plan": "pro", "used_percent": 33,
            "resets_at": int(observed) + 604800, "observed_at": observed,
        }))
        hook = shlex.join([sys.executable, "-B", str(SOURCE), "hook", "--snapshot", str(fixture),
                           "--state-dir", str(root / "state")])
        server = ThreadingHTTPServer(("127.0.0.1", 0), Sink)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        flags = [
            "-c", 'model_provider="daily_guard_fixture"',
            "-c", 'model_providers.daily_guard_fixture.name="Local guard verification"',
            "-c", f'model_providers.daily_guard_fixture.base_url="http://127.0.0.1:{server.server_port}/v1"',
            "-c", 'model_providers.daily_guard_fixture.wire_api="responses"',
            "-c", "model_providers.daily_guard_fixture.requires_openai_auth=false",
            "-c", "model_providers.daily_guard_fixture.request_max_retries=0",
            "-c", "model_providers.daily_guard_fixture.stream_max_retries=0",
            "-c", f"sqlite_home={json.dumps(str(root / 'runtime'))}",
            "-c", "analytics.enabled=false",
            "-c", "features.hooks=true",
            "-c", "hooks.UserPromptSubmit=[{hooks=[{type=\"command\",command=" + json.dumps(hook) + ",timeout=25}]}]",
            "-c", "hooks.Stop=[{hooks=[{type=\"command\",command=" + json.dumps(hook) + ",timeout=25}]}]",
        ]
        environment = {k: v for k, v in os.environ.items() if not k.startswith("HERDR_")}
        try:
            result = subprocess.run([
                binary, "--no-daemon", "exec", "--ignore-user-config", "--ignore-rules",
                "--ephemeral", "--skip-git-repo-check", "--json", "--dangerously-bypass-hook-trust",
                "-C", str(root), *flags, "Reject this synthetic prompt at the daily quota cap.",
            ], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30, env=environment)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)
        events = []
        for line in result.stdout.splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        state_path = root / "state" / ("a" * 64 + ".json")
        helper_ran = state_path.exists() and json.loads(state_path.read_text())["daily_points"] == 33
        completed = [event for event in events if event.get("type") == "turn.completed"]
        zero_tokens = bool(completed) and all(all(value == 0 for value in event.get("usage", {}).values()) for event in completed)
        if posts or not helper_ran or not zero_tokens:
            # This output contains only fixture prompts, paths and localhost-provider diagnostics.
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            raise SystemExit(f"Native rejection not proved; helper ran={helper_ran}, localhost provider requests={len(posts)}")
        print(json.dumps({
            "native_codex_version": subprocess.check_output([binary, "--version"], text=True).strip(),
            "exit_code": result.returncode, "daily_cap_rejection_observed": True,
            "hook_helper_ran": helper_ran, "native_turn_usage_was_zero": zero_tokens,
            "provider_post_requests": len(posts), "openai_inference_requests": 0,
            "event_types": [event.get("type") for event in events],
        }, indent=2))


if __name__ == "__main__":
    main()
