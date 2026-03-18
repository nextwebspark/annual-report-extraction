# Playbook: Fetch Records to Local Data Folder

Use this when you want to pull records from Supabase to `data/` for offline testing or evaluation.

---

## Folder Structure

```
data/
├── input/          ← markdown source files (one per record)
│   ├── index.json  ← lookup: id, document_name, char length
│   └── record_<id>.md
└── output/
    └── record_<id>/
        ├── summary.json          ← counts + IDs at a glance
        ├── company.json          ← companies table row
        ├── company_facts.json    ← company_facts rows
        ├── board_directors.json  ← board_directors rows
        └── board_committees.json ← board_committees rows
```

---

## Step 1 — Fetch markdown inputs

Fetch N records from `landing_parse_cache` where `markdown_llm_clean` is populated.

```python
# Run from project root
python3 - <<'EOF'
import json, os
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")
from supabase import create_client

db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

# ── Configure ──────────────────────────────────────────────────────────────
LIMIT       = 20          # how many records to fetch
OFFSET      = 0           # skip first N (for pagination)
RECORD_IDS  = []          # leave empty to fetch by limit, or set e.g. [84, 212, 213]
# ──────────────────────────────────────────────────────────────────────────

os.makedirs("data/input", exist_ok=True)

if RECORD_IDS:
    result = (
        db.table("landing_parse_cache")
        .select("id, document_name, page_count, markdown_llm_clean")
        .in_("id", RECORD_IDS)
        .execute()
    )
else:
    result = (
        db.table("landing_parse_cache")
        .select("id, document_name, page_count, markdown_llm_clean")
        .not_.is_("markdown_llm_clean", "null")
        .range(OFFSET, OFFSET + LIMIT - 1)
        .execute()
    )

records = result.data
index   = []

for r in records:
    rid      = r["id"]
    doc_name = r.get("document_name", f"record_{rid}")
    markdown = r.get("markdown_llm_clean", "")

    path = f"data/input/record_{rid}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"<!-- id={rid} document_name={doc_name} -->\n\n{markdown}")

    index.append({
        "id": rid,
        "document_name": doc_name,
        "page_count": r.get("page_count"),
        "markdown_length": len(markdown),
        "file": path,
    })
    print(f"  [{rid:>4}] {doc_name[:60]:<60} {len(markdown):>8,} chars")

with open("data/input/index.json", "w") as f:
    json.dump(index, f, indent=2)

print(f"\nSaved {len(index)} files → data/input/")
EOF
```

---

## Step 2 — Run the pipeline for a specific record

```bash
PYTHONPATH=$(pwd) python3 orchestration/run_pipeline.py --record-id <ID>
```

Example:
```bash
PYTHONPATH=$(pwd) python3 orchestration/run_pipeline.py --record-id 212
```

---

## Step 3 — Export extracted output from Supabase to local

After the pipeline runs, fetch all 4 table outputs for a record and save them locally.
You need the `company_id` from the pipeline summary.

```python
# Run from project root — set RECORD_ID and COMPANY_ID before running
python3 - <<'EOF'
import json, os
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")
from supabase import create_client

db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

# ── Configure ──────────────────────────────────────────────────────────────
RECORD_ID  = 212    # landing_parse_cache id
COMPANY_ID = 135    # from pipeline summary output
# ──────────────────────────────────────────────────────────────────────────

company = db.table("companies").select("*").eq("id", COMPANY_ID).single().execute().data
facts   = db.table("company_facts").select("*").eq("company_id", COMPANY_ID).execute().data
fact_ids = [f["id"] for f in facts]

directors  = []
committees = []
for fid in fact_ids:
    directors  += db.table("board_directors").select("*").eq("fact_id", fid).execute().data
    committees += db.table("board_committees").select("*").eq("fact_id", fid).execute().data

out_dir = f"data/output/record_{RECORD_ID}"
os.makedirs(out_dir, exist_ok=True)

for fname, payload in {
    "company.json":          company,
    "company_facts.json":    facts,
    "board_directors.json":  directors,
    "board_committees.json": committees,
}.items():
    with open(f"{out_dir}/{fname}", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)

summary = {
    "record_id": RECORD_ID, "company_id": COMPANY_ID,
    "company_name": company.get("company_name_value"),
    "fact_ids": fact_ids,
    "counts": {
        "company_facts": len(facts),
        "board_directors": len(directors),
        "board_committees": len(committees),
    },
}
with open(f"{out_dir}/summary.json", "w") as f:
    json.dump(summary, f, indent=2)

print(f"Saved to {out_dir}/")
print(json.dumps(summary, indent=2))
EOF
```

---

## Tips

- To re-fetch a single record already in `data/input/`, just delete its `.md` file and re-run Step 1 with `RECORD_IDS = [<id>]`.
- `data/input/index.json` is rebuilt every time Step 1 runs — it always reflects what's on disk.
- Output files are overwritten each time Step 3 runs (safe to re-run).
