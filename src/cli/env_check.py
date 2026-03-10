"""
Unified status display for the ADRC Quality Control Interface.

Combines environment validation and configuration view into a single
'status' command. All config values come from config_manager.
"""

import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .branding import UNM_CHERRY, UNM_LOBO_GRAY, UNM_SILVER, UNM_TURQUOISE


def display_status(console: Console) -> bool:
    """Show environment + configuration status in one view.

    Returns True if all critical checks pass.
    """
    from pipeline.config.config_manager import QCConfig, project_root

    # Load config without exiting on errors
    try:
        config = QCConfig()  # fresh instance from env
    except Exception:
        console.print(f"  [{UNM_CHERRY}]Could not load configuration.[/]\n")
        return False

    errors = config.validate()
    all_ok = not errors

    # ── Environment Section ──────────────────────────────────────────────
    env_table = Table(
        title="Environment",
        border_style=UNM_LOBO_GRAY,
        title_style=f"bold {UNM_TURQUOISE}",
        show_lines=False,
        padding=(0, 1),
    )
    env_table.add_column("Component", style=f"bold {UNM_SILVER}", min_width=14)
    env_table.add_column("Status", justify="center", min_width=3)
    env_table.add_column("Value", style=UNM_LOBO_GRAY, max_width=50)

    # Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 11)
    env_table.add_row("Python", _icon(py_ok), py_ver)

    # .env file
    env_path = project_root / ".env"
    env_status = "Found" if env_path.exists() else "Missing"
    env_table.add_row(".env File", _icon(env_path.exists()), env_status)

    # Key packages
    for pkg in ("rich", "click", "pandas", "requests"):
        try:
            __import__(pkg)
            env_table.add_row(pkg, _icon(True), "Installed")
        except ImportError:
            env_table.add_row(pkg, _icon(False), "Missing")

    console.print()
    console.print(env_table)

    # ── Configuration Section ────────────────────────────────────────────
    cfg_table = Table(
        title="Configuration",
        border_style=UNM_LOBO_GRAY,
        title_style=f"bold {UNM_TURQUOISE}",
        show_lines=False,
        padding=(0, 1),
    )
    cfg_table.add_column("Setting", style=f"bold {UNM_SILVER}", min_width=14)
    cfg_table.add_column("Status", justify="center", min_width=3)
    cfg_table.add_column("Value", style=UNM_LOBO_GRAY, max_width=50)

    # API credentials
    token = config.api_token or ""
    token_display = f"****{token[-4:]}" if len(token) > 4 else ("Set" if token else "Missing")
    cfg_table.add_row("API Token", _icon(bool(token)), token_display)

    url = config.api_url or ""
    url_display = url[:40] + "..." if len(url) > 40 else (url or "Missing")
    cfg_table.add_row("API URL", _icon(bool(url)), url_display)

    # Rule paths
    rule_entries = [
        ("I Rules", config.json_rules_path_i),
        ("I4 Rules", config.json_rules_path_i4),
        ("F Rules", config.json_rules_path_f),
    ]
    for label, path in rule_entries:
        ok = bool(path) and Path(path).is_dir()
        display = Path(path).name if path else "Not set"
        cfg_table.add_row(label, _icon(ok), display)

    # Output directory
    out_ok = bool(config.output_path) and (
        Path(config.output_path).exists() or Path(config.output_path).parent.exists()
    )
    output_display = Path(config.output_path).name if config.output_path else "N/A"
    cfg_table.add_row("Output Dir", _icon(out_ok), output_display)

    # Pipeline settings
    cfg_table.add_row("Mode", _icon(True), config.mode or "N/A")
    cfg_table.add_row("Instruments", _icon(True), str(len(config.instruments)))
    cfg_table.add_row(
        "Events", _icon(True),
        ", ".join(config.events) if config.events else "All",
    )

    console.print(cfg_table)

    # ── Summary ──────────────────────────────────────────────────────────
    if all_ok:
        console.print(f"\n  [{UNM_TURQUOISE}]✓ All checks passed — ready to run.[/]\n")
    else:
        console.print(f"\n  [{UNM_CHERRY}]Issues found:[/]")
        for err in errors:
            console.print(f"    [{UNM_CHERRY}]✗[/] [{UNM_SILVER}]{err}[/]")
        console.print(f"\n  [{UNM_LOBO_GRAY}]Review your .env configuration.[/]\n")

    return all_ok


def _icon(ok: bool) -> str:
    """Return a styled check/cross icon."""
    return "[green]✓[/]" if ok else f"[{UNM_CHERRY}]✗[/]"
