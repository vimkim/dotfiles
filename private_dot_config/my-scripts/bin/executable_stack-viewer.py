#!/usr/bin/env python3
import curses
import sys
import re

# Separator used in the log file to split stack traces.
SEPARATOR = "Stack trace (most recent call first):"

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


def render_ansi_line(stdscr, y, x, line, max_width):
    """
    Renders a line that may include ANSI escape sequences.

    The function:
      - Searches for ANSI sequences (of the form \033[...m).
      - Splits the line into segments.
      - Updates the current color attributes accordingly.
      - Uses curses.addstr() to print each segment with the computed attribute.
    """
    ansi_escape = re.compile(r"\033\[((?:\d+;)*\d*)m")

    # Initial state: use -1 to denote default color.
    current_fg = -1
    current_bg = -1
    current_bold = False
    current_attr = get_color_attr(current_fg, current_bg, current_bold)
    pos = 0  # current position in the line

    for match in ansi_escape.finditer(line):
        start, end = match.span()
        # Print text before the escape sequence.
        if start > pos:
            text = line[pos:start]
            try:
                stdscr.addstr(y, x, text[: max_width - x], current_attr)
            except curses.error:
                pass  # Avoid errors if text overflows.
            x += len(text)
            if x >= max_width:
                return
        # Process the ANSI codes.
        code_str = match.group(1)
        codes = [int(c) for c in code_str.split(";") if c] if code_str else []
        if not codes:
            codes = [0]  # Treat empty codes as reset.
        for code in codes:
            if code == 0:
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
        pos = end  # Advance past the escape sequence.
    # Print any remaining text after the last escape sequence.
    if pos < len(line):
        text = line[pos:]
        try:
            stdscr.addstr(y, x, text[: max_width - x], current_attr)
        except curses.error:
            pass


def load_traces(filename):
    """
    Reads the log file and splits its content into stack traces using the defined separator.
    Returns a list where each element is one complete stack trace.
    """
    with open(filename, "r") as f:
        content = f.read()
    parts = [part.strip() for part in content.split(SEPARATOR) if part.strip()]
    # Prepend the separator to each trace.
    traces = [f"{SEPARATOR}\n{part}" for part in parts]
    return traces


def main(stdscr, traces):
    curses.curs_set(0)
    if curses.has_colors():
        curses.start_color()
        try:
            curses.use_default_colors()
        except Exception:
            pass

    current_idx = 0
    scroll_offset = 0  # Vertical scroll offset for the current stack trace.

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        header = (
            f"Stack trace {current_idx + 1} of {len(traces)} "
            f"(n/→: next, p/←: previous, ↑: scroll up, ↓: scroll down, q: quit)"
        )
        try:
            stdscr.addstr(0, 0, header[:width], curses.A_BOLD)
        except curses.error:
            pass

        # Prepare the current trace lines.
        lines = traces[current_idx].splitlines()
        total_lines = len(lines)
        available_lines = height - 1  # Lines available for the trace after the header.

        # Adjust scroll_offset if necessary.
        if scroll_offset > max(total_lines - available_lines, 0):
            scroll_offset = max(total_lines - available_lines, 0)

        # Render visible portion.
        for idx in range(
            scroll_offset, min(total_lines, scroll_offset + available_lines)
        ):
            y = idx - scroll_offset + 1  # offset by header line
            render_ansi_line(stdscr, y, 0, lines[idx], width)
        stdscr.refresh()

        # Get user input.
        key = stdscr.getch()
        if key in (ord("q"), 27):  # 'q' or ESC quits.
            break
        elif key == ord("n") or key == curses.KEY_RIGHT:
            if current_idx < len(traces) - 1:
                current_idx += 1
                scroll_offset = 0
        elif key == ord("p") or key == curses.KEY_LEFT:
            if current_idx > 0:
                current_idx -= 1
                scroll_offset = 0
        elif key == curses.KEY_DOWN:
            if scroll_offset < total_lines - available_lines:
                scroll_offset += 1
        elif key == curses.KEY_UP:
            if scroll_offset > 0:
                scroll_offset -= 1
        # You may extend with additional keys (like page up/down) if desired.


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
