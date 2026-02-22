# Project Refactoring Plan — `project-refactoring` Branch

> **Branch**: `project-refactoring`  
> **Created**: 2026-02-21  
> **Goal**: Collapse overengineered pipeline infrastructure into a lightweight, maintainable system without changing external behavior.  
> **Prior Work**: Phases 1–6 already completed on this branch (removed duplicate rule loading, empty `__init__.py` files, deprecated validation functions, inlined `run_improved_report_pipeline`, dead error classes, ~850 lines of dead code). This plan covers the **remaining structural consolidation**.

---

## Current State (Post Phase 6)

| File | Lines | Package |
|------|------:|---------|
| `config/config_manager.py` | 455 | config |
| `core/data_processing.py` | 224 | core |
| `core/fetcher.py` | 397 | core |
| `core/pipeline_orchestrator.py` | 555 | core |
| `core/pipeline_results.py` | 145 | core |
| `core/validation_logging.py` | 176 | core |
| `core/visit_processing.py` | 204 | core |
| `io/context.py` | 90 | io |
| `io/hierarchical_router.py` | 246 | io |
| `io/packet_router.py` | 218 | io |
| `io/reports.py` | 732 | io |
| `io/rules.py` | 210 | io |
| `io/unified_rule_loader.py` | 221 | io |
| `logging/logging_config.py` | 226 | logging |
| `processors/instrument_processors.py` | 188 | processors |
| `reports/report_pipeline.py` | 512 | reports |
| `utils/schema_builder.py` | 51 | utils |
| **Total src/pipeline** | **4,854** | |
| **Total tests/** | **3,073** | |

### Dependency Map (who imports what)

```
cli.py
  └─ pipeline_orchestrator (via report_pipeline.run_report_pipeline)

report_pipeline.py
  ├─ pipeline_orchestrator.PipelineOrchestrator
  ├─ hierarchical_router.HierarchicalRuleResolver   ← validate_data()
  ├─ unified_rule_loader.UnifiedRuleLoader           ← validate_data_unified() [UNUSED]
  └─ schema_builder._build_schema_from_raw

pipeline_orchestrator.py
  ├─ pipeline_results.* (7 dataclasses)
  ├─ fetcher.RedcapETLPipeline    (stage 1)
  ├─ rules.load_rules_for_instruments (stage 2, lazy import)
  ├─ hierarchical_router + packet_router (stage 2, lazy import)
  ├─ data_processing.*            (stage 3)
  ├─ visit_processing.*           (stage 3)
  ├─ validation_logging.*         (stage 4)
  ├─ report_pipeline.validate_data (stage 4)
  └─ reports.ReportFactory + context.* (stage 5)

hierarchical_router.py
  └─ packet_router.PacketRuleRouter

fetcher.py
  └─ rules.load_rules_for_instruments

instrument_processors.py
  └─ rules.load_dynamic_rules_for_instrument  (absolute import!)

reports.py
  ├─ context.ExportConfiguration, ProcessingContext, ReportConfiguration
  └─ rules.load_json_rules_for_instrument (lazy, in one method)
```

---

## Refactoring Phases

Each phase is a **single commit** targeting one area. Phases are ordered by dependency — later phases depend on earlier ones being complete. Every phase ends with `pytest` passing and a manual smoke test of the CLI.

---

### Phase 7: Collapse Rule Routing → Single `rule_loader.py`

**Files affected**: `io/packet_router.py`, `io/hierarchical_router.py`, `io/unified_rule_loader.py`, `io/rules.py`  
**Target**: Replace all 4 files with one new `io/rule_loader.py` (~150 lines)  
**Estimated reduction**: 895 → ~150 lines (−745)

#### Why

Four separate modules with three caching layers (`_rule_cache`, `_resolution_cache`, `_packet_cache`), factory functions, cache stats, and preloading — all doing variations of "load JSON from `config/{packet}/`, merge into a dict, handle C2/C2T." The project docs already mark the hierarchical approach as deprecated in favor of the unified approach, but both coexist.

#### What to Build

A single `rule_loader.py` module containing:

```python
# io/rule_loader.py  (~150 lines)

_packet_cache: dict[str, dict] = {}

def load_rules_for_packet(packet: str, config: QCConfig | None = None) -> dict:
    """Load all JSON rule files for a packet directory, merge into flat variable→rules dict.
    
    Handles caching per packet. Returns {variable_name: {rule_dict}} for all
    instruments in that packet.
    """

def resolve_dynamic_rules(record: dict, base_rules: dict) -> dict:
    """Handle C2/C2T discrimination.
    
    Check the discriminant variable in the record. If the instrument is a 
    dynamic rule instrument (C2), load the variant-specific rules (C2T) and 
    merge/override the base rules.
    """

def get_rules_for_record(record: dict, config: QCConfig | None = None) -> dict:
    """Main entry point: determine packet from record, load rules, apply dynamic resolution."""

def clear_cache() -> None:
    """Reset the module-level cache."""
```

#### Step-by-Step

1. **Create `io/rule_loader.py`** with the functions above, extracting the working logic from:
   - `UnifiedRuleLoader.load_packet_rules()` → `load_rules_for_packet()`
   - `HierarchicalRuleResolver._apply_dynamic_routing()` → `resolve_dynamic_rules()`
   - `UnifiedRuleLoader.get_rules_for_record()` → `get_rules_for_record()`
   - Keep the JSON loading logic from `rules.load_json_file()` and `rules.merge_rule_dictionaries()` inline or as private helpers.

2. **Update all consumers** to import from `io.rule_loader`:
   - `report_pipeline.py`: Replace `HierarchicalRuleResolver` usage in `validate_data_with_hierarchical_routing()` with `get_rules_for_record()`.
   - `report_pipeline.py`: Remove `validate_data_unified()` entirely (unused in production).
   - `pipeline_orchestrator.py` stage 2: Replace `HierarchicalRuleResolver` + `PacketRuleRouter` lazy imports with `rule_loader.load_rules_for_packet()`.
   - `fetcher.py`: Replace `from ..io.rules import load_rules_for_instruments` with `from ..io.rule_loader import load_rules_for_packet`.
   - `instrument_processors.py`: Replace `from pipeline.io.rules import load_dynamic_rules_for_instrument` with relative import from `rule_loader`.
   - `reports.py`: Replace lazy `from .rules import load_json_rules_for_instrument` with `rule_loader`.

3. **Delete** `io/packet_router.py`, `io/hierarchical_router.py`, `io/unified_rule_loader.py`, `io/rules.py`.

4. **Update tests**:
   - `test_data_routing.py`: Rewrite to test `rule_loader` functions directly (load per packet, C2/C2T resolution, caching, error handling). Target ~120 lines.
   - `test_unified_rule_loader.py`: **Delete** (subsumed by updated `test_data_routing.py`).
   - `test_unified_validation.py`: **Delete** or merge remaining useful integration tests into `test_pipeline_validation.py`.

5. **Run tests**: `pytest -x` — all must pass.

#### Verification Checklist

- [ ] `load_rules_for_packet("I")` returns merged rules from all `config/I/*.json` files
- [ ] `load_rules_for_packet("I4")` and `load_rules_for_packet("F")` work similarly
- [ ] `get_rules_for_record({"packet": "I", ...})` returns correct rules
- [ ] C2/C2T discrimination works: record with `rmmode = 1` gets C2T rules
- [ ] Cache works: second call doesn't re-read files
- [ ] `clear_cache()` forces re-read on next call
- [ ] No references to `PacketRuleRouter`, `HierarchicalRuleResolver`, `UnifiedRuleLoader`, or `RulesCache` remain in codebase

---

### Phase 8: Strip Reports to 4 Core Outputs

**Files affected**: `io/reports.py`, `io/context.py`  
**Target**: Reduce `reports.py` from 732 → ~150 lines; simplify `context.py`  
**Estimated reduction**: ~822 → ~180 lines (−642)

#### Why

`ReportFactory` has 10+ generation methods. Only 4 outputs are actually needed for the QC workflow:  
1. **Error report** (CSV) — the validation errors  
2. **Validation logs** (CSV) — per-record completeness logs  
3. **Data fetched** (CSV) — raw data audit trail  
4. **JSON tracking** — structured JSON of the run  

The remaining 6 methods (`generate_aggregate_error_report`, `generate_status_report`, `generate_ptid_completed_visits_report`, `generate_rules_validation_log`, `generate_json_status_report`, `generate_passed_validations_report`) plus `ReportMetadata`, `_create_generation_summary`, `get_report_statistics`, the `_generated_reports` list, and per-report file size calculations are analytics overhead.

#### What to Build

Replace the class with 4 simple functions:

```python
# io/reports.py  (~150 lines)

def export_error_report(df_errors: pd.DataFrame, output_dir: Path, file_prefix: str) -> Path | None:
    """Write errors CSV. Returns path or None if empty."""

def export_validation_logs(df_logs: pd.DataFrame, output_dir: Path, file_prefix: str) -> Path | None:
    """Write validation logs CSV."""

def export_data_fetched(df_all: pd.DataFrame, output_dir: Path, file_prefix: str) -> Path | None:
    """Write the fetched data CSV (audit trail)."""

def export_json_tracking(
    df_all: pd.DataFrame, df_errors: pd.DataFrame, 
    output_dir: Path, file_prefix: str, config: QCConfig
) -> Path:
    """Write JSON tracking payload with run metadata."""
```

#### Step-by-Step

1. **Create new `io/reports.py`** with the 4 functions above. Each is essentially:
   ```python
   def export_error_report(df_errors, output_dir, file_prefix):
       if df_errors is None or df_errors.empty:
           return None
       path = output_dir / f"{file_prefix}_errors.csv"
       df_errors.to_csv(path, index=False)
       logger.info("Exported %d errors to %s", len(df_errors), path.name)
       return path
   ```

2. **Simplify `io/context.py`**: 
   - Keep `ProcessingContext` (it carries the DataFrame + instrument list + rules — needed by orchestrator).
   - Remove `ExportConfiguration` class — replace with direct parameters to the 4 functions (output_dir, file_prefix).
   - Remove `ReportConfiguration` class entirely (its booleans gated the removed report methods).
   - Remove `get_status_columns()`, `get_validation_logs_dir()`, `get_report_filename()` — no longer needed.
   - Target: `context.py` ~30 lines (just `ProcessingContext`).

3. **Update `pipeline_orchestrator.py`** stage 5 (`_execute_report_generation_stage`):
   - Replace `ReportFactory(context).export_all_reports(...)` with 4 direct function calls.
   - Remove imports of `ExportConfiguration`, `ReportConfiguration`.

4. **Update `report_pipeline.py`**:
   - Remove any remaining references to `ReportFactory` or the removed report types.

5. **Update tests**:
   - `test_outputs.py`: Rewrite to test the 4 export functions directly. Target ~100 lines.
   - Remove any test cases for aggregate reports, status reports, PTID reports, etc.

6. **Run tests**: `pytest -x`.

#### Verification Checklist

- [ ] Error CSV, validation logs CSV, data-fetched CSV, and JSON tracking file are all generated correctly
- [ ] Empty DataFrames produce no file (return None)
- [ ] No references to `ReportFactory`, `ReportMetadata`, `ExportConfiguration`, `ReportConfiguration` remain
- [ ] `detailed_run` CLI flag still controls whether logs are included (pass `df_logs=None` when disabled)

---

### Phase 9: Flatten Orchestrator + Drop Result Dataclasses

**Files affected**: `core/pipeline_orchestrator.py`, `core/pipeline_results.py`  
**Target**: Replace 700-line orchestrator+results with a ~200-line `run_pipeline()` function  
**Estimated reduction**: 700 → ~200 lines (−500)

#### Why

The pipeline is strictly linear: fetch → load rules → prep data → validate → export. The `PipelineOrchestrator` class wraps each step in a method with timing, logging, and error handling, then packs results into 7 dataclasses. The computed properties on those dataclasses (`error_rate`, `completion_rate`, `loaded_instruments_count`, etc.) are never consumed by anything except logging strings that could compute inline.

#### What to Build

```python
# core/pipeline.py  (~200 lines)

def run_pipeline(config: QCConfig, output_path=None, date_tag=None, time_tag=None) -> dict:
    """Execute the full QC pipeline.
    
    Returns dict with:
        - output_dir: Path
        - errors_df: DataFrame
        - logs_df: DataFrame  
        - records_fetched: int
        - success: bool
        - execution_time: float
        - error: str | None
    """
```

#### Step-by-Step

1. **Create `core/pipeline.py`** with a single `run_pipeline()` function:
   - Linear flow with `try/except` at the top level.
   - Each stage is 10–20 lines inline (no separate methods needed for a linear pipeline).
   - Stage 1 (Fetch): Call `RedcapETLPipeline(config).run(output_path, date_tag, time_tag)`.
   - Stage 2 (Load rules): Call `rule_loader.load_rules_for_packet(packet)` for each packet in the data.
   - Stage 3 (Prep): Call `build_variable_maps()`, `prepare_instrument_data_cache()`, `build_complete_visits_df()`.
   - Stage 4 (Validate): Loop instruments → call `validate_data()` → collect errors, logs, passed.
   - Stage 5 (Export): Call the 4 report functions from Phase 8.
   - Return a simple dict (not dataclasses).
   - Use `time.time()` deltas for timing, `logger.info()` for stage boundaries.

2. **Delete `core/pipeline_results.py`** — all 7 dataclasses removed.

3. **Delete `core/pipeline_orchestrator.py`** — replaced by `core/pipeline.py`.

4. **Update `reports/report_pipeline.py`**:
   - `run_report_pipeline()` now calls `pipeline.run_pipeline()` instead of `PipelineOrchestrator(config).run_pipeline()`.
   - This function becomes very thin (~20 lines): build config, call `run_pipeline()`, log summary.

5. **Update `cli/cli.py`**:
   - Verify it still calls `run_report_pipeline()` — no changes needed if so.

6. **Update tests**:
   - `test_pipeline_validation.py`: Update to test `run_pipeline()` directly with mocked fetcher + filesystem.
   - Remove any tests that specifically test `PipelineOrchestrator` methods or result dataclasses.

7. **Run tests**: `pytest -x`.

#### Verification Checklist

- [ ] CLI `udsv4-qc` runs end to end and produces the same outputs
- [ ] `run_pipeline()` returns a dict with expected keys
- [ ] Errors in any stage are caught and reported cleanly
- [ ] No references to `PipelineOrchestrator`, `PipelineExecutionResult`, or any of the 7 result dataclasses remain
- [ ] Timing info is still logged for each stage

---

### Phase 10: Inline Fetcher to Single Module

**Files affected**: `core/fetcher.py`  
**Target**: Reduce from 397 → ~100 lines  
**Estimated reduction**: −297 lines

#### Why

6 classes/components (`ETLContext`, `ETLResult`, `RedcapApiClient`, `DataTransformer`, `DataSaver`, `RedcapETLPipeline`) for what is: build payload → `requests.post()` → `pd.DataFrame()` → rename `record_id` → optional PTID filter → save CSV. The `DataTransformer.apply_instrument_subset_transformation()` iterates row-by-row (pandas antipattern) and `DataSaver` wraps a single `to_csv()` call.

#### What to Build

```python
# core/fetcher.py  (~100 lines)

def fetch_redcap_data(config: QCConfig, output_path: Path | None = None) -> tuple[pd.DataFrame, list[Path]]:
    """Fetch data from REDCap, apply basic transformations, optionally save.
    
    Returns (dataframe, list_of_saved_files).
    """

def _build_api_payload(config: QCConfig) -> dict:
    """Build the REDCap API POST payload."""

def _apply_ptid_filter(df: pd.DataFrame, config: QCConfig) -> pd.DataFrame:
    """Filter to specific PTIDs if configured."""
```

#### Step-by-Step

1. **Rewrite `core/fetcher.py`**:
   - `fetch_redcap_data()` does the full flow inline: build payload, `requests.post()`, parse JSON, `pd.DataFrame()`, rename columns, apply PTID filter, save CSV if output_path given.
   - Remove `ETLContext`, `ETLResult`, `RedcapApiClient`, `DataTransformer`, `DataSaver`, `RedcapETLPipeline` classes.
   - Replace row-by-row `apply_instrument_subset_transformation()` with vectorized pandas if still needed, or remove if the Phase 9 pipeline handles instrument scoping differently.
   - Keep `validate_and_process()` as a small helper if it does meaningful schema validation (rename `record_id` to `ptid`, check required columns).

2. **Update `core/pipeline.py`** (from Phase 9):
   - Stage 1 calls `fetch_redcap_data(config, output_path)` instead of `RedcapETLPipeline(config).run(...)`.

3. **Update tests**:
   - `test_fetching.py`: Rewrite to test `fetch_redcap_data()` with mocked `requests.post`. Target ~120 lines.
   - Remove tests for `ETLContext`, `ETLResult`, `DataTransformer`, `DataSaver` classes.

4. **Run tests**: `pytest -x`.

#### Verification Checklist

- [ ] `fetch_redcap_data()` returns a DataFrame with `ptid` column (renamed from `record_id`)
- [ ] PTID filtering works when `config.ptid_list` is set
- [ ] CSV saved when `output_path` is provided
- [ ] No references to `ETLContext`, `ETLResult`, `RedcapApiClient`, `DataTransformer`, `DataSaver`, `RedcapETLPipeline` remain

---

### Phase 11: Merge `validation_logging` + `visit_processing` into One Utility

**Files affected**: `core/validation_logging.py` (176 lines), `core/visit_processing.py` (204 lines)  
**Target**: Merge into `core/validation_utils.py` (~50 lines)  
**Estimated reduction**: 380 → ~50 lines (−330)

#### Why

`validation_logging.py` has 7 functions for what is: "check if `{instrument}_complete == 2`, build a dict." `visit_processing.py` has 8 functions decomposed from: "filter the DataFrame to rows where all `_complete` columns equal `'2'`." Both are single-purpose operations that are heavily over-decomposed.

#### What to Build

```python
# core/validation_utils.py  (~50 lines)

def build_validation_log(df: pd.DataFrame, instrument: str, primary_key_field: str) -> list[dict]:
    """Build per-record validation log entries for an instrument.
    
    For each row, checks {instrument}_complete == '2', produces a dict with
    ptid, event, instrument, status, pass/fail, error message.
    """

def find_complete_visits(df: pd.DataFrame, instrument_list: list[str], primary_key_field: str = "ptid") -> tuple[pd.DataFrame, list[tuple]]:
    """Return (summary_df, complete_visit_tuples) where all instruments are complete.
    
    Uses vectorized pandas: build mask where all {instr}_complete == '2', 
    groupby ptid+event, filter.
    """
```

#### Step-by-Step

1. **Create `core/validation_utils.py`** with the two functions above:
   - `build_validation_log()`: For each row in `df`, check `{instrument}_complete`. Build a dict. Return list of dicts. One function, ~20 lines.
   - `find_complete_visits()`: Build completion column names, create a boolean mask, filter, return summary. Vectorized, ~25 lines.

2. **Update `core/pipeline.py`** (from Phase 9):
   - Replace calls to `build_detailed_validation_logs()` / `build_validation_logs_summary()` with `build_validation_log()`.
   - Replace calls to `build_complete_visits_df()` with `find_complete_visits()`.

3. **Update `core/data_processing.py`**:
   - Remove `CompleteVisitsData` and `ValidationLogsData` namedtuples/dataclasses if they're only consumed by the deleted modules. If `pipeline.py` uses them, replace with plain tuples or inline.

4. **Delete** `core/validation_logging.py` and `core/visit_processing.py`.

5. **Update tests**:
   - Merge relevant tests into `test_pipeline_validation.py` or create `test_validation_utils.py` with ~40 lines covering both functions.

6. **Run tests**: `pytest -x`.

#### Verification Checklist

- [ ] `build_validation_log()` produces correct pass/fail entries
- [ ] `find_complete_visits()` correctly identifies rows where all instruments are complete = "2"
- [ ] No references to `extract_record_identifiers`, `determine_completion_status`, `validate_dataframe_not_empty`, or the other decomposed functions remain

---

### Phase 12: Consolidate `report_pipeline.py`

**Files affected**: `reports/report_pipeline.py`  
**Target**: Reduce from 512 → ~80 lines  
**Estimated reduction**: −432 lines

#### Why

After Phases 7–11, most of `report_pipeline.py`'s contents are eliminated:
- `validate_data_unified()` — deleted in Phase 7 (unused).
- `validate_data_with_hierarchical_routing()` — replaced in Phase 7 by `rule_loader`.
- `run_report_pipeline()` — thinned in Phase 9 to a 20-line wrapper.

What remains: `validate_data()` (the production validation function) and `operation_context()` (a logging context manager).

#### Step-by-Step

1. **Slim `report_pipeline.py`** to contain only:
   - `operation_context()` context manager (~15 lines) — used by CLI.
   - `run_report_pipeline(config)` (~20 lines) — calls `pipeline.run_pipeline()`.
   - `validate_data(data, instrument_name, primary_key_field)` (~40 lines) — the per-record validation loop using `rule_loader.get_rules_for_record()` and `schema_builder._build_schema_from_raw()`.
   
2. **Remove all other functions** that were superseded by earlier phases.

3. **Verify CLI path**: `cli.py` → `run_report_pipeline()` → `pipeline.run_pipeline()` → stages.

4. **Run tests**: `pytest -x`.

#### Verification Checklist

- [ ] CLI still works end to end
- [ ] `validate_data()` correctly validates records against rules
- [ ] No orphan imports remain

---

### Phase 13: Simplify Configuration Tests

**Files affected**: `tests/test_configuration.py`, `tests/conftest.py`  
**Target**: Reduce test_configuration.py from 225 → ~80 lines; simplify conftest.py  
**Estimated reduction**: −300 lines across both files

#### Why

14 test methods in 7 classes testing a `@dataclass` config. Tests like `test_default_instruments_exist` verify static data hardcoded in the module. `conftest.py` has fixture boilerplate for components that no longer exist after the refactoring.

#### Step-by-Step

1. **Rewrite `test_configuration.py`** with a single test class (~80 lines):
   - `test_config_creation_with_defaults` — verify `QCConfig()` initializes correctly.
   - `test_env_var_loading` — mock env vars, verify they propagate into config.
   - `test_serialization_roundtrip` — `to_dict()` → reconstruct → assert equal.
   - `test_validation_errors` — test that invalid configs raise appropriate errors.
   - `test_packet_path_resolution` — verify `get_rules_path_for_packet()` returns correct paths.

2. **Prune `conftest.py`**:
   - Remove fixtures that created mock `HierarchicalRuleResolver`, `PacketRuleRouter`, `ReportFactory`, `PipelineOrchestrator` objects.
   - Remove fixtures for deleted result dataclasses.
   - Keep only: `temp_directory`, `sample_config`, `sample_dataframe`, `mock_redcap_api_response`, `mock_validation_rules`, `mock_environment_variables`.
   - Target: ~120 lines.

3. **Audit all test files** for references to deleted classes/functions and remove dead test imports.

4. **Run tests**: `pytest -x`.

#### Verification Checklist

- [ ] All remaining tests pass
- [ ] No test imports reference deleted modules
- [ ] conftest.py has no unused fixtures

---

### Phase 14: Clean Up `data_processing.py` and `instrument_processors.py`

**Files affected**: `core/data_processing.py` (224 lines), `processors/instrument_processors.py` (188 lines)  
**Target**: Merge into `core/data_processing.py` (~150 lines total)  
**Estimated reduction**: 412 → ~150 (−262)

#### Why

After rule-loading consolidation (Phase 7), `instrument_processors.py` can be simplified — its `DynamicInstrumentProcessor` class duplicates C2/C2T logic that now lives in `rule_loader.py`. The `prepare_instrument_data()` function does column selection that `data_processing.py` also does. Merging avoids the cross-package import (absolute `from pipeline.io.rules` → now dead).

Additionally, `data_processing.py` has unused parameters (`instrument_variable_map` in `prepare_instrument_data_cache`) and namedtuples (`CompleteVisitsData`, `ValidationLogsData`) that may have been consumed by modules deleted in Phase 11.

#### Step-by-Step

1. **Merge useful logic from `instrument_processors.py` into `data_processing.py`**:
   - `prepare_instrument_data()` → absorb into `prepare_instrument_data_cache()` or simplify as a helper.
   - Remove `DynamicInstrumentProcessor` class entirely — C2/C2T is handled by `rule_loader.resolve_dynamic_rules()`.

2. **Clean `data_processing.py`**:
   - Remove `CompleteVisitsData` and `ValidationLogsData` if no longer imported (check after Phase 11).
   - Remove unused `instrument_variable_map` parameter from `prepare_instrument_data_cache()`.
   - Remove `is_dynamic_instrument()` — subsumed by `rule_loader`.
   - Remove `extract_variables_from_dynamic_instrument()` — subsumed by `rule_loader`.

3. **Delete `processors/instrument_processors.py`** and the `processors/` directory.

4. **Update imports** in `core/pipeline.py` (from Phase 9).

5. **Run tests**: `pytest -x`.

#### Verification Checklist

- [ ] `prepare_instrument_data_cache()` still builds correct per-instrument DataFrames
- [ ] No absolute `from pipeline.` imports remain (fix to relative imports)
- [ ] `processors/` directory is deleted

---

### Phase 15: Final Cleanup and Documentation Update

**Files affected**: Various  
**Target**: Remove dead imports, update docs, verify final state

#### Step-by-Step

1. **Run linting**: `ruff check src/ tests/` — fix all warnings.
2. **Run type checking**: `mypy src/` — fix all errors.
3. **Run full test suite**: `pytest --tb=short` — all green.
4. **Verify CLI end-to-end**: Run `udsv4-qc --mode complete_visits --initials TEST` and confirm output files are generated.
5. **Remove stale documentation**:
   - Update `docs/data-routing-workflow.md` — remove references to hierarchical routing, update to reflect the flat rule_loader approach.
   - Update `docs/output-reporting.md` — reflect the 4 core report outputs.
   - Update `docs/guidelines.md` — update architecture diagram.
6. **Delete `docs/Patches/RULE_ROUTING.md`** — obsolete after consolidation.
7. **Update `CHANGELOG.md`** with the refactoring summary.

#### Final Target File Structure

```
src/
├── __version__.py
├── cli/
│   ├── __init__.py
│   └── cli.py                         (~228 lines, unchanged)
└── pipeline/
    ├── __init__.py
    ├── config/
    │   └── config_manager.py           (~420 lines, minor cleanup)
    ├── core/
    │   ├── data_processing.py          (~150 lines, merged with instrument_processors)
    │   ├── fetcher.py                  (~100 lines, inlined)
    │   ├── pipeline.py                 (~200 lines, replaces orchestrator + results)
    │   └── validation_utils.py         (~50 lines, merged validation_logging + visit_processing)
    ├── io/
    │   ├── context.py                  (~30 lines, just ProcessingContext)
    │   ├── reports.py                  (~150 lines, 4 export functions)
    │   └── rule_loader.py              (~150 lines, replaces 4 rule files)
    ├── logging/
    │   └── logging_config.py           (~226 lines, unchanged)
    ├── reports/
    │   └── report_pipeline.py          (~80 lines, thin wrapper)
    └── utils/
        └── schema_builder.py           (~51 lines, unchanged)
```

#### Summary Metrics

| Component | Before | After | Reduction |
|-----------|-------:|------:|----------:|
| Rule routing (4 files) | 895 | ~150 | −745 (83%) |
| Reports + context | 822 | ~180 | −642 (78%) |
| Orchestrator + results | 700 | ~200 | −500 (71%) |
| Fetcher | 397 | ~100 | −297 (75%) |
| Validation logging + visit processing | 380 | ~50 | −330 (87%) |
| Report pipeline | 512 | ~80 | −432 (84%) |
| Instrument processors + data processing | 412 | ~150 | −262 (64%) |
| Config tests + conftest | 528 | ~200 | −328 (62%) |
| **Total pipeline src/** | **4,854** | **~1,585** | **−3,269 (67%)** |
| **Total tests/** | **3,073** | **~1,500** | **−1,573 (51%)** |

---

## Agent Execution Instructions

Each phase should be executed as follows:

1. **Read this plan** for the specific phase you're working on.
2. **Read all source files** referenced in that phase to understand current implementation.
3. **Implement the changes** as described, one file at a time.
4. **Run `pytest -x`** after each phase to verify nothing is broken.
5. **Run `ruff check src/ tests/`** to catch import issues.
6. **Commit** with message: `Phase N: <one-line description>`
7. **Do not proceed** to the next phase until all tests pass.

### Critical Rules

- **Never change `nacc_form_validator/`** — this is an external package, not ours.
- **Never change `config/` JSON rule files** — these are data, not code.
- **Never change `config_manager.py` constants** (instrument lists, KEY_MAP, etc.) — these define the domain.
- **Preserve the `QualityCheck` validation interface** — `QualityCheck(schema).validate(record)` is the core validation call and must not change.
- **Preserve CLI interface** — all `click` options and behavior must remain the same.
- **All imports must be relative** within the `pipeline` package (fix `instrument_processors.py`'s absolute imports).
- **Keep logging** — `logger.info()` at stage boundaries is valuable. Remove `logger.debug()` for cache stats and metadata that no longer exist.
