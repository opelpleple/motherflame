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
from __future__ import annotations

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


# ── Backends ───────────────────────────────────────────────────────────────
# Two backends, selected per call by whether a git remote is configured:
#   • local  — writes ciphertext to ~/.motherflame/cloud/ (single machine; the
#              default, zero-setup, good for solo use & testing)
#   • git    — commits/pushes ciphertext to a git remote you control, so a real
#              team actually shares one brain. You host the repo (GitHub/GitLab/
#              self-hosted); the server only ever sees the encrypted blob.

def _backend_path(org_id: str) -> Path:
    CLOUD_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c for c in org_id if c.isalnum() or c in "-_") or "org"
    return CLOUD_DIR / f"{safe}.flame"


def _git(args, cwd, check=True):
    import subprocess
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, check=check)


def _git_sync_dir(remote: str) -> Path:
    """Clone (or reuse) a local working copy of the sync remote under ~/.motherflame/sync/."""
    import hashlib
    base = Path.home() / ".motherflame" / "sync"
    base.mkdir(parents=True, exist_ok=True)
    slug = hashlib.sha1(remote.encode()).hexdigest()[:12]
    repo = base / slug
    if not (repo / ".git").exists():
        _git(["clone", "--depth", "1", remote, str(repo)], cwd=base, check=False)
        if not (repo / ".git").exists():
            # fresh remote with nothing in it → init + set origin
            repo.mkdir(exist_ok=True)
            _git(["init"], cwd=repo)
            _git(["remote", "add", "origin", remote], cwd=repo, check=False)
    return repo


def push(brain: dict, flame_key: str, org_id: str, git_remote: str = None) -> dict:
    """Encrypt the brain client-side and upload ciphertext.
    If git_remote is set, commit+push to that repo (real team sync); otherwise
    write to the local cloud dir."""
    payload = json.dumps(brain, ensure_ascii=False).encode()
    blob = encrypt(payload, flame_key)
    safe = "".join(c for c in org_id if c.isalnum() or c in "-_") or "org"

    if git_remote:
        repo = _git_sync_dir(git_remote)
        # pull latest first so we don't clobber teammates
        _git(["pull", "--no-edit", "origin", "HEAD"], cwd=repo, check=False)
        fpath = repo / f"{safe}.flame"
        fpath.write_bytes(blob)
        _git(["add", fpath.name], cwd=repo)
        _git(["commit", "-m", f"motherflame: update {safe}"], cwd=repo, check=False)
        pr = _git(["push", "origin", "HEAD"], cwd=repo, check=False)
        ok = pr.returncode == 0
        return {"ok": ok, "bytes": len(blob), "items": len(brain.get("items", [])),
                "pushed_at": datetime.now().isoformat(timespec="seconds"),
                "backend": "git", "remote": git_remote,
                "error": (pr.stderr.strip() if not ok else None)}

    path = _backend_path(org_id)
    path.write_bytes(blob)
    return {"ok": True, "bytes": len(blob), "items": len(brain.get("items", [])),
            "pushed_at": datetime.now().isoformat(timespec="seconds"),
            "backend": "local", "location": str(path)}


def pull(flame_key: str, org_id: str, git_remote: str = None) -> dict | None:
    """Download ciphertext and decrypt client-side. Returns brain dict or None."""
    safe = "".join(c for c in org_id if c.isalnum() or c in "-_") or "org"
    if git_remote:
        repo = _git_sync_dir(git_remote)
        _git(["pull", "--no-edit", "origin", "HEAD"], cwd=repo, check=False)
        fpath = repo / f"{safe}.flame"
        if not fpath.exists():
            return None
        return json.loads(decrypt(fpath.read_bytes(), flame_key))

    path = _backend_path(org_id)
    if not path.exists():
        return None
    return json.loads(decrypt(path.read_bytes(), flame_key))


def remote_exists(org_id: str, git_remote: str = None) -> bool:
    safe = "".join(c for c in org_id if c.isalnum() or c in "-_") or "org"
    if git_remote:
        repo = _git_sync_dir(git_remote)
        return (repo / f"{safe}.flame").exists()
    return _backend_path(org_id).exists()


def merge_brains(local: dict, remote: dict) -> tuple[dict, int]:
    """Merge a teammate's brain into ours WITHOUT losing anyone's data.

    Instead of clobbering by key, we union the *claims* from both brains and let
    the conflict resolver recompute the single source of truth. A teammate's
    $50k pricing and our $48k pricing both survive as competing claims — the
    key becomes 'contested' and surfaces for resolution rather than silently
    overwriting.

    Returns (merged_brain, n_new_claims).
    """
    from motherflame import conflicts

    merged = dict(local)
    conflicts.ensure_layers(merged)
    # fold any legacy flat items into claims first (both sides)
    conflicts.migrate_items_to_claims(merged)

    remote = dict(remote)
    conflicts.ensure_layers(remote)
    conflicts.migrate_items_to_claims(remote)

    n_new = 0
    # union claims
    for key, rclaims in remote.get("claims", {}).items():
        ckey = conflicts.canonical_key(key)
        for rc in rclaims:
            existing = merged["claims"].get(ckey, [])
            match = next((c for c in existing
                          if conflicts._norm(c["value"]) == conflicts._norm(rc["value"])
                          and c["source"] == rc["source"]), None)
            if match is None:
                conflicts.add_claim(merged, rc["category"], key, rc["value"],
                                    source=rc.get("source", "remote"),
                                    owner=rc.get("owner", ""),
                                    confidence=rc.get("confidence", 0.7),
                                    ts=rc.get("ts"))
                # carry the tombstone across so a delete survives the merge
                if rc.get("retracted"):
                    for c in merged["claims"][ckey]:
                        if (conflicts._norm(c["value"]) == conflicts._norm(rc["value"])
                                and c["source"] == rc["source"]):
                            c["retracted"] = True
                            c["retracted_at"] = rc.get("retracted_at")
                n_new += 1
            else:
                # claim exists on both sides → a tombstone on EITHER side wins
                if rc.get("retracted") and not match.get("retracted"):
                    match["retracted"] = True
                    match["retracted_at"] = rc.get("retracted_at")

    # union owners (don't override a locally-set owner) and manual resolutions (newest wins)
    for scope, owner in remote.get("owners", {}).items():
        merged["owners"].setdefault(scope, owner)
    for key, res in remote.get("resolutions", {}).items():
        cur = merged["resolutions"].get(key)
        if not cur or res.get("ts", "") > cur.get("ts", ""):
            merged["resolutions"][key] = res

    # union gaps
    merged["gaps"] = sorted(set(local.get("gaps", [])) | set(remote.get("gaps", [])))

    # recompute the single source of truth from all claims
    conflicts.rebuild_canonical(merged)
    return merged, n_new
