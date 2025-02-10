#!/usr/bin/env python3
import curses
import sys
import re

from pygments.lexers.c_cpp import CppLexer
from pygments.formatters.terminal import TerminalFormatter
from pygments import highlight

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
                stdscr.addstr(y, x, text[: max_width - x], current_attr)
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


def main(stdscr, traces):
    curses.curs_set(0)
    if curses.has_colors():
        curses.start_color()
        try:
            curses.use_default_colors()  # Allow use of default terminal colors.
        except Exception:
            pass

    current_idx = 0
    scroll_offset = 0  # Vertical scroll offset for the current stack trace.
    show_full_snippets = False  # Initially show the full code snippet session.

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        snippet_mode = "full" if show_full_snippets else "simplified"
        header = (
            f"Stack trace {current_idx + 1} of {len(traces)} (mode: {snippet_mode}) "
            f"(n/→: next, p/←: previous, ↑: scroll up, ↓: scroll down, t: toggle, q: quit)"
        )
        try:
            stdscr.addstr(0, 0, header[:width], curses.A_BOLD)
        except curses.error:
            pass

        # Get the trace lines. If in simplified mode, filter the lines.
        lines = traces[current_idx].splitlines()
        if not show_full_snippets:
            lines = simplify_trace(lines)

        total_lines = len(lines)
        available_lines = height - 1  # Exclude header

        if scroll_offset > max(total_lines - available_lines, 0):
            scroll_offset = max(total_lines - available_lines, 0)

        lexer = CppLexer()
        formatter = TerminalFormatter()

        highlighted_lines = []
        for line in lines:
            match = ansi_line_number_regex.match(line)
            if match:
                # Extract the line number (with ANSI codes intact) and the code portion.
                line_number = match.group("line_num")
                code_part = match.group("code")
                # Highlight only the code part.
                highlighted_code = highlight(code_part, lexer, formatter).rstrip("\n")
                # Reassemble the line with the original (already colored) line number.
                highlighted_line = f"{line_number}{highlighted_code}"
            else:
                # If no match, highlight the whole line.
                highlighted_line = highlight(line, lexer, formatter).rstrip("\n")
            highlighted_lines.append(highlighted_line)

        # Render the visible portion of the trace.
        for idx in range(
            scroll_offset, min(total_lines, scroll_offset + available_lines)
        ):
            y = idx - scroll_offset + 1  # row 0 is the header

            render_ansi_line(stdscr, y, 0, highlighted_lines[idx], width)
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord("q"), 27):  # Quit on 'q' or ESC.
            break
        elif key == ord("l") or key == curses.KEY_RIGHT:
            if current_idx < len(traces) - 1:
                current_idx += 1
                scroll_offset = 0
        elif key == ord("j") or key == curses.KEY_LEFT:
            if current_idx > 0:
                current_idx -= 1
                scroll_offset = 0
        elif key == curses.KEY_DOWN:
            if scroll_offset < total_lines - available_lines:
                scroll_offset += 1
        elif key == curses.KEY_UP:
            if scroll_offset > 0:
                scroll_offset -= 1
        elif key == ord("d") or key == curses.KEY_NPAGE:
            if scroll_offset < total_lines - available_lines:
                scroll_offset = min(
                    total_lines - available_lines, scroll_offset + height // 2
                )
        elif key == ord("u") or key == curses.KEY_PPAGE:
            if scroll_offset > 0:
                scroll_offset = max(0, scroll_offset - height // 2)
        elif key == ord("t"):
            # Toggle the snippet view mode.
            show_full_snippets = not show_full_snippets
            scroll_offset = 0  # Reset scroll when toggling


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
