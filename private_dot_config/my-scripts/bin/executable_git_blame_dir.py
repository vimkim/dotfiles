#!/usr/bin/env python3

import subprocess
import sys
import os
from typing import List, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileCommitInfo:
    filepath: str
    timestamp: int
    commit_info: str


def get_git_info(filepath: Path) -> Tuple[int, str]:
    """Get the git commit info for a file."""
    try:
        env = os.environ.copy()
        env["FORCE_COLOR"] = "true"  # Force git to output colors

        # Get timestamp and commit info
        result = subprocess.run(
            [
                "git",
                "--no-pager",  # Prevent git from using a pager
                "log",
                "--color=always",  # Force git colors
                "--follow",
                "-1",
                "--format=%at|%C(red)%h%Creset %C(yellow)%as%Creset %C(cyan)%an%Creset %C(green)%cr%Creset %C(white)%s%Creset",
                "--",
                str(filepath),
            ],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )

        if not result.stdout.strip():
            return (0, "")

        timestamp, commit_info = result.stdout.strip().split("|", 1)
        return (int(timestamp), commit_info)
    except subprocess.CalledProcessError:
        return (0, "")


def process_directory(directory: str) -> List[FileCommitInfo]:
    """Process all files in the directory and get their git info."""
    directory_path = Path(directory)
    if not directory_path.is_dir():
        print(f"Error: '{directory}' is not a directory")
        sys.exit(1)

    files_info = []
    for filepath in directory_path.iterdir():
        display_path = str(filepath) + "/" if filepath.is_dir() else str(filepath)
        timestamp, commit_info = get_git_info(filepath)

        if commit_info:  # Only include files with git history
            files_info.append(
                FileCommitInfo(
                    filepath=display_path, timestamp=timestamp, commit_info=commit_info
                )
            )

    return files_info


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <directory_path>")
        print(
            "Shows the last commit information for all files in the specified directory"
        )
        print(f"Example: {sys.argv[0]} src/")
        sys.exit(1)

    directory = sys.argv[1]
    files_info = process_directory(directory)

    # Sort by timestamp in descending order
    files_info.sort(key=lambda x: x.timestamp, reverse=True)

    # Find the maximum filename length for alignment
    max_length = max((len(file_info.filepath) for file_info in files_info), default=0)

    # Print the results
    for file_info in files_info:
        print(f"{file_info.filepath:<{max_length}} | {file_info.commit_info}")


if __name__ == "__main__":
    main()

