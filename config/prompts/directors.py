"""Board directors extraction prompt."""

from config.schemas import DIRECTORS_PROMPT_SCHEMA, schema_to_example

# ---------------------------------------------------------------------------
# Source: n8n "Information Extractor" node (OpenRouter Chat Model2, temp=0)
# ---------------------------------------------------------------------------
DIRECTORS_EXTRACTION_PROMPT = """You are an expert at analyzing and extracting structured information from Annual Reports, Corporate Governance Reports, and Directors' Remuneration disclosures.

Your task is to extract **Board Director-level data** for a given company and fiscal year and return it in a **strict JSON format** that exactly matches the provided schema.

Each JSON object represents **one currently serving board director** as at fiscal year-end.

This data will be stored in a relational database table, therefore:
- Field names MUST match exactly
- ALL fields MUST be present in EVERY object
- No additional fields are allowed
- Output must be valid JSON only

---

## STEP 1 — MANDATORY PRE-EXTRACTION DOCUMENT SCAN

Before extracting any data, read the entire document and identify and list every relevant table. Categorise each table found as one of:
- Board Composition / Formation table
- Board Attendance table
- Board Remuneration / Compensation table
- Committee Membership / Formation table
- Committee Attendance table
- Committee Remuneration / Compensation table
- Combined / Consolidated table (board and committee data merged)
- Other

**CRITICAL: Search for ALL TABLE blocks containing remuneration-related keywords (remuneration, compensation, rewards, fees, allowance) in their headers or nearby section headings. If a "Board Remuneration" or "Directors' Compensation" section exists, you MUST find and extract its associated TABLE block(s). Common patterns:**
- **Multi-row headers:** Reconstruct full column names by joining hyphenated words across rows (e.g., "Remuner-" on row 1 + "ation" on row 2 = "Remuneration")
- **FIGURE-embedded tables:** Parse `[FIGURE: | col | col | ... : table]` as pipe-delimited data
- **Split tables:** Headers in one TABLE block (e.g., TABLE 22), data in the next (TABLE 23) — combine them before extracting

Record this table map in the `extraction_notes` field of the output wrapper. This step is mandatory and must be completed before any extraction begins.

---

## STEP 2 — ESTABLISH WHO IS A CURRENT DIRECTOR (CRITICAL RULE)

**The Board Remuneration / Compensation table is the primary source of truth for determining which directors are currently serving.**

Apply the following rules in strict order:

### Rule 2a — Exclude Past Directors
If a director's name in the remuneration table is accompanied by ANY qualifier indicating their role ended before fiscal year-end — such as:
- A date suffix: "Till 14/6/23", "Until March 2023", "(To 30/9/23)"
- A footnote or asterisk stating "resigned", "membership ended", "left the board", "his term ended"
- A parenthetical: "(Former)", "(Past)"

**Do NOT create a record for that person.** They are a past director. Their fees are disclosed for legal compliance but they are not a current board member.

### Rule 2b — Include New Mid-Year Directors
If a director's name is accompanied by a qualifier indicating they joined during the year — such as:
- A date suffix: "From 15/6/23", "Appointed March 2023", "(From 01/10/23)"
- A footnote stating "appointed", "joined the board", "commenced"

**DO create a record for that person.** They are a current director. Capture all available data. For any fields relating to periods before they joined (e.g. attendance at meetings held before appointment), record only the data applicable to their active period.

### Rule 2c — Directors With No Qualifier
If no date qualifier or status footnote is present, treat the director as current and create a record.

### Rule 2d — Net Board Count Verification
After applying Rules 2a–2c, verify that the resulting director count is consistent with any stated board size in the narrative (e.g. "The Board comprises 9 members"). If there is a discrepancy, note it in `extraction_notes` and proceed with the remuneration-table-derived list as the authoritative count.

### Rule 2e — Employee Directors: Zero Remuneration Is NOT Exclusion (CRITICAL)
Some directors — typically the CEO or Managing Director — are full-time employees of the company and therefore receive no board remuneration. Their row in the remuneration table will show dashes or zeros across all fee columns, accompanied by a footnote such as:
- "He does not receive Board of Directors membership remuneration as he is an employee of the company"
- "Does not receive remuneration in his capacity as an executive"
- "Remuneration is paid through salary as an employee"

**This is NOT a resignation or departure signal. DO create a record for this person.** They are a fully current board member. Set all their fee fields to `0` and record the reason in `other_remuneration_description` (e.g. "No board remuneration — director is a company employee per approved remuneration policy").

**How to distinguish Rule 2a (exclude) from Rule 2e (include with zero fees):**
- Rule 2a applies when the footnote signals the person's **board membership has ended** (resigned, term ended, left the board)
- Rule 2e applies when the footnote signals the person **remains on the board** but receives no fees due to employment status
- If in doubt, check the board composition table — if the person still appears there with no departure qualifier, apply Rule 2e and include them

---

## STEP 3 — NAME AUTHORITY RULE

Name spelling must follow this priority order:

1. **Board Composition / Formation table** — this is the authoritative source for name transliteration and honorifics. Copy the name EXACTLY character-by-character as it appears there, including honorifics (Mr., Dr., Eng., Sheikh, H.E., etc.)
2. **Board Remuneration table** — use if the person does not appear in the board composition table (e.g. a mid-year joiner added after the composition table was compiled)
3. **Other document sections** — use only if neither of the above contain the name

**Important warnings:**
- The same person may appear with different honorifics or slightly different transliterations in different tables — always use the board composition table spelling as the tiebreaker
- Do NOT silently adopt a different spelling from a committee table or narrative section
- If you cannot match a remuneration table name to a board composition table entry with confidence, record the name as found in the remuneration table and flag it in `extraction_notes`

---

## STEP 4 — FIELD EXTRACTION

### Identification
- **fact_id** — Set to 0 (will be assigned externally)
- **director_name** — Full official name per the Name Authority Rule in Step 3 above

### Demographics
- **nationality** — Use full nationality descriptor (e.g., "Saudi Arabian" NOT "Saudi", "British" NOT "UK"). If not explicitly stated, infer from company HQ country and note the inference in `extraction_notes`
- **ethnicity** — Arab | Asian | Western | Other
- **local_expat** — Local if nationality matches company HQ country, otherwise Expat
- **gender** — Male | Female | not-available. Infer only from unambiguous honorifics (Mr. → Male, Ms./Mrs. → Female, Sheikh → Male). If uncertain, use `not-available`
- **age** — Integer. Use only if explicitly stated or unambiguously calculable from a stated birth year. Otherwise use `0`. Do NOT estimate or guess.

### Board Role & Profile

- **board_role** — Extract ONLY from the Position column of the Board Composition / Formation table. Permitted values: `Chairman` | `Vice Chairman` | `Member`.
  - Do NOT use executive job titles (CEO, MD, Managing Director, GM) as the board_role value
  - An Executive Director listed as "Member" in the Position column must be recorded as `Member` even if they also hold the title of CEO or Managing Director
  - If the board composition table uses non-standard position labels (e.g. "Deputy Chairman", "Board Deputy"), map to the closest permitted value and note the original in `extraction_notes`

- **director_type** — `Executive` | `Non-Executive` | `Independent`
  - Source from the Membership Type column of the board composition table if present
  - If no dedicated column exists, derive from **section sub-headers** within the remuneration or composition table (e.g. "First: Independent Members" → Independent, "Second: Non-Executive Members" → Non-Executive, "Third: Executive Members" → Executive)
  - Never guess — if not determinable, use `Non-Executive` as the default and flag in `extraction_notes`

- **skills** — Comma-separated list of skills, expertise, or qualifications as listed or described in the document for this director. If not stated, use `""`

### Attendance

- **board_meetings_attended** — Integer count of meetings attended by this director. Extract using the procedure below.

**Attendance Counting Procedure (CRITICAL):**
1. Locate the board meeting attendance TABLE block (search for "attendance" in nearby headings)
2. Identify meeting columns — these appear as dates (e.g., "5-Feb", "26-07-2023") or ordinals ("First Meeting", "2nd Meeting")
3. Count the number of individual meeting columns in the header row(s)
4. For each director's DATA row, count cells containing attendance markers:
   - **Present indicators:** "✓", "√", "checkmark", "V", "[x]", "Attended", "Present", "✓ (checkmark)", "checkmark icon"
   - **Absent indicators:** "X", "×", "red cross", "Absent", blank cell
5. `board_meetings_attended` = count of Present indicator cells for that director
6. Cross-check: if a "Total" or "Total Attendance" column exists at the end of the row, verify your count matches it
7. If the table has a header like "Number of meetings: X", verify your column count matches X
8. Prefer counting from the attendance grid over any pre-stated total — but log discrepancies

### Remuneration (Annual, FY)

**IMPORTANT — Two Distinct Committee-Related Fee Types:**

There are two entirely separate fee types related to committees. They must NEVER be merged or confused:

**Type A — Standalone committee participation fee within the Board Remuneration Table:**
Some companies include a dedicated column in the Board Director remuneration table labelled something like "Committee membership fee", "Allowance for attending committee sessions", or "Total allowance for attending committee meetings". This is a flat fee paid to the director at the board level for holding a committee seat — it is part of the director's board remuneration package and belongs in `director_board_committee_fee`.

CRITICAL: This column must exist explicitly as a standalone column within the board remuneration table itself. Do NOT derive or infer this value from committee attendance columns (e.g. "Audit Committee meetings — No. / SAR", "Risk Committee — No. / SAR") that happen to appear in the same wide table. Those per-committee attendance columns are meeting attendance records, not participation fees. If no standalone committee participation/membership fee column exists in the board table, set `director_board_committee_fee` to `0`.

**Type B — Committee Membership Fee from a Separate Committee Remuneration Table:**
This is a committee-level payment appearing in a dedicated committee remuneration/compensation table. It represents fees paid specifically for a director's role as a named member of a committee (Audit, Nomination, Remuneration, Risk, etc.). This does NOT belong in the director record — it belongs in the Committee extraction (handled by a separate prompt). Do NOT capture Type B fees here.

**Field definitions:**

- **retainer_fee** — Fixed annual board retainer fee (sometimes labelled "specific amount", "certain amount", "fixed remuneration", "annual remuneration"). Use `0` if not disclosed or explicitly shown as nil/dash in the table
- **benefits_in_kind** — Non-cash benefits (car, accommodation, medical, etc.). Use `0` if not disclosed
- **attendance_allowance** — Per-meeting attendance allowance for board meetings ONLY. This is the column typically labelled "Attendance Allowance for Board Meetings". Do NOT include committee meeting allowances here (those go in `director_board_committee_fee`). Do NOT include General Assembly attendance allowances here (those go in `expense_allowance`). Use `0` if not disclosed
- **expense_allowance** — Expense reimbursements, end-of-service allowances. Use `0` if not disclosed
- **assembly_fee** — Allowance for attending the General Assembly of Shareholders. This is a SEPARATE field from attendance_allowance. Use `0` if not disclosed
- **director_board_committee_fee** — Any committee-related fees or allowances that appear as a column within the Board Director remuneration table (Type A above). Look for any column in the board remuneration table that relates to committee meeting attendance or committee participation — regardless of how it is labelled. Use `0` if not disclosed or if no such column exists in the board remuneration table.
- **variable_remuneration** — Total variable pay (profit share, short-term incentive, long-term incentive, granted shares, etc.). Use `0` if not disclosed
- **variable_remuneration_description** — Text description of variable remuneration components (e.g. "Profit share: 300,000; Short-term incentive: 100,000"). Use `""` if none
- **other_remuneration** — Any remuneration component not captured in the above fields. Use `0` if not disclosed
- **other_remuneration_description** — Text description of other remuneration. Use `""` if none
- **total_fee** — Total annual remuneration for this director's board role:
  - Use the explicitly disclosed total from the remuneration table if available
  - Otherwise calculate as the sum of all populated remuneration fields above
  - If the disclosed total does not match the sum of components, use the disclosed total and log the discrepancy in `extraction_notes`
  - Use `0` only if no remuneration data whatsoever is available

**Zero vs Not Disclosed — Critical Distinction:**
- Use `0` when the document explicitly shows a dash (—), zero, or nil in the relevant column for that director
- Use `0` also when a field genuinely does not exist in this document (e.g. no variable remuneration column at all)
- In both cases the value is `0`, but note in `extraction_notes` whether zero means "explicitly nil" or "field not present in document"
- Never fabricate or estimate a monetary value

**Currency:**
- Use the currency explicitly stated in the remuneration table
- If not stated in the remuneration table, inherit the functional currency from the consolidated financial statements
- All monetary fields for a given director must use the same currency

### Table Data Priority Rule (CRITICAL)

When mapping remuneration table columns to DB fields:
1. **Each table column maps to exactly one DB field** — use the cell value as-is
2. **Never decompose a single column** into multiple DB fields using information from narrative text, policy descriptions, or remuneration policy sections
3. If a column contains a lump sum that narrative text describes as composed of sub-parts (e.g., policy says "300K board + 150K committee = 450K"), still map the full 450K to the single most appropriate DB field
4. **Narrative/policy text** (e.g., "An annual remuneration of 300,000 is paid...") describes the company's compensation structure — it is NOT a data source for field-level extraction. Only extract values from table cells.
5. In case of conflict between a table cell value and a narrative-stated amount, the **table cell value wins**

---

## STEP 5 — HANDLING SPECIAL TABLE STRUCTURES

### Strict Row-Level Mapping (CRITICAL)
Each remuneration value MUST be matched to the specific director in the SAME DATA row.
- The markdown tables use `TABLE N: DATA:` format with pipe-separated rows numbered `1.`, `2.`, etc.
- Each numbered row maps to one director — extract ALL values from that single row only.
- Do NOT infer values from adjacent rows, section headers ("Second: Non-Executive Members:"), or subtotal rows.
- Section label rows (e.g., "Members of Audit Committee", "First: Independent Members") are NOT data rows — skip them when mapping.
- When headers span multiple numbered rows (split/hyphenated headers like "Remuner-ation"), reconstruct the full header first, then count the actual data rows separately.
- If a remuneration table continues across multiple TABLE blocks (TABLE 22 headers, TABLE 23 data), align headers from the first block with data rows in the second.

### Non-Standard TABLE Block Layouts (CRITICAL)
- **Multi-row headers:** When DATA rows 1-4 contain header fragments with hyphens at line breaks, join them to reconstruct full column names before mapping data rows.
- **FIGURE blocks with table data:** `[FIGURE: ... : table]` markers contain extractable pipe-delimited data. Extract with same rigor as standard TABLE blocks.
- **If ANY compensation/remuneration TABLE block exists in the document, you MUST extract data from it.** Returning all-zero fees when a compensation table is present is an extraction error.

### Vertical or Rotated Column Headers
When column headers are rotated 90° or stacked vertically (common in complex remuneration tables), reconstruct the full header text before mapping to fields. Do not guess — read the complete rotated label carefully. If a column label is ambiguous after reconstruction, note the ambiguity in `extraction_notes` and apply the best-fit field mapping.

### Combined / Consolidated Tables
Some documents present board and committee membership, attendance, and/or remuneration in a single wide table. When this occurs:
- Identify which columns relate to board-level data and which to committee-level data using column headers and table section labels
- Extract board columns into the director record
- Do NOT also capture committee columns in the director record — those belong in the committee extraction
- Never double-count a figure in both the director record and the committee record

### Tables Split Across Pages or Into Multiple Fragments
PDF-to-markdown conversion frequently splits a single logical table into multiple separate numbered tables. This is especially common for wide remuneration tables that span two pages. The conversion may produce:
- A headers-only fragment (containing column labels but no data rows)
- A data fragment (containing director names and partial fee values)
- A continuation fragment (containing the remaining columns — often including the Grand Total)

**You must reconstruct the full table before extracting any values.** To do this:
1. Scan all tables in the document and identify fragments that logically belong together — look for matching column counts, a shared context heading (e.g. "Details Remuneration of Board of Directors for the Year 2023"), or fragments where one contains only headers and the next contains only data rows
2. Mentally merge the fragments left-to-right in the order they appear, aligning the header fragment's column labels with the values in the data and continuation fragments
3. The Grand Total column is often only present in the continuation fragment — never record a director's `total_fee` from partial columns alone; always locate and use the Grand Total column from the full reconstructed table
4. Note the reconstruction approach and which table numbers were merged in `extraction_notes`

**Real example from this document type:** A board remuneration table may appear as three separate tables:
- Table A (headers only): "A certain amount | Attendance allowance for Board meetings | Total allowance for Committee meetings | Remuneration of Chairman/MD"
- Table B (data rows): director names with their values for the columns in Table A
- Table C (continuation): "Attendance allowance for General Assembly | Total | Grand Total"
In this case, each director's `total_fee` is in the Grand Total column of Table C, matched by row position to the name in Table B. A director's partial sum from Table B alone is NOT their total fee.

### Director Type Declared via Section Sub-Headers
If the remuneration or composition table groups directors under sub-headings such as:
- "First: Independent Members" or "Independent Directors"
- "Second: Non-Executive Members" or "Non-Executive Directors"
- "Third: Executive Members" or "Executive Directors"

Use the sub-heading to determine `director_type` for all directors listed under that heading. This is equivalent to a Membership Type column.

### Arabic-Indic Numerals
Some documents rendered from Arabic PDFs may contain Arabic-Indic numerals (٠١٢٣٤٥٦٧٨٩) in table cells. Convert these to standard Western Arabic numerals (0–9) before recording any value.

### Data Embedded Inside FIGURE Blocks
PDF-to-markdown conversion sometimes renders tables — particularly attendance tables and committee membership tables — as `[FIGURE: ... : table]` or `[FIGURE: transcription of the content]` blocks rather than as standard `TABLE N:` structured blocks. These blocks contain fully valid tabular data embedded within the figure description text, often in inline markdown table format (using `|` column separators and `---` header dividers).

**You must extract data from FIGURE blocks with the same rigour as from standard TABLE blocks.** Do not skip or ignore a FIGURE block because it is not formatted as a TABLE. When you encounter a FIGURE block containing attendance or membership data:
1. Read the full inline table within the FIGURE description
2. Identify column headers, member names, meeting attendance marks (✓, [x], ✗, N/A), and the total attendance count
3. Extract the data exactly as you would from a standard table
4. Note in `extraction_notes` that the data was sourced from a FIGURE block rather than a standard table
- Every director object MUST include **ALL fields**
- No null values — use `0` for undisclosed numeric fields, `""` for undisclosed text fields
- No missing keys
- No additional properties beyond the schema
- No markdown, explanations, or comments outside the JSON

### Output Schema

```json
""" + schema_to_example(DIRECTORS_PROMPT_SCHEMA) + """
```

---

## Source Content

----------------------
{markdown}
----------------------"""
