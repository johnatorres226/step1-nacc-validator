"""
UNM ADRC Quality Control Interface — Branding and Visual Identity.

Uses University of New Mexico official brand colors and identity.
Reference: https://brand.unm.edu/brand-style/color-palette/index.html
"""

from rich.console import Console
from rich.panel import Panel

# ─── UNM Official Brand Colors ──────────────────────────────────────────────
# Reference: https://brand.unm.edu/brand-style/color-palette/index.html

# Primary Brand Colors
UNM_CHERRY = "#BA0C2F"
UNM_TURQUOISE = "#007A86"
UNM_SILVER = "#A7A8AA"
UNM_LOBO_GRAY = "#63666A"

# Secondary Brand Colors (accent use only)
UNM_HIGH_NOON = "#FFC600"
UNM_SANDIA_SUNSET = "#ED8B00"


def get_lobo_art() -> str:
    """Return the UNM Lobo ASCII art with Rich markup coloring.

    Front-facing Lobo (wolf) rendered in Unicode block characters.
    Body in Cherry, eyes in Turquoise for contrast.
    """
    c = UNM_CHERRY
    t = UNM_TURQUOISE
    return (
        f"[{c}]       ▄▀▀▄              ▄▀▀▄[/]\n"
        f"[{c}]      █    ▀▄   ▄▄▄▄   ▄▀    █[/]\n"
        f"[{c}]      █      ▀▀▀    ▀▀▀      █[/]\n"
        f"[{c}]      █    [/][bold {t}]●[/]"
        f"[{c}]            [/][bold {t}]●[/]"
        f"[{c}]    █[/]\n"
        f"[{c}]       █       ▄▄▄▄▄▄       █[/]\n"
        f"[{c}]        █      ▀    ▀      █[/]\n"
        f"[{c}]         ▀▄              ▄▀[/]\n"
        f"[{c}]           ▀▀▀▀▀▀▀▀▀▀▀▀▀▀[/]"
    )


def display_banner(console: Console, version: str) -> None:
    """Display the ADRC QC Interface banner with UNM branding."""
    lobo = get_lobo_art()

    title_block = (
        f"\n{lobo}\n\n"
        f"  [bold {UNM_TURQUOISE}]ADRC Quality Control Interface[/]"
        f"  [{UNM_SILVER}]v{version}[/]\n"
        f"  [{UNM_LOBO_GRAY}]By University of New Mexico SDCC Dev Team[/]\n"
        f"  [dim {UNM_SILVER}]NACC Alzheimer's Disease Research Center[/]"
    )

    panel = Panel(
        title_block,
        border_style=UNM_CHERRY,
        padding=(0, 2),
    )

    console.print(panel)


def display_separator(console: Console, width: int = 42) -> None:
    """Print a thin UNM-styled separator line."""
    console.print(f"  [{UNM_LOBO_GRAY}]{'─' * width}[/]")
