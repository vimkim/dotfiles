#!/usr/bin/env python3

import subprocess
import sys
import os
import argparse
from typing import List, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
from multiprocessing import Pool, cpu_count
from functools import partial


@dataclass
class FileCommitInfo:
    filepath: str
    timestamp: int
    commit_info: str


def get_git_root() -> Path:
    """Get the git repository root directory."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(result.stdout.strip())


def get_git_files(start_path: Path, recursive: bool = False) -> List[Path]:
    """Get git tracked files from the specified path."""
    cmd = ["git", "ls-files", "--cached", "--others", "--exclude-standard"]

    result = subprocess.run(
        cmd, cwd=start_path, capture_output=True, text=True, check=True
    )

    # Convert paths to absolute paths
    files = [start_path / f for f in result.stdout.splitlines()]

    # Filter files based on the start_path and recursive flag
    rel_start = start_path.resolve()
    filtered_files = []
    for file in files:
        try:
            # Get the relative path from start_path
            rel_path = file.resolve().relative_to(rel_start)

            # For non-recursive, only include files directly in the directory
            if not recursive and len(rel_path.parts) > 1:
                continue

            filtered_files.append(file)
        except ValueError:
            # Path is not relative to start_path
            continue

    return filtered_files


def get_file_info(filepath: Path) -> Optional[FileCommitInfo]:
    """Get git commit info for a single file."""
    try:
        env = os.environ.copy()
        env["FORCE_COLOR"] = "true"

        result = subprocess.run(
            [
                "git",
                "--no-pager",
                "log",
                "--color=always",
                "--follow",
                "-1",
                "--format=%at|%C(green)%cr%Creset %C(red)%h%Creset %C(yellow)%as%Creset %C(cyan)%an%Creset %C(white)%s%Creset",
                "--",
                str(filepath),
            ],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )

        if not result.stdout.strip():
            return None

        timestamp, commit_info = result.stdout.strip().split("|", 1)

        # Use relative path for display
        try:
            display_path = filepath.resolve().relative_to(Path.cwd())
        except ValueError:
            display_path = filepath

        return FileCommitInfo(
            filepath=str(display_path),
            timestamp=int(timestamp),
            commit_info=commit_info,
        )
    except subprocess.CalledProcessError:
        return None


def process_directory(
    directory: str, recursive: bool = False, use_git_root: bool = False
) -> List[FileCommitInfo]:
    """Process files in parallel and get their git info."""
    try:
        if use_git_root:
            start_path = get_git_root()
        else:
            start_path = Path(directory).resolve()
    except subprocess.CalledProcessError:
        print("Error: Not a git repository")
        sys.exit(1)

    if not start_path.is_dir():
        print(f"Error: '{directory}' is not a directory")
        sys.exit(1)

    # Get all git tracked files efficiently
    try:
        files = get_git_files(start_path, recursive)
    except subprocess.CalledProcessError:
        print("Error: Git command failed")
        sys.exit(1)

    if not files:
        return []

    # Process files in parallel
    num_processes = min(cpu_count(), 40)
    with Pool(num_processes) as pool:
        results = pool.map(get_file_info, files)
        files_info = [r for r in results if r is not None]

    return files_info


def main():
    parser = argparse.ArgumentParser(
        description="Show last commit information for files in a directory"
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to analyze (default: current directory)",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively process the specified directory",
    )
    parser.add_argument(
        "-g", "--git-root", action="store_true", help="Process from git root directory"
    )

    args = parser.parse_args()

    files_info = process_directory(args.directory, args.recursive, args.git_root)

    if not files_info:
        print("No git tracked files found in the specified directory")
        return

    # Sort by timestamp in descending order
    files_info.sort(key=lambda x: x.timestamp, reverse=True)

    # Find the maximum filename length for alignment
    max_length = max((len(file_info.filepath) for file_info in files_info), default=0)

    # Print the results
    for file_info in files_info:
        print(f"{file_info.filepath:<{max_length}} | {file_info.commit_info}")


if __name__ == "__main__":
    main()
