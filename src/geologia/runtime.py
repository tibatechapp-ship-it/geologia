"""Shared runtime configuration validation for GEOLOGIA entry points."""
import argparse


def parse_port(value: str | int) -> int:
    """Parse a TCP port and reject values outside the valid non-privileged range."""
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port
