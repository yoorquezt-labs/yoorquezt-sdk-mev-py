"""Formatting utilities for Q MEV AI SDK."""

from __future__ import annotations

import re

ETH_DECIMALS = 18
GWEI_DECIMALS = 9


def format_wei(wei: str | int) -> str:
    """Format a wei value as a human-readable ETH string.

    Example: format_wei("1000000000000000000") => "1.0 ETH"
    """
    value = int(wei)
    whole = value // 10**ETH_DECIMALS
    remainder = value % 10**ETH_DECIMALS
    decimal = str(remainder).zfill(ETH_DECIMALS)[:6].rstrip("0") or "0"
    return f"{whole}.{decimal} ETH"


def format_gwei(gwei: float | str) -> str:
    """Format a gwei value as a human-readable string.

    Example: format_gwei(30.5) => "30.5 gwei"
    """
    value = float(gwei)
    return f"{value} gwei"


def parse_wei(eth: str) -> int:
    """Parse an ETH string to wei as an integer.

    Example: parse_wei("1.5") => 1500000000000000000
    """
    parts = eth.split(".")
    whole = int(parts[0]) * 10**ETH_DECIMALS
    if len(parts) == 1:
        return whole
    decimal_str = parts[1][:ETH_DECIMALS].ljust(ETH_DECIMALS, "0")
    return whole + int(decimal_str)


def truncate_address(address: str, chars: int = 4) -> str:
    """Truncate an Ethereum address for display.

    Example: truncate_address("0xabcdef...ef12") => "0xabcd...ef12"
    """
    if len(address) <= chars * 2 + 2:
        return address
    return f"{address[:chars + 2]}...{address[-chars:]}"


def is_valid_address(address: str) -> bool:
    """Validate an Ethereum address (0x-prefixed, 40 hex chars)."""
    return bool(re.match(r"^0x[0-9a-fA-F]{40}$", address))


def format_duration(ms: int) -> str:
    """Format a duration in milliseconds to a human-readable string.

    Example: format_duration(90000) => "1m 30s"
    """
    if ms < 1000:
        return f"{ms}ms"
    seconds = ms // 1000
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    if minutes < 60:
        if remaining_seconds > 0:
            return f"{minutes}m {remaining_seconds}s"
        return f"{minutes}m"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    if remaining_minutes > 0:
        return f"{hours}h {remaining_minutes}m"
    return f"{hours}h"


def format_percent(rate: float) -> str:
    """Format a rate (0-1) as a percentage string.

    Example: format_percent(0.956) => "95.60%"
    """
    return f"{rate * 100:.2f}%"
