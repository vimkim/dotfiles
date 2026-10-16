#!/usr/bin/env python3
"""Compatibility for callers of the old Python script path."""
import os
from pathlib import Path
import sys

command = Path.home() / ".local/bin/html-serve"
try:
    os.execv(str(command), [str(command), *sys.argv[1:]])
except OSError as error:
    sys.exit(f"html-serve: {error}; install with: cd ~/gh/html-serve && just sync")
