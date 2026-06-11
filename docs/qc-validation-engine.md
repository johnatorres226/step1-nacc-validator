# QC Validation Engine

Built on Cerberus, extended with NACC-specific custom validators in `nacc_form_validator/nacc_validator.py`.

## Validation Approaches

### Unified (Current — use this)

`src/pipeline/io/unified_rule_loader.py` + `src/pipeline/reports/report_pipeline.py`

Loads all rules for a packet type at once; no instrument-level routing.

```python
from src.pipeline.io.unified_rule_loader import UnifiedRuleLoader
from src.pipeline.reports.report_pipeline import validate_data_unified

loader = UnifiedRuleLoader(config)
rules = loader.load_packet_rules("I")   # merges all I-packet rule files

errors, logs, passed = validate_data_unified(
    data=dataframe,
    primary_key_field="ptid",
    instrument_name=None,
)
```

Instrument context is inferred from variable name prefixes (e.g. `a1_birthyr` → `a1`).

### Hierarchical (Deprecated)

`src/pipeline/io/hierarchical_router.py` — three-level routing: Packet → Instrument → Variable.
Maintained for backward compatibility only. Migrate to `UnifiedRuleLoader`.

## Packet Types

| Packet | Rules directory | Visit type |
|--------|-----------------|------------|
| `I` | `config/I/` | Initial Visit |
| `I4` | `config/I4/` | Initial Visit Form 4 |
| `F` | `config/F/` | Follow-up Visit |

## Custom Validation Methods (NACCValidator)

| Method | Purpose |
|--------|---------|
| `_validate_compatibility` | JSON Logic if-then-else cross-field rules |
| `_validate_temporalrules` | Cross-visit longitudinal consistency |
| `_validate_logic` | Formula / math expression evaluation |
| `_validate_compute_gds` | Geriatric Depression Scale scoring |
| `_validate_compare_with` | Cross-field comparison within a record |
| `_validate_compare_with_prev` | Compare current vs previous visit value |
| `_validate_compare_age` | Age-based constraints and date arithmetic |
| `_validate_curr_date_max/min` | Date boundary validation |
| `_validate_curr_year_max/min` | Year boundary validation |
| `_validate_filled` | Conditional field completion requirements |
| `_validate_check_with` | External data check (e.g. RXNORM codes) |

## ValidationResult

```python
@dataclass
class ValidationResult:
    passed: bool                       # True = record passed all rules
    sys_failure: bool                  # True = engine error (not a data error)
    errors: Dict[str, List[str]]       # field → [error messages]
    error_tree: Optional[DocumentErrorTree]
```

## Error Code Ranges

| Range | Category |
|-------|----------|
| `0x1000–0x1FFF` | Date/year/fill/range violations |
| `0x2000–0x2FFF` | Temporal, compatibility, formula errors |
| `0x3000–0x3FFF` | External data, age, complex comparison errors |

## Rule File Structure

```
config/
├── I/          # Initial visit JSON rule files
├── I4/         # Four-month follow-up JSON rule files
└── F/          # Annual follow-up JSON rule files
```

Each file is a Cerberus-compatible schema dict keyed by variable name.
