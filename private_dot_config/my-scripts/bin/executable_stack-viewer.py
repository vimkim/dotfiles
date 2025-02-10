#!/usr/bin/env python3
import curses
import os
import re
import subprocess
import sys

from pygments import lex
from pygments.lexers.c_cpp import CppLexer
from pygments.token import Token

# ---------------------------------------------------------------------------
# Constants and Regular Expressions
# ---------------------------------------------------------------------------

SEPARATOR = "Stack trace (most recent call first):"
DEFAULT_EDITOR = os.environ.get("EDITOR", "nvim")  # Default editor if not set.

lexer = CppLexer()
token_colors = None

# Regex to remove ANSI escape sequences (used in file parsing only)
ANSI_ESCAPE_REGEX = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

# ---------------------------------------------------------------------------
# Trace Processing Functions
# ---------------------------------------------------------------------------


def load_traces(filename: str) -> list[str]:
    with open(filename, "r") as f:
        content = f.read()
    parts = [part.strip() for part in content.split(SEPARATOR) if part.strip()]
    traces = [f"{SEPARATOR}\n{part}" for part in parts]
    return traces


def simplify_trace(lines: list[str]) -> list[str]:
    simplified = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("#"):
            header_line = line
            j = i + 1
            snippet_found = False
            while j < len(lines) and not lines[j].lstrip().startswith("#"):
                snippet_found = True
                j += 1
            if snippet_found:
                simplified.append(header_line + " ....")
            else:
                simplified.append(header_line)
            i = j
        else:
            i += 1
    return simplified


# ---------------------------------------------------------------------------
# Curses Rendering Helper Functions
# ---------------------------------------------------------------------------


def get_curses_attr_for_token(ttype, token_colors):
    """
    Walk up the token type hierarchy until we find a matching entry in our token_colors dict.
    """
    while ttype not in token_colors and ttype.parent is not None:
        ttype = ttype.parent
    return token_colors.get(ttype, curses.A_NORMAL)


def render_line(window, y, x, line, lexer, token_colors, base_attr=0):
    """
    Render a line of text at position (y, x) by tokenizing it using Pygments and applying
    the corresponding curses color attribute for each token.
    """
    pos = x
    for ttype, token in lex(line, lexer):
        attr = get_curses_attr_for_token(ttype, token_colors)
        combined_attr = attr | base_attr
        try:
            window.addstr(y, pos, token, combined_attr)
        except curses.error:
            break  # If we run off the screen.
        pos += len(token)


def render_stacktrace_line(window, y, x, line, base_attr=0):
    """
    For a stacktrace line (starting with '#'), use a regex to split the line into
    components and colorize parts:
      - Frame number and address: default color.
      - Function signature: blue (color pair 9).
      - Filename: green (color pair 10).
      - Line and column numbers: yellow (color pair 11).
    """
    pattern = re.compile(
        r"""
        ^\s*                             # Leading whitespace
        \#(?P<frame>\d+)\s+              # Frame number preceded by #
        (?P<address>0x[0-9a-f]+)\s+       # Address in hex
        in\s+                           # Literal "in"
        (?P<func>[^(]+(?:\([^)]*\))?)\s+  # Function signature (name and optional args)
        # (?P<func>.*)
        at\s+                           # Literal "at"
        (?P<file>[^\s:]+)               # Filename (up to a space or colon)
        (?:\:(?P<line>\d+))?            # Optional line number prefixed by :
        (?:\:(?P<col>\d+))?             # Optional column number prefixed by :
        (.*)$                          # Remainder of the line (e.g. trailing " ....")
    """,
        re.VERBOSE,
    )
    m = pattern.match(line)
    pos = x
    if m:
        # Print the frame number and address (default style).
        prefix = f"#{m.group('frame')}  {m.group('address')}"
        try:
            window.addstr(y, pos, prefix, curses.color_pair(9) | base_attr)
        except curses.error:
            return
        pos += len(prefix)

        _in = " in "
        try:
            window.addstr(y, pos, _in, curses.color_pair(6) | base_attr)
        except curses.error:
            return
        pos += len(_in)

        # Print the function signature using Pygments tokenization.
        func = m.group("func") or ""
        for ttype, token in lex(func, lexer):
            # Determine the attribute for this token from our token_colors mapping.
            attr = get_curses_attr_for_token(ttype, token_colors)
            try:
                window.addstr(y, pos, token, attr | base_attr)
            except curses.error:
                break  # If we run off the screen, stop rendering.
            pos += len(token)

        # Print " at " literal.
        literal = " at "
        try:
            window.addstr(y, pos, literal, base_attr)
        except curses.error:
            return
        pos += len(literal)

        # Print the filename in green (color pair 10).
        file = m.group("file") or ""
        try:
            window.addstr(y, pos, file, curses.color_pair(10) | base_attr)
        except curses.error:
            return
        pos += len(file)

        # Print line number (and column if present) in yellow (color pair 11).
        if m.group("line"):
            line_part = f":{m.group('line')}"
            try:
                window.addstr(y, pos, line_part, curses.color_pair(11) | base_attr)
            except curses.error:
                return
            pos += len(line_part)
        if m.group("col"):
            col_part = f":{m.group('col')}"
            try:
                window.addstr(y, pos, col_part, curses.color_pair(11) | base_attr)
            except curses.error:
                return
            pos += len(col_part)

        # Print any remaining part of the line.
        remainder = m.group(7) or ""
        try:
            window.addstr(y, pos, remainder, base_attr)
        except curses.error:
            return
    else:
        # Fallback: if our regex doesn't match, simply print the line.
        try:
            window.addstr(y, x, line, base_attr)
        except curses.error:
            return


def render_trace_line(window, y, x, line, lexer, token_colors, base_attr=0):
    """
    Determine if the line is a stacktrace line or a regular code line.
    If it starts with '#' (after stripping whitespace) we assume it's a stacktrace
    and use our custom colorizing; otherwise, use the standard Pygments-based rendering.
    """
    if line.lstrip().startswith("#"):
        render_stacktrace_line(window, y, x, line, base_attr)
    else:
        render_line(window, y, x, line, lexer, token_colors, base_attr)


def parse_file_and_line(text: str) -> tuple[str, int] | None:
    """
    Parse a file path and a line number from a stack frame header.
    It expects a pattern like 'at <filename>:<line>' in the text.
    Returns (filename, line_number) if successful, or None otherwise.
    """
    clean_text = ANSI_ESCAPE_REGEX.sub("", text)
    match = re.search(r"\bat\s+(?P<file>\S+?)(?=:\d+\b):(?P<line>\d+)\b", clean_text)
    if match:
        return match.group("file"), int(match.group("line"))
    return None


def open_file_in_editor(stdscr: curses.window, filename: str, line_number: int) -> None:
    """
    Exit curses mode, open the specified file in the configured editor at the given line,
    and then reinitialize curses.
    """
    curses.endwin()
    try:
        subprocess.call([DEFAULT_EDITOR, f"+{line_number}", filename])
    except Exception as e:
        print("Failed to open editor:", e)
    stdscr.clear()
    curses.doupdate()


# ---------------------------------------------------------------------------
# Main Curses Loop
# ---------------------------------------------------------------------------


def main(stdscr: curses.window, traces: list[str]) -> None:
    global token_colors, lexer
    curses.curs_set(0)

    if curses.has_colors():
        curses.start_color()
        try:
            curses.use_default_colors()
        except Exception:
            pass

        # Existing color pairs
        curses.init_pair(1, curses.COLOR_GREEN, -1)  # Comments
        curses.init_pair(2, curses.COLOR_BLUE, -1)  # Keywords
        curses.init_pair(3, curses.COLOR_WHITE, -1)  # Names (identifiers)
        curses.init_pair(4, curses.COLOR_MAGENTA, -1)  # Strings
        curses.init_pair(5, curses.COLOR_CYAN, -1)  # Numbers
        curses.init_pair(6, curses.COLOR_RED, -1)  # Operators
        curses.init_pair(7, curses.COLOR_WHITE, -1)  # Punctuation
        curses.init_pair(8, curses.COLOR_WHITE, -1)  # Generic

        # New color pairs for stacktrace parts and function names:
        curses.init_pair(9, curses.COLOR_BLUE, -1)  # Function signature (general parts)
        curses.init_pair(10, curses.COLOR_GREEN, -1)  # Filename
        curses.init_pair(11, curses.COLOR_YELLOW, -1)  # Line/Column numbers
        curses.init_pair(12, curses.COLOR_YELLOW, -1)  # Function name

        token_colors = {
            Token.Comment: curses.color_pair(1),
            Token.Keyword: curses.color_pair(2),
            Token.Name: curses.color_pair(3),
            Token.String: curses.color_pair(4),
            Token.Number: curses.color_pair(5),
            Token.Operator: curses.color_pair(6),
            Token.Punctuation: curses.color_pair(7),
            Token.Generic: curses.color_pair(8),
        }
    else:
        token_colors = {}

    lexer = CppLexer()
    current_trace_idx = 0
    selected_frame = 0  # This will be our “frame index”
    frame_scroll_offset = 0
    show_full_trace = False  # Toggle: False → simplified (one line per frame), True → full code snippet

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        # Get the raw trace lines for the current trace.
        trace_lines = traces[current_trace_idx].splitlines()

        if show_full_trace:
            # In full mode, we want to show all the lines.
            lines = trace_lines
            # Compute the line numbers for frame headers (lines starting with "#")
            frame_indices = [
                i for i, line in enumerate(trace_lines) if line.lstrip().startswith("#")
            ]
            total_frames = len(frame_indices)
            if total_frames == 0:
                # No header lines found; fall back.
                selected_frame = 0
                highlighted_line = 0
                total_frames = len(lines)
            else:
                # Make sure our selected frame index is within bounds.
                if selected_frame >= total_frames:
                    selected_frame = total_frames - 1
                highlighted_line = frame_indices[selected_frame]
        else:
            # In simplified mode, we already have one line per frame.
            lines = simplify_trace(trace_lines)
            total_frames = len(lines)
            highlighted_line = (
                selected_frame  # Here the list "lines" is one frame per element.
            )

        # Adjust the scroll offset so the highlighted line is visible.
        if highlighted_line < frame_scroll_offset:
            frame_scroll_offset = highlighted_line
        elif highlighted_line >= frame_scroll_offset + (height - 1):
            frame_scroll_offset = highlighted_line - (height - 1) + 1

        # Prepare the header.
        header = (
            f"Stack trace {current_trace_idx + 1}/{len(traces)} "
            f"(Frame {selected_frame + 1}/{total_frames}) "
            f"(←/h: prev trace, →/l: next trace, ↑/k: prev frame, ↓/j: next frame, "
            f"Enter: open file, t: toggle full, q/ESC: quit)"
        )
        try:
            stdscr.addstr(0, 0, header[:width], curses.A_BOLD)
        except curses.error:
            pass

        # Render the visible lines.
        for idx in range(
            frame_scroll_offset, min(len(lines), frame_scroll_offset + (height - 1))
        ):
            y = 1 + idx - frame_scroll_offset
            # Highlight only the frame header in full mode.
            if idx == highlighted_line:
                base_attr = curses.A_REVERSE
            else:
                base_attr = 0
            render_trace_line(stdscr, y, 0, lines[idx], lexer, token_colors, base_attr)

        stdscr.refresh()
        key = stdscr.getch()

        if key in (ord("q"), 27):
            break
        elif key in (curses.KEY_LEFT, ord("h")):
            # Previous stack trace.
            if current_trace_idx > 0:
                current_trace_idx -= 1
                selected_frame = 0
                frame_scroll_offset = 0
        elif key in (curses.KEY_RIGHT, ord("l")):
            # Next stack trace.
            if current_trace_idx < len(traces) - 1:
                current_trace_idx += 1
                selected_frame = 0
                frame_scroll_offset = 0
        elif key in (curses.KEY_UP, ord("k")):
            # Move one frame up.
            if selected_frame > 0:
                selected_frame -= 1
        elif key in (curses.KEY_DOWN, ord("j")):
            # Move one frame down.
            if selected_frame < total_frames - 1:
                selected_frame += 1
        elif key in (ord("e"), curses.KEY_ENTER, 10, 13):
            # Open the file using the header of the selected frame.
            if total_frames > 0:
                if show_full_trace:
                    header_line = lines[frame_indices[selected_frame]]
                else:
                    header_line = lines[selected_frame]
                file_line_info = parse_file_and_line(header_line)
                if file_line_info:
                    filename, line_number = file_line_info
                    open_file_in_editor(stdscr, filename, line_number)
                else:
                    try:
                        stdscr.addstr(
                            height - 1,
                            0,
                            "No file information found for the selected frame. Press any key.",
                            curses.A_BOLD,
                        )
                    except curses.error:
                        pass
                    stdscr.getch()
        elif key == ord("t"):
            # Toggle between simplified and full code snippet view.
            show_full_trace = not show_full_trace
            frame_scroll_offset = 0
            selected_frame = 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python stack_viewer.py <log_file>")
        sys.exit(1)

    log_filename = sys.argv[1]
    traces = load_traces(log_filename)
    if not traces:
        print("No stack traces found using the separator.")
        sys.exit(1)

    curses.wrapper(main, traces)
