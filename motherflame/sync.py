"""
Motherflame Sync — Zero-Knowledge brain sync.

The Org Brain is encrypted *client-side* with a key derived from the Flame Key
before it ever leaves the machine. The backend only ever sees ciphertext.

Crypto:
  - Key derivation:  scrypt(flame_key, salt) → 32-byte key
  - Cipher:          AES-256-GCM (authenticated encryption) via the audited
                     `cryptography` library — NOT hand-rolled. AEAD gives us
                     confidentiality + integrity in one vetted primitive.
  - Blob format:     b"MF2" || salt(16) || nonce(12) || ciphertext+tag

Older brains written with the legacy hand-rolled cipher (b"MF1"/headerless) can
still be DECRYPTED for backward compatibility, but everything new is AES-GCM.

Backend is pluggable: a local ciphertext store (default) or a git remote you
host yourself (real team sync). The host only ever sees the encrypted blob.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime
from pathlib import Path

CLOUD_DIR = Path.home() / ".motherflame" / "cloud"

# Blob format magic. MF2 = AES-256-GCM (current). Legacy blobs have no magic.
_MAGIC_V2 = b"MF2"


class CryptoUnavailable(RuntimeError):
    """Raised when the audited crypto library isn't installed. We refuse to
    fall back to weak crypto silently — sync stops with a clear message."""


def _aesgcm():
    """Import AES-GCM from the audited `cryptography` lib, or fail loudly."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        return AESGCM
    except ImportError as e:
        raise CryptoUnavailable(
            "Encrypted sync requires the 'cryptography' package "
            "(AES-256-GCM). Install it:  pip install cryptography"
        ) from e


# ── Key derivation ─────────────────────────────────────────────────────────

def derive_key(flame_key: str, salt: bytes) -> bytes:
    """Derive a 32-byte encryption key from the Flame Key via scrypt."""
    return hashlib.scrypt(flame_key.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)


# ── Authenticated encryption (AES-256-GCM, audited lib) ────────────────────

def encrypt(plaintext: bytes, flame_key: str) -> bytes:
    """AES-256-GCM. Returns MF2 || salt(16) || nonce(12) || ct+tag."""
    AESGCM = _aesgcm()
    salt  = os.urandom(16)
    nonce = os.urandom(12)                       # 96-bit nonce (GCM standard)
    key   = derive_key(flame_key, salt)
    ct    = AESGCM(key).encrypt(nonce, plaintext, None)   # ct includes the tag
    return _MAGIC_V2 + salt + nonce + ct


def decrypt(blob: bytes, flame_key: str) -> bytes:
    """Verify + decrypt. AES-GCM for MF2 blobs; legacy fallback for old data.
    Raises ValueError on wrong key / tampering."""
    if blob[:3] == _MAGIC_V2:
        AESGCM = _aesgcm()
        body = blob[3:]
        if len(body) < 16 + 12 + 16:
            raise ValueError("ciphertext too short / corrupt")
        salt, nonce, ct = body[:16], body[16:28], body[28:]
        key = derive_key(flame_key, salt)
        try:
            from cryptography.exceptions import InvalidTag
            return AESGCM(key).decrypt(nonce, ct, None)
        except InvalidTag:
            raise ValueError("authentication failed — wrong Flame Key or tampered data")
    # ── Legacy path: decrypt brains written by the old hand-rolled cipher ──
    return _decrypt_legacy(blob, flame_key)


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """Legacy SHA-256 CTR keystream — used ONLY to read old blobs, never to write."""
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest())
        counter += 1
    return bytes(out[:length])


def _decrypt_legacy(blob: bytes, flame_key: str) -> bytes:
    """Read a pre-AES-GCM blob: salt(16)||nonce(16)||mac(32)||ct."""
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

def _blob_slug(org_id: str, flame_key: str = None) -> str:
    """Stable filename for the encrypted brain blob.

    IMPORTANT: derive from the Flame Key when available, NOT the typed org name.
    Members may capitalize the org differently (TrustFinance vs Trustfinance) —
    if the blob name followed org_name, two members would read/write DIFFERENT
    files on the same remote and silently never sync. The Flame Key is identical
    for everyone in the org, so it's the correct stable key.
    """
    if flame_key:
        # mf_<org>_<hex> → use the whole key, sanitized; falls back to org slug
        safe = "".join(c for c in flame_key if c.isalnum() or c in "-_")
        if safe:
            return safe
    return "".join(c for c in (org_id or "") if c.isalnum() or c in "-_") or "org"


def _backend_path(org_id: str, flame_key: str = None) -> Path:
    CLOUD_DIR.mkdir(parents=True, exist_ok=True)
    return CLOUD_DIR / f"{_blob_slug(org_id, flame_key)}.flame"


def _git(args, cwd, check=True):
    import subprocess
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, check=check)


def check_remote(remote: str, timeout: int = 10) -> dict:
    """Probe a git sync remote without cloning. Returns
    {ok, status, detail} where status is one of:
      reachable | empty | auth_failed | not_found | no_network | invalid
    Used by `team`/`doctor`/pre-push so remote problems surface clearly
    instead of failing silently mid-sync."""
    import subprocess
    if not remote:
        return {"ok": False, "status": "invalid", "detail": "no remote set"}
    try:
        p = subprocess.run(
            ["git", "ls-remote", remote],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0",   # never block on a credential prompt
                 "GIT_SSH_COMMAND": "ssh -oBatchMode=yes -oConnectTimeout=8"},
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": "no_network", "detail": "timed out reaching remote"}
    except FileNotFoundError:
        return {"ok": False, "status": "invalid", "detail": "git not installed"}
    if p.returncode == 0:
        if p.stdout.strip():
            return {"ok": True, "status": "reachable", "detail": "ok"}
        return {"ok": True, "status": "empty", "detail": "reachable but no commits yet"}
    err = (p.stderr or "").lower()
    if any(s in err for s in ("permission denied", "authentication failed",
                              "could not read", "access denied", "publickey")):
        return {"ok": False, "status": "auth_failed", "detail": p.stderr.strip().splitlines()[-1] if p.stderr.strip() else "auth failed"}
    if any(s in err for s in ("not found", "does not exist", "repository not found")):
        return {"ok": False, "status": "not_found", "detail": "repository not found"}
    if any(s in err for s in ("could not resolve", "network", "timed out", "unable to access")):
        return {"ok": False, "status": "no_network", "detail": "network error"}
    return {"ok": False, "status": "invalid", "detail": (p.stderr or "unknown error").strip().splitlines()[-1] if p.stderr.strip() else "unknown error"}


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
    # Ensure a committer identity exists for THIS repo even if the user has no
    # global git config (common on fresh machines / CI) — otherwise commit fails
    # silently and push has no ref to send.
    _git(["config", "user.email", "sync@motherflame.local"], cwd=repo, check=False)
    _git(["config", "user.name", "Motherflame Sync"], cwd=repo, check=False)
    # Normalize the branch name so push/pull target a known ref.
    _git(["checkout", "-B", "main"], cwd=repo, check=False)
    return repo


def push(brain: dict, flame_key: str, org_id: str, git_remote: str = None) -> dict:
    """Encrypt the brain client-side and upload ciphertext.
    If git_remote is set, commit+push to that repo (real team sync); otherwise
    write to the local cloud dir."""
    payload = json.dumps(brain, ensure_ascii=False).encode()
    blob = encrypt(payload, flame_key)
    safe = _blob_slug(org_id, flame_key)

    if git_remote:
        repo = _git_sync_dir(git_remote)
        safe_name = f"{safe}.flame"
        fpath = repo / safe_name
        # Retry loop: if a teammate pushed between our pull and push, re-merge
        # their (decrypted) brain into ours and try again — no lost updates.
        last_err = None
        for attempt in range(4):
            _git(["pull", "--no-edit", "-X", "ours", "origin", "main"], cwd=repo, check=False)
            # If a remote blob exists, decrypt + merge so we don't overwrite it
            current = brain
            if fpath.exists():
                try:
                    remote_brain = json.loads(decrypt(fpath.read_bytes(), flame_key))
                    current, _ = merge_brains(brain, remote_brain)
                except ValueError:
                    current = brain  # wrong key / unrelated file → keep ours
            blob = encrypt(json.dumps(current, ensure_ascii=False).encode(), flame_key)
            fpath.write_bytes(blob)
            _git(["add", safe_name], cwd=repo)
            _git(["commit", "-m", f"motherflame: update {safe}"], cwd=repo, check=False)
            pr = _git(["push", "origin", "main"], cwd=repo, check=False)
            if pr.returncode == 0:
                return {"ok": True, "bytes": len(blob), "items": len(current.get("items", [])),
                        "pushed_at": datetime.now().isoformat(timespec="seconds"),
                        "backend": "git", "remote": git_remote, "attempts": attempt + 1}
            last_err = pr.stderr.strip()
            # non-fast-forward → loop pulls again and re-merges
        return {"ok": False, "bytes": len(blob), "items": len(brain.get("items", [])),
                "pushed_at": datetime.now().isoformat(timespec="seconds"),
                "backend": "git", "remote": git_remote, "error": last_err}

    path = _backend_path(org_id, flame_key)
    path.write_bytes(blob)
    return {"ok": True, "bytes": len(blob), "items": len(brain.get("items", [])),
            "pushed_at": datetime.now().isoformat(timespec="seconds"),
            "backend": "local", "location": str(path)}


def pull(flame_key: str, org_id: str, git_remote: str = None) -> dict | None:
    """Download ciphertext and decrypt client-side. Returns brain dict or None."""
    safe = _blob_slug(org_id, flame_key)
    if git_remote:
        repo = _git_sync_dir(git_remote)
        _git(["pull", "--no-edit", "origin", "main"], cwd=repo, check=False)
        fpath = repo / f"{safe}.flame"
        if not fpath.exists():
            # Back-compat: an older client may have written an org-name blob.
            legacy = repo / (("".join(c for c in (org_id or "") if c.isalnum() or c in "-_") or "org") + ".flame")
            if legacy.exists():
                fpath = legacy
            else:
                return None
        return json.loads(decrypt(fpath.read_bytes(), flame_key))

    path = _backend_path(org_id, flame_key)
    if not path.exists():
        return None
    return json.loads(decrypt(path.read_bytes(), flame_key))


def remote_exists(org_id: str, git_remote: str = None, flame_key: str = None) -> bool:
    safe = _blob_slug(org_id, flame_key)
    if git_remote:
        repo = _git_sync_dir(git_remote)
        return (repo / f"{safe}.flame").exists()
    return _backend_path(org_id, flame_key).exists()


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
