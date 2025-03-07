import gdb
import os
from datetime import datetime


class DumpCommand(gdb.Command):
    """Dumps the result of a GDB expression to a file.
    Usage: dump [filename] <expression>
    If filename is omitted, output goes to gdb_output.log"""

    def __init__(self):
        super(DumpCommand, self).__init__("dump", gdb.COMMAND_DATA)

    def invoke(self, arg, from_tty):
        args = gdb.string_to_argv(arg)
        if len(args) < 1:
            print("Usage: dump [filename] <expression>")
            return

        # If only one argument is provided, use default filename
        if len(args) == 1:
            filename = "gdb_output.log"
            expression = args[0]
        else:
            filename = args[0]
            expression = " ".join(args[1:])

        try:
            # Evaluate the expression
            result = gdb.execute(f"p {expression}", to_string=True)

            # Add timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            output = f"--- {timestamp} ---\n{expression}:\n{result}\n\n"

            # Append to file
            with open(filename, "a") as f:
                f.write(output)

            print(f"Output saved to {filename}")
        except Exception as e:
            print(f"Error: {e}")


DumpCommand()
