"""Compare ignore-aware fd/find searches over a directory or a fixed fixture.

Run: python3 tests/benchmark_recent_docs.py --fixture --runs 3
Or:  python3 tests/benchmark_recent_docs.py ~/gh --runs 3

The fixture contains 3,000 visible and 15,000 excluded documents across ten
repositories: hidden files, node_modules, and each supported ignore-file type.
Real-directory output can differ because fd also reads global/VCS excludes.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path)
    parser.add_argument("--fixture", action="store_true", help="build a deterministic ignored/visible tree")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    if args.fixture and args.directory:
        parser.error("choose a directory or --fixture")
    if args.runs < 1:
        parser.error("--runs must be at least 1")

    fd = shutil.which("fd")
    if not fd:
        parser.error("fd must be installed to compare both backends")
    source = Path(__file__).resolve().parents[1] / "private_dot_config/my-scripts/bin/executable_recent-docs.sh"
    samples = {"fd": [], "find": []}
    outputs = {}
    diagnostics = {}

    with tempfile.TemporaryDirectory(prefix="recent-docs-benchmark-") as temporary:
        root = Path(temporary)
        script = root / "recent-docs.sh"
        shutil.copy2(source, script)
        directory = args.directory or Path.home()
        if args.fixture:
            directory = root / "fixture"
            for repo_number in range(10):
                repo = directory / f"repo-{repo_number:02}"
                repo.mkdir(parents=True)
                (repo / ".git").mkdir()
                for name, ignored in ((".gitignore", "generated"), (".ignore", "cache"),
                                      (".fdignore", "vendor")):
                    (repo / name).write_text(ignored + "/\n")
                for category in ("docs", ".hidden", "node_modules", "generated", "cache", "vendor"):
                    folder = repo / category
                    folder.mkdir()
                    for number in range(300):
                        path = folder / f"{number:03}.md"
                        path.write_text("fixture\n")
                        modified = 1_700_000_000_000_000_000 + repo_number * 300 + number
                        os.utime(path, ns=(modified, modified))
        directory = directory.resolve()
        environment = dict(os.environ)
        if args.fixture:
            fixture_home = root / "home"
            fixture_home.mkdir()
            environment.update(HOME=str(fixture_home), XDG_CONFIG_HOME=str(fixture_home / ".config"),
                               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        for backend in samples:
            bin_dir = root / backend
            bin_dir.mkdir()
            for name, executable in (("python3", sys.executable), ("find", shutil.which("find"))):
                (bin_dir / name).symlink_to(executable)
            if backend == "fd":
                (bin_dir / "fd").symlink_to(fd)

        for run in range(args.runs):
            # Alternate order to reduce the advantage from filesystem caching.
            order = ("fd", "find") if run % 2 == 0 else ("find", "fd")
            for backend in order:
                metrics = root / "metrics"
                result = subprocess.run(
                    [
                        "/usr/bin/time", "-f", "%e %U %S %M", "-o", str(metrics),
                        "/bin/bash", str(script), str(directory),
                    ],
                    env=dict(environment, PATH=str(root / backend)),
                    capture_output=True,
                    text=True,
                )
                wall, user, system, rss = map(float, metrics.read_text().splitlines()[-1].split())
                sample = dict(
                    wall_seconds=wall, cpu_seconds=user + system,
                    peak_rss_kib=int(rss), exit_code=result.returncode,
                )
                samples[backend].append(sample)
                outputs[backend] = result.stdout
                lines = result.stderr.splitlines()
                diagnostics[backend] = dict(line_count=len(lines), first_lines=lines[:3])
                print(json.dumps(dict(backend=backend, run=run + 1, **sample)), flush=True)

    report = dict(
        directory=str(directory),
        runs_per_backend=args.runs,
        identical_final_output=outputs["fd"] == outputs["find"],
        files_displayed={name: len(output.splitlines()) for name, output in outputs.items()},
        exit_codes={name: [sample["exit_code"] for sample in runs] for name, runs in samples.items()},
        diagnostics=diagnostics,
        median={
            name: {
                key: statistics.median(sample[key] for sample in runs)
                for key in ("wall_seconds", "cpu_seconds", "peak_rss_kib")
            }
            for name, runs in samples.items()
        },
    )
    print(json.dumps(report, indent=2))
    successful = all(sample["exit_code"] == 0 for runs in samples.values() for sample in runs)
    if args.fixture:
        successful = successful and report["identical_final_output"] and all(
            count == 30 for count in report["files_displayed"].values())
    return 0 if successful else 1


if __name__ == "__main__":
    sys.exit(main())
