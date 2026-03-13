#!/usr/bin/env python
"""Scrape NACC check classifications from REDCap survey pages.

Fetches check data from NACC's published IVP and FVP survey pages and
saves a lookup file for classifying validation errors as 'alert' or 'error'.

IMPORTANT: The NACC survey pages use client-side JavaScript rendering (DataTables).
This scraper attempts to parse server-rendered HTML but may not capture data if the
page is fully JS-rendered. In that case, manually export data from the NACC pages:

1. Visit https://redcap.naccdata.org/surveys/?__report=F3ED7TRJKCRWW4ET (IVP)
2. Visit https://redcap.naccdata.org/surveys/?__report=NPT99LJFXRWRAM7N (FVP)
3. Export CSV from each page (if available) or copy table data
4. Run this script with --from-csv <file.csv> to convert

Usage:
    python src/scrapper/scrape_nacc_checks.py [--force] [--from-csv FILE]

Options:
    --force         Overwrite existing file even if less than 30 days old
    --from-csv FILE Convert a manually exported CSV to the lookup JSON
"""

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import requests

# Survey URLs for each packet type
_SURVEY_URLS = {
    "IVP": "https://redcap.naccdata.org/surveys/?__report=F3ED7TRJKCRWW4ET",
    "FVP": "https://redcap.naccdata.org/surveys/?__report=NPT99LJFXRWRAM7N",
}

# Map packet labels to internal codes
_PACKET_LABEL_MAP = {
    "i - uds initial visit (new participants)": "I",
    "i4 - uds initial visit (existing participants)": "I4",
    "f - uds follow-up visit": "F",
    "m - uds milestone visit": "M",
}

# Output path relative to project root
_OUTPUT_PATH = Path(__file__).parents[2] / "config" / "nacc_check_classifications.json"

# Staleness threshold
_MAX_AGE_DAYS = 30


class _TableParser(HTMLParser):
    """Parse HTML table rows from NACC survey pages."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._current_row: list[str] = []
        self._current_cell: str = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._in_table = True
        elif tag == "tr" and self._in_table:
            self._in_row = True
            self._current_row = []
        elif tag in ("td", "th") and self._in_row:
            self._in_cell = True
            self._current_cell = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            self._in_table = False
        elif tag == "tr" and self._in_row:
            self._in_row = False
            if self._current_row:
                self.rows.append(self._current_row)
        elif tag in ("td", "th") and self._in_cell:
            self._in_cell = False
            self._current_row.append(self._current_cell.strip())

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell += data


def _extract_packet_code(packet_label: str) -> str:
    """Map packet label to internal packet code."""
    label_lc = packet_label.strip().lower()
    for pattern, code in _PACKET_LABEL_MAP.items():
        if label_lc.startswith(pattern.split(" - ")[0]):
            return code
    # Fallback: try to extract from label
    if "initial" in label_lc and "existing" in label_lc:
        return "I4"
    if "initial" in label_lc:
        return "I"
    if "follow" in label_lc:
        return "F"
    if "milestone" in label_lc:
        return "M"
    return "I"  # Default fallback


def _fetch_page(base_url: str, page: int) -> str:
    """Fetch a single page from the survey."""
    url = f"{base_url}&__page={page}" if page > 1 else base_url
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def _parse_rows(html: str) -> list[dict[str, Any]]:
    """Parse HTML table and extract check records."""
    parser = _TableParser()
    parser.feed(html)

    if len(parser.rows) < 2:
        return []

    # First row is headers, rest are data
    headers = [h.lower().strip() for h in parser.rows[0]]
    records = []

    for row in parser.rows[1:]:
        if len(row) < 6:
            continue

        # Map columns by index (based on known structure)
        # Column 0: check_code, 1: error_type, 2: form, 3: packet_label,
        # 4: variable, 5: check_category, 6: short_desc, 7: full_desc
        record = {
            "check_code": row[0].strip() if len(row) > 0 else "",
            "error_type": row[1].strip().lower() if len(row) > 1 else "error",
            "form": row[2].strip().lower() if len(row) > 2 else "",
            "packet_label": row[3].strip() if len(row) > 3 else "",
            "variable": row[4].strip().lower() if len(row) > 4 else "",
            "check_category": row[5].strip() if len(row) > 5 else "Conformity",
            "short_desc": row[6].strip() if len(row) > 6 else "",
            "full_desc": row[7].strip() if len(row) > 7 else "",
        }

        # Skip header rows that might appear on subsequent pages
        if record["check_code"].lower() in ("check_code", "check code", ""):
            continue

        # Derive packet code
        record["packet"] = _extract_packet_code(record["packet_label"])

        records.append(record)

    return records


def _scrape_survey(name: str, base_url: str) -> list[dict[str, Any]]:
    """Scrape all pages from a survey."""
    all_records: list[dict[str, Any]] = []
    page = 1
    max_pages = 20  # Safety limit

    print(f"Scraping {name} from {base_url}")

    while page <= max_pages:
        try:
            html = _fetch_page(base_url, page)
            records = _parse_rows(html)

            if not records:
                print(f"  Page {page}: no records (end of data)")
                break

            all_records.extend(records)
            print(f"  Page {page}: {len(records)} records")
            page += 1

        except requests.RequestException as e:
            print(f"  Page {page}: request failed - {e}")
            break

    return all_records


def _build_lookup(checks: list[dict[str, Any]]) -> dict[str, str]:
    """Build lookup dict from checks list."""
    lookup: dict[str, str] = {}
    for check in checks:
        # Key format: "{packet}|{form}|{variable}|{check_category}"
        key = f"{check['packet']}|{check['form']}|{check['variable']}|{check['check_category']}"
        lookup[key] = check["error_type"]
    return lookup


def _should_scrape(force: bool) -> bool:
    """Check if we should scrape based on file age."""
    if force:
        return True
    if not _OUTPUT_PATH.exists():
        return True

    # Check file age
    try:
        data = json.loads(_OUTPUT_PATH.read_text(encoding="utf-8"))
        scraped_at = data.get("_meta", {}).get("scraped_at", "")
        if not scraped_at:
            return True
        scraped_date = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
        age = datetime.now(scraped_date.tzinfo) - scraped_date
        if age > timedelta(days=_MAX_AGE_DAYS):
            print(f"Existing file is {age.days} days old (> {_MAX_AGE_DAYS}), refreshing...")
            return True
        print(f"Existing file is {age.days} days old (< {_MAX_AGE_DAYS}), skipping. Use --force to override.")
        return False
    except (json.JSONDecodeError, KeyError, ValueError):
        return True


def _import_from_csv(csv_path: Path) -> list[dict[str, Any]]:
    """Import check data from a manually exported CSV file.

    Expected CSV columns (case-insensitive):
        check_code, error_type, form, packet (or packet_label), variable,
        check_category, short_desc (optional), full_desc (optional)
    """
    records: list[dict[str, Any]] = []

    with csv_path.open(encoding="utf-8-sig") as f:  # utf-8-sig handles BOM
        reader = csv.DictReader(f)
        # Normalize headers to lowercase
        if reader.fieldnames:
            reader.fieldnames = [h.lower().strip() for h in reader.fieldnames]

        for row in reader:
            # Handle packet_label or packet column
            packet_label = row.get("packet_label", row.get("packet", ""))
            packet = _extract_packet_code(packet_label) if "uds" in packet_label.lower() else packet_label.upper()

            record = {
                "check_code": row.get("check_code", "").strip(),
                "error_type": row.get("error_type", "error").strip().lower(),
                "form": row.get("form", "").strip().lower(),
                "packet": packet,
                "variable": row.get("variable", "").strip().lower(),
                "check_category": row.get("check_category", "Conformity").strip(),
                "short_desc": row.get("short_desc", "").strip(),
                "full_desc": row.get("full_desc", "").strip(),
            }

            if record["check_code"] and record["variable"]:
                records.append(record)

    return records


def _write_output(all_checks: list[dict[str, Any]], source: str) -> int:
    """Write checks to output JSON file."""
    if not all_checks:
        print("ERROR: No checks to write.")
        return 1

    alert_count = sum(1 for c in all_checks if c["error_type"] == "alert")
    lookup = _build_lookup(all_checks)

    output = {
        "_meta": {
            "scraped_at": datetime.utcnow().isoformat() + "Z",
            "sources": {"manual_import": source} if "csv" in source.lower() else _SURVEY_URLS,
            "total_checks": len(all_checks),
            "alert_count": alert_count,
        },
        "checks": [
            {
                "check_code": c["check_code"],
                "error_type": c["error_type"],
                "packet": c["packet"],
                "form": c["form"],
                "variable": c["variable"],
                "check_category": c["check_category"],
                "short_desc": c.get("short_desc", ""),
                "full_desc": c.get("full_desc", ""),
            }
            for c in all_checks
        ],
        "lookup": lookup,
    }

    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nSummary:")
    print(f"  Total checks: {len(all_checks)}")
    print(f"  Alerts: {alert_count}")
    print(f"  Errors: {len(all_checks) - alert_count}")
    print(f"  Output: {_OUTPUT_PATH}")

    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Scrape NACC check classifications")
    parser.add_argument("--force", action="store_true", help="Force refresh even if file is recent")
    parser.add_argument("--from-csv", type=Path, metavar="FILE", help="Import from manually exported CSV")
    args = parser.parse_args()

    # CSV import mode
    if args.from_csv:
        if not args.from_csv.exists():
            print(f"ERROR: CSV file not found: {args.from_csv}")
            return 1
        print(f"Importing from CSV: {args.from_csv}")
        all_checks = _import_from_csv(args.from_csv)
        return _write_output(all_checks, str(args.from_csv))

    # Web scraping mode
    if not _should_scrape(args.force):
        return 0

    all_checks: list[dict[str, Any]] = []

    for name, url in _SURVEY_URLS.items():
        checks = _scrape_survey(name, url)
        all_checks.extend(checks)
        print(f"  Total from {name}: {len(checks)}")

    if not all_checks:
        print("ERROR: No checks scraped.")
        print("The NACC pages use client-side JavaScript rendering.")
        print("Please manually export the data and use: --from-csv <file.csv>")
        print("\nAlternatively, ensure config/nacc_check_classifications.json exists")
        print("with sample data. The pipeline will use 'error' as default for unmatched checks.")
        return 1

    return _write_output(all_checks, "web_scrape")


if __name__ == "__main__":
    sys.exit(main())
