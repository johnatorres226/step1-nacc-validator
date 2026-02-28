# CONFIG_RULE_ROUTING.md — Namespaced Rule Pool Implementation Plan

> **Branch**: `feature/namespaced-rule-pool`  
> **Parent Branch**: `project-refactoring` (post-Phase 7+)  
> **Created**: 2026-02-27  
> **Goal**: Replace static instrument-to-JSON routing (`instrument_json_mapping`, `DYNAMIC_RULE_INSTRUMENTS`, `is_dynamic_rule_instrument()`, `get_discriminant_variable()`, `get_rule_mappings()`) with a **Namespaced Rule Pool** that auto-discovers rules from packet directories, indexes them by variable name with O(1) lookup, and handles C2/C2T conflicts through automatic namespace disambiguation — eliminating all manual rule registration.

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Architecture Overview](#2-architecture-overview)
3. [Implementation Rules](#3-implementation-rules)
4. [Implementation Phases](#4-implementation-phases)
5. [Subagent Roles & Skills](#5-subagent-roles--skills)
6. [Commit Behavior](#6-commit-behavior)
7. [Testing Strategy](#7-testing-strategy)
8. [Verification Checklists](#8-verification-checklists)
9. [Rollback Plan](#9-rollback-plan)

---

## 1. Problem Statement

### Current State: Static Routing

The current architecture in `config_manager.py` + `rule_loader.py` uses **three static declarations** to route rules:

| Static Structure | Location | Purpose | Lines |
|---|---|---|---|
| `instrument_json_mapping` | `config_manager.py:57-78` | Maps 19 instrument names → JSON filenames | 22 |
| `DYNAMIC_RULE_INSTRUMENTS` | `config_manager.py:108-114` | Hardcodes C2/C2T discriminant config | 7 |
| Helper functions (`is_dynamic_rule_instrument`, `get_discriminant_variable`, `get_rule_mappings`) | `config_manager.py:117-133` | Read from `DYNAMIC_RULE_INSTRUMENTS` | 17 |

**Every new instrument or rule file requires editing `config_manager.py`** — touching constants, mappings, and potentially adding new special-case helpers.

### Consumer Dependency Map (What Imports These Statics)

```
config_manager.py  ← defines instrument_json_mapping, DYNAMIC_RULE_INSTRUMENTS, helpers
  ├── rule_loader.py           ← imports instrument_json_mapping, is_dynamic_rule_instrument, 
  │                               get_discriminant_variable, get_rule_mappings
  ├── data_processing.py       ← imports is_dynamic_rule_instrument, get_discriminant_variable
  ├── report_pipeline.py       ← imports is_dynamic_rule_instrument, get_discriminant_variable
  └── (no other consumers)
```

### Target State: Auto-Discovered Namespaced Pool

```
config/{packet}/rules/*.json  ──auto-scan──►  NamespacedRulePool
                                                ├── _rules[variable] → RuleEntry     (O(1) flat lookup)
                                                ├── _namespaced[namespace][variable]  (conflict disambiguation)
                                                └── _conflicts: set[str]             (auto-detected overlaps)
```

- **Zero registration** for new instruments — drop a `*_rules.json` file in the packet directory.
- **C2/C2T conflict** auto-detected and resolved via namespace hint at validation time.
- **Same O(1) per-variable lookup** performance as current system.
- **Eliminates** `instrument_json_mapping`, `DYNAMIC_RULE_INSTRUMENTS`, and all three helper functions.

---

## 2. Architecture Overview

### New Module: `src/pipeline/io/rule_pool.py`

```
NamespacedRulePool
├── load_packet(packet: str, config: QCConfig) → None
│   └── Scans config/{packet}/rules/*.json
│       └── For each file: namespace = stem.replace("_rules", "")
│           └── Parses JSON → stores as RuleEntry per variable
│               └── Builds flat index + conflict set
├── get_rule(variable: str, namespace: str | None = None) → RuleEntry | None
│   └── O(1): if conflict + namespace → _namespaced[namespace][variable]
│   └── O(1): else → _rules[variable]
├── get_all_rules() → dict[str, RuleEntry]
│   └── Returns flat index (all non-conflicting + first-wins for conflicts)
├── get_all_rules_for_namespace(namespace: str) → dict[str, RuleEntry]
│   └── Returns all rules from a specific source file
├── conflict_variables → set[str]
│   └── Variables existing in 2+ rule files (e.g., C2 ∩ C2T overlap)
└── clear() → None
    └── Reset pool state
```

### Data Flow Change

**Before** (static routing):
```
record["packet"] → get_rules_path_for_packet() → rules_dir
instrument_name  → instrument_json_mapping[name] → ["c2_rules.json", "c2t_rules.json"]
                 → is_dynamic_rule_instrument() → True
                 → get_discriminant_variable() → "loc_c2_or_c2t"
                 → record["loc_c2_or_c2t"] → "C2T"
                 → load specific c2t_rules.json → flat rules dict
```

**After** (pool):
```
record["packet"] → pool.load_packet(packet)          [one-time, cached]
variable_name    → pool.get_rule(var, namespace=ns)   [O(1) per variable]
                                                       ns = record.get("loc_c2_or_c2t", "").lower() or None
```

### What Gets Removed

| Component | File | Action |
|---|---|---|
| `instrument_json_mapping` | `config_manager.py` | **Delete** |
| `DYNAMIC_RULE_INSTRUMENTS` | `config_manager.py` | **Delete** |
| `get_discriminant_variable()` | `config_manager.py` | **Delete** |
| `get_rule_mappings()` | `config_manager.py` | **Delete** |
| `is_dynamic_rule_instrument()` | `config_manager.py` | **Delete** |
| `special_col_discriminat_var` field on `QCConfig` | `config_manager.py` | **Delete** |
| `load_rules_for_instrument()` | `rule_loader.py` | **Delete** |
| `_load_dynamic_variant_rules()` | `rule_loader.py` | **Delete** |
| `_load_instrument_rules_for_packet()` | `rule_loader.py` | **Delete** |
| `load_rules_for_instruments()` | `rule_loader.py` | **Delete** |
| `resolve_dynamic_rules()` | `rule_loader.py` | **Replaced** by pool namespace lookup |

### What Gets Preserved

| Component | File | Status |
|---|---|---|
| `instruments` list | `config_manager.py` | **Keep** — needed for REDCap form fetching + completion status tracking |
| `QCConfig.get_rules_path_for_packet()` | `config_manager.py` | **Keep** — pool calls it to find directories |
| `load_rules_for_packet()` | `rule_loader.py` | **Keep** — merges all rules flat (used by pool internally or as fallback) |
| `get_rules_for_record()` | `rule_loader.py` | **Rewrite** — delegates to pool |
| `clear_cache()` | `rule_loader.py` | **Keep** — clears pool state |
| `variable_instrument_mapping.json` | `config/` | **Keep** — used for variable→instrument reverse lookup in reporting |

---

## 3. Implementation Rules

### R1: No External Package Changes
Never modify anything under `nacc_form_validator/`. It is an external dependency.

### R2: No Rule File Changes
Never modify `config/{I,I4,F,M}/rules/*.json`. These are data authored by domain experts.

### R3: Preserve CLI Interface
All `click` options and behavior in `src/cli/cli.py` must remain unchanged. The refactoring is internal.

### R4: Preserve QualityCheck Interface
`QualityCheck(schema=...).validate_record(record)` is the core validation call. The pool changes how rules are *loaded*, not how they are *applied*.

### R5: Preserve instruments List
The `instruments` list in `config_manager.py` is still needed for:
- REDCap API `forms` parameter in data fetching
- `{instrument}_complete` completion status tracking
- Error report `instrument_name` column

Do **not** derive instruments from rule file names — the `instruments` list is the source of truth for REDCap form names.

### R6: Namespace Convention
Namespace = JSON filename stem with `_rules` suffix stripped:
- `c2_rules.json` → namespace `"c2"`
- `c2t_rules.json` → namespace `"c2t"`
- `header_rules.json` → namespace `"header"`
- `a1a_rules_optional.json` → namespace `"a1a_rules_optional"` (note: only `*_rules.json` stripped, not `*_rules_optional.json`)

**Decision**: Only files matching `*_rules.json` (not `*_rules_optional.json`) are loaded into the pool. Optional rules are a separate concern.

### R7: Conflict Resolution
When the same variable name appears in 2+ rule files:
1. The variable is added to `_conflicts` set.
2. The first-loaded file wins in the flat `_rules` index (files are sorted alphabetically).
3. Callers **must** pass `namespace=` for conflict variables to get the correct variant.
4. A `WARNING` log is emitted at pool load time listing all conflicts.

### R8: Discriminant Variable Handling
The C2/C2T discriminant logic moves **out of routing config** and **into validation-time logic**:
- The pool auto-detects that `c2_rules.json` and `c2t_rules.json` share overlapping variables.
- At validation time, `report_pipeline.validate_data()` reads `record["loc_c2_or_c2t"]` to determine namespace.
- The discriminant variable name (`loc_c2_or_c2t`) is the **only** hardcoded reference that remains. It moves to a minimal constant:

```python
# In report_pipeline.py or a thin config constant
NAMESPACE_DISCRIMINANTS: dict[str, str] = {
    "c2c2t_neuropsychological_battery_scores": "loc_c2_or_c2t",
}
```

This replaces the 20-line `DYNAMIC_RULE_INSTRUMENTS` system with a 3-line lookup.

### R9: Relative Imports Only
All imports within the `pipeline` package must use relative imports (`from ..config.config_manager import ...`).

### R10: Test Parity
Every deleted test must be replaced by an equivalent test against the new pool API. No net reduction in test coverage for rule loading/routing behavior.

---

## 4. Implementation Phases

### Phase A: Create `rule_pool.py` Module (NEW)

**Files created**: `src/pipeline/io/rule_pool.py`  
**Files modified**: None  
**Estimated lines**: ~120

#### What to Build

```python
# src/pipeline/io/rule_pool.py

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

from ..config.config_manager import QCConfig, get_config
from ..logging.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RuleEntry:
    """A single variable's validation rule with source metadata."""
    variable: str
    rule: dict[str, Any]
    source_file: str
    namespace: str


class NamespacedRulePool:
    """
    Auto-discovered, namespaced rule pool with O(1) per-variable lookup.
    
    Loads all *_rules.json files from a packet directory, indexes by variable,
    and auto-detects namespace conflicts (e.g., C2/C2T overlapping variables).
    """

    def __init__(self) -> None:
        self._rules: dict[str, RuleEntry] = {}
        self._namespaced: dict[str, dict[str, RuleEntry]] = {}
        self._conflicts: set[str] = set()
        self._loaded_packets: set[str] = set()

    def load_packet(self, packet: str, config: QCConfig | None = None) -> None:
        """Load all *_rules.json files from a packet's rules directory."""
        ...

    def get_rule(self, variable: str, namespace: str | None = None) -> RuleEntry | None:
        """O(1) rule lookup. Use namespace for conflict disambiguation."""
        ...

    def get_all_rules(self) -> dict[str, RuleEntry]:
        """Return the flat index (first-wins for conflicts)."""
        return dict(self._rules)

    def get_all_rules_for_namespace(self, namespace: str) -> dict[str, RuleEntry]:
        """Get all rules from a specific source file/namespace."""
        return dict(self._namespaced.get(namespace, {}))
    
    def get_resolved_rules_dict(self, namespace: str | None = None) -> dict[str, dict[str, Any]]:
        """
        Return {variable: rule_dict} suitable for schema building.
        
        If namespace is given and a variable is in conflict, use the namespaced version.
        Otherwise use the flat index.
        """
        ...

    @property
    def conflict_variables(self) -> frozenset[str]:
        return frozenset(self._conflicts)

    @property
    def loaded_packets(self) -> frozenset[str]:
        return frozenset(self._loaded_packets)

    def clear(self) -> None:
        self._rules.clear()
        self._namespaced.clear()
        self._conflicts.clear()
        self._loaded_packets.clear()

    def __len__(self) -> int:
        return len(self._rules)

    def __repr__(self) -> str:
        return (
            f"NamespacedRulePool(rules={len(self._rules)}, "
            f"namespaces={len(self._namespaced)}, "
            f"conflicts={len(self._conflicts)})"
        )


# Module-level singleton pool with lazy initialization
_pool: NamespacedRulePool | None = None


def get_pool(config: QCConfig | None = None) -> NamespacedRulePool:
    """Get or create the module-level rule pool singleton."""
    global _pool
    if _pool is None:
        _pool = NamespacedRulePool()
    return _pool


def reset_pool() -> None:
    """Reset the module-level pool (for testing)."""
    global _pool
    if _pool is not None:
        _pool.clear()
    _pool = None
```

#### Acceptance Criteria

- [ ] `NamespacedRulePool` can be instantiated and `load_packet()` discovers all `*_rules.json` files
- [ ] Variables unique across files are in `_rules` with O(1) lookup
- [ ] Variables in 2+ files are in `_conflicts` and accessible via `get_rule(var, namespace=...)`
- [ ] `get_resolved_rules_dict()` returns a dict compatible with `_build_schema_from_raw()`
- [ ] Unit tests pass in isolation (no integration with pipeline yet)

---

### Phase B: Integrate Pool into `rule_loader.py`

**Files modified**: `src/pipeline/io/rule_loader.py`  
**Estimated diff**: ~60 lines changed

#### Changes

1. **Rewrite `get_rules_for_record()`** to delegate to pool:

```python
def get_rules_for_record(
    record: dict, instrument_name: str, config: QCConfig | None = None
) -> dict:
    """Main entry point: load rules from pool, resolve namespace for conflicts."""
    packet = _validate_packet(record.get("packet", ""))
    cfg = _get_config(config)
    
    pool = get_pool(cfg)
    if packet not in pool.loaded_packets:
        pool.load_packet(packet, cfg)
    
    # Determine namespace for instruments with conflict variables
    namespace = _resolve_namespace(record, instrument_name)
    
    return pool.get_resolved_rules_dict(namespace=namespace)
```

2. **Add `_resolve_namespace()` helper**:

```python
# Minimal discriminant config — the ONLY hardcoded reference remaining
_NAMESPACE_DISCRIMINANTS: dict[str, str] = {
    "c2c2t_neuropsychological_battery_scores": "loc_c2_or_c2t",
}

_DISCRIMINANT_VALUE_TO_NAMESPACE: dict[str, str] = {
    "C2": "c2",
    "C2T": "c2t",
}


def _resolve_namespace(record: dict, instrument_name: str) -> str | None:
    """Resolve namespace for instruments with conflicting variables."""
    disc_var = _NAMESPACE_DISCRIMINANTS.get(instrument_name)
    if not disc_var:
        return None
    
    value = str(record.get(disc_var, "")).upper().strip()
    return _DISCRIMINANT_VALUE_TO_NAMESPACE.get(value)
```

3. **Delete these functions** (replaced by pool):
   - `load_rules_for_instrument()`
   - `_load_dynamic_variant_rules()`
   - `_load_instrument_rules_for_packet()`
   - `load_rules_for_instruments()`
   - `resolve_dynamic_rules()`

4. **Keep** `load_rules_for_packet()` as a thin wrapper over pool for backward compatibility.

5. **Update `clear_cache()`** to also call `reset_pool()`.

#### Acceptance Criteria

- [ ] `get_rules_for_record()` returns correct rules for I, I4, F packets
- [ ] C2/C2T discrimination still works via namespace
- [ ] Deleted functions are no longer importable
- [ ] `clear_cache()` resets pool state

---

### Phase C: Remove Static Routing from `config_manager.py`

**Files modified**: `src/pipeline/config/config_manager.py`  
**Estimated diff**: ~50 lines removed

#### Deletions

1. **Delete `instrument_json_mapping`** dict (lines 57-78)
2. **Delete `DYNAMIC_RULE_INSTRUMENTS`** dict (lines 108-114)
3. **Delete `get_discriminant_variable()`** function
4. **Delete `get_rule_mappings()`** function
5. **Delete `is_dynamic_rule_instrument()`** function
6. **Delete `special_col_discriminat_var`** field from `QCConfig` dataclass

#### Preservation

- **Keep `instruments` list** — needed for REDCap form fetching
- **Keep `QCConfig.get_rules_path_for_packet()`** — pool calls it
- **Keep `KEY_MAP`** — used by schema_builder
- **Keep all env var loading, validation, singleton pattern**

#### Acceptance Criteria

- [ ] No references to `instrument_json_mapping` exist anywhere in codebase
- [ ] No references to `DYNAMIC_RULE_INSTRUMENTS` exist anywhere
- [ ] `grep -r "instrument_json_mapping\|DYNAMIC_RULE_INSTRUMENTS\|is_dynamic_rule_instrument\|get_discriminant_variable\|get_rule_mappings" src/` returns zero matches
- [ ] `QCConfig` still validates and loads correctly

---

### Phase D: Update Consumers

**Files modified**: `report_pipeline.py`, `data_processing.py`, `pipeline.py`

#### D1. `report_pipeline.py`

- Remove imports: `get_discriminant_variable`, `is_dynamic_rule_instrument`
- `validate_data()` no longer needs `discriminant_info` computation inline — the pool handles it
- Simplify error dict: `discriminant` field can be populated from `_resolve_namespace()` if needed

#### D2. `data_processing.py`

- Remove imports: `is_dynamic_rule_instrument`, `get_discriminant_variable`
- `_get_variables_for_instrument()` → Rewrite to use pool:
  ```python
  def _get_variables_for_instrument(instrument: str, rules_cache: dict[str, Any]) -> list[str]:
      return list(rules_cache.get(instrument, {}).keys())
  ```
  The `is_dynamic_rule_instrument` branch is eliminated because the pool already provides merged variable lists.

- `_prepare_single_instrument()` → Remove the `is_dynamic_rule_instrument` branch that adds discriminant variable columns. Instead, always include `loc_c2_or_c2t` when instrument is `c2c2t_neuropsychological_battery_scores` (a single `if` check, not a config lookup).

#### D3. `pipeline.py`

- Stage 2 (Load Rules): Replace `load_rules_for_instrument()` loop with pool-based loading:
  ```python
  # Stage 2: Load Rules
  from ..io.rule_pool import get_pool
  pool = get_pool(config)
  for packet in ["I", "I4", "F"]:
      try:
          pool.load_packet(packet, config)
      except FileNotFoundError:
          logger.warning("No rules directory for packet %s", packet)
  
  # Build rules_cache from pool for backward-compatible instrument-keyed structure
  rules_cache = _build_rules_cache_from_pool(pool, config.instruments)
  ```

- Add helper `_build_rules_cache_from_pool()`:
  ```python
  def _build_rules_cache_from_pool(pool, instruments):
      """Build {instrument: {variable: rule_dict}} from pool for Stage 3/4 compatibility."""
      from ..config.config_manager import instruments as all_instruments
      # Use variable_instrument_mapping.json to reverse-map variables to instruments
      ...
  ```

#### Acceptance Criteria

- [ ] `validate_data()` produces identical error output for same input data
- [ ] `data_processing.py` has zero imports from static routing helpers
- [ ] Pipeline Stage 2 uses pool instead of per-instrument loading
- [ ] All `pytest -x` pass

---

### Phase E: Update and Expand Tests

**Files modified**: `tests/test_data_routing.py`, `tests/conftest.py`  
**Files created**: `tests/test_rule_pool.py`

See [Section 7: Testing Strategy](#7-testing-strategy) for full details.

---

## 5. Subagent Roles & Skills

### Role 1: **Pool Architect** (Phase A)

**Skill**: `clean-code`  
**Responsibility**: Implement `rule_pool.py` with the `NamespacedRulePool` class and `RuleEntry` dataclass.

**Execution Protocol**:
1. Read `clean-code` skill file for coding standards.
2. Read `config/I/rules/` directory to understand JSON rule file structure.
3. Read `config/F/rules/c2_rules.json` and `config/F/rules/c2t_rules.json` to identify overlapping variables.
4. Implement `rule_pool.py` following the architecture in Phase A.
5. Write unit tests in `tests/test_rule_pool.py`.
6. Run `pytest tests/test_rule_pool.py -x`.
7. Run `ruff check src/pipeline/io/rule_pool.py`.
8. Commit: `Phase A: Add NamespacedRulePool with auto-discovery and conflict detection`.

**Key Decisions This Agent Makes**:
- File glob pattern (`*_rules.json` vs `*.json` — rule: only `*_rules.json`, skip optional)
- Frozen vs mutable `RuleEntry` (rule: frozen for hashability)
- Whether to expose `_namespaced` directly (rule: only through methods)

---

### Role 2: **Integration Engineer** (Phases B + C)

**Skill**: `audit-context-building`  
**Responsibility**: Rewire `rule_loader.py` to delegate to pool, remove static routing from `config_manager.py`.

**Execution Protocol**:
1. Read `audit-context-building` skill file.
2. Read current `rule_loader.py` and `config_manager.py` in full.
3. Read all files that import from `config_manager.py` routing helpers (use `grep`).
4. Implement Phase B changes to `rule_loader.py`.
5. Run `pytest -x` — expect some failures from removed exports.
6. Implement Phase C deletions in `config_manager.py`.
7. Run `pytest -x` — catalog remaining failures.
8. Do NOT fix consumer failures (that's Role 3).
9. Commit B: `Phase B: Rewire rule_loader.py to delegate to NamespacedRulePool`.
10. Commit C: `Phase C: Remove static routing from config_manager.py`.

**Key Decisions This Agent Makes**:
- Exact signature of rewritten `get_rules_for_record()`
- How `_NAMESPACE_DISCRIMINANTS` is structured (keep minimal)
- Whether `load_rules_for_packet()` wraps pool or remains independent (rule: wraps pool)

---

### Role 3: **Consumer Updater** (Phase D)

**Skill**: `function-analyzer`  
**Responsibility**: Update all consumer modules that imported deleted static routing symbols.

**Execution Protocol**:
1. Read `function-analyzer` skill file.
2. Run: `grep -rn "instrument_json_mapping\|DYNAMIC_RULE_INSTRUMENTS\|is_dynamic_rule_instrument\|get_discriminant_variable\|get_rule_mappings\|load_rules_for_instrument\|load_rules_for_instruments\|resolve_dynamic_rules\|_load_dynamic_variant_rules\|special_col_discriminat_var" src/ tests/`
3. For each match, analyze the calling context and determine the pool-based replacement.
4. Update `report_pipeline.py` (Phase D1).
5. Update `data_processing.py` (Phase D2).
6. Update `pipeline.py` (Phase D3).
7. Run `pytest -x` after each file.
8. Commit: `Phase D: Update all consumers to use NamespacedRulePool`.

**Key Decisions This Agent Makes**:
- How to build `rules_cache` from pool for backward-compatible Stage 3/4 integration
- Whether to use `variable_instrument_mapping.json` for reverse lookup (recommended: yes)
- How to populate `discriminant` field in error dicts (use namespace value)

---

### Role 4: **Test Engineer** (Phase E)

**Skill**: `clean-code`  
**Responsibility**: Write comprehensive tests, update existing tests, ensure coverage parity.

**Execution Protocol**:
1. Read current `tests/test_data_routing.py` and `tests/conftest.py`.
2. Create `tests/test_rule_pool.py` with full pool unit tests.
3. Update `tests/test_data_routing.py` to use pool-based loading.
4. Update `tests/conftest.py` to remove fixtures for deleted components.
5. Run `pytest --tb=short` — all green.
6. Run `pytest --cov=src/pipeline/io/rule_pool --cov-report=term-missing` — verify >90% coverage.
7. Commit: `Phase E: Test suite for NamespacedRulePool and updated routing tests`.

---

## 6. Commit Behavior

### Branch Strategy

```
project-refactoring (parent)
  └── feature/namespaced-rule-pool (this work)
       ├── Phase A: Add NamespacedRulePool module
       ├── Phase B: Rewire rule_loader.py
       ├── Phase C: Remove static routing from config_manager.py
       ├── Phase D: Update all consumers
       └── Phase E: Test suite updates
```

### Commit Rules

| Rule | Description |
|------|-------------|
| **One phase per commit** | Each phase is exactly 1 commit. Never combine phases. |
| **Tests must pass** | `pytest -x` must pass before committing. Phases B+C are allowed to have test failures that Phase D resolves — commit B and C separately but note the known failures. |
| **Lint must pass** | `ruff check src/ tests/` must pass before committing. |
| **Type check should pass** | `mypy src/pipeline/io/rule_pool.py` should pass. Not blocking but recommended. |
| **Commit message format** | `Phase {X}: {one-line description}` |
| **No squash** | Keep individual phase commits for bisectability. |
| **Tag after Phase E** | Tag `rule-pool-v1` after all phases complete and green. |

### Commit Messages

```
Phase A: Add NamespacedRulePool with auto-discovery and conflict detection
Phase B: Rewire rule_loader.py to delegate to NamespacedRulePool
Phase C: Remove static routing declarations from config_manager.py
Phase D: Update report_pipeline, data_processing, pipeline to use pool
Phase E: Comprehensive test suite for NamespacedRulePool and routing
```

### Pre-Commit Checklist (Every Phase)

```bash
# 1. Lint
ruff check src/ tests/

# 2. Tests
pytest -x --tb=short

# 3. Verify no stale references (after Phase C+)
grep -rn "instrument_json_mapping\|DYNAMIC_RULE_INSTRUMENTS" src/ tests/

# 4. Verify imports clean
python -c "from src.pipeline.io.rule_pool import NamespacedRulePool; print('OK')"

# 5. Commit
git add -A
git commit -m "Phase X: description"
```

---

## 7. Testing Strategy

### Test File Structure

```
tests/
├── test_rule_pool.py          # NEW — unit tests for NamespacedRulePool
├── test_data_routing.py       # UPDATED — integration tests using pool
├── test_configuration.py      # UPDATED — remove refs to deleted config statics
├── test_pipeline_validation.py # UPDATED — verify end-to-end with pool
├── conftest.py                # UPDATED — add pool fixtures, remove dead fixtures
└── ...
```

### Test Plan: `test_rule_pool.py` (NEW, ~180 lines)

#### Unit Tests for `NamespacedRulePool`

```python
class TestNamespacedRulePool:
    """Unit tests for NamespacedRulePool auto-discovery and conflict detection."""

    # --- Loading ---
    
    def test_load_packet_discovers_all_rule_files(self, tmp_rules_dir):
        """Pool finds and loads all *_rules.json files in a packet directory."""

    def test_load_packet_skips_optional_rule_files(self, tmp_rules_dir_with_optional):
        """Files matching *_rules_optional.json are not loaded."""

    def test_load_packet_skips_non_json_files(self, tmp_rules_dir_with_txt):
        """Non-JSON files are ignored."""

    def test_load_packet_skips_invalid_json(self, tmp_rules_dir_with_bad_json):
        """Files with invalid JSON are skipped with a warning."""

    def test_load_packet_skips_non_dict_json(self, tmp_rules_dir_with_list_json):
        """JSON files containing arrays instead of dicts are skipped."""

    def test_load_packet_empty_directory(self, tmp_empty_rules_dir):
        """Empty directory loads zero rules without error."""

    def test_load_packet_nonexistent_directory(self):
        """FileNotFoundError raised for missing directory."""

    def test_load_packet_idempotent(self, tmp_rules_dir):
        """Loading the same packet twice does not duplicate rules."""

    def test_load_multiple_packets(self, tmp_rules_dirs):
        """Loading I then F merges both packet's rules."""

    # --- Namespace Extraction ---

    def test_namespace_from_filename(self, tmp_rules_dir):
        """'c2_rules.json' → namespace 'c2', 'header_rules.json' → namespace 'header'."""

    # --- Flat Index (No Conflicts) ---

    def test_get_rule_unique_variable(self, loaded_pool):
        """Unique variable returns correct RuleEntry via flat index."""

    def test_get_rule_missing_variable(self, loaded_pool):
        """Missing variable returns None."""

    def test_get_all_rules_returns_flat_dict(self, loaded_pool):
        """get_all_rules() returns all unique + first-wins for conflicts."""

    # --- Conflict Detection ---

    def test_conflicts_detected_for_overlapping_variables(self, pool_with_c2_c2t):
        """Variables in both c2_rules.json and c2t_rules.json are in conflicts."""

    def test_conflict_variables_property(self, pool_with_c2_c2t):
        """conflict_variables returns frozenset of conflicting variable names."""

    def test_get_rule_conflict_without_namespace_returns_first_wins(self, pool_with_c2_c2t):
        """Without namespace, conflict variable returns alphabetically-first file's rule."""

    def test_get_rule_conflict_with_namespace_returns_correct_variant(self, pool_with_c2_c2t):
        """With namespace='c2t', conflict variable returns c2t variant."""

    def test_get_rule_conflict_with_unknown_namespace_returns_none(self, pool_with_c2_c2t):
        """With namespace='nonexistent', conflict variable returns None."""

    # --- get_resolved_rules_dict ---

    def test_resolved_rules_dict_no_namespace(self, loaded_pool):
        """Returns {variable: rule_dict} for all rules (first-wins for conflicts)."""

    def test_resolved_rules_dict_with_namespace(self, pool_with_c2_c2t):
        """With namespace='c2t', conflict variables use c2t rules."""

    def test_resolved_rules_dict_compatible_with_schema_builder(self, loaded_pool):
        """Output is directly usable by _build_schema_from_raw()."""

    # --- Pool Lifecycle ---

    def test_clear_resets_all_state(self, loaded_pool):
        """clear() empties rules, namespaces, conflicts, loaded_packets."""

    def test_len_returns_flat_rule_count(self, loaded_pool):
        """len(pool) returns number of unique variables in flat index."""

    def test_repr(self, loaded_pool):
        """repr shows counts of rules, namespaces, conflicts."""

    # --- Singleton ---

    def test_get_pool_returns_singleton(self):
        """get_pool() returns same instance on repeated calls."""

    def test_reset_pool_clears_singleton(self):
        """reset_pool() causes next get_pool() to return fresh instance."""
```

### Test Plan: `test_data_routing.py` (UPDATED, ~120 lines)

```python
class TestRuleLoaderWithPool:
    """Integration tests for rule_loader.py backed by NamespacedRulePool."""

    def test_get_rules_for_record_i_packet(self, config_with_rules):
        """Record with packet='I' returns rules from I directory."""

    def test_get_rules_for_record_f_packet(self, config_with_rules):
        """Record with packet='F' returns rules from F directory."""

    def test_get_rules_for_record_i4_packet(self, config_with_rules):
        """Record with packet='I4' returns rules from I4 directory."""

    def test_get_rules_for_record_invalid_packet(self):
        """Invalid packet raises ValueError."""

    def test_get_rules_for_record_c2_discrimination(self, config_with_rules):
        """C2/C2T instrument with loc_c2_or_c2t='C2' returns C2 rules."""

    def test_get_rules_for_record_c2t_discrimination(self, config_with_rules):
        """C2/C2T instrument with loc_c2_or_c2t='C2T' returns C2T rules."""

    def test_get_rules_for_record_missing_discriminant(self, config_with_rules):
        """Missing discriminant variable returns merged/default rules."""

    def test_caching_across_calls(self, config_with_rules):
        """Second call for same packet does not re-read files."""

    def test_clear_cache_forces_reload(self, config_with_rules):
        """clear_cache() causes next call to re-read from disk."""
```

### Test Plan: Fixture Updates in `conftest.py`

```python
# NEW fixtures

@pytest.fixture
def tmp_rules_dir(tmp_path):
    """Create a temporary rules directory with sample rule files."""
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    
    (rules_dir / "a1_rules.json").write_text(json.dumps({
        "a1_birthyr": {"type": "integer", "min": 1900, "max": 2026},
        "a1_sex": {"type": "integer", "allowed": [1, 2]},
    }))
    (rules_dir / "b1_rules.json").write_text(json.dumps({
        "b1_height": {"type": "float", "min": 0, "max": 300},
    }))
    return rules_dir


@pytest.fixture  
def pool_with_c2_c2t(tmp_path):
    """Create pool with C2 and C2T rule files that share overlapping variables."""
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    
    (rules_dir / "c2_rules.json").write_text(json.dumps({
        "mocacomp": {"type": "integer", "allowed": [0, 1]},
        "mocatots": {"type": "integer", "min": 0, "max": 30},
        "c2_unique_var": {"type": "string"},
    }))
    (rules_dir / "c2t_rules.json").write_text(json.dumps({
        "mocacomp": {"type": "integer", "allowed": [0, 1, 2]},  # different rule!
        "mocatots": {"type": "integer", "min": 0, "max": 100},  # different range!
        "c2t_unique_var": {"type": "string"},
    }))
    
    pool = NamespacedRulePool()
    # ... load with mock config pointing to tmp_path
    return pool


# REMOVED fixtures (no longer needed)
# - mock_hierarchical_resolver
# - mock_packet_router
# - mock_instrument_json_mapping
```

### Coverage Targets

| Module | Target | Method |
|---|---|---|
| `rule_pool.py` | >95% | `pytest --cov=src/pipeline/io/rule_pool` |
| `rule_loader.py` (rewritten parts) | >90% | `pytest --cov=src/pipeline/io/rule_loader` |
| `config_manager.py` (after deletions) | >85% | `pytest --cov=src/pipeline/config` |

### Test Execution Order

```bash
# Phase A: Pool unit tests only
pytest tests/test_rule_pool.py -x -v

# Phase B+C: Routing tests (some may fail until Phase D)
pytest tests/test_data_routing.py -x -v

# Phase D: Full suite
pytest -x --tb=short

# Phase E: Coverage verification
pytest --cov=src/pipeline --cov-report=term-missing --tb=short
```

---

## 8. Verification Checklists

### After Phase A (Pool Module)

- [ ] `NamespacedRulePool` instantiates cleanly
- [ ] `load_packet("I")` discovers all 27 `*_rules.json` files in `config/I/rules/`
- [ ] `load_packet("F")` discovers all 27 files in `config/F/rules/`
- [ ] `load_packet("I4")` discovers all 27 files in `config/I4/rules/`
- [ ] `*_rules_optional.json` files are **not** loaded
- [ ] `conflict_variables` correctly identifies overlapping C2/C2T variables
- [ ] `get_rule("a1_birthyr")` returns correct `RuleEntry`
- [ ] `get_rule("mocacomp", namespace="c2t")` returns C2T variant
- [ ] `get_resolved_rules_dict()` output works with `_build_schema_from_raw()`
- [ ] `ruff check src/pipeline/io/rule_pool.py` passes
- [ ] `pytest tests/test_rule_pool.py -x` passes

### After Phase B (rule_loader.py Rewrite)

- [ ] `get_rules_for_record({"packet": "I", ...}, "a1_participant_demographics")` returns rules
- [ ] `get_rules_for_record({"packet":"F","loc_c2_or_c2t":"C2T",...}, "c2c2t_...")` returns C2T rules
- [ ] `clear_cache()` resets both `_packet_cache` and pool
- [ ] `load_rules_for_instrument` is no longer importable from `rule_loader`
- [ ] `resolve_dynamic_rules` is no longer importable from `rule_loader`

### After Phase C (config_manager.py Cleanup)

- [ ] `instrument_json_mapping` is no longer in `config_manager.py`
- [ ] `DYNAMIC_RULE_INSTRUMENTS` is no longer in `config_manager.py`
- [ ] `is_dynamic_rule_instrument()` is no longer importable
- [ ] `get_discriminant_variable()` is no longer importable
- [ ] `get_rule_mappings()` is no longer importable
- [ ] `QCConfig` has no `special_col_discriminat_var` field
- [ ] `QCConfig.get_rules_path_for_packet()` still works
- [ ] `instruments` list is unchanged
- [ ] `get_config()` still loads and validates

### After Phase D (Consumer Updates)

- [ ] `report_pipeline.py` has zero imports of deleted symbols
- [ ] `data_processing.py` has zero imports of deleted symbols
- [ ] `pipeline.py` uses pool for Stage 2
- [ ] `grep -rn "instrument_json_mapping\|DYNAMIC_RULE_INSTRUMENTS\|is_dynamic_rule_instrument\|get_discriminant_variable\|get_rule_mappings" src/` returns **zero** matches
- [ ] `pytest -x` passes (full suite)
- [ ] CLI end-to-end produces identical output files

### After Phase E (Tests)

- [ ] `pytest tests/test_rule_pool.py -x -v` — all pass
- [ ] `pytest tests/test_data_routing.py -x -v` — all pass
- [ ] `pytest --tb=short` — all pass
- [ ] Pool coverage >95%
- [ ] No test file imports deleted symbols
- [ ] No stale fixtures in `conftest.py`

---

## 9. Rollback Plan

If the pool approach causes unexpected issues after merging:

1. **Git revert**: Each phase is a separate commit, so `git revert` specific phases.
2. **Feature flag**: If partial rollback needed, add a `USE_RULE_POOL` env var that switches between pool and static routing in `rule_loader.py`.
3. **Compatibility layer**: The `instruments` list and `QCConfig.get_rules_path_for_packet()` are preserved, so re-adding `instrument_json_mapping` is a copy-paste from git history.

### Risk Assessment

| Risk | Likelihood | Mitigation |
|---|---|---|
| C2/C2T namespace resolution fails edge case | Medium | Comprehensive conflict tests in Phase A |
| Optional rule files accidentally loaded | Low | Glob pattern `*_rules.json` excludes `*_rules_optional.json` |
| Performance regression from loading all rules | Very Low | ~27 small JSON files per packet, <10ms total |
| Consumer breakage from deleted imports | High (expected) | Phase D systematically fixes all consumers |
| `variable_instrument_mapping.json` stale | Low | Existing data file, not modified |

---

## Appendix: File Inventory

### Files Created
| File | Phase | Lines |
|---|---|---|
| `src/pipeline/io/rule_pool.py` | A | ~120 |
| `tests/test_rule_pool.py` | E | ~180 |

### Files Modified
| File | Phase | Change Summary |
|---|---|---|
| `src/pipeline/io/rule_loader.py` | B | Rewrite `get_rules_for_record()`, delete 5 functions |
| `src/pipeline/config/config_manager.py` | C | Delete ~50 lines of static routing |
| `src/pipeline/reports/report_pipeline.py` | D | Remove 2 imports, simplify discriminant handling |
| `src/pipeline/core/data_processing.py` | D | Remove 2 imports, simplify dynamic instrument branch |
| `src/pipeline/core/pipeline.py` | D | Replace Stage 2 with pool loading |
| `tests/test_data_routing.py` | E | Rewrite for pool-based routing |
| `tests/conftest.py` | E | Add pool fixtures, remove dead fixtures |
| `tests/test_configuration.py` | E | Remove refs to deleted config statics |

### Files Deleted
None — all changes are modifications. Dead code is removed from existing files, not whole-file deletions.
