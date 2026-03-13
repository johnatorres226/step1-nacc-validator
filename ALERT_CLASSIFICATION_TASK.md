# Alert Classification Task — Agent Context Document

**Date Generated**: March 13, 2026  
**Purpose**: Complete context for an agentic AI to implement NACC alert classification in this project with minimal disruption to the existing codebase.

---

## 1. What This Project Does (Brief)

`udsv4-redcap-qc-validator` is a CLI tool (`udsv4-qc`) that:
1. Fetches UDS V4 data from a REDCap report (`src/pipeline/core/fetcher.py`)
2. Routes records to packet-specific JSON rule sets (`config/I/`, `config/I4/`, `config/F/`, `config/M/`)
3. Validates each record against those rules using `nacc_form_validator.QualityCheck` (cerberus-based)
4. Writes a CSV of all failures to `output/QC_CompleteVisits_<datetime>/Errors/Final_Error_Dataset_<datetime>.csv`

All validation errors today are treated identically — there is **no distinction between `error` and `alert`** in any output.

---

## 2. Problem Being Solved

NACC's downstream processing system (flywheel-gear-extensions) classifies each validation failure as one of `"error"`, `"alert"`, or `"warning"` by consulting a REDCap QC Checks database. This project catches the same failures pre-upload but does not show that classification — so users cannot tell which failures will block submission vs. which are advisory alerts.

This task adds an `nacc_check_type` column to every error row in `Final_Error_Dataset_*.csv` indicating `"error"` or `"alert"` (with a fallback of `"error"` for any unmatched check).

---

## 3. The NACC Published Check Data (Source of Truth)

NACC publishes all check classifications publicly — **no login required** — at two paginated REDCap survey pages:

| Packet | URL | Record count |
|--------|-----|-------------|
| IVP (I + I4 packets) | `https://redcap.naccdata.org/surveys/?__report=F3ED7TRJKCRWW4ET` | 3,948 |
| FVP (F packet) | `https://redcap.naccdata.org/surveys/?__report=NPT99LJFXRWRAM7N` | TBD |

Each page renders a table. Page 1 of 4 is returned on the base URL; pages are accessed with `&__page=2`, `&__page=3`, etc.

### Column Structure of Each Row

```
check_code | error_type | form | packet_label | variable | check_category | short_desc | full_desc | cross_form | related_vars
```

**Example rows:**

| check_code | error_type | form | packet_label | variable | check_category | short_desc | full_desc |
|------------|-----------|------|-------------|----------|---------------|-----------|----------|
| `a1-ivp-c-108` | **Alert** | A1 | I - UDS Initial Visit (new participants) | ZIP | Conformity | ZIP conforms | Q14. ZIP must be between 006 and 999, or blank |
| `a1-ivp-c-002` | Error | A1 | I - UDS Initial Visit (new participants) | BIRTHMO | Conformity | BIRTHMO conforms | Q1a. BIRTHMO (birth month) must be between 1 and 12 |
| `a1-ivp-p-1001` | **Alert** | A1 | I - UDS Initial Visit (new participants) | RACEUNKN | Plausibility | If one race is known, cannot check Unknown | ... |
| `a1-i4vp-p-1008` | Error | A1 | I4 - UDS Initial Visit (existing participants) | BIRTHMO | Plausibility | BIRTHMO aligns with birth month from UDSv3 | ... |

### Key Patterns

- **Check code format**: `{form_lc}-{packet_abbrev}-{check_cat_abbrev}-{number}`
  - `ivp` = I packet (new participants)
  - `i4vp` = I4 packet (existing participants)
  - `fvp` = F packet (follow-up visit)
  - `c` = Conformity, `m` = Missingness, `p` = Plausibility

- **Alerts concentrate in**: Plausibility checks (`-p-` codes) and a small number of Conformity checks. Nearly all Missingness checks are Errors.

- **Packet label → internal packet code mapping**:
  - `"I - UDS Initial Visit (new participants)"` → `"I"`
  - `"I4 - UDS Initial Visit (existing participants)"` → `"I4"`
  - `"F - UDS Follow-Up Visit"` → `"F"`
  - `"M - ..."` → `"M"`

---

## 4. Current Codebase — Key Files and Their Roles

```
src/
  pipeline/
    core/
      pipeline.py          ← orchestrates the 5-stage pipeline
      fetcher.py           ← fetches data from REDCap
      data_processing.py   ← instruments ↔ rules mapping
    reports/
      report_pipeline.py   ← validate_data() — builds error dicts ← MAIN TOUCH POINT
    io/
      reports.py           ← export_error_report() writes Final_Error_Dataset_*.csv
      rule_loader.py       ← get_rules_for_record(), _NAMESPACE_DISCRIMINANTS
    config/
      config_manager.py    ← QCConfig, get_config()
config/
  I/rules/*.json           ← validation rules for I packet
  I4/rules/*.json          ← validation rules for I4 packet
  F/rules/*.json           ← validation rules for F packet
  M/rules/*.json           ← validation rules for M packet
```

### The Error Dict (one entry per failure, built in `report_pipeline.py`)

```python
{
    "ptid":                  pk_value,
    "instrument_name":       instrument_name,   # e.g. "a1", "b1", "c2"
    "variable":              actual_variable,   # e.g. "zip", "birthmo" (lowercase)
    "error_message":         msg,
    "current_value":         record_dict.get(actual_variable, ""),
    "packet":                packet_value,      # "I", "I4", "F", or "M"
    "json_rule_path":        rules_path,        # e.g. "config/I/rules/a1_rules.json"
    "redcap_event_name":     ...,
    "redcap_repeat_instance": ...,
    "visitdate":             ...,
    "qc_date":               ...,
    "discriminant":          ...,
    "error_interpretation":  "",               # always empty string today
    # TO ADD ↓
    # "nacc_check_type":    "error" | "alert"  # new field
}
```

### Where Errors Flow

```
validate_data()                    (report_pipeline.py)
    → all_errors.extend(errors)    (pipeline.py:185)
    → errors_df = pd.DataFrame(all_errors)
    → export_error_report(errors_df, ...)  (io/reports.py)
    → Final_Error_Dataset_*.csv
```

---

## 5. The Two Tasks

---

### TASK 1 — Scraper: Stage NACC Check Classifications Locally

**Goal**: Fetch the IVP and FVP published check tables and save them as a look-up file in the repo that can be regenerated or updated at any time.

**Where to create the scraper**: `redcap-tools/scrape_nacc_checks.py`

The `redcap-tools/` directory already exists in this repo and is the natural home for data-collection utilities.

**Output file**: `config/nacc_check_classifications.json`

#### Scraper Logic

```
for each survey URL (IVP, FVP):
    for page in 1..N (until no rows returned):
        GET https://redcap.naccdata.org/surveys/?__report=<TOKEN>&__page=<N>
        parse HTML table rows
        for each row:
            extract: check_code, error_type, form, packet_label, variable, check_category, short_desc
            normalize: error_type to lowercase ("error" / "alert")
            map packet_label → packet_code (I / I4 / F / M)
            normalize: form to lowercase (A1 → a1)
            normalize: variable to lowercase (ZIP → zip)
        accumulate results
save all results to config/nacc_check_classifications.json
```

**NOTE on HTML parsing**: The survey page returns a standard HTML `<table>`. Use `requests` + `html.parser` (stdlib). Do **not** add new dependencies; both are already available in the project. The table headers are:
- Column 0: check_code
- Column 1: error_type (the word "Error" or "Alert" or "Warning")
- Column 2: form (e.g., "A1")
- Column 3: packet_label (e.g., "I - UDS Initial Visit (new participants)")
- Column 4: variable
- Column 5: check_category
- Column 6: short_desc
- Column 7: full_desc (may be long)
- Columns 8+: cross_form refs, related vars (can be stored but not needed for lookup)

#### Output JSON Structure

Keyed by `(packet_code, form_lc, variable_lc, check_category)` for fast lookup. The natural representation: a flat list with a secondary lookup dict. Store both to keep the scraper output readable and the lookup fast.

```json
{
  "_meta": {
    "scraped_at": "2026-03-13T...",
    "sources": {
      "IVP": "https://redcap.naccdata.org/surveys/?__report=F3ED7TRJKCRWW4ET",
      "FVP": "https://redcap.naccdata.org/surveys/?__report=NPT99LJFXRWRAM7N"
    },
    "total_checks": 3948,
    "alert_count": 87
  },
  "checks": [
    {
      "check_code": "a1-ivp-c-108",
      "error_type": "alert",
      "packet": "I",
      "form": "a1",
      "variable": "zip",
      "check_category": "Conformity",
      "short_desc": "ZIP conforms",
      "full_desc": "Q14. ZIP (zip code) must be between 006 and 999, or blank"
    },
    ...
  ],
  "lookup": {
    "I|a1|zip|Conformity": "alert",
    "I|a1|raceunkn|Plausibility": "alert",
    "I|a1|birthmo|Conformity": "error",
    ...
  }
}
```

The `lookup` dict key format is `"{packet}|{form}|{variable}|{check_category}"` — all lowercase for packet/form/variable, original case for check_category.

#### Scraper CLI Usage

```
python redcap-tools/scrape_nacc_checks.py
```

Should print progress and write `config/nacc_check_classifications.json`. Add `--force` flag to overwrite existing file; default is to skip if file exists and is less than 30 days old. This makes it safe to re-run and safe to call from CI if ever needed.

#### Existing Dependencies Available

- `requests` — already in `requirements.txt`
- `html.parser` — stdlib
- `json` — stdlib
- `datetime` — stdlib
- `pathlib` — stdlib

---

### TASK 2 — Classify Errors: Add `nacc_check_type` to Error Output

**Goal**: At validation time, look up each error's `(packet, instrument_name, variable, inferred_check_category)` in the staged `config/nacc_check_classifications.json` and append `nacc_check_type` to the error dict.

**Constraint**: The only files to touch are:
1. **`src/pipeline/reports/report_pipeline.py`** — load the lookup once at module level and populate the field per error
2. **Nothing else** — `pipeline.py`, `io/reports.py`, `fetcher.py`, etc. are untouched

This works because `errors_df = pd.DataFrame(all_errors)` naturally picks up any new keys in the error dicts, and `df_errors.to_csv(...)` in `export_error_report()` writes all columns — no changes needed downstream.

#### Inferring Check Category

The check category (`Conformity`, `Missingness`, `Plausibility`) must be inferred from the error message because cerberus does not emit it directly.

Use this heuristic (covers ~95% of cases):

```python
def _infer_check_category(error_msg: str) -> str:
    msg_lc = error_msg.lower()
    # Missingness: presence/absence rules
    if any(p in msg_lc for p in ("cannot be blank", "must be blank", "must be present",
                                  "conditionally present", "conditionally blank",
                                  "cannot be empty", "required field")):
        return "Missingness"
    # Plausibility: logic/temporal/compatibility rules
    if any(p in msg_lc for p in ("temporalrules", "compatibility rule",
                                  "should not equal", "should equal",
                                  "should be less than", "should be greater")):
        return "Plausibility"
    # Default: value/range checks
    return "Conformity"
```

#### Lookup Function

Add to `report_pipeline.py`:

```python
import json as _json
from pathlib import Path as _Path

_CLASSIFICATIONS_PATH = _Path(__file__).parents[3] / "config" / "nacc_check_classifications.json"
_CHECK_LOOKUP: dict[str, str] = {}

def _load_check_lookup() -> dict[str, str]:
    """Load the pre-scraped NACC check classifications lookup. Returns empty dict on error."""
    global _CHECK_LOOKUP
    if _CHECK_LOOKUP:
        return _CHECK_LOOKUP
    if not _CLASSIFICATIONS_PATH.exists():
        logger.warning(
            "nacc_check_classifications.json not found. "
            "Run: python redcap-tools/scrape_nacc_checks.py"
        )
        return {}
    try:
        data = _json.loads(_CLASSIFICATIONS_PATH.read_text(encoding="utf-8"))
        _CHECK_LOOKUP = data.get("lookup", {})
        return _CHECK_LOOKUP
    except Exception:
        logger.warning("Failed to load nacc_check_classifications.json", exc_info=True)
        return {}


def _get_nacc_check_type(packet: str, instrument: str, variable: str, error_msg: str) -> str:
    """Return 'alert' or 'error' for this failure. Defaults to 'error' if not found."""
    lookup = _load_check_lookup()
    if not lookup:
        return "error"
    category = _infer_check_category(error_msg)
    key = f"{packet}|{instrument.lower()}|{variable.lower()}|{category}"
    return lookup.get(key, "error")
```

#### Integration Point in `validate_data()`

In the `errors.append(...)` block (around line 150 of `report_pipeline.py`), add one field:

```python
errors.append(
    {
        primary_key_field: pk_value,
        "instrument_name": instrument_name,
        "variable": actual_variable,
        "error_message": msg,
        "current_value": record_dict.get(actual_variable, ""),
        "packet": packet_value,
        "json_rule_path": rules_path,
        "redcap_event_name": record_dict.get("redcap_event_name", ""),
        "redcap_repeat_instance": record_dict.get("redcap_repeat_instance", ""),
        "visitdate": record_dict.get("visitdate", ""),
        "qc_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "discriminant": discriminant_info,
        "error_interpretation": "",
        "nacc_check_type": _get_nacc_check_type(       # ← NEW
            packet_value, instrument_name, actual_variable, msg
        ),
    }
)
```

That's the only code change needed in the validation pipeline.

---

## 6. Testing Requirements

### For the Scraper (`redcap-tools/scrape_nacc_checks.py`)

No automated tests required — it's a data-collection utility. It should print:
- How many records were fetched per page
- Total records
- Alert count vs error count
- Output file path

Verify manually by inspecting `config/nacc_check_classifications.json`:
- `_meta.total_checks` should be ~3948 for IVP
- `_meta.alert_count` should be non-trivial (likely 50–150)
- Sample a known alert: `lookup["I|a1|zip|Conformity"]` should be `"alert"`

### For the Classification Integration

Add a unit test to the existing test suite (`tests/`). The pattern should follow project conventions:

```python
# tests/test_nacc_check_classification.py

def test_get_nacc_check_type_returns_error_when_no_file(monkeypatch, tmp_path):
    """If classifications file is missing, default to 'error'."""
    from src.pipeline.reports import report_pipeline
    monkeypatch.setattr(report_pipeline, "_CLASSIFICATIONS_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(report_pipeline, "_CHECK_LOOKUP", {})
    result = report_pipeline._get_nacc_check_type("I", "a1", "birthmo", "cannot be blank")
    assert result == "error"


def test_get_nacc_check_type_returns_alert_from_lookup(monkeypatch):
    """When lookup contains the key, return its value."""
    from src.pipeline.reports import report_pipeline
    monkeypatch.setattr(report_pipeline, "_CHECK_LOOKUP", {"I|a1|zip|Conformity": "alert"})
    result = report_pipeline._get_nacc_check_type("I", "a1", "zip", "must be between 006 and 999")
    assert result == "alert"


def test_infer_check_category_missingness():
    from src.pipeline.reports.report_pipeline import _infer_check_category
    assert _infer_check_category("cannot be blank") == "Missingness"
    assert _infer_check_category("must be present") == "Missingness"


def test_infer_check_category_plausibility():
    from src.pipeline.reports.report_pipeline import _infer_check_category
    assert _infer_check_category("temporalrules violation") == "Plausibility"
    assert _infer_check_category("compatibility rule no: 3") == "Plausibility"


def test_infer_check_category_conformity_default():
    from src.pipeline.reports.report_pipeline import _infer_check_category
    assert _infer_check_category("must be between 1 and 12") == "Conformity"
```

---

## 7. Constraints and Philosophy

These constraints are non-negotiable and reflect the existing codebase's design philosophy:

1. **No new dependencies**. Use `requests` (already present) and stdlib only. Do not add `beautifulsoup4`, `lxml`, `httpx`, or any other library.

2. **No restructuring of existing files**. Do not refactor `pipeline.py`, `io/reports.py`, `config_manager.py`, or any non-touched file. All changes are additive.

3. **Graceful degradation**. If `nacc_check_classifications.json` is missing or malformed, the pipeline must continue running normally — `nacc_check_type` simply defaults to `"error"`. A single log warning is sufficient. Never raise.

4. **Single concern per task**. The scraper only scrapes and saves. The classifier only reads and classifies. They do not call each other.

5. **The scraper is a standalone tool**, not imported by the pipeline. It is run manually or via a maintenance script. Its output (`config/nacc_check_classifications.json`) is what the pipeline consumes.

6. **Do not touch** `nacc_form_validator/` — that is a vendored/library package and is out of scope.

7. **The `lookup` dict in the JSON is the performance contract** — the pipeline reads it once at module level (cached in `_CHECK_LOOKUP`) and does O(1) dict lookups at validation time. No re-reading on each record.

8. **Column ordering in CSV**: The new `nacc_check_type` column will appear in whatever position `pd.DataFrame(all_errors)` places it (naturally the last column added). Do not reorder columns.

---

## 8. File Change Summary

| File | Action | Notes |
|------|--------|-------|
| `redcap-tools/scrape_nacc_checks.py` | **Create new** | Standalone scraper, ~120 lines |
| `config/nacc_check_classifications.json` | **Create (generated)** | Output of the scraper |
| `src/pipeline/reports/report_pipeline.py` | **Edit** | Add `_infer_check_category`, `_load_check_lookup`, `_get_nacc_check_type` functions + one field in `errors.append(...)` |
| `tests/test_nacc_check_classification.py` | **Create new** | Unit tests for classifier functions |

No other files are modified.

---

## 9. Verification After Implementation

After both tasks are complete, do a full end-to-end smoke test:

```powershell
# Step 1: Run the scraper
python redcap-tools/scrape_nacc_checks.py

# Verify output exists
Get-Content config/nacc_check_classifications.json | ConvertFrom-Json | Select-Object _meta

# Step 2: Run the pipeline
poetry run udsv4-qc -i JT

# Step 3: Check the output CSV has the new column
$latest = Get-ChildItem output/ | Sort-Object LastWriteTime | Select-Object -Last 1
$csv = Get-ChildItem "$($latest.FullName)/Errors/" -Filter "*.csv" | Select-Object -First 1
$data = Import-Csv $csv.FullName
$data | Select-Object -First 5 | Format-Table ptid, instrument_name, variable, nacc_check_type -AutoSize

# Verify alerts appear
$data | Where-Object { $_.nacc_check_type -eq "alert" } | Measure-Object
```

Expected: `nacc_check_type` column present; some rows show `"alert"`, most show `"error"`.

---

## 10. Quick Reference — Known Alert Check Codes (IVP Sample)

These are confirmed alerts from the IVP survey page, useful for testing the scraper and verifying lookups:

| check_code | packet | form | variable | check_category |
|-----------|--------|------|----------|---------------|
| `a1-ivp-c-108` | I | a1 | zip | Conformity |
| `a1-ivp-c-124` | I | a1 | priocc | Conformity |
| `a1-ivp-p-1001` | I | a1 | raceunkn | Plausibility |
| `a1-ivp-p-1002` | I | a1 | gendkn | Plausibility |
| `a1-ivp-p-1003` | I | a1 | gennoans | Plausibility |
| `a1-ivp-p-1004` | I | a1 | sexorndnk | Plausibility |
| `a1-ivp-p-1005` | I | a1 | sexornnoan | Plausibility |
| `a1-ivp-p-1006` | I | a1 | served | Plausibility |
| `a1-ivp-p-1007` | I | a1 | frmdatea1 | Plausibility |
| `a1-ivp-p-1008..1014` | I | a1 | livsitua/residenc | Plausibility |
| `a1-i4vp-p-1001..1032` | I4 | a1 | various | Plausibility |
| `a1a-ivp-p-1003..1008` | I | a1a | various | Plausibility |
| `a2-ivp-p-1001..1002` | I | a2 | inlivwth | Plausibility |
