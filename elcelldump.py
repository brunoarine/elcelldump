#!/usr/bin/env python3
"""
Cell Tower Identifier for Elsys Amplimax modems.

Connects to the Amplimax web interface, sends AT+CEREG commands
to the built-in AT command terminal, and displays cell tower info
including eNodeB ID and Sector.

Usage:
    python3 celltower.py                 # uses default IP 192.168.10.254
    python3 celltower.py 192.168.1.100   # custom IP
    python3 celltower.py --raw           # also show raw AT responses
"""

import argparse
import re
import sys
import time

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependencies. Install with:")
    print("  pip install requests beautifulsoup4")
    sys.exit(1)

DEFAULT_IP = "192.168.10.254"
AT_CMD_PATH = "/boafrm/formATComand"
AT_PAGE_PATH = "/send_AT_commands.htm"
TIMEOUT = 10

MNC_OPERATORS = {
    "02": "TIM", "03": "TIM", "04": "TIM",
    "05": "Claro",
    "06": "Vivo", "10": "Vivo", "11": "Vivo", "23": "Vivo",
    "15": "Sercomtel",
    "31": "Oi",
    "32": "Algar", "33": "Algar", "34": "Algar",
    "39": "Nextel",
}

STAT_CODES = {
    0: "Not registered, not searching",
    1: "Registered, home network",
    2: "Not registered, searching",
    3: "Registration denied",
    4: "Unknown",
    5: "Registered, roaming",
}


class Amplimax:
    """Interface to the Amplimax AT command terminal via its web UI."""

    def __init__(self, ip: str):
        self.base_url = f"http://{ip}"
        self.session = requests.Session()

    def send_at(self, command: str) -> str:
        """Send an AT command and return the response text."""
        resp = self.session.post(
            f"{self.base_url}{AT_CMD_PATH}",
            data={
                "COMANDO_AT": command,
                "send": "Enviar",
                "submit-url": AT_PAGE_PATH,
            },
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        textarea = soup.find("textarea", {"name": "result"})
        if textarea is None:
            raise RuntimeError("Could not find result textarea in response.")
        return textarea.get_text()

    def clear(self):
        """Clear the result textarea."""
        self.session.post(
            f"{self.base_url}{AT_CMD_PATH}",
            data={
                "limpar": "Limpar",
                "submit-url": AT_PAGE_PATH,
            },
            timeout=TIMEOUT,
            allow_redirects=True,
        )


def parse_cereg(text: str) -> dict | None:
    """Parse a +CEREG response line from AT output."""
    match = re.search(
        r'\+CEREG:\s*(\d+),(\d+),"([0-9A-Fa-f]+)","([0-9A-Fa-f]+)",(\d+)',
        text,
    )
    if not match:
        return None

    n, stat, tac_hex, ci_hex, act = match.groups()
    stat = int(stat)
    act = int(act)
    tac = int(tac_hex, 16)
    ci = int(ci_hex, 16)

    return {
        "stat": stat,
        "stat_desc": STAT_CODES.get(stat, "Unknown"),
        "tac_hex": tac_hex.upper(),
        "tac": tac,
        "ci_hex": ci_hex.upper(),
        "ci": ci,
        "act": act,
        "enb_id": ci >> 8,
        "sector": ci & 0xFF,
    }


def parse_cops(text: str) -> dict | None:
    """Parse a +COPS response line from AT output."""
    match = re.search(r'\+COPS:\s*(\d+),(\d+),"([^"]+)",(\d+)', text)
    if not match:
        return None

    mode, fmt, operator, act = match.groups()
    return {"operator": operator, "act": int(act)}


def format_output(cereg: dict, cops: dict | None) -> str:
    """Format parsed cell info for display."""
    lines = []
    lines.append("")
    lines.append("=" * 50)
    lines.append("  CELL TOWER INFORMATION")
    lines.append("=" * 50)
    lines.append("")

    if cops:
        lines.append(f"  Operator     : {cops['operator']}")

    lines.append(f"  Registration : {cereg['stat_desc']}")
    lines.append(f"  Technology   : LTE (E-UTRAN)")
    lines.append("")
    lines.append(f"  TAC (hex)    : {cereg['tac_hex']}")
    lines.append(f"  TAC (dec)    : {cereg['tac']}")
    lines.append(f"  Cell ID (hex): {cereg['ci_hex']}")
    lines.append(f"  Cell ID (dec): {cereg['ci']}")
    lines.append("")
    lines.append(f"  eNodeB ID    : {cereg['enb_id']}")
    lines.append(f"  Sector       : {cereg['sector']}")

    if cops:
        mncs = [
            mnc
            for mnc, op in MNC_OPERATORS.items()
            if op.lower() in cops["operator"].lower()
        ]
        if mncs:
            lines.append(f"  MNC: {', '.join(mncs)} ({cops['operator']})")

    lines.append("-" * 50)
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Identify the cell tower your Amplimax modem is connected to.",
    )
    parser.add_argument(
        "ip",
        nargs="?",
        default=DEFAULT_IP,
        help=f"Amplimax IP address (default: {DEFAULT_IP})",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Show raw AT command responses",
    )
    args = parser.parse_args()

    modem = Amplimax(args.ip)

    # Step 1: Clear previous results
    try:
        print(f"Connecting to Amplimax at {args.ip}...")
        modem.clear()
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to {args.ip}", file=sys.stderr)
        print(
            "Make sure the Amplimax is powered on and you are "
            "connected via Ethernet.",
            file=sys.stderr,
        )
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"Error: Connection to {args.ip} timed out.", file=sys.stderr)
        sys.exit(1)

    try:
        # Step 2: Enable verbose CEREG mode
        print("Enabling verbose CEREG mode...")
        raw_cereg2 = modem.send_at("AT+CEREG=2")
        if args.raw:
            print(f"  >> AT+CEREG=2\n{raw_cereg2.strip()}\n")
        time.sleep(0.5)

        # Step 3: Query CEREG
        print("Querying cell registration info...")
        modem.clear()
        raw_cereg = modem.send_at("AT+CEREG?")
        if args.raw:
            print(f"  >> AT+CEREG?\n{raw_cereg.strip()}\n")

        cereg = parse_cereg(raw_cereg)
        if not cereg:
            print("Error: Could not parse +CEREG response.", file=sys.stderr)
            print(f"Raw response:\n{raw_cereg.strip()}", file=sys.stderr)
            sys.exit(1)
        time.sleep(0.5)

        # Step 4: Query COPS for operator name
        print("Querying operator info...")
        modem.clear()
        raw_cops = modem.send_at("AT+COPS?")
        if args.raw:
            print(f"  >> AT+COPS?\n{raw_cops.strip()}\n")

        cops = parse_cops(raw_cops)

    except requests.exceptions.ConnectionError:
        print(f"Error: Lost connection to {args.ip}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"Error: Request timed out.", file=sys.stderr)
        sys.exit(1)
    except (requests.exceptions.HTTPError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Step 5: Display results
    print(format_output(cereg, cops))


if __name__ == "__main__":
    main()
