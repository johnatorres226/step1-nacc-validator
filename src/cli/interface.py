"""
Interactive CLI interface for the ADRC Quality Control system.

Provides a REPL-style interface where users can run QC validation,
check environment status, view configuration, and review results —
all within a single session branded with UNM identity.
"""

from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from src.__version__ import __version__

from .branding import (
    UNM_CHERRY,
    UNM_LOBO_GRAY,
    UNM_SILVER,
    UNM_TURQUOISE,
    display_banner,
    display_separator,
)
from .env_check import display_status


# ─── Help Display ────────────────────────────────────────────────────────────


def display_help(console: Console) -> None:
    """Display available commands in a clean table."""
    table = Table(
        show_header=False,
        border_style=UNM_LOBO_GRAY,
        padding=(0, 2),
        show_edge=False,
    )
    table.add_column("Command", style=f"bold {UNM_TURQUOISE}", min_width=16)
    table.add_column("Description", style=UNM_SILVER)

    commands = [
        ("run", "Run QC validation (complete visits)"),
        ("run -dr", "Run with detailed reports"),
        ("run -dr -ps", "Run with detailed + passed rules log"),
        ("status", "View environment, config, and readiness"),
        ("help", "Show this command reference"),
        ("clear", "Clear screen and show banner"),
        ("exit", "Exit the interface"),
    ]

    for cmd, desc in commands:
        table.add_row(cmd, desc)

    console.print()
    console.print(f"  [bold {UNM_TURQUOISE}]Available Commands[/]")
    display_separator(console)
    console.print(table)
    console.print()


# ─── Interactive Loop ────────────────────────────────────────────────────────


def run_interactive(console: Console | None = None) -> None:
    """Launch the interactive ADRC Quality Control Interface.

    This is the main entry point for the REPL-style interface.
    Prompts for user initials, then enters a command loop.
    """
    if console is None:
        console = Console()

    # Show the banner
    console.print()
    display_banner(console, __version__)

    # Prompt for initials
    console.print()
    initials = Prompt.ask(
        f"  [{UNM_TURQUOISE}]Enter your initials[/]",
        console=console,
    )
    initials = initials.strip().upper()[:3]

    if not initials:
        console.print(f"  [{UNM_CHERRY}]Initials are required. Exiting.[/]\n")
        return

    console.print(
        f"  [{UNM_TURQUOISE}]✓[/] Session started for "
        f"[bold {UNM_CHERRY}]{initials}[/]"
    )
    console.print(
        f"  [{UNM_LOBO_GRAY}]Type 'help' for commands or 'exit' to quit.[/]\n"
    )

    # Command loop
    while True:
        try:
            raw = console.input(
                f"  [{UNM_CHERRY}]ADRC[/] [{UNM_TURQUOISE}]❯[/] "
            ).strip()

            if not raw:
                continue

            parts = raw.split()
            cmd = parts[0].lower()

            if cmd in ("exit", "quit", "q"):
                console.print(f"\n  [{UNM_LOBO_GRAY}]Goodbye, {initials}.[/]\n")
                break

            elif cmd == "help":
                display_help(console)

            elif cmd in ("status", "check", "config"):
                display_status(console)

            elif cmd == "clear":
                console.clear()
                display_banner(console, __version__)
                console.print()

            elif cmd == "run":
                flags = {p.lower() for p in parts[1:]}
                detailed = "-dr" in flags or "--detailed-run" in flags
                passed = "-ps" in flags or "--passed-rules" in flags
                _run_qc(console, initials, detailed=detailed, passed_rules=passed)

            else:
                console.print(f"  [{UNM_CHERRY}]Unknown command:[/] {raw}")
                console.print(
                    f"  [{UNM_LOBO_GRAY}]Type 'help' for available commands.[/]\n"
                )

        except KeyboardInterrupt:
            console.print(
                f"\n\n  [{UNM_LOBO_GRAY}]Interrupted. Goodbye, {initials}.[/]\n"
            )
            break
        except EOFError:
            break


# ─── QC Pipeline Execution ──────────────────────────────────────────────────


def _run_qc(
    console: Console,
    initials: str,
    *,
    detailed: bool = False,
    passed_rules: bool = False,
) -> None:
    """Execute the QC validation pipeline from the interactive interface."""
    if passed_rules and not detailed:
        console.print(f"  [{UNM_CHERRY}]--passed-rules requires --detailed-run.[/]")
        console.print(f"  [{UNM_LOBO_GRAY}]Use: run -dr -ps[/]\n")
        return

    # Describe the run
    mode_label = (
        "Detailed + Passed Rules"
        if passed_rules
        else "Detailed"
        if detailed
        else "Standard"
    )
    console.print()
    console.print(
        f"  [{UNM_TURQUOISE}]Starting QC Validation[/]  [{UNM_SILVER}]({mode_label})[/]"
    )
    console.print(
        f"  [{UNM_LOBO_GRAY}]Initials: {initials}  │  Mode: complete_visits[/]"
    )
    display_separator(console)

    try:
        from pipeline.config.config_manager import get_config
        from pipeline.logging.logging_config import setup_logging
        from pipeline.reports.report_pipeline import run_report_pipeline

        # Enable logging during the run so the user sees progress
        setup_logging(
            log_level="INFO",
            console_output=True,
            structured_logging=False,
            performance_tracking=True,
        )

        config = get_config(force_reload=True, skip_validation=True)
        errors = config.validate()
        if errors:
            console.print(f"\n  [{UNM_CHERRY}]Configuration errors:[/]")
            for err in errors:
                console.print(f"    [{UNM_CHERRY}]✗[/] [{UNM_SILVER}]{err}[/]")
            console.print(f"\n  [{UNM_LOBO_GRAY}]Run 'check' to diagnose.[/]\n")
            return

        # Apply runtime parameters
        config.user_initials = initials
        config.mode = "complete_visits"
        config.detailed_run = detailed
        config.passed_rules = passed_rules

        console.print()
        run_report_pipeline(config=config)

        console.print(f"\n  [{UNM_TURQUOISE}]✓ QC validation complete.[/]")
        console.print(
            f"  [{UNM_SILVER}]Results saved to: {Path(config.output_path).resolve()}[/]\n"
        )

    except SystemExit:
        console.print(
            f"\n  [{UNM_CHERRY}]Configuration invalid. Run 'check' to diagnose.[/]\n"
        )
    except Exception as e:
        console.print(f"\n  [{UNM_CHERRY}]Pipeline failed:[/] [{UNM_SILVER}]{e}[/]\n")
    finally:
        # Silence logging between interactive commands
        try:
            from pipeline.logging.logging_config import setup_logging

            setup_logging(log_level="CRITICAL", console_output=False)
        except Exception:
            pass
