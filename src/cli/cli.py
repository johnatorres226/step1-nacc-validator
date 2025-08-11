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
        from pipeline.report_pipeline import get_datastore_path
        config_instance = get_config(force_reload=True)
        errors = config_instance.validate()
        status = {
            "valid": not errors,
            "errors": errors,
            "redcap_configured": bool(config_instance.api_token and config_instance.api_url),
            "output_path_exists": Path(config_instance.output_path).exists(),
            "json_rules_path_exists": Path(config_instance.json_rules_path).exists(),
            "datastore_exists": Path(get_datastore_path()).exists(),
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
            "datastore_exists": False,
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
    config_table.add_row(
        "Enhanced Datastore",
        "[CHECK] Available" if status['datastore_exists'] else "[WARNING] Available",
        "Error tracking, trend analysis (complete_events mode only)",
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
    help='Select the QC validation mode. Note: Datastore tracking only works with complete_events mode.',
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
@click.option('--disable-database', is_flag=True, help='Disable database tracking for this run (useful for testing).')
def run(
    mode: str,
    output_dir: str,
    events: List[str],
    ptid_list: List[str],
    include_qced: bool,
    user_initials: str,
    disable_database: bool,
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
    enable_database = (mode == 'complete_visits' and not disable_database)
    
    if enable_database:
        console.print("🗄️ [bold green]Database tracking enabled[/bold green] - validation data will be stored for analysis")
    elif disable_database and mode == 'complete_visits':
        console.print("🚫 [bold yellow]Database tracking disabled[/bold yellow] - running in test mode")
    elif mode != 'complete_visits':
        console.print("ℹ️ [bold blue]Database tracking not available[/bold blue] - only supported for complete_visits mode")

    # Display summary before running
    _display_run_summary(base_config)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task(description="", total=None)
            run_report_pipeline(config=base_config, enable_datastore=enable_database)

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


@cli.command()
@click.option('--instruments', '-i', multiple=True, help='Specific instruments to analyze.')
@click.option('--output-path', '-o', type=click.Path(), default='output', help='Output directory for analysis report.')
@click.option('--days-back', '-d', type=int, default=30, help='Number of days to look back for analysis.')
def datastore(instruments: tuple, output_path: str, days_back: int):
    """Generate datastore analysis report for error tracking and trends."""
    try:
        from pipeline.report_pipeline import generate_datastore_analysis
        from pipeline.config_manager import get_config
        
        config = get_config()
        
        # Use provided instruments or fall back to config
        instrument_list = list(instruments) if instruments else config.instruments
        
        if not instrument_list:
            console.print("[bold red]No instruments specified. Please provide instruments via -i or configure them in settings.[/bold red]")
            sys.exit(1)
        
        console.print(f"[bold blue]Generating datastore analysis for {len(instrument_list)} instruments...[/bold blue]")
        
        # Generate analysis
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task(description="Analyzing datastore...", total=None)
            analysis_file = generate_datastore_analysis(output_path, instrument_list)
        
        console.print(f"[bold green]Analysis complete![/bold green]")
        console.print(f"Report saved to: [cyan]{Path(analysis_file).resolve()}[/cyan]")
        
        # Display summary
        summary_table = Table(title="📈 Datastore Analysis Summary")
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="magenta")
        
        summary_table.add_row("Instruments Analyzed", str(len(instrument_list)))
        summary_table.add_row("Analysis Period", f"{days_back} days")
        summary_table.add_row("Report Location", str(Path(analysis_file).resolve()))
        
        console.print(summary_table)
        
    except Exception as e:
        logger.error(f"Error generating datastore analysis: {e}", exc_info=True)
        console.print(f"[bold red]Error generating analysis. See logs for details.[/bold red]")
        sys.exit(1)


@cli.command()
@click.option('--enable-datastore/--disable-datastore', default=True, help='Enable or disable datastore functionality.')
@click.option('--test-mode/--production-mode', default=False, help='Use test database instead of production database.')
@click.option('--mode', '-m', type=click.Choice(['custom', 'complete_instruments', 'complete_events'], case_sensitive=False), 
              default='complete_events', help='Validation mode (datastore only works with complete_events).')
@click.option('--instruments', '-i', multiple=True, help='Specific instruments to validate.')
@click.option('--events', '-e', multiple=True, help='Specific events to validate.')
@click.option('--output-path', '-o', type=click.Path(), default='output', help='Output directory.')
@click.option('--user-initials', '-u', type=str, help='User initials for the run.')
def run_enhanced(enable_datastore: bool, test_mode: bool, mode: str, instruments: tuple, events: tuple, 
                output_path: str, user_initials: str):
    """Run enhanced validation with datastore integration (complete_events mode only)."""
    try:
        from pipeline.report_pipeline import run_enhanced_report_pipeline
        from pipeline.config_manager import get_config
        
        config = get_config()
        
        # Update config with provided values
        if instruments:
            config.instruments = list(instruments)
        if events:
            config.events = list(events)
        if output_path:
            config.output_path = output_path
        if user_initials:
            config.user_initials = user_initials.strip().upper()[:3]
        
        config.mode = mode
        config.test_mode = test_mode  # Set test mode in config
        
        # Validate config
        errors = config.validate()
        if errors:
            console.print(f"[bold red]Configuration errors:[/bold red]")
            for error in errors:
                console.print(f"  - {error}")
            sys.exit(1)
        
        # Show warning if datastore is enabled but mode is not complete_events
        if enable_datastore and mode != 'complete_events':
            console.print(f"[bold yellow]Warning: Datastore functionality is limited to complete_events mode.[/bold yellow]")
            console.print(f"[yellow]Current mode: {mode}. Datastore will be disabled.[/yellow]")
            enable_datastore = False
        
        # Display configuration
        mode_title = mode.replace('_', ' ').title()
        mode_suffix = " (TEST MODE)" if test_mode else ""
        table = Table(title=f"🚀 Enhanced QC Run Configuration (Mode: {mode_title}{mode_suffix})")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="magenta")
        
        table.add_row("Mode", mode_title)
        table.add_row("Test Mode", "Yes" if test_mode else "No")
        table.add_row("Datastore Enabled", "Yes" if enable_datastore else "No")
        table.add_row("Instruments", ", ".join(config.instruments) if config.instruments else "All")
        table.add_row("Events", ", ".join(config.events) if config.events else "All")
        table.add_row("Output Directory", str(Path(config.output_path).resolve()))
        table.add_row("User Initials", config.user_initials or "N/A")
        
        console.print(table)
        
        # Run enhanced pipeline
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task(description="Running enhanced validation...", total=None)
            run_enhanced_report_pipeline(config, enable_datastore)
        
        console.print(f"[bold green]Enhanced QC Run Complete![/bold green]")
        
        # Show enhanced output directory information
        event_type = mode.replace('_', ' ').title().replace(' ', '_')
        date_tag = datetime.now().strftime("%d%b%Y").upper()
        enhanced_dir_name = f"ENHANCED_QC_{event_type}_{date_tag}"
        enhanced_output_path = Path(config.output_path) / enhanced_dir_name
        
        console.print(f"Enhanced Results saved to: [cyan]{enhanced_output_path.resolve()}[/cyan]")
        
        if enable_datastore:
            console.print(f"[bold blue]Enhanced Datastore functionality enabled:[/bold blue]")
            console.print(f"  - Error comparison between runs")
            console.print(f"  - Trend analysis over time")
            console.print(f"  - Pattern detection for recurring issues")
            console.print(f"  - Enhanced summary report: ENHANCED_SUMMARY_{date_tag}.txt")
            console.print(f"  - Enhanced output files with error status")
        
    except Exception as e:
        logger.error(f"Error running enhanced validation: {e}", exc_info=True)
        console.print(f"[bold red]Error running enhanced validation. See logs for details.[/bold red]")
        sys.exit(1)


@cli.command()
@click.option('--instrument', '-i', required=True, help='Instrument name to analyze')
@click.option('--output-dir', '-o', help='Output directory for analysis report')
@click.option('--days-back', '-d', default=30, help='Number of days to analyze (default: 30)')
@click.option('--datastore-path', help='Path to datastore database file')
def datastore_analysis(instrument: str, output_dir: str, days_back: int, datastore_path: str):
    """Generate datastore analysis report for error trends and patterns."""
    try:
        from pipeline.datastore import EnhancedDatastore
        from pipeline.report_pipeline import generate_datastore_analysis_report, get_datastore_path
        
        # Use default paths if not provided
        if not output_dir:
            output_dir = "output"
        if not datastore_path:
            datastore_path = get_datastore_path()
        
        # Check if datastore exists
        if not Path(datastore_path).exists():
            console.print(f"[bold red]Datastore not found at: {datastore_path}[/bold red]")
            console.print("Run some complete_events validations first to populate the datastore.")
            sys.exit(1)
        
        console.print(f"[bold green]Generating datastore analysis for {instrument}...[/bold green]")
        
        # Generate analysis report
        report_path = generate_datastore_analysis_report(
            instrument=instrument,
            output_path=output_dir,
            datastore_path=datastore_path
        )
        
        console.print(f"[bold green]Analysis complete![/bold green]")
        console.print(f"Report saved to: [cyan]{Path(report_path).resolve()}[/cyan]")
        
        # Display summary
        datastore = EnhancedDatastore(datastore_path)
        dashboard = datastore.generate_quality_dashboard(instrument)
        
        summary_table = Table(title=f"📊 Datastore Analysis Summary: {instrument}")
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="magenta")
        
        summary = dashboard['summary']
        summary_table.add_row("Error Rate Trend", summary['error_rate_trend'])
        summary_table.add_row("Current Error Rate", f"{summary['current_error_rate']:.2f}%")
        summary_table.add_row("Average Error Rate", f"{summary['average_error_rate']:.2f}%")
        summary_table.add_row("Total Historical Runs", str(summary['total_historical_runs']))
        
        patterns = dashboard['patterns']
        summary_table.add_row("Repeated Patterns", str(patterns['repeated_patterns']))
        summary_table.add_row("Error Clusters", str(patterns['error_clusters']))
        summary_table.add_row("Systematic Issues", str(patterns['systematic_issues']))
        
        console.print(summary_table)
        
    except Exception as e:
        logger.error(f"Error generating datastore analysis: {e}", exc_info=True)
        console.print(f"[bold red]Failed to generate analysis. See logs for details.[/bold red]")
        sys.exit(1)


@cli.command()
@click.option('--datastore-path', help='Path to datastore database file')
def datastore_status(datastore_path: str):
    """Show datastore status and available instruments."""
    try:
        from pipeline.datastore import EnhancedDatastore
        from pipeline.report_pipeline import get_datastore_path
        
        if not datastore_path:
            datastore_path = get_datastore_path()
        
        if not Path(datastore_path).exists():
            console.print(f"[bold red]Datastore not found at: {datastore_path}[/bold red]")
            console.print("The datastore will be created when you run your first complete_events validation.")
            return
        
        datastore = EnhancedDatastore(datastore_path)
        
        # Get instruments and run counts
        import sqlite3
        conn = sqlite3.connect(datastore_path)
        cursor = conn.execute('''
            SELECT instrument, COUNT(*) as run_count, 
                   MIN(timestamp) as first_run,
                   MAX(timestamp) as last_run
            FROM validation_runs
            GROUP BY instrument
            ORDER BY instrument
        ''')
        
        instruments = cursor.fetchall()
        conn.close()
        
        if not instruments:
            console.print("[bold yellow]Datastore is empty. Run some complete_events validations first.[/bold yellow]")
            return
        
        status_table = Table(title="📊 Datastore Status")
        status_table.add_column("Instrument", style="cyan")
        status_table.add_column("Total Runs", style="magenta")
        status_table.add_column("First Run", style="green")
        status_table.add_column("Last Run", style="green")
        
        for instrument, run_count, first_run, last_run in instruments:
            # Format timestamps
            first_run_str = datetime.fromisoformat(first_run).strftime('%Y-%m-%d %H:%M')
            last_run_str = datetime.fromisoformat(last_run).strftime('%Y-%m-%d %H:%M')
            
            status_table.add_row(instrument, str(run_count), first_run_str, last_run_str)
        
        console.print(status_table)
        
        console.print(f"\n[bold green]Datastore Location:[/bold green] {Path(datastore_path).resolve()}")
        console.print(f"[bold green]Total Instruments:[/bold green] {len(instruments)}")
        
    except Exception as e:
        logger.error(f"Error checking datastore status: {e}", exc_info=True)
        console.print(f"[bold red]Failed to check datastore status. See logs for details.[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    cli()
