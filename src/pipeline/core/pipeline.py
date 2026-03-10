"""
QC pipeline execution.

Single entry point: ``run_pipeline(config)`` executes the full
fetch → load rules → prep → validate → export flow and returns
a plain dict with the results.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ..config.config_manager import QCConfig

logger = logging.getLogger(__name__)


def _build_rules_cache_from_pool(pool: Any, config: QCConfig) -> dict[str, dict]:
    """Build ``{instrument: {variable: rule_dict}}`` from pool.

    Uses namespace_to_instrument mapping to route rules from their source
    file namespace to the correct instrument.
    """
    from ..config.config_manager import namespace_to_instrument
    from ..io.rule_pool import NamespacedRulePool

    assert isinstance(pool, NamespacedRulePool)

    rules_cache: dict[str, dict] = {}
    all_rules = pool.get_all_rules()

    for var, entry in all_rules.items():
        inst = namespace_to_instrument.get(entry.namespace)
        if inst and inst in config.instruments:
            rules_cache.setdefault(inst, {})[var] = entry.rule
        else:
            logger.warning(
                "No instrument mapping for variable '%s' (namespace='%s')",
                var,
                entry.namespace,
            )

    return rules_cache


def run_pipeline(
    config: QCConfig,
    output_path: str | Path | None = None,
    date_tag: str | None = None,
    time_tag: str | None = None,
) -> dict[str, Any]:
    """Execute the full QC pipeline.

    Returns a dict with:
        output_dir      – Path to the run output folder
        errors_df       – DataFrame of validation errors
        logs_df         – DataFrame of validation logs
        records_fetched – int
        generated_files – list[Path]
        success         – bool
        execution_time  – float (seconds)
        error           – str | None
    """
    from ..core.data_processing import (
        build_variable_maps,
        prepare_instrument_data_cache,
        preprocess_cast_types,
    )
    from ..core.validation_utils import build_validation_log
    from ..io.reports import (
        export_data_fetched,
        export_error_report,
        export_json_tracking,
        export_validation_logs,
    )
    from ..reports.report_pipeline import validate_data
    from .fetcher import fetch_report_data

    pipeline_start = time.time()

    # --- Resolve date/time tags and output directory -----------------------
    now = datetime.now()
    date_tag = date_tag or now.strftime("%d%b%Y").upper()
    time_tag = time_tag or now.strftime("%H%M%S")

    run_type = config.mode.replace("_", " ").title().replace(" ", "")
    base = Path(output_path) if output_path else Path(config.output_path)
    output_dir = base / f"QC_{run_type}_{date_tag}_{time_tag}"
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Starting QC pipeline  —  %d instruments, mode=%s",
        len(config.instruments),
        config.mode,
    )
    logger.info("Output: %s", output_dir)

    try:
        # ── Stage 1: Data Fetch ───────────────────────────────────────────
        t0 = time.time()
        
        # Use report-based fetch (pre-filtered data from REDCap report)
        logger.info("Fetching data from REDCap report %s", config.report_id)
        data_df, records_fetched = fetch_report_data(config, output_dir, date_tag, time_tag)
            
        logger.info("Fetched %d records (%.1fs)", records_fetched, time.time() - t0)

        # ── Stage 2: Load Rules ───────────────────────────────────────────
        t0 = time.time()
        from ..io.rule_loader import clear_cache
        from ..io.rule_pool import get_pool

        # Clear packet isolation state and reset pool for fresh run
        clear_cache()

        pool = get_pool(config)

        # Determine which packets are in the data
        packets_in_data: set[str] = set()
        if not data_df.empty and "packet" in data_df.columns:
            valid_packets = {"I", "I4", "F"}
            packets_in_data = {
                p.upper() for p in data_df["packet"].dropna().unique()
                if p.upper() in valid_packets
            }

        # Load the first/primary packet to build the initial rules_cache
        # The per-record packet isolation in get_rules_for_record() will handle
        # dynamic rule switching during validation
        if len(packets_in_data) == 0:
            logger.warning("No valid packets in data — defaulting to packet I")
            packets_in_data = {"I"}

        # Sort to ensure deterministic first packet selection
        primary_packet = sorted(packets_in_data)[0]
        logger.info("Primary packet for rules cache: %s", primary_packet)

        if len(packets_in_data) > 1:
            logger.info(
                "Multiple packets in data: %s — per-record packet isolation "
                "will be used during validation",
                ", ".join(sorted(packets_in_data)),
            )

        try:
            pool.load_packet(primary_packet, config)
        except (FileNotFoundError, ValueError):
            logger.warning("No rules directory for packet %s", primary_packet)

        rules_cache = _build_rules_cache_from_pool(pool, config)

        variable_to_inst, inst_to_vars = build_variable_maps(config.instruments, rules_cache)
        logger.info(
            "Loaded rules for %d/%d instruments (%.1fs)",
            len(rules_cache),
            len(config.instruments),
            time.time() - t0,
        )

        # ── Stage 3: Data Preparation ─────────────────────────────────────
        t0 = time.time()

        instrument_cache: dict[str, pd.DataFrame] = {}
        if not data_df.empty:
            instrument_cache = prepare_instrument_data_cache(
                data_df,
                config.instruments,
                inst_to_vars,
                rules_cache,
                config.primary_key_field,
            )
        logger.info("Data preparation done (%.1fs)", time.time() - t0)

        # ── Stage 4: Validation ───────────────────────────────────────────
        t0 = time.time()
        all_errors: list[dict] = []
        all_logs: list[dict] = []
        all_passed: list[dict] = []
        status_parts: list[pd.DataFrame] = []

        for i, instrument in enumerate(config.instruments, 1):
            df_inst = instrument_cache.get(instrument, pd.DataFrame())
            if df_inst.empty:
                continue

            logger.info("Validating %s (%d/%d)", instrument, i, len(config.instruments))

            # Completeness logs
            build_validation_log(df_inst, instrument, config.primary_key_field)

            # Cast types then validate
            inst_rules = rules_cache.get(instrument, {})
            df_inst = preprocess_cast_types(df_inst, inst_rules)
            errors, logs, passed = validate_data(
                df_inst,
                inst_rules,
                instrument_name=instrument,
                primary_key_field=config.primary_key_field,
            )
            all_errors.extend(errors)
            all_logs.extend(logs)
            all_passed.extend(passed)

            rec = df_inst[[config.primary_key_field, "redcap_event_name"]].copy()
            rec["instrument_name"] = instrument
            status_parts.append(rec)

        errors_df = pd.DataFrame(all_errors) if all_errors else pd.DataFrame()
        logs_df = pd.DataFrame(all_logs) if all_logs else pd.DataFrame()
        all_records_df = (
            pd.concat(status_parts, ignore_index=True).drop_duplicates(
                subset=[config.primary_key_field, "redcap_event_name", "instrument_name"]
            )
            if status_parts
            else pd.DataFrame()
        )
        logger.info("Validation done: %d errors (%.1fs)", len(errors_df), time.time() - t0)

        # ── Stage 5: Export Reports ───────────────────────────────────────
        t0 = time.time()
        generated: list[Path] = []

        p = export_error_report(errors_df, output_dir, date_tag, time_tag)
        if p:
            generated.append(p)

        p = export_validation_logs(logs_df, output_dir, date_tag, time_tag)
        if p:
            generated.append(p)

        p = export_data_fetched(all_records_df, output_dir, date_tag, time_tag)
        if p:
            generated.append(p)

        upload_ready = getattr(config, "upload_ready_path", None)
        jp = export_json_tracking(
            df_all=all_records_df,
            df_errors=errors_df,
            output_dir=output_dir,
            date_tag=date_tag,
            time_tag=time_tag,
            user_initials=config.user_initials or "N/A",
            upload_ready_path=upload_ready,
        )
        generated.append(jp)
        logger.info("Exported %d report files (%.1fs)", len(generated), time.time() - t0)

        total = time.time() - pipeline_start
        logger.info("Pipeline complete (%.1fs)", total)

        return {
            "output_dir": output_dir,
            "errors_df": errors_df,
            "logs_df": logs_df,
            "records_fetched": records_fetched,
            "generated_files": generated,
            "success": True,
            "execution_time": total,
            "error": None,
        }

    except Exception as exc:
        total = time.time() - pipeline_start
        logger.exception("Pipeline failed: %s", exc)
        return {
            "output_dir": output_dir,
            "errors_df": pd.DataFrame(),
            "logs_df": pd.DataFrame(),
            "records_fetched": 0,
            "generated_files": [],
            "success": False,
            "execution_time": total,
            "error": str(exc),
        }
