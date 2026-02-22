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
    from ..core.validation_logging import build_detailed_validation_logs
    from ..core.visit_processing import build_complete_visits_df
    from ..io.reports import (
        export_data_fetched,
        export_error_report,
        export_json_tracking,
        export_validation_logs,
    )
    from ..reports.report_pipeline import validate_data
    from .fetcher import fetch_redcap_data

    pipeline_start = time.time()

    # --- Resolve date/time tags and output directory -----------------------
    now = datetime.now()
    date_tag = date_tag or now.strftime("%d%b%Y").upper()
    time_tag = time_tag or now.strftime("%H%M%S")

    run_type = config.mode.replace("_", " ").title().replace(" ", "")
    base = Path(output_path) if output_path else Path(config.output_path)
    output_dir = base / f"QC_{run_type}_{date_tag}_{time_tag}"
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting QC pipeline  —  %d instruments, mode=%s", len(config.instruments), config.mode)
    logger.info("Output: %s", output_dir)

    try:
        # ── Stage 1: Data Fetch ───────────────────────────────────────────
        t0 = time.time()
        data_df, records_fetched = fetch_redcap_data(config, output_dir, date_tag, time_tag)
        logger.info("Fetched %d records (%.1fs)", records_fetched, time.time() - t0)

        # ── Stage 2: Load Rules ───────────────────────────────────────────
        t0 = time.time()
        from ..io.rule_loader import load_rules_for_instrument

        rules_cache: dict[str, dict] = {}
        for instrument in config.instruments:
            rules = load_rules_for_instrument(instrument, config)
            if rules:
                rules_cache[instrument] = rules
            else:
                logger.warning("No rules for instrument %s", instrument)

        variable_to_inst, inst_to_vars = build_variable_maps(config.instruments, rules_cache)
        logger.info("Loaded rules for %d/%d instruments (%.1fs)", len(rules_cache), len(config.instruments), time.time() - t0)

        # ── Stage 3: Data Preparation ─────────────────────────────────────
        t0 = time.time()

        if config.mode == "complete_visits" and not data_df.empty:
            cv_df, cv_tuples = build_complete_visits_df(data_df, config.instruments)
            if not cv_df.empty:
                idx = data_df.set_index([config.primary_key_field, "redcap_event_name"]).index
                cv_idx = cv_df.set_index([config.primary_key_field, "redcap_event_name"]).index
                data_df = data_df[idx.isin(cv_idx)].copy()
                logger.info("Filtered to %d complete visits", len(cv_df))
            else:
                logger.warning("No complete visits found — nothing to validate")
                data_df = pd.DataFrame()

        instrument_cache: dict[str, pd.DataFrame] = {}
        if not data_df.empty:
            instrument_cache = prepare_instrument_data_cache(
                data_df, config.instruments, inst_to_vars, rules_cache, config.primary_key_field,
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
            detail_logs = build_detailed_validation_logs(df_inst, instrument, config.primary_key_field)

            # Cast types then validate
            inst_rules = rules_cache.get(instrument, {})
            df_inst = preprocess_cast_types(df_inst, inst_rules)
            errors, logs, passed = validate_data(
                df_inst, inst_rules, instrument_name=instrument, primary_key_field=config.primary_key_field,
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
