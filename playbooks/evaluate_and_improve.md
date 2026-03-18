# Playbook: Evaluate Extraction Accuracy & Improve Prompts

Use this after running the pipeline on a record to assess output quality and apply targeted fixes.

---

## Prerequisites

- Pipeline has been run for the target record (`data/output/record_<id>/` exists)
- Source markdown is available at `data/input/record_<id>.md`

---

## Step 1 — Read the source document

Open `data/input/record_<id>.md` and locate these sections:

| Section to find | What to look for |
|-----------------|-----------------|
| Board composition / formation table | Official names, membership type (Non-Executive / Independent / Executive), position (Chairman / Vice Chairman / Member) |
| Board meetings attendance table | Meetings attended per director |
| Remuneration table A (board) | Retainer, attendance allowance, committee attendance, expenses, total — amounts in thousands |
| Remuneration table B (committees) | Fixed retainer + session allowance + total per committee member |
| Skills / qualifications table | Degrees, certifications, prior roles |
| Committee membership table | Who is in which committee and their role (Chair / Member) |

> **Rule:** The board composition table is the authoritative source for `board_role` and `director_type`. Narrative sections (CEO letters, biographies) may use different titles — ignore them for these fields.

---

## Step 2 — Cross-check extracted directors

Compare `data/output/record_<id>/board_directors.json` against the source tables.

Check every director row for:

| Field | What to verify | Common failure modes |
|-------|---------------|----------------------|
| `director_name` | Exact spelling matches board composition table | Extra/missing letters in transliterated Arabic names |
| `board_role` | Matches POSITION column (Chairman/Vice Chairman/Member) | LLM uses executive title (CEO, MD) instead of board position |
| `director_type` | Matches MEMBERSHIP TYPE column (Non-Executive/Independent/Executive) | Usually correct |
| `board_meetings_attended` | Matches the meetings attendance table total column | Off-by-one if checkmarks not counted |
| `retainer_fee` | Matches "Specific Amount / Fixed Remuneration" column (convert from thousands) | Unit confusion (200 → 200,000) |
| `attendance_allowance` | Matches "Attendance allowance for board meetings" column | LLM may include committee attendance here instead |
| `director_board_committee_fee` | Matches committee total from remuneration table B | May be 0 if director is not on any committee |
| `expense_allowance` | Matches "Expenses Allowance" column | Often 0 or a small number |
| `total_fee` | Sum: retainer + board_attendance + committee_fee + expenses | Verify arithmetic |
| `nationality` | Full country name (e.g., "Saudi Arabian") | "Saudi" vs "Saudi Arabian" inconsistency |
| `age` | 0 unless explicitly stated in document | Correct to leave 0 |

### Quick verification script

```python
# Edit RECORD_ID, then run from project root
python3 - <<'EOF'
import json

RECORD_ID = 212  # ← change this

with open(f"data/output/record_{RECORD_ID}/board_directors.json") as f:
    directors = json.load(f)

print(f"{'Name':<40} {'Role':<18} {'Type':<16} {'Meetings':>8} {'Total':>12}")
print("-" * 100)
for d in sorted(directors, key=lambda x: x["director_name"]):
    print(
        f"{d['director_name']:<40} "
        f"{d['board_role']:<18} "
        f"{d['director_type']:<16} "
        f"{d['board_meetings_attended']:>8} "
        f"{d['total_fee']:>12,.0f}"
    )

grand_total = sum(d["total_fee"] for d in directors)
print("-" * 100)
print(f"{'TOTAL':<40} {'':>44} {grand_total:>12,.0f}")
EOF
```

---

## Step 3 — Cross-check extracted committees

Compare `data/output/record_<id>/board_committees.json` against the source tables.

| Field | What to verify | Common failure modes |
|-------|---------------|----------------------|
| `member_name` | Exact spelling matches source | Name drift vs board_directors table |
| `committee_name` | Full official name (e.g., "Audit Committee") | Abbreviation or wrong name |
| `committee_role` | Chair / Member / Vice Chair | Role from the membership/qualification table |
| `committee_meetings_attended` | = committee_allowances ÷ 3,000 (if 3K per meeting) | Attendance not disclosed → 0 |
| `committee_retainer_fee` | Fixed annual committee retainer | Often 50K–150K for listed companies |
| `committee_allowances` | Per-session fee × sessions attended | |
| `committee_total_fee` | retainer + allowances | |

**Cross-check names across tables:** Every `member_name` in committees should match a `director_name` in directors (except outside-board committee members like external auditors).

### Quick verification script

```python
# Edit RECORD_ID, then run from project root
python3 - <<'EOF'
import json

RECORD_ID = 212  # ← change this

with open(f"data/output/record_{RECORD_ID}/board_committees.json") as f:
    committees = json.load(f)
with open(f"data/output/record_{RECORD_ID}/board_directors.json") as f:
    directors = json.load(f)

director_names = {d["director_name"] for d in directors}

print(f"{'Member':<40} {'Committee':<40} {'Role':<12} {'Mtgs':>4} {'Total':>10}")
print("-" * 110)
for c in sorted(committees, key=lambda x: (x["committee_name"], x["member_name"])):
    name_match = "✓" if c["member_name"] in director_names else "⚠ outside-board"
    print(
        f"{c['member_name']:<40} "
        f"{c['committee_name']:<40} "
        f"{c['committee_role']:<12} "
        f"{c['committee_meetings_attended']:>4} "
        f"{c['committee_total_fee']:>10,.0f}  {name_match}"
    )

print("-" * 110)
print(f"Total committee rows: {len(committees)}")
print(f"\nName cross-check:")
for c in committees:
    if c["member_name"] not in director_names:
        print(f"  ⚠ '{c['member_name']}' not found in board_directors (may be outside-board)")
EOF
```

---

## Step 4 — Classify issues found

For each issue, decide the category:

| Category | Description | Fix location |
|----------|-------------|--------------|
| **Prompt ambiguity** | Instruction missing or unclear — LLM made a reasonable but wrong choice | `config/prompts.py` |
| **Prompt rule missing** | Edge case not covered (e.g. outside-board committee members) | `config/prompts.py` |
| **Schema mismatch** | Field definition doesn't match what the source document provides | `config/schemas.py` |
| **Temperature too high** | Factual field varies across runs | `config/settings.py` — lower temperature |
| **Model limitation** | LLM consistently fails on a specific pattern regardless of prompt changes | Consider a different model or post-processing |
| **Document quality** | Markdown parsing artefacts (mangled tables, missing columns) | Note in `directives/extract_info.md` |

---

## Step 5 — Apply prompt fixes

Edit `config/prompts.py`. Fixes should be **targeted and minimal** — change only the instruction that addresses the root cause.

### Pattern for fixing `board_role` ambiguity (example from record 212):

```
Before:
- **board_role** — Chairman, Vice Chairman, Member, Managing Director, etc.

After:
- **board_role** — Use the POSITION column from the official Board Composition table ONLY:
  Chairman | Vice Chairman | Member.
  Do NOT use executive job titles (CEO, MD, Managing Director) as board_role.
  An Executive director whose position in the composition table is "Member"
  must be recorded as "Member".
```

### Pattern for fixing name spelling drift:

```
Before:
- **director_name** — Full official name of the board director

After:
- **director_name** — Full official name, copied EXACTLY character-by-character
  from the Board Composition / Formation table. Preserve the exact transliteration
  of Arabic names as shown in that table.
```

### Pattern for fixing nationality inconsistency:

```
Before:
- **nationality**

After:
- **nationality** — Use full country name (e.g., "Saudi Arabian" NOT "Saudi").
  If not explicitly stated, infer from company HQ country.
```

---

## Step 6 — Update directives/extract_info.md

After every evaluation, update the directive file:

```markdown
## Last Run

| Field | Value |
|-------|-------|
| Timestamp | 2026-02-24 |
| Record ID | 212 |
| Status | Success |
| Company name | Electrical Industries Co. |
| Fiscal year | 2023 |
| Directors inserted | 8 |
| Committees inserted | 6 |
| Notes | 2 prompt fixes applied (board_role, name spelling) |

## Edge Cases

- Executive board members (e.g. CEO/MD) hold the position "Member" in the board
  composition table — do not use their executive title as board_role.
- Committee members outside the board appear in board_committees but NOT in
  board_directors. These are correctly excluded.
- When remuneration is split across two tables (board table + committee table),
  total_fee = board total + committee retainer (the attendance portion is
  already in the board table).

## Learnings

- "Saudi" vs "Saudi Arabian" inconsistency arises when the prompt does not
  specify full country name format. Always require full country name.
- Temperature 0.0 is preferred over 0.2 for all factual extractions.
```

---

## Step 7 — Re-run and verify the fix

Re-run only the affected extractor (no need to re-run company extraction):

```bash
# Re-run directors only
PYTHONPATH=$(pwd) python3 execution/extract_directors.py --record-id 212 --fact-id 61

# Re-run committees only
PYTHONPATH=$(pwd) python3 execution/extract_committees.py --record-id 212 --fact-id 61

# Or re-run full pipeline (company upserts safely, directors/committees upsert safely)
PYTHONPATH=$(pwd) python3 orchestration/run_pipeline.py --record-id 212
```

Then re-export to local and re-run Step 2 / Step 3 to confirm the fix.

---

## Config reference

| File | What to change |
|------|---------------|
| `config/prompts.py` | Add/clarify extraction rules; fix field definitions |
| `config/schemas.py` | Add/remove fields; adjust types or enums |
| `config/settings.py` | Change model, temperature, table names |
| `directives/extract_info.md` | Record last run, edge cases, learnings |
