"""API key scopes, expiration, rotation, IP allowlisting, and token counting."""

import ipaddress
from typing import Optional

from src.core.config import settings
from src.core.logging import logger

# ── IP Allowlist ───────────────────────────────────────────────


class IPAllowlist:
    def __init__(self, allowed_cidrs: list[str] | None = None):
        self._networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        for cidr in allowed_cidrs or settings.ip_allowlist:
            try:
                self._networks.append(ipaddress.ip_network(cidr, strict=False))
            except ValueError:
                logger.warning(f"Invalid CIDR in allowlist: {cidr}")

    def is_allowed(self, ip: str) -> bool:
        if not self._networks:
            return True
        try:
            addr = ipaddress.ip_address(ip)
            return any(addr in net for net in self._networks)
        except ValueError:
            return False


_ip_allowlist: Optional[IPAllowlist] = None


def get_ip_allowlist() -> IPAllowlist:
    global _ip_allowlist
    if _ip_allowlist is None:
        _ip_allowlist = IPAllowlist()
    return _ip_allowlist


# ── Token Counter ──────────────────────────────────────────────


class TokenCounter:
    """Approximate token counting without external libraries."""

    @staticmethod
    def count(text: str) -> int:
        words = len(text.split())
        chars = len(text)
        punct = sum(1 for c in text if c in ".,!?;:\"'()[]{}")
        return max(1, int(words * 1.3 + chars * 0.25 + punct * 0.1))

    @staticmethod
    def count_batch(texts: list[str]) -> list[int]:
        return [TokenCounter.count(t) for t in texts]


token_counter = TokenCounter()
