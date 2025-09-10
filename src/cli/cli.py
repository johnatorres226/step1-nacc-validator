#!/usr/bin/env python3
"""
UDSv4 REDCap QC Validator - Enhanced Unified Command Line Interface

A professional command-line tool for running quality control validation
on UDSv4 REDCap data with comprehensive reporting and configuration management.
"""

import warnings
from pathlib import Path

import click
from rich.console import Console

from pipeline.config.config_manager import (
    QCConfig,
    get_config,
)
from pipeline.logging.logging_config import get_logger, setup_logging
from pipeline.reports.report_pipeline import operation_context, run_report_pipeline

# Initialize console and logger
console = Console()
logger = get_logger("cli")


@click.group(context_settings={"help_option_names": ["-h", "--help"]}, invoke_without_command=True)
@click.version_option(version="0.1.0")
@click.option("--log-level",
              type=click.Choice(["DEBUG",
                                 "INFO",
                                 "WARNING",
                                 "ERROR"],
                                case_sensitive=False),
              default="INFO",
              help="Set the logging level.",
              )
@click.option("--mode",
              "-m",
              type=click.Choice(["complete_visits",
                                 "all_incomplete_visits"],
                                case_sensitive=False),
              default="complete_visits",
              help="Select the QC validation mode. [default: complete_visits]",
              )
@click.option("--output-dir",
              type=click.Path(file_okay=False,
                              dir_okay=True,
                              writable=True,
                              resolve_path=True),
              help="Override the default output directory.",
              )
@click.option("--event", "events", multiple=True,
              help="Specify one or more events to run.")
@click.option("--ptid", "ptid_list", multiple=True,
              help="Specify one or more PTIDs to check.")
@click.option("--initials", "-i", "user_initials", required=False,
              help="User initials for reporting (3 characters max).")
@click.option("--log", "-l", is_flag=True,
              help="Show terminal logging during execution.")
@click.option("--detailed-run", "-dr", is_flag=True,
              help=("Generate detailed outputs including Validation_Logs, "
                    "Completed_Visits, Reports, and Generation_Summary files."))
@click.option("--passed-rules", "-ps", is_flag=True,
              help=("Generate comprehensive Rules Validation log for "
                    "diagnostic purposes (requires --detailed-run/-dr, "
                    "large file, slow generation)."))
@click.pass_context
def cli(
    ctx: click.Context,
    log_level: str,
    mode: str,
    output_dir: str,
    events: list[str],
    ptid_list: list[str],
    user_initials: str,
    log: bool,
    detailed_run: bool,
    passed_rules: bool,
) -> None:
    """UDSv4 REDCap QC Validator - A comprehensive CLI for data quality control.

    When invoked without a subcommand, the tool runs the QC pipeline. Use
    the `config` subcommand to inspect configuration.
    """
    # Minimal startup logging - detailed logging configured later
    setup_logging(log_level="ERROR")
    warnings.filterwarnings(
        "ignore",
        message=(
            "No validation schema is defined for the arguments of rule "
            "'compatibility'"))

    # If a subcommand was invoked, let Click handle it
    if ctx.invoked_subcommand:
        return

    # Otherwise, run the QC pipeline using the parameters provided
    # Validate that --passed-rules can only be used with --detailed-run
    if passed_rules and not detailed_run:
        _msg = (
            "The --passed-rules/-ps option requires --detailed-run/-dr to be enabled. "
            "Use: udsv4-qc -i INITIALS -dr -ps"
        )
        raise click.ClickException(_msg)

    # Ensure required initials are present for runs
    if not user_initials:
        _msg = "The --initials/-i option is required for runs."
        raise click.UsageError(_msg)

    # Configure logging properly using the logging_config module
    if log:
        setup_logging(
            log_level="INFO",
            console_output=True,
            structured_logging=False,
            performance_tracking=True
        )
    else:
        setup_logging(
            log_level="CRITICAL",
            console_output=False,
            structured_logging=False,
            performance_tracking=False
        )

    try:
        # Initialization and configuration validation
        base_config = get_config(force_reload=True)
        config_errors = base_config.validate()
        if config_errors:
            console.print("Configuration errors detected:")
            for error in config_errors:
                console.print(f"   → {error}")
            ctx.exit(1)

        # Update config with runtime parameters
        if output_dir:
            base_config.output_path = output_dir
        if events:
            base_config.events = list(events)
        if ptid_list:
            base_config.ptid_list = list(ptid_list)

        base_config.user_initials = user_initials.strip().upper()[:3]
        base_config.mode = mode
        base_config.detailed_run = detailed_run
        base_config.passed_rules = passed_rules

        if log:
            _display_run_summary(base_config)

        # Execute pipeline
        if log:
            with operation_context("qc_validation", f"Processing {mode} mode"):
                run_report_pipeline(config=base_config)
            logger.info("Results saved to: %s", Path(base_config.output_path).resolve())
            logger.info("QC validation pipeline complete")
        else:
            run_report_pipeline(config=base_config)

    except Exception as e:
        if log:
            logger.exception("QC validation pipeline failed")
            console.print("An error occurred. Check the logs above for details.")
        else:
            console.print(f"QC validation pipeline failed: {e}")
        ctx.exit(1)


@cli.command()
@click.option("--detailed", "-d", is_flag=True,
              help="Show detailed configuration.")
@click.option(
    "--json-output", is_flag=True, help="Output configuration as JSON.")
def config(detailed: bool, json_output: bool) -> None:
    """Displays the current configuration status and validates settings."""
    try:
        config_instance = get_config(force_reload=True)
        errors = config_instance.validate()
        status = {
            "valid": not errors,
            "errors": errors,
            "redcap_configured": bool(
                config_instance.api_token and config_instance.api_url),
            "output_path_exists": Path(config_instance.output_path).exists(),
            "packet_rules_configured": bool(
                config_instance.json_rules_path_i and
                config_instance.json_rules_path_i4 and
                config_instance.json_rules_path_f),
        }
    except SystemExit:
        # This happens if get_config fails validation internally
        # In this case, we can assume the config is invalid
        status = {
            "valid": False,
            "errors": [
                "Critical configuration error. "
                "Run with --detailed for more info."
            ],
            "redcap_configured": False,
            "output_path_exists": False,
            "packet_rules_configured": False,
        }

    if json_output:
        console.print_json(data=status)
        return

    if status["valid"]:
        console.print("UDSv4 QC Validator Status: Ready")
    else:
        console.print(
            "UDSv4 QC Validator Status: Configuration issues detected")

    console.print("\nSystem Configuration:")

    console.print(
        f"Overall System: {
            'Ready' if status['valid'] else 'Issues Found'}")
    if status["errors"]:
        console.print(f"  Issues: {len(status['errors'])}")

    console.print(
        f"REDCap API: {
            'Connected' if status['redcap_configured'] else 'Not Configured'}")
    console.print(
        f"Output Directory: {
            'Ready' if status['output_path_exists'] else 'Will be created'}")
    console.print(
        f"Validation Rules: {
            'Configured' if status['packet_rules_configured'] else 'Missing'}")

    if detailed and "legacy_compatibility" in status:
        legacy_info = status["legacy_compatibility"]
        console.print("\nData Components:")
        console.print(
            f"Instruments: {
                legacy_info.get(
                    'instruments_count',
                    0)}")
        console.print(f"Events: {legacy_info.get('events_count', 0)}")
        console.print(f"JSON Mappings: {legacy_info.get('mapping_count', 0)}")

    if status["errors"]:
        console.print("\nConfiguration Issues:")
        for error in status["errors"]:
            console.print(f"  - {error}")



def _display_run_summary(config: QCConfig) -> None:
    """Displays a summary of the QC run configuration."""
    mode_title = config.mode.replace(
        "_", " ").title() if config.mode else "N/A"
    console.print(f"\nQC Run Configuration (Mode: {mode_title})")

    console.print(f"User Initials: {config.user_initials or 'N/A'}")
    console.print(f"Output Directory: {Path(config.output_path).resolve()}")
    console.print(f"Log Level: {config.log_level}")
    console.print(
        f"Events: {
            'All' if not config.events else ', '.join(
                config.events)}")
    console.print(
        f"Participants: {
            'All' if not config.ptid_list else ', '.join(
                config.ptid_list)}")

    console.print("")


if __name__ == "__main__":
    cli()
