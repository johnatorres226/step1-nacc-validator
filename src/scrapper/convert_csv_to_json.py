#!/usr/bin/env python
"""Convert NACC quality check CSVs to JSON lookup format.

Reads IVP and FVP quality check CSVs from config/quality-check/ and
generates config/nacc_check_classifications.json.

Usage:
    python src/scrapper/convert_csv_to_json.py
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

# Paths
_CONFIG_DIR = Path(__file__).parents[2] / "config"
_QUALITY_CHECK_DIR = _CONFIG_DIR / "quality-check"
_OUTPUT_PATH = _CONFIG_DIR / "nacc_check_classifications.json"

# Map packet labels to internal codes
_PACKET_LABEL_MAP = {
    "i - uds initial visit (new participants)": "I",
    "i4 - uds initial visit (existing participants)": "I4",
    "f - uds follow-up visit": "F",
    "m - uds milestone visit": "M",
}


def _extract_packet_code(packet_label: str) -> str:
    """Map packet label to internal packet code."""
    label_lc = packet_label.strip().lower()
    
    # Check longer patterns first to avoid "i4" matching "i"
    # Sort by pattern length descending
    sorted_patterns = sorted(_PACKET_LABEL_MAP.items(), key=lambda x: -len(x[0]))
    for pattern, code in sorted_patterns:
        prefix = pattern.split(" - ")[0]
        if label_lc.startswith(prefix):
            return code
    
    # Fallback
    if "initial" in label_lc and "existing" in label_lc:
        return "I4"
    if "initial" in label_lc:
        return "I"
    if "follow" in label_lc:
        return "F"
    if "milestone" in label_lc:
        return "M"
    return ""


def _read_csv(csv_path: Path) -> list[dict[str, Any]]:
    """Read quality check CSV and convert to normalized records."""
    # Try different encodings
    for encoding in ["utf-8-sig", "utf-8", "cp1252", "latin-1"]:
        records = []  # Reset for each encoding attempt
        try:
            with csv_path.open(encoding=encoding) as f:
                reader = csv.DictReader(f)
                rows_read = 0
                
                for row in reader:
                    rows_read += 1
                    # Map CSV columns to internal names
                    error_type = row.get("Error Type", "").strip().lower()
                    packet_label = row.get("Packet", "").strip()
                    
                    # Skip rows with empty error_type or packet
                    if not error_type or not packet_label:
                        continue
                    
                    record = {
                        "check_code": row.get("Error Code", "").strip(),
                        "error_type": error_type,
                        "form": row.get("Form Name", "").strip().lower(),
                        "packet_label": packet_label,
                        "packet": _extract_packet_code(packet_label),
                        "variable": row.get("Variable Name", "").strip().lower(),
                        "check_category": row.get("Type of Check", "Conformity").strip(),
                        "short_desc": row.get("Name of the Test", "").strip(),
                        "full_desc": row.get("Full Test Description", "").strip(),
                    }
                    
                    if record["check_code"] and record["variable"] and record["packet"]:
                        records.append(record)
                
                print(f"  (Encoding: {encoding}, raw rows: {rows_read})")
                return records
        except UnicodeDecodeError:
            continue
    
    raise ValueError(f"Could not decode {csv_path} with any known encoding")



def _build_lookup(checks: list[dict[str, Any]]) -> dict[str, str]:
    """Build lookup dict from checks list."""
    lookup: dict[str, str] = {}
    for check in checks:
        # Key format: "{packet}|{form}|{variable}|{check_category}"
        key = f"{check['packet']}|{check['form']}|{check['variable']}|{check['check_category']}"
        lookup[key] = check["error_type"]
    return lookup


def main() -> int:
    """Convert CSVs to JSON."""
    all_checks: list[dict[str, Any]] = []
    sources: dict[str, str] = {}
    
    # Process each CSV file
    for csv_file in sorted(_QUALITY_CHECK_DIR.glob("*.csv")):
        print(f"Processing: {csv_file.name}")
        records = _read_csv(csv_file)
        all_checks.extend(records)
        sources[csv_file.stem] = str(csv_file)
        
        # Stats
        alerts = sum(1 for r in records if r["error_type"] == "alert")
        errors = sum(1 for r in records if r["error_type"] == "error")
        print(f"  Records: {len(records)} (alerts: {alerts}, errors: {errors})")
    
    if not all_checks:
        print("ERROR: No checks found in CSV files.")
        return 1
    
    # Build output
    alert_count = sum(1 for c in all_checks if c["error_type"] == "alert")
    lookup = _build_lookup(all_checks)
    
    output = {
        "_meta": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "sources": sources,
            "total_checks": len(all_checks),
            "alert_count": alert_count,
            "lookup_keys": len(lookup),
        },
        "checks": [
            {
                "check_code": c["check_code"],
                "error_type": c["error_type"],
                "packet": c["packet"],
                "form": c["form"],
                "variable": c["variable"],
                "check_category": c["check_category"],
                "short_desc": c["short_desc"],
                "full_desc": c["full_desc"],
            }
            for c in all_checks
        ],
        "lookup": lookup,
    }
    
    # Write output
    _OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    
    print(f"\n=== Summary ===")
    print(f"Total checks: {len(all_checks)}")
    print(f"Alerts: {alert_count}")
    print(f"Errors: {len(all_checks) - alert_count}")
    print(f"Unique lookup keys: {len(lookup)}")
    print(f"Output: {_OUTPUT_PATH}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
