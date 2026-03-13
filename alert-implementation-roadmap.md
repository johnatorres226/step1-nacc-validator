# Alert System Implementation Roadmap

## Current State vs Target State

### Current Error Structure
```python
# Your current error dictionary
{
    "ptid": "12345",
    "instrument_name": "a1",
    "variable": "birthmo",
    "error_message": "field 'birthmo' is required",
    "current_value": "",
    "packet": "I",
    "json_rule_path": "config/I/a1.json",
    "redcap_event_name": "initial_visit_arm_1"
}
```

### Target Error Structure (Downstream)
```python
# Downstream's FileError with error_type classification
{
    "ptid": "12345",
    "type": "alert",  # <-- NEW: "alert", "error", or "warning"
    "code": "W0042",  # <-- Enhanced with NACC code
    "variable": "birthmo",
    "message": "Birth month should be reviewed for consistency",
    "current_value": "",
    "location": {"key_path": "birthmo"},
    "visitnum": "1",
    "date": "2024-01-15"
}
```

---

## Implementation Phases

### Phase 1: Alert Classification Setup (1-2 days)

**Goal**: Create configuration system for classifying errors vs alerts

#### Step 1.1: Define Alert Classification Config
Create `config/alert_classifications.json`:

```json
{
  "error_type_mappings": {
    "required": "error",
    "type": "error",
    "allowed": "error",
    "min": "error",
    "max": "error",
    "minlength": "error",
    "maxlength": "error",
    "regex": "error",
    
    "temporalrules": "alert",
    "compatibility": "alert",
    "logic": "alert",
    "compare_with": "alert",
    "compute_gds": "warning",
    "filled": "warning"
  },
  
  "error_code_mappings": {
    "E0001": {"type": "error", "description": "Required field missing"},
    "E0002": {"type": "error", "description": "Invalid data type"},
    "W0042": {"type": "alert", "description": "Temporal consistency check"},
    "W0043": {"type": "alert", "description": "Cross-form logic check"},
    "I0010": {"type": "warning", "description": "Informational notice"}
  },
  
  "rule_specific_overrides": {
    "birthmo": {
      "nullable": "warning"
    },
    "visitdate": {
      "temporalrules": "error"
    }
  }
}
```

#### Step 1.2: Update Error Models
Modify `nacc_form_validator/models.py`:

```python
from typing import Literal, Optional
from dataclasses import dataclass, field

ErrorType = Literal["error", "alert", "warning"]

@dataclass
class EnhancedValidationError:
    """Extended error model with severity classification."""
    error_type: ErrorType = "error"  # NEW: Severity level
    error_code: Optional[str] = None  # NEW: NACC error code
    variable: str = ""
    error_message: str = ""
    current_value: str = ""
    rule_name: str = ""  # NEW: Which rule failed
    
    # Existing fields
    ptid: str = ""
    instrument_name: str = ""
    packet: str = ""
    json_rule_path: str = ""
    redcap_event_name: str = ""
    
    # NEW: Enhanced metadata
    severity_justification: str = ""
    can_submit_with_alert: bool = False

@dataclass
class ValidationResult:
    """Enhanced validation result with alert support."""
    passed: bool
    sys_failure: bool
    errors: dict[str, list[str]]
    error_tree: DocumentErrorTree | None
    
    # NEW: Classified error tracking
    error_count: int = 0
    alert_count: int = 0
    warning_count: int = 0
    classified_errors: list[EnhancedValidationError] = field(default_factory=list)
    
    def has_blocking_errors(self) -> bool:
        """Check if there are any blocking errors."""
        return self.error_count > 0
    
    def has_review_items(self) -> bool:
        """Check if there are alerts that need review."""
        return self.alert_count > 0 or self.warning_count > 0
```

#### Step 1.3: Create Alert Classifier Module
Create `nacc_form_validator/alert_classifier.py`:

```python
"""Alert classification logic for NACC validation errors."""

import json
import logging
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

ErrorType = Literal["error", "alert", "warning"]

class AlertClassifier:
    """Classifies validation errors into errors, alerts, or warnings."""
    
    DEFAULT_CLASSIFICATIONS = {
        "required": "error",
        "type": "error",
        "allowed": "error",
        "temporalrules": "alert",
        "compatibility": "alert",
        "logic": "alert",
        "filled": "warning",
    }
    
    def __init__(self, config_path: Path | None = None):
        """Initialize with optional custom configuration."""
        self.config_path = config_path
        self.rule_mappings: dict[str, ErrorType] = {}
        self.code_mappings: dict[str, dict] = {}
        self.overrides: dict[str, dict] = {}
        
        if config_path and config_path.exists():
            self._load_config(config_path)
        else:
            logger.info("Using default error classifications")
            self.rule_mappings = self.DEFAULT_CLASSIFICATIONS.copy()
    
    def _load_config(self, config_path: Path) -> None:
        """Load classification configuration from JSON file."""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            self.rule_mappings = config.get("error_type_mappings", {})
            self.code_mappings = config.get("error_code_mappings", {})
            self.overrides = config.get("rule_specific_overrides", {})
            
            logger.info("Loaded alert classifications from %s", config_path)
        except Exception as e:
            logger.warning("Failed to load config, using defaults: %s", e)
            self.rule_mappings = self.DEFAULT_CLASSIFICATIONS.copy()
    
    def classify(
        self,
        rule_name: str,
        variable_name: str = "",
        error_code: str = ""
    ) -> ErrorType:
        """Classify an error based on rule, variable, and code.
        
        Priority:
        1. Variable-specific override (highest)
        2. Error code mapping
        3. Rule type mapping
        4. Default to "error" (safest)
        """
        # Check variable-specific override
        if variable_name and variable_name in self.overrides:
            if rule_name in self.overrides[variable_name]:
                return self.overrides[variable_name][rule_name]
        
        # Check error code mapping
        if error_code and error_code in self.code_mappings:
            return self.code_mappings[error_code].get("type", "error")
        
        # Check rule type mapping
        if rule_name in self.rule_mappings:
            return self.rule_mappings[rule_name]
        
        # Default to error for safety
        logger.debug("No classification for rule '%s', defaulting to 'error'", rule_name)
        return "error"
    
    def get_summary(self, classified_errors: list) -> dict:
        """Generate summary statistics of errors by type."""
        return {
            "total": len(classified_errors),
            "errors": sum(1 for e in classified_errors if e.error_type == "error"),
            "alerts": sum(1 for e in classified_errors if e.error_type == "alert"),
            "warnings": sum(1 for e in classified_errors if e.error_type == "warning"),
        }
```

---

### Phase 2: Integration with Validation Engine (2-3 days)

**Goal**: Integrate alert classification into validation process

#### Step 2.1: Update Quality Check Logic
Modify `nacc_form_validator/quality_check.py`:

```python
from nacc_form_validator.alert_classifier import AlertClassifier, ErrorType

class QualityCheck:
    def __init__(
        self,
        primary_key: str,
        schema: dict,
        strict: bool = True,
        datastore=None,
        alert_classifier: AlertClassifier | None = None  # NEW
    ):
        self.primary_key = primary_key
        self.schema = schema
        self.strict = strict
        self.datastore = datastore
        self.alert_classifier = alert_classifier or AlertClassifier()  # NEW
    
    def validate(self, record: dict) -> ValidationResult:
        """Validate record with alert classification."""
        # ... existing validation logic ...
        
        # NEW: Classify errors after validation
        classified_errors = []
        for field, error_list in result.errors.items():
            for error_msg in error_list:
                rule_name = self._extract_rule_name(error_msg)
                error_type = self.alert_classifier.classify(
                    rule_name=rule_name,
                    variable_name=field
                )
                
                classified_errors.append(EnhancedValidationError(
                    error_type=error_type,
                    variable=field,
                    error_message=error_msg,
                    rule_name=rule_name,
                    current_value=str(record.get(field, "")),
                    # ... other fields
                ))
        
        # Count by type
        result.error_count = sum(1 for e in classified_errors if e.error_type == "error")
        result.alert_count = sum(1 for e in classified_errors if e.error_type == "alert")
        result.warning_count = sum(1 for e in classified_errors if e.error_type == "warning")
        result.classified_errors = classified_errors
        
        return result
```

#### Step 2.2: Update Pipeline Error Handling
Modify `src/pipeline/reports/report_pipeline.py`:

```python
def validate_data(
    data: pd.DataFrame,
    validation_rules: dict[str, dict[str, Any]],
    instrument_name: str,
    primary_key_field: str,
    alert_classifier: AlertClassifier | None = None  # NEW
) -> tuple[list[dict], list[dict], list[dict]]:
    """Validate data with alert classification support."""
    
    classifier = alert_classifier or AlertClassifier()
    errors, logs, passed_records = [], [], []
    
    for record_dict in data.to_dict("records"):
        result = quality_check.validate(record_dict)
        
        if result.sys_failure:
            # System errors remain critical
            errors.append(...)
        elif result.has_blocking_errors():
            # Only blocking errors fail validation
            for err in result.classified_errors:
                if err.error_type == "error":
                    errors.append({
                        "error_type": err.error_type,  # NEW
                        "error_severity": "BLOCKING",  # NEW
                        "variable": err.variable,
                        "error_message": err.error_message,
                        # ... existing fields
                    })
        
        # Track alerts separately (non-blocking)
        if result.has_review_items():
            for err in result.classified_errors:
                if err.error_type in ("alert", "warning"):
                    errors.append({
                        "error_type": err.error_type,  # NEW
                        "error_severity": "NON_BLOCKING",  # NEW
                        "variable": err.variable,
                        "error_message": err.error_message,
                        # ... existing fields
                    })
    
    return errors, logs, passed_records
```

---

### Phase 3: Enhanced Report Generation (1-2 days)

**Goal**: Generate separate error and alert reports

#### Step 3.1: Update Report Export
Modify `src/pipeline/io/reports.py`:

```python
def export_error_report(
    df_errors: pd.DataFrame, 
    output_dir: Path, 
    date_tag: str, 
    time_tag: str
) -> dict[str, Path | None]:
    """Export errors, alerts, and warnings as separate files."""
    
    if df_errors is None or df_errors.empty:
        logger.info("No validation issues to report")
        return {"errors": None, "alerts": None, "warnings": None}
    
    # Ensure error_type column exists
    if "error_type" not in df_errors.columns:
        df_errors["error_type"] = "error"  # Default for backward compatibility
    
    # Split by type
    df_blocking = df_errors[df_errors["error_type"] == "error"]
    df_alerts = df_errors[df_errors["error_type"] == "alert"]
    df_warnings = df_errors[df_errors["error_type"] == "warning"]
    
    output_paths = {}
    
    # Errors (blocking)
    if not df_blocking.empty:
        path = output_dir / "Errors" / f"Blocking_Errors_{date_tag}_{time_tag}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        df_blocking.to_csv(path, index=False)
        logger.info("Exported %d blocking errors to %s", len(df_blocking), path.name)
        output_paths["errors"] = path
    else:
        output_paths["errors"] = None
    
    # Alerts (review required)
    if not df_alerts.empty:
        path = output_dir / "Alerts" / f"Review_Alerts_{date_tag}_{time_tag}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        df_alerts.to_csv(path, index=False)
        logger.info("Exported %d alerts to %s", len(df_alerts), path.name)
        output_paths["alerts"] = path
    else:
        output_paths["alerts"] = None
    
    # Warnings (informational)
    if not df_warnings.empty:
        path = output_dir / "Warnings" / f"Info_Warnings_{date_tag}_{time_tag}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        df_warnings.to_csv(path, index=False)
        logger.info("Exported %d warnings to %s", len(df_warnings), path.name)
        output_paths["warnings"] = path
    else:
        output_paths["warnings"] = None
    
    # Also export combined report for backward compatibility
    path = output_dir / "Errors" / f"All_Issues_{date_tag}_{time_tag}.csv"
    df_errors.to_csv(path, index=False)
    logger.info("Exported %d total issues to %s", len(df_errors), path.name)
    output_paths["combined"] = path
    
    return output_paths
```

#### Step 3.2: Create Alert Summary Report
Add new function in `src/pipeline/io/reports.py`:

```python
def export_alert_summary(
    df_errors: pd.DataFrame,
    output_dir: Path,
    date_tag: str,
    time_tag: str
) -> Path | None:
    """Export summary of issues by severity and type."""
    
    if df_errors is None or df_errors.empty:
        return None
    
    # Aggregate by participant and severity
    summary = (
        df_errors.groupby(["ptid", "redcap_event_name", "error_type"])
        .size()
        .reset_index(name="count")
        .pivot_table(
            index=["ptid", "redcap_event_name"],
            columns="error_type",
            values="count",
            fill_value=0
        )
        .reset_index()
    )
    
    # Add overall status
    summary["qc_status"] = summary.apply(
        lambda row: "BLOCKED" if row.get("error", 0) > 0 else (
            "REVIEW_REQUIRED" if row.get("alert", 0) > 0 else "PASSED"
        ),
        axis=1
    )
    
    path = output_dir / "Reports" / f"QC_Summary_by_Severity_{date_tag}_{time_tag}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(path, index=False)
    logger.info("Exported severity summary for %d participants", len(summary))
    
    return path
```

---

### Phase 4: CLI and User Experience (1 day)

**Goal**: Update CLI to show alert statistics and handle new outputs

#### Step 4.1: Update CLI Summary Display
Modify `src/cli/cli.py`:

```python
def _display_validation_summary(result: dict) -> None:
    """Display validation summary with error type breakdown."""
    
    console.print("\n[bold cyan]QC Validation Summary[/bold cyan]")
    console.print("─" * 50)
    
    df_errors = result.get("errors_df")
    if df_errors is None or df_errors.empty:
        console.print("[green]✓ No issues found - All validations passed![/green]")
        return
    
    # Count by type
    if "error_type" in df_errors.columns:
        type_counts = df_errors["error_type"].value_counts()
        
        blocking_errors = type_counts.get("error", 0)
        alerts = type_counts.get("alert", 0)
        warnings = type_counts.get("warning", 0)
        
        if blocking_errors > 0:
            console.print(f"[bold red]✗ Blocking Errors:[/bold red] {blocking_errors}")
        if alerts > 0:
            console.print(f"[bold yellow]⚠ Review Alerts:[/bold yellow] {alerts}")
        if warnings > 0:
            console.print(f"[dim]ℹ Info Warnings:[/dim] {warnings}")
        
        # Overall status
        if blocking_errors > 0:
            console.print("\n[bold red]Status: FAILED - Must fix errors before submission[/bold red]")
        elif alerts > 0:
            console.print("\n[bold yellow]Status: REVIEW REQUIRED - Data can be submitted with review[/bold yellow]")
        else:
            console.print("\n[bold green]Status: PASSED WITH WARNINGS - Ready for submission[/bold green]")
    else:
        # Backward compatibility
        console.print(f"[red]✗ Total Issues:[/red] {len(df_errors)}")
    
    console.print("─" * 50)
```

#### Step 4.2: Add Alert Filtering Options
Update CLI arguments:

```python
@click.option(
    "--severity",
    "-s",
    type=click.Choice(["all", "errors", "alerts", "warnings"], case_sensitive=False),
    default="all",
    help="Filter issues by severity level (default: all)"
)
@click.option(
    "--fail-on-alerts",
    is_flag=True,
    default=False,
    help="Treat alerts as blocking errors (default: false)"
)
def qc_run(initials, severity, fail_on_alerts, **kwargs):
    """Run QC validation with alert support."""
    # ... existing code ...
    
    # Apply severity filtering
    if severity != "all" and df_errors is not None:
        df_errors = df_errors[df_errors["error_type"] == severity]
    
    # Optionally fail on alerts
    if fail_on_alerts:
        alert_count = (df_errors["error_type"] == "alert").sum()
        if alert_count > 0:
            raise click.ClickException(f"Found {alert_count} alerts (treated as errors)")
```

---

### Phase 5: Testing and Validation (2-3 days)

**Goal**: Ensure alert system works correctly and doesn't break existing functionality

#### Test Cases

1. **Classification Accuracy Test**
   ```python
   def test_alert_classification():
       classifier = AlertClassifier()
       
       assert classifier.classify("required") == "error"
       assert classifier.classify("temporalrules") == "alert"
       assert classifier.classify("filled") == "warning"
   ```

2. **Backward Compatibility Test**
   ```python
   def test_backward_compatibility():
       # Ensure old code still works without error_type
       df_old_format = pd.DataFrame({
           "ptid": ["123"],
           "error_message": ["Field required"]
       })
       
       result = export_error_report(df_old_format, tmp_path, "DATE", "TIME")
       assert result is not None
   ```

3. **Report Generation Test**
   ```python
   def test_separate_report_generation():
       df_mixed = pd.DataFrame({
           "ptid": ["123", "123", "456"],
           "error_type": ["error", "alert", "warning"],
           "error_message": ["Required", "Temporal", "Info"]
       })
       
       result = export_error_report(df_mixed, tmp_path, "DATE", "TIME")
       
       assert result["errors"] is not None
       assert result["alerts"] is not None
       assert result["warnings"] is not None
   ```

4. **End-to-End Validation Test**
   ```python
   def test_full_pipeline_with_alerts():
       config = QCConfig(...)
       result = run_pipeline(config)
       
       df_errors = result["errors_df"]
       assert "error_type" in df_errors.columns
       
       # Verify classification
       error_count = (df_errors["error_type"] == "error").sum()
       alert_count = (df_errors["error_type"] == "alert").sum()
       
       assert error_count >= 0
       assert alert_count >= 0
   ```

---

## Migration Strategy

### Step 1: Enable Alerts Alongside Existing System
- Add `error_type` column to error DataFrames (default to "error")
- Generate both old and new reports during transition period
- Allow users to test new reports without disrupting existing workflows

### Step 2: Communication and Training
- Document new error types and meanings
- Provide examples of each type
- Train data coordinators on how to handle alerts vs errors

### Step 3: Gradual Rollout
1. **Week 1**: Deploy with conservative classification (most rules → error)
2. **Week 2**: Review generated alerts, adjust classifications
3. **Week 3**: Expand alert classifications based on feedback
4. **Week 4**: Remove old report format, keep only new format

### Step 4: Validation Against Downstream
- Run same test cases through both systems
- Compare error classifications
- Adjust your classifications to match downstream behavior
- Document any intentional differences

---

## Expected Benefits

### Immediate Benefits
1. **Reduced False Positives**: Alerts don't block submission
2. **Better Prioritization**: Clear separation of critical vs review items
3. **Improved Workflow**: Data coordinators can submit data with alerts for review
4. **Enhanced Reporting**: Separate reports for different severity levels

### Long-term Benefits
1. **Alignment with NACC**: Error classifications match downstream system
2. **Fewer Surprises**: Alerts in your system = alerts downstream
3. **Better Data Quality**: Reviewers can focus on critical errors first
4. **Improved Training**: Clear understanding of error severity

---

## Rollback Plan

If issues arise:

1. **Immediate**: Set all classifications to "error" via config override
2. **Short-term**: Revert to single combined error report
3. **Long-term**: Fall back to previous version while investigating

Configuration-based system allows easy rollback without code changes.

---

## Success Metrics

### Technical Metrics
- No regression in existing error detection
- All legacy tests still pass
- New tests cover alert classification logic

### User Metrics
- Reduced time to resolve validation issues
- Fewer support requests about "false errors"
- Increased data submission success rate

### Alignment Metrics
- 90%+ agreement with downstream alert classifications
- Zero surprise alerts post-upload
- Consistent error messaging across systems

---

## Next Steps

1. **Review Classification Config**: Decide which rules should be errors vs alerts
2. **Request NACC QC Database Access**: Get official error code classifications
3. **Pilot with Small Dataset**: Test alert system on recent data
4. **Gather Feedback**: Ask data coordinators which classifications make sense
5. **Iterate**: Adjust classifications based on real-world usage

---

## Questions to Answer

1. **Which validation rules should generate alerts vs errors?**
   - Temporal rules?
   - Logic checks?
   - Cross-form compatibility?

2. **Should some alerts be configurable per center?**
   - Different centers may have different data quality standards

3. **How to handle alert review workflow?**
   - Who reviews alerts?
   - What's the approval process?
   - How to track alert resolution?

4. **Integration with REDCap?**
   - Should alert status be uploaded back to REDCap?
   - New fields needed for alert tracking?

---

## Resources

- **Downstream Repo**: https://github.com/naccdata/flywheel-gear-extensions
- **Analysis Document**: `docs/downstream-alerts-analysis.md`
- **NACC Form Validator**: https://github.com/naccdata/nacc-form-validator
- **Cerberus Validation**: https://docs.python-cerberus.org/

---

**Document Version**: 1.0  
**Last Updated**: 2026-03-13  
**Author**: GitHub Copilot Analysis
