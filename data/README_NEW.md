# Validation History Database

This directory contains the **validation history database** used by the UDS-v4 REDCap QC Validator Enhanced Mode.

## Database Overview

The `validation_history.db` file is a SQLite database that stores:

- **Validation Run History**: Complete metadata for each validation run
- **Error Records**: Detailed error information with full context
- **Trend Analysis**: Historical error patterns and insights

## 🌐 Network Drive Configuration

This database is designed to be placed on a **network drive** for multi-user access across the team.

### Environment Variable Setup

Set the environment variable to point to your network database location:

```bash
# Windows (PowerShell)
$env:VALIDATION_HISTORY_DB_PATH = "\\network-drive\shared\validation_history.db"

# Windows (Command Prompt)
set VALIDATION_HISTORY_DB_PATH=\\network-drive\shared\validation_history.db

# Linux/Mac
export VALIDATION_HISTORY_DB_PATH="/mnt/network-drive/shared/validation_history.db"
```

### Network Drive Assumptions

**🔗 Shared Access**: Multiple users can access the same database simultaneously

**📊 Centralized Insights**: All team validation runs contribute to shared trend analysis

**🔄 Consistent Data**: Single source of truth for all validation history

**🐌 Network Performance Impact**:

- Database reads/writes over network drives are **significantly slower** than local operations
- Expect 2-10x slower performance depending on network conditions
- Large datasets may experience noticeable delays

## Database Schema

### 1. `validation_runs`

```sql
CREATE TABLE validation_runs (
    run_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    event_type TEXT NOT NULL,
    total_records INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    processing_time_seconds REAL NOT NULL,
    summary_stats TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### 2. `error_records`

```sql
CREATE TABLE error_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    expected_value TEXT,
    actual_value TEXT,
    severity TEXT NOT NULL DEFAULT 'ERROR',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES validation_runs(run_id)
);
```

### 3. `error_trends`

```sql
CREATE TABLE error_trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    field_name TEXT NOT NULL,
    error_type TEXT NOT NULL,
    occurrence_count INTEGER NOT NULL,
    last_seen TEXT NOT NULL,
    trend_direction TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

## Usage Instructions

### Prerequisites

- Must use `--mode complete_events` (enforced by the system)
- Database will be automatically created if it doesn't exist
- Requires appropriate network drive permissions

### Running Enhanced Mode

Enhanced Mode is the **only way** to interact with the validation history database.

**Why Enhanced Mode Only?**

- Ensures data quality and consistency
- Prevents partial/incomplete validation runs from contaminating trends
- Provides comprehensive error context for analysis
- Maintains database integrity with proper transaction handling

#### Option 1: Use Enhanced Mode

```bash
python -m udsv4_redcap_qc_validator run-enhanced --center_id 123 --mode complete_events
```

#### Option 2: Enable Datastore in Regular Mode (Code Modification Required)

If you need datastore functionality in regular mode, you can enable it by modifying the code:

```python
# In src/pipeline/report_pipeline.py
# Change the datastore initialization to include regular mode
if mode == 'complete_events' or enable_datastore_for_all_modes:
    # Enable datastore for all modes
    use_datastore = True
```

**⚠️ Warning**: Enabling datastore for all modes may result in incomplete data in the database.

## CLI Commands

### Check Database Status

```bash
python -m udsv4_redcap_qc_validator datastore-status
```

### Generate Analysis Reports

```bash
# Generate comprehensive analysis
python -m udsv4_redcap_qc_validator datastore-analysis --output-dir ./analysis_reports

# Generate trend analysis for specific field
python -m udsv4_redcap_qc_validator datastore-analysis --field-name "a1_field" --output-dir ./analysis_reports
```

### View Configuration

```bash
python -m udsv4_redcap_qc_validator config
```

## Performance Considerations

### Network Drive Performance

Set expectations for network database operations:

```bash
# Local database operations: ~100-1000ms
# Network database operations: ~1-10 seconds
```

### Optimization Tips

- **Expected**: Network database operations are inherently slower
- **Mitigation**: Use database analysis commands to minimize frequent queries
- **Monitoring**: Check database size regularly to prevent performance degradation

### Database Size Monitoring

```bash
# Check database file size
Get-Item "\\network-drive\shared\validation_history.db" | Select-Object Length

# Monitor growth over time
python -m udsv4_redcap_qc_validator datastore-status
```

## Troubleshooting

### Common Issues

#### Database Connection Problems

```bash
# Verify network path access
Test-Path "\\network-drive\shared\validation_history.db"

# Check environment variable
echo $env:VALIDATION_HISTORY_DB_PATH
```

#### Performance Issues

### Backup Database

```bash
Copy-Item "\\network-drive\shared\validation_history.db" "\\network-drive\shared\validation_history_backup.db"
```

### Database Size Monitoring

```bash
# Windows PowerShell
Get-Item "\\network-drive\shared\validation_history.db" | Select-Object Length, LastWriteTime

# Expected size growth: ~1-10MB per validation run
# Monitor monthly to prevent excessive growth
```

**Size Guidelines**:

- **Small**: < 100MB (excellent performance)
- **Medium**: 100MB - 1GB (good performance)
- **Large**: > 1GB (consider cleanup or archival)

### Database Cleanup

```bash
# Clean old records (older than 6 months)
python -m udsv4_redcap_qc_validator datastore-cleanup --months 6

# Or use custom date
python -m udsv4_redcap_qc_validator datastore-cleanup --before-date "2024-01-01"
```

## Security Considerations

### Network Drive Permissions

- Ensure proper read/write permissions for all team members
- Consider database file locking during concurrent access
- Implement regular backups to prevent data loss

### Data Privacy

- Database contains validation error information
- May include sensitive field names or data patterns
- Follow your organization's data handling policies

## Getting Help

If you encounter issues:

1. Check this README for common solutions
2. Verify network drive connectivity and permissions
3. Review database file permissions and access rights
4. Contact your system administrator for network drive issues
5. Check the application logs in the `logs/` directory

## Database Location

**Default Location**: Set via `VALIDATION_HISTORY_DB_PATH` environment variable

**Backup Location**: Same directory as main database with `_backup` suffix

**Network Path Format**:

- Windows: `\\server\share\path\validation_history.db`
- Linux/Mac: `/mnt/network-drive/path/validation_history.db`
