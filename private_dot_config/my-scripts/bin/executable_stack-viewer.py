#!/usr/bin/env python3
import curses
import sys
import re
import os
import subprocess

from pygments.lexers.c_cpp import CppLexer
from pygments.formatters.terminal import TerminalFormatter
from pygments import highlight

# Separator used in the log file to split stack traces.
SEPARATOR = "Stack trace (most recent call first):"

# Regex for stripping ANSI escape sequences.
ansi_escape = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

# Mapping from ANSI SGR codes to curses colors.
ansi_fg_colors = {
    30: curses.COLOR_BLACK,
    31: curses.COLOR_RED,
    32: curses.COLOR_GREEN,
    33: curses.COLOR_YELLOW,
    34: curses.COLOR_BLUE,
    35: curses.COLOR_MAGENTA,
    36: curses.COLOR_CYAN,
    37: curses.COLOR_WHITE,
}

ansi_bg_colors = {
    40: curses.COLOR_BLACK,
    41: curses.COLOR_RED,
    42: curses.COLOR_GREEN,
    43: curses.COLOR_YELLOW,
    44: curses.COLOR_BLUE,
    45: curses.COLOR_MAGENTA,
    46: curses.COLOR_CYAN,
    47: curses.COLOR_WHITE,
}

ansi_line_number_regex = re.compile(
    r"^(?P<line_num>(?:\x1b\[[0-9;]*m)*\s*\d+:\s*(?:\x1b\[[0-9;]*m)*)(?P<code>.*)$"
)

# Global cache for our color pairs.
color_pair_cache = {}
next_color_pair = 1


def get_color_attr(fg, bg, bold):
    """
    Returns a curses attribute composed of a color pair (for the given fg and bg)
    combined with bold if needed. This function maintains a cache to re-use color pairs.
    """
    global color_pair_cache, next_color_pair
    key = (fg, bg)
    if key not in color_pair_cache:
        # When fg or bg is -1, we attempt to use the terminal default.
        curses.init_pair(next_color_pair, fg, bg)
        color_pair_cache[key] = next_color_pair
        next_color_pair += 1
    attr = curses.color_pair(color_pair_cache[key])
    if bold:
        attr |= curses.A_BOLD
    return attr


def render_ansi_line(stdscr, y, x, line, max_width, extra_attr=0):
    """
    Renders a line that may include ANSI escape sequences.
    An additional attribute (e.g. A_REVERSE) can be OR’ed via extra_attr.

    The function:
      - Searches for ANSI sequences (of the form \033[...m).
      - Splits the line into segments.
      - Updates the current color attributes accordingly.
      - Uses curses.addstr() to print each segment with the computed attribute.
    """
    ansi_escape = re.compile(r"\033\[((?:\d+;)*\d*)m")

    # Initial state (using -1 to indicate the terminal's default color)
    current_fg = -1
    current_bg = -1
    current_bold = False
    current_attr = get_color_attr(current_fg, current_bg, current_bold)
    pos = 0  # current position in the line

    for match in ansi_escape.finditer(line):
        start, end = match.span()
        # Print the text before the escape sequence.
        if start > pos:
            text = line[pos:start]
            try:
                stdscr.addstr(y, x, text[: max_width - x], current_attr | extra_attr)
            except curses.error:
                pass  # Avoid curses errors if text overflows
            x += len(text)
            if x >= max_width:
                return
        # Process the ANSI codes.
        code_str = match.group(1)
        codes = [int(c) for c in code_str.split(";") if c] if code_str else []
        # If no code is provided, ANSI treats it as a reset.
        if not codes:
            codes = [0]
        for code in codes:
            if code == 0:
                # Reset to defaults.
                current_fg = -1
                current_bg = -1
                current_bold = False
            elif code == 1:
                current_bold = True
            elif 30 <= code <= 37:
                current_fg = ansi_fg_colors.get(code, current_fg)
            elif 40 <= code <= 47:
                current_bg = ansi_bg_colors.get(code, current_bg)
        current_attr = get_color_attr(current_fg, current_bg, current_bold)
        pos = end  # Move past the escape sequence.
    # Print any remaining text after the last escape sequence.
    if pos < len(line):
        text = line[pos:]
        try:
            stdscr.addstr(y, x, text[: max_width - x], current_attr | extra_attr)
        except curses.error:
            pass


def load_traces(filename):
    """
    Reads the log file and splits its content into stack traces using the defined separator.
    Returns a list where each element is one complete stack trace.
    """
    with open(filename, "r") as f:
        content = f.read()
    # Split by separator and filter out empty parts.
    parts = [part.strip() for part in content.split(SEPARATOR) if part.strip()]
    # Prepend the separator back to each trace.
    traces = [f"{SEPARATOR}\n{part}" for part in parts]
    return traces


def simplify_trace(lines):
    """
    Given a list of lines for a trace, returns a simplified list where each stack frame
    is represented by only its header line (i.e. lines that start with '#' after stripping)
    followed by " ...." if the header was followed by additional snippet lines.
    """
    simplified = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("#"):
            header_line = line
            # Check for additional snippet lines (non-header lines) following this header.
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


def strip_ansi(text):
    """Remove any ANSI escape sequences from the text."""
    return ansi_escape.sub("", text)


def parse_file_and_line(text):
    """
    Extracts a file path and line number from a stack frame header.
    It expects the file info to appear after the keyword "at".
    Returns a tuple (filename, line_number) or None if no match is found.
    """
    clean_text = strip_ansi(text)
    # Use a non-greedy match for the file name so that only the first colon is used
    m = re.search(r"\bat\s+(?P<file>\S+?)(?=:\d+\b):(?P<line>\d+)\b", clean_text)
    if m:
        return m.group("file"), int(m.group("line"))
    else:
        return None


def open_file_in_editor(stdscr, filename, line_number):
    """
    Exits curses mode, opens the file in the editor at the specified line,
    and then reinitializes curses.
    """
    curses.endwin()
    editor = os.environ.get("EDITOR", "nvim")  # Default to neovim if desired.
    try:
        subprocess.call([editor, f"+{line_number}", filename])
    except Exception as e:
        print("Failed to open editor:", e)
    stdscr.clear()
    curses.doupdate()


def main(stdscr, traces):
    # Initialize the curses settings.
    curses.curs_set(0)
    if curses.has_colors():
        curses.start_color()
        try:
            curses.use_default_colors()  # Allow use of default terminal colors.
        except Exception:
            pass

    # Use the simplified view for selection (each stack frame is one line).
    current_trace_idx = 0  # Which trace (among multiple traces) is active.
    selected_frame = 0  # Which frame (line) is selected in the current trace.
    frame_scroll_offset = (
        0  # For cases when the number of frames exceeds the screen height.
    )

    lexer = CppLexer()
    formatter = TerminalFormatter()

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        # Split the current trace into lines and then simplify it to just one header per frame.
        trace_lines = traces[current_trace_idx].splitlines()
        simplified_frames = simplify_trace(trace_lines)
        total_frames = len(simplified_frames)

        # Ensure our selected frame index is within bounds.
        if total_frames == 0:
            selected_frame = 0
        elif selected_frame >= total_frames:
            selected_frame = total_frames - 1

        # Adjust scrolling so that the selected frame is visible.
        available_lines = height - 1  # Reserve the top line for the header.
        if selected_frame < frame_scroll_offset:
            frame_scroll_offset = selected_frame
        elif selected_frame >= frame_scroll_offset + available_lines:
            frame_scroll_offset = selected_frame - available_lines + 1

        # Header with instructions.
        header = (
            f"Stack trace {current_trace_idx + 1}/{len(traces)} "
            f"(Frame {selected_frame + 1}/{total_frames}) "
            f"(←/h: prev trace, →/l: next trace, ↑/↓: select frame, Enter: open file, q/ESC: quit)"
        )
        try:
            stdscr.addstr(0, 0, header[:width], curses.A_BOLD)
        except curses.error:
            pass

        # Render the visible portion of the stack frames.
        for idx in range(
            frame_scroll_offset,
            min(total_frames, frame_scroll_offset + available_lines),
        ):
            y = 1 + idx - frame_scroll_offset  # row 0 is the header
            extra_attr = curses.A_REVERSE if idx == selected_frame else 0

            # Use the same highlighting logic as before.
            match = ansi_line_number_regex.match(simplified_frames[idx])
            if match:
                line_number = match.group("line_num")
                code_part = match.group("code")
                highlighted_code = highlight(code_part, lexer, formatter).rstrip("\n")
                highlighted_line = f"{line_number}{highlighted_code}"
            else:
                highlighted_line = highlight(
                    simplified_frames[idx], lexer, formatter
                ).rstrip("\n")

            render_ansi_line(stdscr, y, 0, highlighted_line, width, extra_attr)

        stdscr.refresh()
        key = stdscr.getch()

        if key in (ord("q"), 27):  # Quit on 'q' or ESC.
            break
        elif key in (curses.KEY_LEFT, ord("h")):
            # Go to the previous stack trace.
            if current_trace_idx > 0:
                current_trace_idx -= 1
                selected_frame = 0
                frame_scroll_offset = 0
        elif key in (curses.KEY_RIGHT, ord("l")):
            # Go to the next stack trace.
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
            # Open the file in the editor based on the selected stack frame.
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


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python stack_viewer.py <log_file>")
        sys.exit(1)

    filename = sys.argv[1]
    traces = load_traces(filename)
    if not traces:
        print("No stack traces found using the separator.")
        sys.exit(1)

    curses.wrapper(main, traces)
