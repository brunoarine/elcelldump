# Amplimax Cell Tower Identifier

A CLI tool to identify the cell tower your Elsys Amplimax modem is connected to. It queries the modem's web interface and displays eNodeB ID, sector, TAC, and operator information.

## How It Works

The tool connects to the Amplimax web interface and sends AT commands to the built-in **Quectel** LTE module (EC25 series) through the AT command terminal page. It uses:

- `AT+CEREG=2` — Enables verbose EPS network registration status
- `AT+CEREG?` — Queries cell registration info (TAC, Cell ID)
- `AT+COPS?` — Queries operator name

The Cell ID is parsed to extract the eNodeB ID (upper 24 bits) and sector number (lower 8 bits).

## Installation

Using `uv`:

```bash
uv venv && source .venv/bin/activate
uv pip install requests beautifulsoup4
```

Or with pip:

```bash
pip install requests beautifulsoup4
```

## Usage

```bash
# Default IP (192.168.10.254)
uv run elcelldump.py

# Custom IP
uv run elcelldump.py 192.168.1.100

# Show raw AT responses
uv run elcelldump.py --raw
```

## Requirements

- Amplimax modem connected via Ethernet
- Web interface accessible at the modem's IP address
