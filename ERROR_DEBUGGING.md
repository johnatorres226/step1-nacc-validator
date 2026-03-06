# ERROR_DEBUGGING.md — Cross-Packet Rule Collision Investigation

> **Branch**: `qc-debug`  
> **Parent Branch**: `project-refactoring`  
> **Created**: 2026-03-06  
> **Status**: Under Investigation

---

## Executive Summary

The QC error output increased dramatically from **~200 errors (Feb 27)** to **~900 errors (Mar 3)**, a **207% increase**. This document details the root cause investigation and fix plan.

---

## 1. Observed Symptoms

### Error Count Comparison

| Run Date | Output Folder | Total Errors |
|----------|---------------|-------------|
| Feb 21, 2026 | `QC_CompleteVisits_21FEB2026_*` | ~299 |
| Mar 3, 2026 | `QC_CompleteVisits_03MAR2026_205420` | **919** |
| **Delta** | | **+620 errors (+207%)** |

### New Error Variables (Not in Baseline)

These variables appeared in the Mar 3 output but were absent from Feb 21:

| Variable | Instrument | Error Type |
|----------|-----------|------------|
| `nwinfkid` | a3_participant_family_history | null value not allowed |
| `nwinfpar` | a3_participant_family_history | null value not allowed |
| `nwinfsib` | a3_participant_family_history | null value not allowed |
| `newinf` | a2_coparticipant_demographics | null value not allowed |
| `otraila` | c2c2t_neuropsychological_battery_scores | null value not allowed |
| `otrailb` | c2c2t_neuropsychological_battery_scores | null value not allowed |

**Key Observation**: These are **F-packet-specific variables** that should NOT be validated against I/I4 packet records.

---

## 2. Root Cause Analysis

### The Bug: Cross-Packet Namespace Collision in `NamespacedRulePool`

#### Location
- **File**: [src/pipeline/core/pipeline.py](src/pipeline/core/pipeline.py#L113-118)
- **File**: [src/pipeline/io/rule_pool.py](src/pipeline/io/rule_pool.py#L136-144)

#### What Happens

1. **In `pipeline.py` (Lines 113-118)**:
   ```python
   for packet in ("I", "I4", "F"):
       try:
           pool.load_packet(packet, config)
   ```
   All three packets are loaded into the **same** `NamespacedRulePool` singleton.

2. **Namespace Collision**:
   - `config/I/rules/a3_rules.json` → namespace `"a3"`
   - `config/F/rules/a3_rules.json` → namespace `"a3"` (SAME!)

3. **No Conflict Detection**:
   In `rule_pool.py` (Lines 136-144):
   ```python
   if variable in self._rules:
       if self._rules[variable].namespace != namespace:  # Same namespace!
           self._conflicts.add(variable)  # NOT triggered
   ```
   Since both files share the **same namespace** (`"a3"`), no conflict is detected.

4. **First-Wins Semantics**:
   The flat `_rules` index keeps whichever rule was loaded first (from I packet), but the **namespace index is overwritten** with F packet rules.

#### Impact

When validating an **I/I4 packet record**:

| Variable | Expected Rule (I packet) | Actual Applied Rule (F packet) |
|----------|-------------------------|-------------------------------|
| `momyob` | `required: true` | `nullable: true` (depends on `nwinfpar`) |
| `nwinfpar` | **NOT PRESENT** | `required: true` → **FALSE POSITIVE ERROR** |

The F-packet variables (`nwinfkid`, `nwinfpar`, etc.) are correctly added to the pool (they don't exist in I/I4), but their **dependency relationships are broken** because parent rules like `momyob` have conflicting semantics.

---

## 3. Evidence

### Rule File Analysis

**config/I/rules/a3_rules.json** (I packet - Initial Visit):
```json
{
    "momyob": {
        "type": "integer",
        "required": true,
        ...
    }
}
```

**config/F/rules/a3_rules.json** (F packet - Follow-up Visit):
```json
{
    "nwinfpar": {
        "type": "integer",
        "required": true,
        ...
    },
    "momyob": {
        "type": "integer",
        "nullable": true,
        "depends_on": "nwinfpar"
        ...
    }
}
```

The F packet introduces `nwinfpar` as a gating field for family history updates, and makes `momyob` nullable based on that field. When both are loaded into the same pool:
- `nwinfpar` gets added (F-only)
- `momyob` rule from I packet persists (first-wins)
- The relationship between them is **undefined** for I packet records

---

## 4. Fix Strategy

### Option A: Per-Packet Pool Isolation (Recommended)

**Approach**: Load only the record's packet rules at validation time, not all packets upfront.

**Changes**:
1. Remove the pre-loading loop in `pipeline.py` (Lines 113-118)
2. Let `get_rules_for_record()` load the specific packet on-demand
3. Add `pool.clear()` or use packet-scoped pool instances

**Pros**:
- Clean separation of concerns
- Aligns with original design intent in `CONFIG_RULE_ROUTING.md`
- No namespace collision possible

**Cons**:
- Slightly more I/O (loading per-record instead of upfront)
- Need to manage pool lifecycle carefully

### Option B: Packet-Prefixed Namespaces

**Approach**: Modify `_namespace_from_path()` to include packet prefix.

```python
# Before: "a3_rules.json" → "a3"
# After:  "config/I/rules/a3_rules.json" → "i_a3"
```

**Pros**:
- Minimal code changes
- Conflicts are now detectable

**Cons**:
- Breaks existing namespace_to_instrument mapping
- Requires updating all consumers of namespace

### Decision: **Option A — Per-Packet Pool Isolation**

---

## 5. Implementation Plan

### Step 1: Create Reproduction Test

```python
# tests/test_packet_rule_isolation.py
def test_loading_multiple_packets_creates_collision():
    """Demonstrates the bug: loading I then F shares namespace 'a3'."""
    pool = NamespacedRulePool()
    pool.load_packet("I", config)
    pool.load_packet("F", config)
    
    # Bug: momyob rule is from I packet (first-wins)
    momyob_rule = pool.get_rule("momyob")
    assert momyob_rule.source_file == "a3_rules.json"  # Which packet?
    
    # Bug: nwinfpar is F-only but gets applied to I records
    nwinfpar_rule = pool.get_rule("nwinfpar")
    assert nwinfpar_rule is not None  # Shouldn't exist for I validation!
```

### Step 2: Implement Fix

Modify `pipeline.py` to scope pool loading:

```python
# Instead of pre-loading all packets:
# for packet in ("I", "I4", "F"):
#     pool.load_packet(packet, config)

# Load per-record's packet in validation loop
for instrument in config.instruments:
    ...
    for idx, record in df_inst.iterrows():
        packet = record.get("packet", "").upper()
        if packet not in pool.loaded_packets:
            pool.clear()  # Reset to prevent collision
            pool.load_packet(packet, config)
```

### Step 3: Verify Fix

Run QC pipeline and confirm:
- Error count returns to ~200-300 baseline
- F-packet variables (`nwinfpar`, etc.) no longer appear in I/I4 record errors

---

## 6. Test Execution Commands

```bash
# Reproduce the bug
pytest tests/test_packet_rule_isolation.py::test_loading_multiple_packets_creates_collision -v

# Verify fix
pytest tests/test_packet_rule_isolation.py::test_packet_scoped_pool_prevents_collision -v

# Full regression
pytest tests/ -v --ignore=tests/test_report_fetching.py -k "not integration"
```

---

## 7. Verification Checklist

- [ ] Reproduction test fails before fix, passes after
- [ ] Full test suite passes
- [ ] QC pipeline run produces ~200-300 errors (matching baseline)
- [ ] F-packet variables (`nwinfpar`, `nwinfkid`, `nwinfsib`) do not appear in I/I4 errors
- [ ] I-packet variables validate correctly with I rules
- [ ] F-packet variables validate correctly with F rules

---

## 8. References

- [CONFIG_RULE_ROUTING.md](CONFIG_RULE_ROUTING.md) — Original namespaced pool design
- [src/pipeline/io/rule_pool.py](src/pipeline/io/rule_pool.py) — Pool implementation
- [src/pipeline/core/pipeline.py](src/pipeline/core/pipeline.py) — Pipeline orchestration
- [src/pipeline/io/rule_loader.py](src/pipeline/io/rule_loader.py) — Rule loading API
