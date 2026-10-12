"""Brute-force protection for the endpoints anyone can call without a session.

Counted in memory. The API runs as one process (see docker-entrypoint.sh), so one
dictionary sees every request, and a restart forgetting the counts costs nothing worth a
table. A second worker or replica would give each its own counts and quietly multiply
every limit - move this to Postgres or Redis before that happens.

Cloudflare in front does not replace this: it sees addresses, not accounts, so a
password guessed at from a thousand addresses gets past it, and the Railway domain
reaches the API without going through it at all.
"""

import ipaddress
import math
import time
from collections import deque
from dataclasses import dataclass, field

from fastapi import HTTPException, Request

from ..config import Limit, parse_limits, settings

# Published at https://www.cloudflare.com/ips/ - changes rarely, and a stale list fails
# safe: an unknown Cloudflare address is counted as itself, never trusted.
_CLOUDFLARE = tuple(
    ipaddress.ip_network(n)
    for n in (
        "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
        "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
        "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
        "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
        "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32",
        "2405:8100::/32", "2a06:98c0::/29", "2c0f:f248::/32",
    )
)

# Sweep expired keys every this many attempts, so memory tracks recent traffic only.
_SWEEP_EVERY = 1000


def _parse_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def client_ip(request: Request) -> str:
    """The caller's address, as a counting key."""
    raw = request.headers.get(settings.client_ip_header, "") if settings.client_ip_header else ""
    ip = _parse_ip(raw) or _parse_ip(request.client.host if request.client else "")
    if ip is None:
        return "unknown"

    # Behind Cloudflare the edge sees Cloudflare, not the person. Its header is believed
    # only from Cloudflare's own addresses: anyone can send it, only Cloudflare can send
    # it from there.
    if any(ip in net for net in _CLOUDFLARE):
        ip = _parse_ip(request.headers.get("cf-connecting-ip", "")) or ip

    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    # One IPv6 subscriber usually gets a whole /64; counting single addresses would let
    # them rotate through it.
    if ip.version == 6:
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    return str(ip)


@dataclass
class _Bucket:
    hits: deque[float] = field(default_factory=deque)
    longest_sec: int = 0


_buckets: dict[str, _Bucket] = {}
_since_sweep = 0


def _wait(bucket: _Bucket, limits: tuple[Limit, ...], now: float) -> float:
    """Seconds until one more is allowed under every limit; 0 if right now."""
    hits = bucket.hits
    while hits and hits[0] <= now - bucket.longest_sec:
        hits.popleft()
    wait = 0.0
    for limit in limits:
        recent = [t for t in hits if t > now - limit.window_sec]
        if len(recent) >= limit.count:
            # The hit that has to age out before there is room for one more.
            wait = max(wait, recent[-limit.count] + limit.window_sec - now)
    return wait


def _sweep(now: float) -> None:
    for key in [k for k, b in _buckets.items() if not b.hits or b.hits[-1] <= now - b.longest_sec]:
        del _buckets[key]


class TooManyAttempts(Exception):
    def __init__(self, retry_after: int):
        super().__init__(f"retry after {retry_after}s")
        self.retry_after = retry_after

    def http(self) -> HTTPException:
        minutes = math.ceil(self.retry_after / 60)
        return HTTPException(
            status_code=429,
            detail=f"Too many attempts. Try again in {minutes} min.",
            headers={"Retry-After": str(self.retry_after)},
        )


class Attempt:
    """One request's place in the counts: by email and by IP.

    Taken before any work is done, not after it fails. The handlers await the database
    in between, so counting only once a password turned out wrong would let a hundred
    parallel guesses all pass the check before the first of them was recorded.
    """

    def __init__(self, request: Request, scope: str, email: str, per_email: str, per_ip: str):
        self._keys = [
            (f"{scope}:email:{email.strip().lower()}", parse_limits(per_email)),
            (f"{scope}:ip:{client_ip(request)}", parse_limits(per_ip)),
        ]
        self._at: float | None = None

    def take(self) -> None:
        """Count this request, or raise TooManyAttempts without counting it."""
        global _since_sweep
        now = time.monotonic()
        active = [(key, limits) for key, limits in self._keys if limits]
        buckets = []
        wait = 0.0
        for key, limits in active:
            bucket = _buckets.setdefault(key, _Bucket())
            bucket.longest_sec = max(bucket.longest_sec, *(l.window_sec for l in limits))
            buckets.append(bucket)
            wait = max(wait, _wait(bucket, limits, now))
        if wait > 0:
            raise TooManyAttempts(max(1, math.ceil(wait)))

        for bucket in buckets:
            bucket.hits.append(now)
        self._at = now

        _since_sweep += 1
        if _since_sweep >= _SWEEP_EVERY:
            _since_sweep = 0
            _sweep(now)

    def succeeded(self) -> None:
        """The password was right: this was the owner, not a guess. Their address starts
        clean, and this attempt stops counting against the IP they share with others."""
        email_key, ip_key = self._keys[0][0], self._keys[1][0]
        _buckets.pop(email_key, None)
        bucket = _buckets.get(ip_key)
        if bucket is not None and self._at is not None:
            try:
                bucket.hits.remove(self._at)
            except ValueError:
                pass


def reset() -> None:
    """Forget every count. For the tests."""
    global _since_sweep
    _buckets.clear()
    _since_sweep = 0
