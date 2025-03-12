#!/usr/bin/env python3
import re
import subprocess
import sys
import os
import tempfile


def parse_diff(lines, temp_dir):
    """
    Parse diff lines to extract diff hunks.
    For each hunk, capture the entire hunk block and write it to a temporary file.
    Returns a list of entries in the format:
      "ID<TAB>filepath:line_number<TAB>HUNK_HEADER<TAB>TMPFILE"
    """
    entries = []
    current_file = None
    hunk_block = []
    hunk_start_line = None
    hunk_header = None
    hunk_id = 0

    # Patterns for file headers and hunk headers.
    pattern_git_file = re.compile(r"^\+\+\+\s+(.*)")
    pattern_index_file = re.compile(r"^Index:\s+(.*)")
    pattern_hunk = re.compile(r"^@@\s+-\d+(?:,\d+)?\s+\+(\d+)")

    def flush_hunk():
        nonlocal hunk_block, hunk_id, hunk_header, hunk_start_line
        if hunk_block and current_file and hunk_start_line is not None and hunk_header:
            tmp_filepath = os.path.join(temp_dir, f"{hunk_id}.txt")
            with open(tmp_filepath, "w", encoding="utf-8") as hf:
                hf.write("\n".join(hunk_block))
            # Build an entry with four fields: ID, "filepath:line", hunk header, and the tmp file path.
            entry = f"{hunk_id}\t{current_file}:{hunk_start_line}\t{hunk_header}\t{tmp_filepath}"
            entries.append(entry)
            hunk_block.clear()
            hunk_header = None
            hunk_start_line = None
            hunk_id += 1

    for line in lines:
        line = line.rstrip("\n")

        # Detect file header lines.
        if line.startswith("+++ ") or line.startswith("Index: "):
            flush_hunk()
            m = pattern_git_file.match(line)
            if m:
                current_file = m.group(1)
                # Remove any leading "a/" or "b/"
                if current_file.startswith("a/") or current_file.startswith("b/"):
                    current_file = current_file[2:]
                continue
            m = pattern_index_file.match(line)
            if m:
                current_file = m.group(1)
                continue

        # Detect hunk header lines.
        m = pattern_hunk.match(line)
        if m:
            flush_hunk()
            hunk_start_line = m.group(1)
            hunk_header = line
            hunk_block.append(line)
            continue

        # Append lines if inside a hunk.
        if hunk_block:
            hunk_block.append(line)

    flush_hunk()
    return entries


def fuzzy_select(entries):
    """
    Uses fzf to let the user select one entry from the list.
    The preview window shows the contents of the temporary file (i.e. the diff hunk).
    Returns the selected entry string.
    """
    if not entries:
        return None

    preview_cmd = "cat {4} | delta --width=${FZF_PREVIEW_COLUMNS:-$COLUMNS}"
    fzf_cmd = [
        "fzf",
        "--header=Select a diff chunk",
        "--delimiter=\t",
        f"--preview={preview_cmd}",
        "--preview-window=bottom:70%",
    ]
    try:
        fzf = subprocess.Popen(
            fzf_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        print("Error: fzf is not installed or not in your PATH.", file=sys.stderr)
        sys.exit(1)

    input_data = "\n".join(entries)
    selected, _ = fzf.communicate(input_data)
    return selected.strip() if selected else None


def open_in_editor(filepath, line_number):
    """
    Opens the given file at the specified line number in the editor.
    Uses the $EDITOR environment variable, defaulting to vim.
    """
    editor = os.environ.get("EDITOR", "vim")
    subprocess.run([editor, f"+{line_number}", filepath])


def main():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Read from a file if provided, otherwise from standard input.
        if len(sys.argv) >= 2:
            try:
                with open(sys.argv[1], "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except Exception as e:
                print(f"Error reading file {sys.argv[1]}: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            lines = sys.stdin.readlines()

        entries = parse_diff(lines, temp_dir)
        if not entries:
            print("No diff hunk entries found.")
            sys.exit(0)

        selected = fuzzy_select(entries)
        if not selected:
            sys.exit(0)

        # Expected format: ID<TAB>filepath:line_number<TAB>hunk header<TAB>tempfile.
        try:
            parts = selected.split("\t")
            if len(parts) < 2:
                raise ValueError("Invalid selection format.")
            file_line = parts[1]
            filepath, line_str = file_line.split(":", 1)
            line_number = int(line_str)
        except ValueError:
            print("Failed to parse the selected entry:", selected, file=sys.stderr)
            sys.exit(1)

        open_in_editor(filepath, line_number)


if __name__ == "__main__":
    main()
