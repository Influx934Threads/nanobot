"""Network security utilities — SSRF protection and internal URL detection."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
from pathlib import Path
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Blocked private/internal networks (SSRF protection)
# ---------------------------------------------------------------------------
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),   # carrier-grade NAT
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),   # link-local / cloud metadata
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),          # unique local
    ipaddress.ip_network("fe80::/10"),         # link-local v6
]

# ---------------------------------------------------------------------------
# Allowlist — loaded from ~/.nanobot/config.json → tools → networkAllowlist
# ---------------------------------------------------------------------------
_ALLOWED_IPS: set[str] = set()
_ALLOWED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
_ALLOWLIST_LOADED = False

_URL_RE = re.compile(r"https?://[^\s\"'`;|<>]+", re.IGNORECASE)


def _load_allowlist():
    """Load the private-IP allowlist from config.json (lazy, once)."""
    global _ALLOWED_IPS, _ALLOWED_NETWORKS, _ALLOWLIST_LOADED
    if _ALLOWLIST_LOADED:
        return

    home = os.environ.get("HOME", "")
    config_path = Path(home) / ".nanobot" / "config.json"
    if not config_path.exists():
        _ALLOWLIST_LOADED = True
        return

    try:
        with open(config_path, "r") as f:
            data = json.load(f)
        tools_cfg = data.get("tools", {})
        entries = tools_cfg.get("networkAllowlist", [])
    except Exception:
        _ALLOWLIST_LOADED = True
        return

    for entry in entries:
        try:
            addr = ipaddress.ip_address(entry)
            _ALLOWED_IPS.add(str(addr))
        except ValueError:
            try:
                net = ipaddress.ip_network(entry, strict=False)
                _ALLOWED_NETWORKS.append(net)
            except ValueError:
                pass  # skip invalid silently

    _ALLOWLIST_LOADED = True


def _is_private(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an address is in a blocked private/internal range.

    Addresses in the allowlist (config.json → tools → networkAllowlist) are
    exempted and will return False (i.e. NOT private).
    """
    _load_allowlist()

    # Allowlist takes priority
    if str(addr) in _ALLOWED_IPS:
        return False
    for net in _ALLOWED_NETWORKS:
        if addr in net:
            return False

    return any(addr in net for net in _BLOCKED_NETWORKS)


def validate_url_target(url: str) -> tuple[bool, str]:
    """Validate a URL is safe to fetch: scheme, hostname, and resolved IPs.

    Returns (ok, error_message).  When ok is True, error_message is empty.
    """
    try:
        p = urlparse(url)
    except Exception as e:
        return False, str(e)

    if p.scheme not in ("http", "https"):
        return False, f"Only http/https allowed, got '{p.scheme or 'none'}'"
    if not p.netloc:
        return False, "Missing domain"

    hostname = p.hostname
    if not hostname:
        return False, "Missing hostname"

    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        return False, f"Cannot resolve hostname: {hostname}"

    for info in infos:
        try:
            addr = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if _is_private(addr):
            return False, f"Blocked: {hostname} resolves to private/internal address {addr}"

    return True, ""


def validate_resolved_url(url: str) -> tuple[bool, str]:
    """Validate an already-fetched URL (e.g. after redirect). Only checks the IP, skips DNS."""
    try:
        p = urlparse(url)
    except Exception:
        return True, ""

    hostname = p.hostname
    if not hostname:
        return True, ""

    try:
        addr = ipaddress.ip_address(hostname)
        if _is_private(addr):
            return False, f"Redirect target is a private address: {addr}"
    except ValueError:
        # hostname is a domain name, resolve it
        try:
            infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except socket.gaierror:
            return True, ""
        for info in infos:
            try:
                addr = ipaddress.ip_address(info[4][0])
            except ValueError:
                continue
            if _is_private(addr):
                return False, f"Redirect target {hostname} resolves to private address {addr}"

    return True, ""


def contains_internal_url(command: str) -> bool:
    """Return True if the command string contains a URL targeting an internal/private address."""
    for m in _URL_RE.finditer(command):
        url = m.group(0)
        ok, _ = validate_url_target(url)
        if not ok:
            return True
    return False
