#!/usr/bin/env python3
import curses
import sys

SEPARATOR = "Stack trace (most recent call first):"


def load_traces(filename):
    """
    Reads the entire file and splits it into separate stack traces using the separator.
    Returns a list of strings where each string is one complete stack trace.
    """
    with open(filename, "r") as f:
        content = f.read()

    # Split by the separator.
    # The split might leave an empty string before the first occurrence;
    # filter out empty parts.
    parts = [part.strip() for part in content.split(SEPARATOR) if part.strip()]
    # Optionally, prepend the separator back to each trace to keep a consistent header.
    traces = [f"{SEPARATOR}\n{part}" for part in parts]
    return traces


def main(stdscr, traces):
    # Hide the cursor.
    curses.curs_set(0)
    # Start with the first trace.
    current_idx = 0

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        # Prepare a header with instructions and current trace info.
        header = (
            f"Stack trace {current_idx + 1} of {len(traces)} "
            f"(n: next, p: previous, q: quit)"
        )
        stdscr.addstr(0, 0, header[:width], curses.A_BOLD)

        # Retrieve the current stack trace and split it into lines.
        lines = traces[current_idx].splitlines()
        # Display each line (starting at row 1)
        for i, line in enumerate(lines, start=1):
            if i >= height:
                break  # stop printing if you run out of screen space
            stdscr.addstr(i, 0, line[:width])
        stdscr.refresh()

        # Wait for user input.
        key = stdscr.getch()
        if key in (ord("q"), 27):  # 'q' or ESC to quit
            break
        elif key == ord("n"):
            # Go to next trace if available.
            if current_idx < len(traces) - 1:
                current_idx += 1
        elif key == ord("p"):
            # Go to previous trace if available.
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

    # Initialize curses and start the main loop.
    curses.wrapper(main, traces)
