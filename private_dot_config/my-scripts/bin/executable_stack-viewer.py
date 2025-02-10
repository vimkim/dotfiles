#!/usr/bin/env python3
import curses
import os
import re
import subprocess
import sys

from pygments import highlight
from pygments.formatters.terminal import TerminalFormatter
from pygments.lexers.c_cpp import CppLexer

# ---------------------------------------------------------------------------
# Constants and Regular Expressions
# ---------------------------------------------------------------------------

SEPARATOR = "Stack trace (most recent call first):"
DEFAULT_EDITOR = os.environ.get("EDITOR", "nvim")  # Default editor if not set.

# Regex to remove ANSI escape sequences.
ANSI_ESCAPE_REGEX = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

# Regex for finding ANSI SGR (Select Graphic Rendition) codes.
ANSI_SGR_REGEX = re.compile(r"\033\[((?:\d+;)*\d*)m")

# Regex to capture a line number and the code from a stack frame header.
ANSI_LINE_NUMBER_REGEX = re.compile(
    r"^(?P<line_num>(?:\x1b\[[0-9;]*m)*\s*\d+:\s*(?:\x1b\[[0-9;]*m)*)(?P<code>.*)$"
)

# Mapping from ANSI SGR codes (foreground) to curses colors.
ANSI_FG_COLORS = {
    30: curses.COLOR_BLACK,
    31: curses.COLOR_RED,
    32: curses.COLOR_GREEN,
    33: curses.COLOR_YELLOW,
    34: curses.COLOR_BLUE,
    35: curses.COLOR_MAGENTA,
    36: curses.COLOR_CYAN,
    37: curses.COLOR_WHITE,
}

# Mapping from ANSI SGR codes (background) to curses colors.
ANSI_BG_COLORS = {
    40: curses.COLOR_BLACK,
    41: curses.COLOR_RED,
    42: curses.COLOR_GREEN,
    43: curses.COLOR_YELLOW,
    44: curses.COLOR_BLUE,
    45: curses.COLOR_MAGENTA,
    46: curses.COLOR_CYAN,
    47: curses.COLOR_WHITE,
}

# Global cache for curses color pairs.
color_pair_cache = {}
next_color_pair = 1

# ---------------------------------------------------------------------------
# ANSI & Curses Helper Functions
# ---------------------------------------------------------------------------


def get_color_attr(fg: int, bg: int, bold: bool) -> int:
    """
    Returns a curses attribute composed of a color pair (fg, bg)
    and adds the bold attribute if specified.

    The function caches created color pairs to avoid reinitialization.
    """
    global color_pair_cache, next_color_pair
    key = (fg, bg)
    if key not in color_pair_cache:
        curses.init_pair(next_color_pair, fg, bg)
        color_pair_cache[key] = next_color_pair
        next_color_pair += 1
    attr = curses.color_pair(color_pair_cache[key])
    if bold:
        attr |= curses.A_BOLD
    return attr


def render_ansi_line(
    stdscr: curses.window,
    y: int,
    x: int,
    line: str,
    max_width: int,
    extra_attr: int = 0,
) -> None:
    """
    Render a line that may contain ANSI escape sequences on the given curses window.
    An extra attribute (e.g. reverse video) can be combined via extra_attr.
    """
    current_fg = -1  # Default foreground (terminal default)
    current_bg = -1  # Default background (terminal default)
    current_bold = False
    current_attr = get_color_attr(current_fg, current_bg, current_bold)
    pos = 0  # Current position in the line

    # Process each ANSI SGR code in the line.
    for match in ANSI_SGR_REGEX.finditer(line):
        start, end = match.span()
        # Print text preceding the ANSI escape sequence.
        if start > pos:
            text = line[pos:start]
            try:
                stdscr.addstr(y, x, text[: max_width - x], current_attr | extra_attr)
            except curses.error:
                pass  # Ignore if text goes off-screen.
            x += len(text)
            if x >= max_width:
                return

        # Process the ANSI codes.
        code_str = match.group(1)
        codes = [int(c) for c in code_str.split(";") if c] if code_str else []
        if not codes:
            codes = [0]  # Reset if no codes are provided.
        for code in codes:
            if code == 0:
                # Reset attributes.
                current_fg = -1
                current_bg = -1
                current_bold = False
            elif code == 1:
                current_bold = True
            elif 30 <= code <= 37:
                current_fg = ANSI_FG_COLORS.get(code, current_fg)
            elif 40 <= code <= 47:
                current_bg = ANSI_BG_COLORS.get(code, current_bg)
        current_attr = get_color_attr(current_fg, current_bg, current_bold)
        pos = end

    # Render any remaining text after the last ANSI escape.
    if pos < len(line):
        text = line[pos:]
        try:
            stdscr.addstr(y, x, text[: max_width - x], current_attr | extra_attr)
        except curses.error:
            pass


# ---------------------------------------------------------------------------
# Trace Processing Functions
# ---------------------------------------------------------------------------


def load_traces(filename: str) -> list[str]:
    """
    Load stack traces from a file by splitting on the designated separator.
    Returns a list of trace strings (each prepended with the separator).
    """
    with open(filename, "r") as f:
        content = f.read()
    parts = [part.strip() for part in content.split(SEPARATOR) if part.strip()]
    traces = [f"{SEPARATOR}\n{part}" for part in parts]
    return traces


def simplify_trace(lines: list[str]) -> list[str]:
    """
    Given the lines of a stack trace, return a simplified list where each stack frame
    is reduced to its header line. If a header is followed by extra snippet lines,
    " ...." is appended.
    """
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


def strip_ansi(text: str) -> str:
    """
    Remove ANSI escape sequences from the text.
    """
    return ANSI_ESCAPE_REGEX.sub("", text)


def parse_file_and_line(text: str) -> tuple[str, int] | None:
    """
    Parse a file path and a line number from a stack frame header.
    It expects a pattern like 'at <filename>:<line>' in the text.
    Returns (filename, line_number) if successful, or None otherwise.
    """
    clean_text = strip_ansi(text)
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
# Display Helper Functions
# ---------------------------------------------------------------------------


def draw_header(
    stdscr: curses.window,
    current_trace: int,
    total_traces: int,
    selected_frame: int,
    total_frames: int,
    width: int,
) -> None:
    """
    Draw the header containing navigation instructions and the current trace/frame info.
    """
    header = (
        f"Stack trace {current_trace + 1}/{total_traces} "
        f"(Frame {selected_frame + 1}/{total_frames}) "
        f"(←/h: prev trace, →/l: next trace, ↑/↓: select frame, Enter: open file, q/ESC: quit)"
    )
    try:
        stdscr.addstr(0, 0, header[:width], curses.A_BOLD)
    except curses.error:
        pass


def display_trace_frames(
    stdscr: curses.window,
    frames: list[str],
    selected_index: int,
    scroll_offset: int,
    available_lines: int,
    width: int,
    lexer: CppLexer,
    formatter: TerminalFormatter,
) -> None:
    """
    Render the list of stack frames on the screen, applying syntax highlighting.
    The selected frame is highlighted with a reverse video attribute.
    """
    for idx in range(scroll_offset, min(len(frames), scroll_offset + available_lines)):
        y = 1 + idx - scroll_offset  # row 0 is reserved for the header
        extra_attr = curses.A_REVERSE if idx == selected_index else 0

        frame_line = frames[idx]
        match = ANSI_LINE_NUMBER_REGEX.match(frame_line)
        if match:
            line_number_part = match.group("line_num")
            code_part = match.group("code")
            highlighted_code = highlight(code_part, lexer, formatter).rstrip("\n")
            highlighted_line = f"{line_number_part}{highlighted_code}"
        else:
            highlighted_line = highlight(frame_line, lexer, formatter).rstrip("\n")

        render_ansi_line(stdscr, y, 0, highlighted_line, width, extra_attr)


# ---------------------------------------------------------------------------
# Main Curses Loop
# ---------------------------------------------------------------------------


def main(stdscr: curses.window, traces: list[str]) -> None:
    """
    The main loop for the stack trace viewer.
    Handles screen drawing, navigation, and user input.
    """
    # Configure curses.
    curses.curs_set(0)
    if curses.has_colors():
        curses.start_color()
        try:
            curses.use_default_colors()
        except Exception:
            pass

    # Navigation state.
    current_trace_idx = 0  # Index into the list of traces.
    selected_frame = 0  # Selected frame within the current trace.
    frame_scroll_offset = 0

    # Initialize Pygments for C/C++ syntax highlighting.
    lexer = CppLexer()
    formatter = TerminalFormatter()

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        # Process the current trace.
        trace_lines = traces[current_trace_idx].splitlines()
        simplified_frames = simplify_trace(trace_lines)
        total_frames = len(simplified_frames)

        # Ensure the selected frame is within bounds.
        if total_frames == 0:
            selected_frame = 0
        elif selected_frame >= total_frames:
            selected_frame = total_frames - 1

        # Adjust scrolling so that the selected frame is visible.
        available_lines = height - 1  # Reserve the top line for header.
        if selected_frame < frame_scroll_offset:
            frame_scroll_offset = selected_frame
        elif selected_frame >= frame_scroll_offset + available_lines:
            frame_scroll_offset = selected_frame - available_lines + 1

        # Draw header and frames.
        draw_header(
            stdscr, current_trace_idx, len(traces), selected_frame, total_frames, width
        )
        display_trace_frames(
            stdscr,
            simplified_frames,
            selected_frame,
            frame_scroll_offset,
            available_lines,
            width,
            lexer,
            formatter,
        )

        stdscr.refresh()
        key = stdscr.getch()

        # Process user input.
        if key in (ord("q"), 27):  # Quit on 'q' or ESC.
            break
        elif key in (curses.KEY_LEFT, ord("h")):
            # Go to the previous trace.
            if current_trace_idx > 0:
                current_trace_idx -= 1
                selected_frame = 0
                frame_scroll_offset = 0
        elif key in (curses.KEY_RIGHT, ord("l")):
            # Go to the next trace.
            if current_trace_idx < len(traces) - 1:
                current_trace_idx += 1
                selected_frame = 0
                frame_scroll_offset = 0
        elif key == curses.KEY_UP:
            # Move selection up.
            if selected_frame > 0:
                selected_frame -= 1
        elif key == curses.KEY_DOWN:
            # Move selection down.
            if selected_frame < total_frames - 1:
                selected_frame += 1
        elif key in (curses.KEY_ENTER, 10, 13):
            # Attempt to open the file in the editor based on the selected frame.
            if total_frames > 0:
                selected_line = simplified_frames[selected_frame]
                file_line_info = parse_file_and_line(selected_line)
                if file_line_info:
                    filename, line_number = file_line_info
                    open_file_in_editor(stdscr, filename, line_number)
                else:
                    # Inform the user if no file information was found.
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


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

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
