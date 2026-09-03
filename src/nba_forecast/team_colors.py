"""Accessible NBA team colorways used by the analytical interface."""

from __future__ import annotations

from typing import Final


DEFAULT_THEME: Final[dict[str, str]] = {
    "primary": "#ff7345",
    "secondary": "#153149",
    "accent": "#ffd1bf",
}

TEAM_COLORS: Final[dict[str, dict[str, str]]] = {
    "ATL": {"primary": "#E03A3E", "secondary": "#C1D32F", "accent": "#F4AF23"},
    "BOS": {"primary": "#007A33", "secondary": "#BA9653", "accent": "#FFFFFF"},
    "BRK": {"primary": "#000000", "secondary": "#FFFFFF", "accent": "#707070"},
    "CHO": {"primary": "#1D1160", "secondary": "#00788C", "accent": "#A1A1A4"},
    "CHI": {"primary": "#CE1141", "secondary": "#000000", "accent": "#FFFFFF"},
    "CLE": {"primary": "#860038", "secondary": "#FDBB30", "accent": "#041E42"},
    "DAL": {"primary": "#00538C", "secondary": "#B8C4CA", "accent": "#002B5E"},
    "DEN": {"primary": "#0E2240", "secondary": "#FEC524", "accent": "#8B2131"},
    "DET": {"primary": "#C8102E", "secondary": "#1D42BA", "accent": "#BEC0C2"},
    "GSW": {"primary": "#1D428A", "secondary": "#FFC72C", "accent": "#FFFFFF"},
    "HOU": {"primary": "#CE1141", "secondary": "#000000", "accent": "#C4CED4"},
    "IND": {"primary": "#002D62", "secondary": "#FDBB30", "accent": "#BEC0C2"},
    "LAC": {"primary": "#C8102E", "secondary": "#1D428A", "accent": "#BEC0C2"},
    "LAL": {"primary": "#552583", "secondary": "#FDB927", "accent": "#FFFFFF"},
    "MEM": {"primary": "#5D76A9", "secondary": "#12173F", "accent": "#F5B335"},
    "MIA": {"primary": "#98002E", "secondary": "#F9A01B", "accent": "#000000"},
    "MIL": {"primary": "#00471B", "secondary": "#EEE1C6", "accent": "#0077C0"},
    "MIN": {"primary": "#0C2340", "secondary": "#236192", "accent": "#9EA2A2"},
    "NOP": {"primary": "#0C2340", "secondary": "#C8102E", "accent": "#85714D"},
    "NYK": {"primary": "#006BB6", "secondary": "#F58426", "accent": "#BEC0C2"},
    "OKC": {"primary": "#007AC1", "secondary": "#EF3B24", "accent": "#F9A01B"},
    "ORL": {"primary": "#0077C0", "secondary": "#C4CED4", "accent": "#000000"},
    "PHI": {"primary": "#006BB6", "secondary": "#ED174C", "accent": "#C4CED4"},
    "PHO": {"primary": "#1D1160", "secondary": "#E56020", "accent": "#63727A"},
    "POR": {"primary": "#E03A3E", "secondary": "#000000", "accent": "#FFFFFF"},
    "SAC": {"primary": "#5A2D81", "secondary": "#63727A", "accent": "#FFFFFF"},
    "SAS": {"primary": "#C4CED4", "secondary": "#000000", "accent": "#FFFFFF"},
    "TOR": {"primary": "#CE1141", "secondary": "#000000", "accent": "#A1A1A4"},
    "UTA": {"primary": "#002B5C", "secondary": "#F9A01B", "accent": "#78BE20"},
    "WAS": {"primary": "#002B5C", "secondary": "#E31837", "accent": "#FFFFFF"},
}


def _rgb(hex_color: str) -> tuple[float, float, float]:
    value = hex_color.lstrip("#")
    return tuple(int(value[index : index + 2], 16) / 255 for index in (0, 2, 4))


def _relative_luminance(hex_color: str) -> float:
    channels = []
    for channel in _rgb(hex_color):
        channels.append(channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast_ratio(first: str, second: str) -> float:
    light = max(_relative_luminance(first), _relative_luminance(second))
    dark = min(_relative_luminance(first), _relative_luminance(second))
    return (light + 0.05) / (dark + 0.05)


def _mix(first: str, second: str, second_weight: float) -> str:
    """Blend two colors for readable light-theme surfaces and highlights."""
    first_rgb = _rgb(first)
    second_rgb = _rgb(second)
    channels = [round((one * (1 - second_weight) + two * second_weight) * 255) for one, two in zip(first_rgb, second_rgb)]
    return "#" + "".join(f"{channel:02X}" for channel in channels)


def _readable_text(background: str) -> str:
    dark_text = "#08131f"
    light_text = "#ffffff"
    return dark_text if _contrast_ratio(background, dark_text) >= _contrast_ratio(background, light_text) else light_text


def _readable_display(colors: dict[str, str]) -> str:
    """Pick a team color that remains readable as text on a white surface."""
    for color in (colors["primary"], colors["secondary"], colors["accent"]):
        if _contrast_ratio(color, "#ffffff") >= 4.5:
            return color
    return "#102A43"


def get_team_theme(team_abbr: str | None) -> dict[str, str]:
    """Return a complete readable theme, falling back to the league default."""
    if not team_abbr or team_abbr not in TEAM_COLORS:
        return {
            **DEFAULT_THEME,
            "display": "#ff7345",
            "display_text": "#08131f",
            "primary_text": "#08131f",
            "accent_text": "#6f2410",
            "button": "#ff7345",
            "button_text": "#08131f",
            "soft_button": "#ffd1bf",
            "soft_button_text": "#6f2410",
            "background": "#08131f",
            "surface": "#102235",
            "surface_2": "#153149",
            "surface_3": "#1b3c57",
            "text": "#f7f3ec",
            "muted": "#b9c8d3",
            "line": "rgba(233, 242, 248, .18)",
            "app_background": "radial-gradient(circle at 82% 4%, #1d4b68 0, transparent 32%), var(--ink)",
            "topbar_background": "rgba(16,34,53,.94)",
            "card_background": "linear-gradient(145deg, rgba(27,60,87,.98), rgba(16,34,53,.98))",
            "dataframe_background": "#f7f3ec",
            "dataframe_text": "#142434",
        }

    colors = TEAM_COLORS[team_abbr]
    display = _readable_display(colors)
    button = next(
        color for color in (colors["secondary"], colors["primary"], colors["accent"])
        if _relative_luminance(color) < 0.9
    )
    surface_2 = _mix(colors["primary"], "#ffffff", 0.93)
    surface_3 = _mix(colors["secondary"], "#ffffff", 0.89)
    soft_button = _mix(button, "#ffffff", 0.78)
    return {
        **colors,
        "display": display,
        "primary_text": _readable_text(colors["primary"]),
        "accent_text": _readable_text(colors["accent"]),
        "display_text": _readable_text(display),
        "button": button,
        "button_text": _readable_text(button),
        "soft_button": soft_button,
        "soft_button_text": _readable_text(soft_button),
        "background": "#f8fafc",
        "surface": "#ffffff",
        "surface_2": surface_2,
        "surface_3": surface_3,
        "text": "#102a43",
        "muted": "#516679",
        "line": _mix(colors["primary"], "#ffffff", 0.72),
        "app_background": f"linear-gradient(135deg, #ffffff 0%, {surface_2} 70%, {surface_3} 100%)",
        "topbar_background": "rgba(255,255,255,.96)",
        "card_background": f"linear-gradient(145deg, #ffffff, {surface_2})",
        "dataframe_background": "#ffffff",
        "dataframe_text": "#102a43",
    }
