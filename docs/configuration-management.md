# Configuration

All configuration is loaded from environment variables via `QCConfig` dataclass in `src/pipeline/config/config_manager.py`.

## Required Environment Variables

| Variable | Description |
|----------|-------------|
| `REDCAP_API_TOKEN` | REDCap API authentication token |
| `REDCAP_API_URL` | REDCap API endpoint URL |
| `PROJECT_ID` | REDCap project identifier |
| `JSON_RULES_PATH_I` | Path to Initial Visit validation rules |
| `JSON_RULES_PATH_I4` | Path to Initial Visit (Form 4) validation rules |
| `JSON_RULES_PATH_F` | Path to Follow-up Visit validation rules |

## Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDCAP_REPORT_ID` | — | Report ID to fetch from REDCap |
| `OUTPUT_PATH` | `project_root/output` | Output directory |
| `LOG_PATH` | — | Log directory |
| `UPLOAD_READY_PATH` | — | Upload-ready staging directory |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `MAX_WORKERS` | `4` | Concurrent processing threads |
| `TIMEOUT` | `300` | API request timeout (seconds) |
| `RETRY_ATTEMPTS` | `3` | Retries for failed operations |
| `PTID_LIST` | `None` | Comma-separated PTIDs to process (omit for all) |
| `GENERATE_HTML_REPORT` | `true` | Enable HTML report generation |

## REDCap Events

```python
uds_events = [
    "udsv4_ivp_1_arm_1",  # Initial Visit
    "udsv4_fvp_2_arm_1",  # Follow-up Visit
]
```

## Instrument-to-Rule Mapping

Each instrument maps to one or more JSON rule files under `config/{I,I4,F}/`:

```python
instrument_json_mapping = {
    "form_header":                              ["header_rules.json"],
    "a1_participant_demographics":              ["a1_rules.json"],
    "a2_coparticipant_demographics":            ["a2_rules.json"],
    "a3_participant_family_history":            ["a3_rules.json"],
    "a4_participant_medications":               ["a4_rules.json"],
    "a4a_adrd_specific_treatments":             ["a4a_rules.json"],
    "a5d2_participant_health_history_...",      ["a5d2_rules.json"],
    "a1a_sdoh":                                 ["a1a_rules.json"],
    "b1_vital_signs_and_anthropometrics":       ["b1_rules.json"],
    "b4_cdr_dementia_staging_instrument":       ["b4_rules.json"],
    "b5_neuropsychiatric_inventory_..._npiq":   ["b5_rules.json"],
    "b6_geriatric_depression_scale":            ["b6_rules.json"],
    "b7_functional_assessment_scale_fas":       ["b7_rules.json"],
    "b8_neurological_examination_findings":     ["b8_rules.json"],
    "b9_clinician_judgment_of_symptoms":        ["b9_rules.json"],
    "b3_unified_parkinsons_..._updrs_m":        ["b3_rules.json"],
    "d1a_clinical_syndrome":                    ["d1a_rules.json"],
    "d1b_etiological_diagnosis_..._support":    ["d1b_rules.json"],
    "c2c2t_neuropsychological_battery_scores":  ["c2_rules.json", "c2t_rules.json"],
}
```

The `c2c2t` instrument uses dynamic rule selection based on `loc_c2_or_c2t`:
- `C2` → `c2_rules.json`
- `C2T` → `c2t_rules.json`

## Key Config Methods

| Method | Description |
|--------|-------------|
| `get_config()` | Returns singleton `QCConfig`; loads + validates on first call |
| `get_config(force_reload=True)` | Forces reload from environment |
| `get_config(skip_validation=True)` | Skips validation (use in tests) |
| `config.get_rules_path_for_packet(packet)` | Returns rules path for `I`, `I4`, or `F` |
| `config.to_dict()` | Serializes config for debugging |
| `config.validate()` | Returns list of validation error strings |

## JSON Schema → Cerberus Key Map

```python
KEY_MAP = {
    "type": "type",         "nullable": "nullable",
    "min": "min",           "max": "max",
    "pattern": "regex",     "allowed": "allowed",
    "forbidden": "forbidden","required": "required",
    "anyof": "anyof",       "oneof": "oneof",
    "allof": "allof",       "formatting": "formatting",
    "compatibility": "compatibility",
}
```
