"""
Motherflame Sync — Zero-Knowledge brain sync.

The Org Brain is encrypted *client-side* with a key derived from the Flame Key
before it ever leaves the machine. The backend only ever sees ciphertext —
true zero-knowledge.

Crypto (stdlib-only, no external deps):
  - Key derivation:  scrypt(flame_key, salt) → 32-byte key
  - Cipher:          AES-free stream cipher built from SHA-256 in CTR mode
  - Authentication:  HMAC-SHA256 over the ciphertext (encrypt-then-MAC)

Backend is pluggable. The default "local" backend writes ciphertext to
~/.motherflame/cloud/<org>.flame — a stand-in for a real ZK cloud bucket,
so push/pull are fully testable today and swap to HTTP later.
"""

import hashlib
import hmac
import json
import os
from datetime import datetime
from pathlib import Path

CLOUD_DIR = Path.home() / ".motherflame" / "cloud"


# ── Key derivation ─────────────────────────────────────────────────────────

def derive_key(flame_key: str, salt: bytes) -> bytes:
    """Derive a 32-byte encryption key from the Flame Key via scrypt."""
    return hashlib.scrypt(flame_key.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)


# ── Stream cipher (SHA-256 CTR keystream) ──────────────────────────────────

def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """Generate `length` bytes of keystream by hashing key||nonce||counter."""
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def encrypt(plaintext: bytes, flame_key: str) -> bytes:
    """Encrypt-then-MAC. Returns salt(16) || nonce(16) || mac(32) || ciphertext."""
    salt  = os.urandom(16)
    nonce = os.urandom(16)
    key   = derive_key(flame_key, salt)
    ks    = _keystream(key, nonce, len(plaintext))
    ct    = bytes(a ^ b for a, b in zip(plaintext, ks))
    mac   = hmac.new(key, nonce + ct, hashlib.sha256).digest()
    return salt + nonce + mac + ct


def decrypt(blob: bytes, flame_key: str) -> bytes:
    """Verify MAC then decrypt. Raises ValueError if authentication fails."""
    if len(blob) < 64:
        raise ValueError("ciphertext too short / corrupt")
    salt, nonce, mac, ct = blob[:16], blob[16:32], blob[32:64], blob[64:]
    key = derive_key(flame_key, salt)
    expected = hmac.new(key, nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        raise ValueError("authentication failed — wrong Flame Key or tampered data")
    ks = _keystream(key, nonce, len(ct))
    return bytes(a ^ b for a, b in zip(ct, ks))


# ── Backend (local stand-in for ZK cloud) ──────────────────────────────────

def _backend_path(org_id: str) -> Path:
    CLOUD_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c for c in org_id if c.isalnum() or c in "-_") or "org"
    return CLOUD_DIR / f"{safe}.flame"


def push(brain: dict, flame_key: str, org_id: str) -> dict:
    """Encrypt the brain client-side and upload ciphertext. Returns receipt."""
    payload = json.dumps(brain, ensure_ascii=False).encode()
    blob = encrypt(payload, flame_key)
    path = _backend_path(org_id)
    path.write_bytes(blob)
    return {
        "ok": True,
        "bytes": len(blob),
        "items": len(brain.get("items", [])),
        "pushed_at": datetime.now().isoformat(timespec="seconds"),
        "location": str(path),
    }


def pull(flame_key: str, org_id: str) -> dict | None:
    """Download ciphertext and decrypt client-side. Returns brain dict or None."""
    path = _backend_path(org_id)
    if not path.exists():
        return None
    blob = path.read_bytes()
    payload = decrypt(blob, flame_key)   # raises on wrong key / tamper
    return json.loads(payload)


def remote_exists(org_id: str) -> bool:
    return _backend_path(org_id).exists()


def merge_brains(local: dict, remote: dict) -> tuple[dict, int]:
    """Merge remote facts into local by key (newest wins). Returns (merged, n_new)."""
    by_key = {it["key"]: it for it in local.get("items", [])}
    n_new = 0
    for it in remote.get("items", []):
        k = it["key"]
        if k not in by_key:
            by_key[k] = it
            n_new += 1
        else:
            # keep whichever has the newer harvested_at
            a = by_key[k].get("harvested_at", "")
            b = it.get("harvested_at", "")
            if b > a:
                by_key[k] = it
    merged = dict(local)
    merged["items"] = list(by_key.values())
    # union of gaps
    merged["gaps"] = sorted(set(local.get("gaps", [])) | set(remote.get("gaps", [])))
    return merged, n_new
