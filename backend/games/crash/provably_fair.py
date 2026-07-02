"""Provably-fair crash point generation: commit/reveal + a public formula.

The server commits to a crash point before betting closes (publishing
sha256(server_seed)) without revealing anything about its value — a
SHA-256 hash is one-way, so a player can't work backwards from the hash
to predict the crash point. After the round crashes, the server reveals
server_seed; anyone can recompute crash_point_for(server_seed, nonce)
themselves and confirm both the commitment and the outcome.

This is the widely-published Bustabit-style formula: a well-understood,
previously-audited construction, rather than a novel scheme invented
for this project.
"""
import hashlib
import hmac
import secrets
from math import floor

HOUSE_EDGE_DIVISOR = 33  # 1-in-33 rounds instantly crash at 1.00x (~3% house edge)


def generate_server_seed() -> str:
    """A fresh, unpredictable seed for one round. Kept secret until reveal."""
    return secrets.token_hex(32)


def commit_hash(server_seed: str) -> str:
    """The public commitment published at the start of the round."""
    return hashlib.sha256(server_seed.encode()).hexdigest()


def crash_point_for(server_seed: str, nonce: int) -> float:
    """Deterministic crash point in [1.00, ...]. Same inputs -> same output,
    so this can be recomputed by anyone once server_seed is revealed."""
    digest = hmac.new(server_seed.encode(), str(nonce).encode(), hashlib.sha256).hexdigest()
    h = int(digest[:13], 16)  # first 52 bits
    e = 2 ** 52

    if h % HOUSE_EDGE_DIVISOR == 0:
        return 1.00

    crash_point = floor((100 * e - h) / (e - h)) / 100
    return max(1.00, crash_point)


def verify(server_seed: str, nonce: int, expected_hash: str, expected_crash_point: float) -> bool:
    """Recompute everything from the revealed seed and confirm it matches
    what was published before the round ran."""
    if commit_hash(server_seed) != expected_hash:
        return False
    return crash_point_for(server_seed, nonce) == expected_crash_point
