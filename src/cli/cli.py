#!/usr/bin/env python3
"""
UDSv4 REDCap QC Validator - Enhanced Unified Command Line Interface

A professional command-line tool for running quality control validation
on UDSv4 REDCap data with comprehensive reporting and configuration management.
"""

import json
import sys
from pathlib import Path
from typing import List
import warnings
from datetime import datetime

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from pipeline.config_manager import (
    QCConfig,
    get_config,
)
from pipeline.logging_config import get_logger, setup_logging
from pipeline.report_pipeline import run_report_pipeline

# Initialize console and logger
console = Console()
logger = get_logger('cli')


@click.group(context_settings=dict(help_option_names=['-h', '--help']))
@click.version_option(version="1.0.0")
@click.option(
    '--log-level',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR'], case_sensitive=False),
    default='INFO',
    help='Set the logging level.',
)
def cli(log_level: str):
    """UDSv4 REDCap QC Validator - A comprehensive CLI for data quality control."""
    setup_logging(log_level=log_level.upper())
    logger.info(f"CLI started with log level: {log_level.upper()}")
    # Suppress the UserWarning from cerberus about the custom 'compatibility' rule
    warnings.filterwarnings("ignore", message="No validation schema is defined for the arguments of rule 'compatibility'")


@cli.command()
@click.option('--detailed', '-d', is_flag=True, help='Show detailed configuration.')
@click.option('--json-output', is_flag=True, help='Output configuration as JSON.')
def config(detailed: bool, json_output: bool):
    """Displays the current configuration status and validates settings."""
    try:
        config_instance = get_config(force_reload=True)
        errors = config_instance.validate()
        status = {
            "valid": not errors,
            "errors": errors,
            "redcap_configured": bool(config_instance.api_token and config_instance.api_url),
            "output_path_exists": Path(config_instance.output_path).exists(),
            "json_rules_path_exists": Path(config_instance.json_rules_path).exists(),
        }
    except SystemExit:
        # This happens if get_config fails validation internally
        # In this case, we can assume the config is invalid
        status = {
            "valid": False,
            "errors": ["Critical configuration error. Run with --detailed for more info."],
            "redcap_configured": False,
            "output_path_exists": False,
            "json_rules_path_exists": False,
        }


    if json_output:
        console.print_json(data=status)
        return

    panel_title = "[TARGET] UDSv4 QC Validator Status"
    if status['valid']:
        panel = Panel.fit("[CHECK] All systems ready for QC validation!",
                          title=panel_title, border_style="green")
    else:
        panel = Panel.fit("[WARNING] Configuration issues detected",
                          title=panel_title, border_style="yellow")
    console.print(panel)

    config_table = Table(title="System Configuration")
    config_table.add_column("Component", style="cyan", width=20)
    config_table.add_column("Status", width=15)
    config_table.add_column("Details", style="dim")

    config_table.add_row(
        "Overall System",
        "[CHECK] Ready" if status['valid'] else "[X] Issues Found",
        f"{len(status['errors'])} issues" if status['errors'] else "All components ready",
    )
    config_table.add_row(
        "REDCap API",
        "[CHECK] Connected" if status['redcap_configured'] else "[X] Not Configured",
        "API credentials found" if status['redcap_configured'] else "Check .env file",
    )
    config_table.add_row(
        "Output Directory",
        "[CHECK] Ready" if status['output_path_exists'] else "[WARNING] Will be created",
        f"Path: {get_config().output_path}",
    )
    config_table.add_row(
        "Validation Rules",
        "[CHECK] Loaded" if status['json_rules_path_exists'] else "[X] Missing",
        "JSON rules directory found" if status['json_rules_path_exists'] else "Check JSON_RULES_PATH",
    )
    console.print(config_table)

    if detailed and 'legacy_compatibility' in status:
        legacy_info = status['legacy_compatibility']
        data_table = Table(title="Data Components")
        data_table.add_column("Component", style="cyan")
        data_table.add_column("Count", style="green")
        data_table.add_row("Instruments", str(legacy_info.get('instruments_count', 0)))
        data_table.add_row("Events", str(legacy_info.get('events_count', 0)))
        data_table.add_row("JSON Mappings", str(legacy_info.get('mapping_count', 0)))
        console.print(data_table)

    if status['errors']:
        console.print("\n[red][WARNING] Configuration Issues:[/red]")
        for error in status['errors']:
            console.print(f"  [red]•[/red] {error}")


@cli.command()
@click.option(
    '--mode',
    required=True,
    type=click.Choice(['complete_visits', 'all_incomplete_visits', 'custom'], case_sensitive=False),
    help='Select the QC validation mode.',
)
@click.option(
    '--output-dir',
    type=click.Path(file_okay=False, dir_okay=True, writable=True, resolve_path=True),
    help='Override the default output directory.',
)
@click.option('--event', 'events', multiple=True, help='Specify one or more events to run.')
@click.option('--ptid', 'ptid_list', multiple=True, help='Specify one or more PTIDs to check.')
@click.option('--include-qced', is_flag=True, help='Include records that have already been QCed.')
@click.option('--initials', 'user_initials', help='User initials for reporting (3 characters max).')
def run(
    mode: str,
    output_dir: str,
    events: List[str],
    ptid_list: List[str],
    include_qced: bool,
    user_initials: str,
):
    """Runs the QC validation pipeline based on the selected mode."""
    logger.info(f"Running QC pipeline in '{mode}' mode.")

    # Get base configuration
    base_config = get_config(force_reload=True)

    # Validate configuration before proceeding
    config_errors = base_config.validate()
    if config_errors:
        console.print("[bold red]Configuration errors detected:[/bold red]")
        for error in config_errors:
            console.print(f"- {error}")
        return

    # Use provided initials or prompt if not provided
    if not user_initials:
        user_initials = click.prompt("Enter your initials for reporting", type=str)

    # Update config with runtime parameters
    if output_dir:
        base_config.output_path = output_dir
    if events:
        base_config.events = list(events)
    if ptid_list:
        base_config.ptid_list = list(ptid_list)
    
    base_config.user_initials = user_initials.strip().upper()[:3]
    base_config.mode = mode
    base_config.include_qced = include_qced

    # Determine database usage
    # Display summary before running
    _display_run_summary(base_config)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task(description="", total=None)
            run_report_pipeline(config=base_config)

        console.print(f"[bold green]QC Run Complete![/bold green]")
        console.print(f"Results saved to: [cyan]{Path(base_config.output_path).resolve()}[/cyan]")

    except Exception as e:
        logger.error(f"An unexpected error occurred during the QC run: {e}", exc_info=True)
        console.print(f"[bold red]An error occurred. See logs for details.[/bold red]")
        sys.exit(1)


def _display_run_summary(config: QCConfig):
    """Displays a summary of the QC run configuration."""
    mode_title = config.mode.replace('_', ' ').title() if config.mode else "N/A"
    table = Table(title=f"📊 QC Run Configuration (Mode: {mode_title})")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("User Initials", config.user_initials or "N/A")
    table.add_row("Output Directory", str(Path(config.output_path).resolve()))
    table.add_row("Log Level", config.log_level)
    table.add_row("Events", "All" if not config.events else ", ".join(config.events))
    table.add_row("Participants", "All" if not config.ptid_list else ", ".join(config.ptid_list))

    if config.mode == 'custom':
        table.add_row("Include Previously QCed", "Yes" if config.include_qced else "No")

    console.print(table)



if __name__ == "__main__":
    cli()
