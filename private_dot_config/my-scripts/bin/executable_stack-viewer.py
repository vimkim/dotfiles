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
    # Regular expression to match ANSI escape sequences (SGR codes)
    ansi_escape = re.compile(r"\033\[((?:\d+;)*\d*)m")

    # Initial state (using -1 to indicate the terminal's default color)
    current_fg = -1
    current_bg = -1
    current_bold = False
    current_attr = get_color_attr(current_fg, current_bg, current_bold)
    pos = 0  # current position in the line

    # Process each ANSI escape sequence found in the line.
    for match in ansi_escape.finditer(line):
        start, end = match.span()
        # Print the text before this escape sequence.
        if start > pos:
            text = line[pos:start]
            try:
                stdscr.addstr(y, x, text[: max_width - x], current_attr)
            except curses.error:
                pass  # Avoid curses errors if text overflows
            x += len(text)
            if x >= max_width:
                return
        # Parse the escape code numbers.
        code_str = match.group(1)
        codes = [int(c) for c in code_str.split(";") if c] if code_str else []
        # If no code is provided, ANSI treats it as a reset.
        if not codes:
            codes = [0]
        # Update the current attribute state for each code.
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
            # Extend here for additional ANSI codes if needed.
        current_attr = get_color_attr(current_fg, current_bg, current_bold)
        pos = end  # Move past the escape sequence.
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
    # Split by separator and filter out empty parts.
    parts = [part.strip() for part in content.split(SEPARATOR) if part.strip()]
    # Optionally prepend the separator back to each trace.
    traces = [f"{SEPARATOR}\n{part}" for part in parts]
    return traces


def main(stdscr, traces):
    curses.curs_set(0)
    if curses.has_colors():
        curses.start_color()
        try:
            curses.use_default_colors()  # Allow use of default terminal colors.
        except Exception:
            pass
    current_idx = 0

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        header = (
            f"Stack trace {current_idx + 1} of {len(traces)} "
            f"(n: next, p: previous, q: quit)"
        )
        try:
            stdscr.addstr(0, 0, header[:width], curses.A_BOLD)
        except curses.error:
            pass

        # Split the current trace into lines and print them one by one.
        lines = traces[current_idx].splitlines()
        for i, line in enumerate(lines, start=1):
            if i >= height:
                break
            # Use the ANSI-aware rendering function.
            render_ansi_line(stdscr, i, 0, line, width)
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord("q"), 27):  # Quit on 'q' or ESC.
            break
        elif key == ord("n"):
            if current_idx < len(traces) - 1:
                current_idx += 1
        elif key == ord("p"):
            if current_idx > 0:
                current_idx -= 1


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
