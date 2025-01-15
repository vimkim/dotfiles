#!/usr/bin/env python3
import subprocess
import re
from colorama import init, Fore, Style

# Initialize colorama
init()


def run_ss_command():
    """Execute ss command and return its output"""
    try:
        result = subprocess.run(
            ["ss", "-tulpn"], capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Error running ss command: {e}{Style.RESET_ALL}")
        exit(1)
    except FileNotFoundError:
        print(
            f"{Fore.RED}Error: ss command not found. Please install iproute2 package.{Style.RESET_ALL}"
        )
        exit(1)


def parse_ss_line(line):
    """Parse a single line of ss output"""
    parts = line.strip().split()
    if len(parts) < 5 or parts[0] == "Netid":  # Skip header and invalid lines
        return None

    protocol = parts[0]

    # Extract local address and port
    local_addr = parts[4]
    local_port = local_addr.split(":")[-1]

    # Extract peer address and port
    peer_addr = parts[5]

    # Extract process info if it exists
    process = " ".join(parts[6:]) if len(parts) > 6 else ""

    try:
        port_num = int(local_port)
    except ValueError:
        if local_port == "*":
            port_num = 0
        else:
            return None

    return {
        "protocol": protocol,
        "state": parts[1],
        "local_addr": local_addr,
        "peer_addr": peer_addr,
        "port": port_num,
        "process": process,
    }


def colorize_port(port):
    """Apply color to port number based on its range"""
    if port < 1024:
        return f"{Fore.RED}{port}{Style.RESET_ALL}"  # System ports in red
    elif port < 49152:
        return f"{Fore.YELLOW}{port}{Style.RESET_ALL}"  # Registered ports in yellow
    else:
        return f"{Fore.GREEN}{port}{Style.RESET_ALL}"  # Dynamic ports in green


def colorize_state(state):
    """Apply color to connection state"""
    if state == "LISTEN":
        return f"{Fore.CYAN}{state}{Style.RESET_ALL}"
    elif state == "UNCONN":
        return f"{Fore.BLUE}{state}{Style.RESET_ALL}"
    else:
        return state


def main():
    # Get ss output
    ss_output = run_ss_command()

    # Parse and store valid entries
    entries = []
    for line in ss_output.split("\n"):
        parsed = parse_ss_line(line)
        if parsed:
            entries.append(parsed)

    # Sort by port number
    sorted_entries = sorted(entries, key=lambda x: x["port"])

    # Print header
    print(
        f"\n{Fore.WHITE}{Style.BRIGHT}{'Protocol':<8} {'State':<10} {'Port':<10} "
        f"{'Local Address':<30} {'Peer Address':<20} Process{Style.RESET_ALL}"
    )
    print("-" * 90)

    # Print sorted entries
    for entry in sorted_entries:
        print(
            f"{Fore.MAGENTA}{entry['protocol']:<8}{Style.RESET_ALL} "
            f"{colorize_state(entry['state']):<10} "
            f"{colorize_port(entry['port']):<10} "
            f"{entry['local_addr']:<30} "
            f"{entry['peer_addr']:<20} "
            f"{Fore.GREEN}{entry['process']}{Style.RESET_ALL}"
        )

    print(f"\n{Fore.WHITE}{Style.BRIGHT}Color Legend:{Style.RESET_ALL}")
    print(f"{Fore.RED}Red Ports:{Style.RESET_ALL} System ports (0-1023)")
    print(f"{Fore.YELLOW}Yellow Ports:{Style.RESET_ALL} Registered ports (1024-49151)")
    print(
        f"{Fore.GREEN}Green Ports:{Style.RESET_ALL} Dynamic/Private ports (49152-65535)"
    )
    print(f"{Fore.CYAN}Cyan State:{Style.RESET_ALL} LISTEN state")
    print(f"{Fore.BLUE}Blue State:{Style.RESET_ALL} UNCONN state")


if __name__ == "__main__":
    main()
