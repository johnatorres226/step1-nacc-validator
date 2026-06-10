# Data Fetching System

Fetches pre-filtered QC data from a REDCap report. No ETL transformations — REDCap handles filtering upstream.

**Entry point**: `src/pipeline/core/fetcher.py` → `fetch_report_data(config, output_path, date_tag, time_tag)`

## Execution Flow

1. Validate `config.report_id` is set
2. Build POST payload (`_build_report_payload`)
3. POST to REDCap API (`_post_api`)
4. Convert response to DataFrame; rename `record_id` → `ptid` if needed (`_validate_and_map`)
5. Filter to `config.ptid_list` if set (`_apply_ptid_filter`)
6. Optionally save to `{output_path}/Data_Fetched/Report_Data_{report_id}_{date}_{time}.csv`
7. Return `(DataFrame, record_count)`

## Required Data Fields

After fetch, these columns must be present or the run raises `ValueError`:

```python
REQUIRED_FIELDS = ["ptid", "redcap_event_name"]
```

## API Payload

```python
{
    "token":               config.api_token,
    "content":             "report",
    "report_id":           config.report_id,
    "format":              "json",
    "rawOrLabel":          "raw",
    "rawOrLabelHeaders":   "raw",
    "exportCheckboxLabel": "false",
    "returnFormat":        "json",
}
```

## Error Types

| Error | Cause |
|-------|-------|
| `ValueError: REDCAP_REPORT_ID is not configured` | Missing `report_id` |
| `RuntimeError: API request timed out after Ns` | Network/timeout |
| `RuntimeError: REDCap API request failed: ...` | HTTP / auth error |
| `RuntimeError: Failed to parse JSON response` | Malformed REDCap response |
| `ValueError: Missing required fields: ptid` | Report missing required columns |

No automatic retry — if the report fetch fails, fix config and re-run.
