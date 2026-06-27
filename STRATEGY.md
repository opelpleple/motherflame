# Motherflame — Project Strategy & Roadmap

> Grill → Find Gap → Optimize
> เขียนหลัง research ตลาดจริง (Tana, Augment Code, Anthropic context engineering)

---

## 1. GRILL — โครงการนี้จะไปแนวทางไหน?

### สิ่งที่ตลาดบอก (จาก research)
- **"The models are not the bottleneck anymore"** — frontier model ที่ไม่รู้จักบริษัทคุณ ก็ตอบผิดอย่างมั่นใจ → **knowledge คือ bottleneck**
- **"A stale source is worse than none, because the agent trusts it"** — ความสดของ context สำคัญที่สุด
- **"The hard part is having a current, connected, permissioned source to retrieve from"** — RAG ไม่ยาก, การ maintain source ต่างหากที่ยาก
- Knowledge ติดอยู่ใน 6 ที่: disconnected prompts, isolated sessions, individual configs, fragmented tools, non-transferable workflows, siloed history

### Landscape — คู่แข่ง
| เจ้า | จุดยืน | จุดอ่อน |
|---|---|---|
| **Tana** | "company context layer" + MCP server | ต้องย้ายงานเข้า workspace ของเขา (lock-in, heavy) |
| **Augment Code** | cross-agent org memory | enterprise dev teams, infra หนัก, แพง |
| **Glean / Notion AI** | enterprise knowledge search | ต้องอยู่ใน ecosystem ของเขา |

### Motherflame's Wedge (จุดต่างที่ชนะได้)
> **"Harvest context จากที่ที่มันอยู่แล้ว — ไฟล์และ agent ของแต่ละคน — ขึ้นมาเป็น central brain โดยไม่ต้องย้ายงาน, ใช้ AI key ของตัวเอง, $1/seat"**

- Tana = ย้ายเข้า workspace เขา → Motherflame = **อยู่ที่เดิม แค่ harvest ขึ้นมา**
- Augment = enterprise dev → Motherflame = **ทุกทีม, ทุกขนาด, ราคาถูกแบบ Obsidian**
- ทุกเจ้า = AI ของเขา → Motherflame = **bring-your-own-AI (variable cost = 0)**

**คำตอบ: แนวทางคือ "the lightweight org-brain that you don't migrate into" — wedge ที่ไม่มีใครเล่นเพราะทุกคนอยากเป็น platform ที่คุณย้ายเข้าไป**

---

## 2. FIND GAP — ช่องว่างที่ต้องเติม (เรียงตามความสำคัญ)

### 🔴 Gap 1: Freshness — ของจริงที่ตลาดบอกว่าสำคัญสุด แต่เรายังไม่มี
ตอนนี้ harvest เป็น **one-time snapshot**. Research บอกชัด "stale source is worse than none".
- ไม่มี re-scan / incremental update
- ไม่รู้ว่า fact ไหนเก่า fact ไหนใหม่
- ไม่มี "ไฟล์นี้เปลี่ยน → update brain"

### 🔴 Gap 2: "Collective brain" ยังเป็นแค่ชื่อ — จริงๆ เป็น local-only
positioning ขายว่า "collective/central brain ที่ทุกคนเข้าถึง" แต่ตอนนี้:
- แต่ละคนมี `~/.motherflame/brain.json` ของตัวเอง
- **ไม่มี sync, ไม่มี server, ไม่ได้ share กันจริง**
- นี่คือ gap ที่ทำให้ value prop ทั้งหมดยังไม่จริง

### 🟠 Gap 3: ไม่มี MCP server — Tana ชนะตรงนี้
- Tana: agent ภายนอก (Claude Code) เชื่อม brain ได้ผ่าน MCP
- Motherflame: brain ใช้ได้แค่ใน CLI ตัวเอง
- ถ้าไม่มี MCP = ไม่ใช่ "context layer for ANY agent" จริง

### 🟠 Gap 4: Harvest quality อ่อน (keyword regex)
- ตอนนี้ใช้ keyword matching (`"pricing"`, `"team of"`) → จับได้แต่ผิวเผิน
- คู่แข่งใช้ RAG / LLM extraction จริง
- เรามี LLM key อยู่แล้ว (setup) แต่ harvest ไม่ได้ใช้

### 🟡 Gap 5: ไม่มี "capture from work"
- Tana ชู "context captured as work happens"
- Motherflame = manual `/harvest` เท่านั้น
- ขาด: watch folder, git hook, หรือ scheduled re-scan

---

## 3. OPTIMIZE — ลงมือทำ (ปรับปรุงของจริง, เรียงลำดับ)

### Phase 1 — ทำให้ value prop จริง (2 gap แรก)
**1A. LLM-powered harvest** (เติม Gap 4 ก่อน เพราะง่าย+impact สูง)
- เปลี่ยน keyword regex → ส่งเนื้อไฟล์ให้ LLM extract signals จริง
- มี key อยู่แล้ว, แค่ต่อ pipeline
- ผล: fact มีคุณภาพขึ้นทันที

**1B. Freshness layer** (เติม Gap 1)
- เก็บ file hash + mtime ใน ledger
- `/refresh` → re-scan เฉพาะไฟล์ที่เปลี่ยน
- mark fact ว่า fresh/stale ตาม source file

### Phase 2 — ทำให้ "collective" จริง (Gap 2)
- Zero-knowledge cloud sync (ตามที่วางไว้: Flame Key encrypt ที่ client)
- `motherflame push` / `motherflame pull` → brain sync ข้ามเครื่อง
- เริ่มจาก simple: shared brain.json ผ่าน cloud storage + client-side encrypt

### Phase 3 — เปิดให้ทุก agent เชื่อม (Gap 3)
- MCP server: `motherflame mcp` → expose brain เป็น MCP endpoint
- Claude Code / Cursor / Hermes เชื่อมได้
- นี่คือสิ่งที่ทำให้เป็น "protocol" ตาม path: Product → Protocol → Platform

### Phase 4 — capture from work (Gap 5)
- watch mode / git post-commit hook → auto-harvest
- scheduled re-scan

---

## ลำดับที่แนะนำให้ลงมือ
1. **1A LLM harvest** ← เริ่มตรงนี้ (impact สูง, effort ต่ำ, มี key แล้ว)
2. **1B Freshness** ← ต่อเนื่อง, แก้ gap ที่ตลาดบอกว่าสำคัญสุด
3. **Phase 2 sync** ← ทำให้ "collective" จริง
4. **Phase 3 MCP** ← เปิดสู่ ecosystem

> เหตุผล: 1A+1B ทำให้ของที่มีอยู่ "ดีจริง" ก่อน แล้วค่อยขยาย (sync/MCP) — ไม่ใช่เพิ่ม feature ใหม่บนของที่ยังอ่อน
