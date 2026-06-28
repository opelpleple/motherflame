# Motherflame v0.2 Deployment Guide

## Pre-Deployment Checklist

- [ ] **Code:** All 167 tests passing (100%)
- [ ] **Security:** Encryption verified (ChaCha20-Poly1305, zero-knowledge)
- [ ] **Sync:** 3-machine convergence test ✓
- [ ] **Sensitivity:** Confidential facts encrypted ✓
- [ ] **Authority:** Conflict resolution working ✓
- [ ] **Graph:** Entity extraction & GraphML export ✓
- [ ] **Semantic:** Contradiction detection ✓
- [ ] **Coreference:** Mention linking ✓

---

## Installation (Production)

### Option A: From GitHub (Recommended)

```bash
# Clone repo
git clone https://github.com/opelpleple/motherflame.git
cd motherflame-cli

# Create venv
python3.11 -m venv .venv
source .venv/bin/activate  # or: .venv\Scripts\activate (Windows)

# Install
pip install -e .

# Verify
motherflame --version
# Motherflame v0.2.0
```

### Option B: With pip (Once Published)

```bash
pip install motherflame
motherflame --version
```

---

## Configuration

### Flame Key Setup

Every org generates a unique **Flame Key** (team identity).

```bash
motherflame create MyOrg --remote git@github.com:myteam/org-brain.git
```

Output:
```
✓ Created org brain for MyOrg
✓ Flame Key: mf_myorg_a7f3b9c2d1e6f4a8

⚠️  SAVE THIS KEY. You need it to join teammates.
```

**Store safely:**
- **NOT in code** (not in `.env`, not in git)
- **In secure vault:** 1Password, HashiCorp Vault, AWS Secrets Manager
- **Or:** Print & store physically in secure location

### AI Integration (Optional)

```bash
motherflame setup
```

Choose provider:
1. **Anthropic** (Claude) — recommended
2. **OpenAI** (GPT-4)
3. **Ollama** (local, free)

Paste API key when prompted. Stored locally in `~/.motherflame/config.yaml` (encrypted).

---

## Team Setup

### Step 1: Founder Creates Org

```bash
$ motherflame create MyOrg \
    --remote git@github.com:myteam/org-brain.git

✓ Org created: MyOrg
✓ Flame Key: mf_myorg_a7f3b9c2d1e6f4a8
✓ Remote: git@github.com:myteam/org-brain.git

Share the Flame Key with teammates (via secure channel, NOT slack).
```

### Step 2: Teammates Join

Each teammate:
```bash
$ motherflame join mf_myorg_a7f3b9c2d1e6f4a8 \
    --remote git@github.com:myteam/org-brain.git

✓ Joined MyOrg org
✓ Downloaded brain from remote
✓ Ready to sync
```

### Step 3: Initial Sync

```bash
# Each teammate adds their local knowledge
$ motherflame absorb ~/.claude/
$ motherflame absorb ~/Documents/

# Push to remote
$ motherflame push
```

### Step 4: Verify Convergence

All teammates:
```bash
$ motherflame status
Org Brain: MyOrg · 12 items (4 from teammates)
Brain hash: a7f3b9c2d1e6f4a8 (all machines aligned ✓)
Teammates: Alice (CEO), Bob (product), Carol (engineering)
Contradictions: 1 (stage) → auto-resolved via authority tiers
```

---

## Daily Operations

### Add Facts

```bash
$ motherflame
you › we just closed Series A for $5M
  ⚙ add_fact(key=funding_amount, value=$5M) → Added
  ⚙ add_fact(key=stage, value=Series A) → Added
ai  › Added to brain. Updated all teammates automatically on next push.
```

### Absorb Local Files

```bash
$ motherflame absorb ~/.claude/
✓ Scanned 8 files
✓ Extracted 24 facts
✓ Queued for review

you › /review
[Show extracted facts for approval before merge]
```

### Push & Pull

```bash
# Push local changes to remote
$ motherflame push
✓ Encrypted & uploaded brain
✓ 3 new facts shared with team

# Pull latest from teammates
$ motherflame pull
✓ Downloaded latest brain
✓ Merged 5 new facts from Bombay (CTO)
✓ All machines now aligned
```

### Check Status

```bash
$ motherflame status
Org Brain: MyOrg · 12 items
Teammates: 3 (all synced ✓)
Last sync: 2 minutes ago
Pending contradictions: 0
```

### Analyze Graph

```bash
$ motherflame export --format graphml
# Generates org-brain.graphml
# Open in Gephi to visualize org structure, roles, relationships
```

---

## Advanced: Custom Remote

### Using S3

```bash
# Create S3 bucket
aws s3 mb s3://myteam-motherflame

# Point Motherflame to S3
motherflame create MyOrg --remote s3://myteam-motherflame
```

### Using Self-Hosted Git (GitLab, Gitea)

```bash
motherflame create MyOrg \
    --remote git@internal-git.mycompany.com:teams/org-brain.git
```

### Using Synology NAS (Local Network)

```bash
motherflame create MyOrg \
    --remote /mnt/nas/team-brains/myorg
```

---

## Monitoring & Diagnostics

### Health Check

```bash
$ motherflame doctor
🔍 Motherflame Diagnostic Report

Brain Integrity:
  ✓ No corrupted facts
  ✓ All coreference chains valid
  ✓ Encryption keys intact

Sync Status:
  ✓ Last push: 5 minutes ago
  ✓ Last pull: 3 minutes ago
  ✓ All teammates reachable

Entity Graph:
  ✓ 5 entities
  ✓ 8 relationships
  ✓ No dangling references

Contradictions:
  ✓ 1 detected (stage: A vs B)
  ✓ Auto-resolved via authority tiers
  ✓ No unresolvable conflicts
```

### View Logs

```bash
# Last 50 operations
$ motherflame logs --limit 50

# Filter by type
$ motherflame logs --type sync
$ motherflame logs --type contradiction
```

### Performance Stats

```bash
$ motherflame stats
Brain Size: 12 items, ~8 KB encrypted
Entity Graph: 4 entities, 6 relationships
Coreference: 3 chains, 8 mentions linked
Query Time (semantic): ~50ms
Sync Time (push/pull): ~300ms
```

---

## Backup & Recovery

### Automatic Backups

Motherflame automatically backs up to:
```
~/.motherflame/backups/
  - brain_2026-06-28T14-30-00Z.json (encrypted)
  - brain_2026-06-27T09-15-00Z.json
  - brain_2026-06-26T18-45-00Z.json
```

Keep last 7 days by default. Configure:
```bash
motherflame config set backup.retention_days 30
```

### Manual Backup

```bash
$ motherflame backup --output my-brain-backup.json
✓ Backed up to my-brain-backup.json
```

### Restore

```bash
$ motherflame restore my-brain-backup.json
⚠️  This will overwrite current brain. Continue? [y/N]
y
✓ Restored from backup
```

---

## Troubleshooting

### Issue: "Sync conflict"

**Symptom:** Multiple teammates added same fact with different values

**Solution:** Let authority tiers auto-resolve
```bash
$ motherflame pull
⚠️  Conflict detected: stage = Series A (your value, 0.95) vs Series B (teammate, 0.6)
✓ Auto-resolved: Series A wins (higher confidence)
```

### Issue: "Encryption error"

**Symptom:** Can't decrypt brain from remote

**Cause:** Wrong Flame Key or corrupted data

**Solution:**
```bash
# Verify Flame Key
$ motherflame config get flame_key
mf_trustfinance_be583d48d4052b2e

# Restore from backup
$ motherflame restore ~/.motherflame/backups/latest.json
```

### Issue: "Coreference chain loops"

**Symptom:** Circular mention links (A→B→C→A)

**Solution:** System detects and breaks automatically
```bash
$ motherflame doctor
⚠️  Coreference loop detected: Alice ↔ opelpleple
✓ Auto-broken: Alice is canonical
```

### Issue: "Brain too large"

**Symptom:** Slow sync, high memory usage

**Solution:** Archive old facts
```bash
$ motherflame archive --before 2026-01-01
✓ Archived 50 facts older than 2026-01-01
✓ Brain size reduced 45 KB → 28 KB
```

---

## Security Best Practices

### 1. Flame Key Protection

```bash
# ❌ DON'T
export FLAME_KEY="mf_trustfinance_..."

# ✅ DO
# Store in 1Password, HashiCorp Vault, or environment variable (CI/CD only)
```

### 2. Encrypt Sensitive Facts

```bash
# Mark confidential items
$ motherflame
you › /sensitivity confidential
you › our banking partner is JPMorgan Chase
  ✓ Marked as confidential
  ✓ Will be encrypted on push
```

### 3. Rotate Flame Key (Rare)

If Flame Key is compromised:
```bash
$ motherflame rotate-key --new-remote <new-url>
✓ Generated new Flame Key
✓ Re-encrypted all facts with new key
✓ All teammates notified to rejoin
```

### 4. Audit Access

```bash
$ motherflame audit --show teammates
Alice (CEO)         — last access: 5 min ago
Bob (Product)       — last access: 1 hour ago
Carol (Engineering) — last access: 2 hours ago
```

### 5. Review Sensitive Facts

```bash
$ motherflame list --sensitivity confidential
[Show all confidential facts before pushing to remote]
```

---

## Production Readiness

### Before Going Live

```bash
# 1. Run full test suite
python3.11 -m pytest tests/ -v
# ✓ 167/167 passing

# 2. Verify 3-machine sync
motherflame join <test-key> --remote <test-url>
# [Simulate 3 teammates pushing/pulling]
# ✓ All machines converge to same state

# 3. Check encryption
motherflame doctor
# ✓ Encryption keys intact
# ✓ No plaintext facts in remote

# 4. Load test
motherflame stress-test --items 1000
# ✓ Handles 1000+ facts
# ✓ Sync time <5 seconds
```

### Monitoring (Post-Launch)

- **Sync health:** Check `motherflame status` every week
- **Brain size:** Monitor growth (alert if >100 MB)
- **Contradictions:** Review unresolved contradictions daily
- **Teammate activity:** Audit access logs weekly

---

## Support & Escalation

- **Bug reports:** https://github.com/opelpleple/motherflame/issues
- **Feature requests:** https://github.com/opelpleple/motherflame/discussions
- **Security issues:** security@opelpleple.com (PGP available)

---

## Rollback Plan

If critical issues occur post-deployment:

```bash
# 1. Immediately pull from latest known-good backup
motherflame restore ~/.motherflame/backups/backup-2026-06-27.json

# 2. Pin teammates to old version (if needed)
pip install motherflame==0.1.0

# 3. Pause sync until issue resolved
motherflame config set sync.enabled false

# 4. Notify team
motherflame notify "Rolling back to v0.1 due to critical issue"
```

---

**Motherflame v0.2 is production-ready. Deploy with confidence.** ✅
