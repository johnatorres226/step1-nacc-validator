"""
Environment validation for the ADRC Quality Control Interface.

Checks that all required dependencies, credentials, and paths are
properly configured before running the QC pipeline.
"""

import os
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .branding import UNM_CHERRY, UNM_LOBO_GRAY, UNM_SILVER, UNM_TURQUOISE


def check_environment(console: Console) -> bool:
    """Run environment checks and display results.

    Returns True if all critical checks pass.
    """
    checks: list[tuple[str, str, bool]] = []

    # 1. Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    checks.append(("Python", py_ver, sys.version_info >= (3, 11)))

    # 2. .env file
    from pipeline.config.config_manager import project_root

    env_path = project_root / ".env"
    checks.append((".env File", "Found" if env_path.exists() else "Missing", env_path.exists()))

    # 3. REDCap API credentials
    token = os.getenv("REDCAP_API_TOKEN", "")
    token_ok = bool(token)
    token_display = f"****{token[-4:]}" if len(token) > 4 else ("Set" if token else "Missing")
    checks.append(("API Token", token_display, token_ok))

    url = os.getenv("REDCAP_API_URL", "")
    url_ok = bool(url)
    url_display = url[:40] + "..." if len(url) > 40 else (url or "Missing")
    checks.append(("API URL", url_display, url_ok))

    # 4. Rule paths (I, I4, F packets)
    rule_paths = [
        ("I Rules", "JSON_RULES_PATH_I"),
        ("I4 Rules", "JSON_RULES_PATH_I4"),
        ("F Rules", "JSON_RULES_PATH_F"),
    ]
    for label, env_var in rule_paths:
        path = os.getenv(env_var, "")
        path_ok = bool(path) and Path(path).is_dir()
        display = Path(path).name if path else "Not set"
        checks.append((label, display, path_ok))

    # 5. Output directory
    out_path = os.getenv("OUTPUT_PATH", str(project_root / "output"))
    out_ok = Path(out_path).exists() or Path(out_path).parent.exists()
    checks.append(("Output Dir", Path(out_path).name, out_ok))

    # 6. Key packages
    for pkg_name in ("rich", "click", "pandas", "requests"):
        try:
            __import__(pkg_name)
            checks.append((pkg_name, "Installed", True))
        except ImportError:
            checks.append((pkg_name, "Missing", False))

    # Build results table
    all_ok = True
    table = Table(
        title="Environment Check",
        border_style=UNM_LOBO_GRAY,
        title_style=f"bold {UNM_TURQUOISE}",
        show_lines=False,
        padding=(0, 1),
    )
    table.add_column("Component", style=f"bold {UNM_SILVER}", min_width=12)
    table.add_column("Status", justify="center", min_width=3)
    table.add_column("Value", style=UNM_LOBO_GRAY, max_width=50)

    for name, detail, ok in checks:
        status = f"[green]✓[/]" if ok else f"[{UNM_CHERRY}]✗[/]"
        if not ok:
            all_ok = False
        table.add_row(name, status, detail)

    console.print(table)

    if all_ok:
        console.print(f"\n  [{UNM_TURQUOISE}]✓ All checks passed — ready to run.[/]\n")
    else:
        console.print(
            f"\n  [{UNM_CHERRY}]⚠ Some checks failed. Review your .env configuration.[/]\n"
        )

    return all_ok
