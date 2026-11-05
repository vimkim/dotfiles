"""Alternate real shell startups before and after the reminder in a disposable home."""

import argparse
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_claude_auth_renewal import RenewalTest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-ref", required=True)
    parser.add_argument("--runs", type=int, default=20)
    args = parser.parse_args()
    case = RenewalTest()
    case.setUp()
    try:
        case.prepare_shells()
        case.cached("")
        config = case.home / ".config/nushell/config.nu"
        targets = {"dot_bashrc": case.home / ".bashrc",
                   "private_dot_config/nushell/config.nu": config}
        after = {name: path.read_bytes() for name, path in targets.items()}
        before = {name: subprocess.check_output(["git", "show", f"{args.before_ref}:{name}"], cwd=ROOT)
                  for name in targets}
        nu = shutil.which("nu")
        commands = {
            "bash -c true": (["/usr/bin/bash", "-c", "true"], False),
            "bash -lc true": (["/usr/bin/bash", "-lc", "true"], False),
            "nu -c 'true | ignore'": ([nu, "-c", "true | ignore"], False),
            "interactive bash login": (["/usr/bin/bash", "-ilc", "printf STARTUP_DONE"], True),
            "interactive nu": ([nu, "--config", str(config), "-i", "-c", "print STARTUP_DONE"], True),
            "cached helper": ([str(case.helper)], False),
        }
        report = {}
        for name, (command, interactive) in commands.items():
            samples = {"before": [], "after": []}
            for iteration in range(args.runs + 1):
                for label, sources in (("before", before), ("after", after)):
                    for source, target in targets.items():
                        target.write_bytes(sources[source])
                    started = time.perf_counter_ns()
                    if name == "cached helper" and label == "before":
                        subprocess.run(["/usr/bin/bash", "-c", ":"], check=True, capture_output=True)
                    elif interactive:
                        output = case.interactive(command)
                        assert "STARTUP_DONE" in output, output
                        assert "Error:" not in output, output
                    else:
                        result = subprocess.run(command, env=case.env, capture_output=True, timeout=10)
                        assert result.returncode == 0, result.stderr
                        assert result.stdout == result.stderr == b"", (name, result.stdout, result.stderr)
                    elapsed = (time.perf_counter_ns() - started) / 1e6
                    if iteration:
                        samples[label].append(elapsed)
            report[name] = {label: {"median_ms": round(statistics.median(values), 3),
                                    "range_ms": [round(min(values), 3), round(max(values), 3)]}
                            for label, values in samples.items()}
        report["runs_per_side"] = args.runs
        print(json.dumps(report, indent=2))
    finally:
        case.doCleanups()


if __name__ == "__main__":
    main()
