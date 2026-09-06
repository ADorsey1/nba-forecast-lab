"""NBA Forecast Lab analytical interface."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from html import escape
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nba_forecast.freshness import live_status, MARKET_MAX_AGE_DAYS
from nba_forecast.snapshots import SnapshotError, read_snapshot, resolve_snapshot
from nba_forecast.teams import EAST, WEST
from nba_forecast.team_colors import get_team_theme
from nba_forecast.lab_ui import render_lab

PAGES = [
    "Home",
    "Forecast",
    "Creative Lab",
    "Standings",
    "Rosters",
    "Recent Moves",
    "Methodology",
    "Diagnostics",
]
SEARCH_INDEX = {
    "Creative Lab": "Fantasy trades, signings, rotations, player development and scenario comparisons.",
    "Home": "League overview, current system snapshot, and league leaders.",
    "Forecast": "Projected wins, live context, uncertainty ranges, and team Model summary.",
    "Standings": "League-wide, East, and West projected seeds.",
    "Rosters": "Current player roster rows joined to injury context.",
    "Recent Moves": "Trades, signings, waives, releases, and transaction history.",
    "Methodology": "Feature construction, Ridge model, ensemble weights, and simulation math.",
    "Diagnostics": "Backtesting metrics, data provenance, contract checks, and limitations.",
}
NAV_LABELS = {"Recent Moves": "Moves", "Methodology": "Methods"}
UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")
CONTACT_URL = "https://github.com/ADorsey1/nba-forecast-lab/issues"
AUTO_RELOAD_MINUTES = 15


def load_outputs() -> dict:
    data_root = Path(os.environ.get("NBA_FORECAST_DATA_ROOT", ROOT / "data"))
    return read_snapshot(resolve_snapshot(data_root))


st.set_page_config(
    page_title="NBA Forecast Lab",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Space+Grotesk:wght@500;600;700&display=swap');
:root {
  --ink: #08131f;
  --surface: #102235;
  --surface-2: #153149;
  --surface-3: #1b3c57;
  --text: #f7f3ec;
  --muted: #b9c8d3;
  --orange: #ff7345;
  --orange-soft: #ffd1bf;
  --line: rgba(233, 242, 248, .18);
}
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background: radial-gradient(circle at 82% 4%, #1d4b68 0, transparent 32%), var(--ink); color: var(--text); }
.stApp, .stApp p, .stApp label, .stApp small, .stApp [data-testid="stMarkdownContainer"] { color: var(--text) !important; }
.stApp h1, .stApp h2, .stApp h3, .stApp h4 { font-family: 'Space Grotesk', sans-serif; color: var(--text) !important; letter-spacing: -.04em; }
.block-container { max-width: 1480px; padding: 1.2rem 3rem 5rem; }
[data-testid="stSidebar"] { display: none; }
.topbar { display:flex; align-items:center; gap:1rem; background:rgba(16,34,53,.94); border:1px solid var(--line); border-radius:18px; padding:.55rem .7rem; box-shadow:0 14px 35px rgba(0,0,0,.18); }
.brand-lockup { display:flex; align-items:center; gap:.7rem; min-width:0; padding:.1rem .15rem; }
.brand-mark-wrap { display:grid; place-items:center; width:2.5rem; height:2.5rem; flex:0 0 2.5rem; color:var(--team-display, var(--orange)); background:linear-gradient(145deg, var(--team-primary, #ff7345), var(--team-secondary, #153149)); border:1px solid rgba(255,255,255,.2); border-radius:13px; box-shadow:0 7px 16px rgba(0,0,0,.22); }
.brand-mark-wrap svg { width:1.8rem; height:1.8rem; }
.brand-copy { display:flex; flex-direction:column; gap:.04rem; min-width:0; }
.brand-name { font-family:'Space Grotesk', sans-serif; font-size:1.02rem; font-weight:700; letter-spacing:-.035em; white-space:nowrap; }
.brand-subtitle { color:var(--muted); font-size:.62rem; font-weight:700; letter-spacing:.13em; text-transform:uppercase; white-space:nowrap; }
.brand-status { display:inline-flex; align-items:center; gap:.35rem; margin-left:.15rem; padding:.3rem .5rem; border:1px solid var(--line); border-radius:999px; color:var(--muted); font-size:.63rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; white-space:nowrap; }
.brand-status-dot { width:.4rem; height:.4rem; border-radius:50%; background:#53d18a; box-shadow:0 0 0 .2rem rgba(83,209,138,.14); }
.brand-status.is-degraded .brand-status-dot { background:#f2bf62; box-shadow:0 0 0 .2rem rgba(242,191,98,.14); }
.st-key-desktop-navigation { display:block; }
.st-key-mobile-navigation { display:none; }
.st-key-desktop-tools { display:block; }
.st-key-desktop-navigation .stButton > button { min-height:2.65rem; padding:.25rem .35rem; font-size:.78rem; white-space:nowrap; }
.st-key-mobile-navigation .stButton > button { min-height:2.65rem; padding:.25rem .5rem; font-size:.9rem; }
.st-key-desktop-tools .stButton > button { min-height:2.65rem; padding:.25rem .5rem; font-size:.76rem; white-space:nowrap; }
.st-key-account-actions .stButton > button { min-height:2.65rem; padding:.25rem .5rem; font-size:.74rem; }
.st-key-topbar-row { position:sticky; top:3.4rem; z-index:100; padding:.45rem .55rem; background:var(--surface); border:1px solid var(--line); border-radius:18px; box-shadow:0 12px 28px rgba(0,0,0,.16); }
.auth-shell { max-width: 540px; margin: 8vh auto 1.25rem; padding: 2.2rem 2.3rem 1.4rem; background: linear-gradient(145deg, rgba(27,60,87,.98), rgba(16,34,53,.98)); border: 1px solid var(--line); border-radius: 20px; box-shadow: 0 20px 50px rgba(0,0,0,.24); }
.auth-shell h1 { margin: .45rem 0 .8rem; color: var(--text) !important; }
.auth-shell p { color: var(--muted) !important; line-height: 1.55; }
.auth-shell .auth-kicker { color: var(--orange) !important; font-size: .74rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }
.stApp [data-testid="stForm"] { max-width: 540px; margin: 0 auto; padding: 1.3rem 2.3rem 1.5rem; background: var(--surface); border: 1px solid var(--line); border-radius: 0 0 20px 20px; }
.last-updated { margin:.35rem 0 1rem; color:var(--muted); font-size:.78rem; letter-spacing:.02em; }
.last-updated strong { color:var(--text); }
.cookie-banner { position:fixed; left:auto; right:1.25rem; bottom:1.25rem; z-index:120; display:flex; align-items:center; justify-content:space-between; gap:.8rem; padding:.65rem .8rem; background:var(--surface); border:1px solid var(--line); border-radius:13px; box-shadow:0 14px 35px rgba(0,0,0,.3); }
.cookie-banner p { margin:0; color:var(--text) !important; font-size:.72rem; line-height:1.35; }
.st-key-cookie-banner-container { position:fixed; left:auto; right:1.25rem; bottom:1.25rem; z-index:120; width:min(420px, calc(100vw - 2.5rem)); display:grid; grid-template-columns:1fr auto; align-items:center; gap:.7rem; padding:.65rem .8rem; background:var(--surface); border:1px solid var(--line); border-radius:13px; box-shadow:0 14px 35px rgba(0,0,0,.3); }
.st-key-cookie-banner-container .cookie-banner { position:static; padding:0; background:transparent; border:0; box-shadow:none; }
.st-key-cookie-banner-container .stButton { margin:0; }
.skip-link { position:fixed; left:1rem; top:-4rem; z-index:150; padding:.7rem 1rem; background:var(--team-button); color:var(--team-button-text) !important; border-radius:0 0 10px 10px; font-weight:700; text-decoration:none; }
.skip-link:focus { top:0; }
.scroll-top, .floating-contact { position:fixed; right:1.25rem; z-index:110; display:inline-flex; align-items:center; justify-content:center; min-width:3rem; min-height:2.7rem; padding:.35rem .7rem; background:var(--surface); color:var(--text) !important; border:1px solid var(--line); border-radius:999px; box-shadow:0 10px 24px rgba(0,0,0,.24); text-decoration:none; font-size:.78rem; font-weight:700; }
.scroll-top { bottom:1.25rem; }
.floating-contact { bottom:4.5rem; background:var(--team-button); color:var(--team-button-text) !important; border-color:var(--team-button); }
.scroll-top:hover, .floating-contact:hover { transform:translateY(-2px); border-color:var(--team-display); }
#scroll-progress { position:fixed; left:0; top:0; z-index:200; width:0; height:4px; background:var(--team-display, var(--orange)); box-shadow:0 0 12px var(--team-display, var(--orange)); }
@keyframes nba-rise-in { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }
.hero, .card, .stat-card { animation:nba-rise-in .55s ease both; }
.card:hover, .stat-card:hover { transform:translateY(-3px); border-color:var(--team-display); box-shadow:0 18px 34px rgba(0,0,0,.25); transition:transform .2s ease, box-shadow .2s ease, border-color .2s ease; }
.stButton > button, .stSelectbox [data-baseweb="select"], .stTextInput input { transition:border-color .2s ease, box-shadow .2s ease, transform .2s ease; }
.stButton > button:hover { box-shadow:0 5px 14px rgba(0,0,0,.16); transform:translateY(-1px); }
.hero { padding: 3.3rem 0 1.8rem; }
.eyebrow, .section-label { color: var(--orange) !important; font-size: .74rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }
.hero h1 { font-size: clamp(2.8rem, 6vw, 5.3rem); line-height: .94; margin: .45rem 0 1.1rem; color: var(--text) !important; }
.hero p { max-width: 760px; color: var(--muted) !important; font-size: 1.08rem; line-height: 1.65; }
.hero-shell { display:grid; grid-template-columns:minmax(0, 1.35fr) minmax(280px, .65fr); gap:2rem; align-items:end; padding:1.4rem 0 1.4rem; }
.st-key-hero-shell { padding:1.4rem 0 1.4rem; }
.hero-shell .hero, .st-key-hero-shell .hero { padding:1.8rem 0 1.2rem; }
.hero-shell .hero h1, .st-key-hero-shell .hero h1 { font-size:clamp(2.6rem, 4.2vw, 4.15rem); }
.hero-panel { position:relative; overflow:hidden; min-height:245px; padding:1.35rem; background:linear-gradient(145deg, color-mix(in srgb, var(--team-primary) 30%, var(--surface-2)), var(--surface)); border:1px solid var(--line); border-radius:22px; box-shadow:0 18px 38px rgba(0,0,0,.2); }
.hero-panel::after { content:""; position:absolute; right:-3.2rem; bottom:-4rem; width:13rem; height:13rem; border:1px solid color-mix(in srgb, var(--team-display) 55%, transparent); border-radius:50%; opacity:.6; }
.hero-panel .panel-kicker { color:var(--team-display); font-size:.68rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase; }
.hero-panel h3 { margin:.9rem 0 .35rem; font-size:1.35rem; }
.hero-panel p { position:relative; z-index:1; color:var(--muted) !important; font-size:.83rem; line-height:1.5; }
.hero-panel .panel-value { position:relative; z-index:1; margin:.4rem 0 .85rem; font-family:'Space Grotesk', sans-serif; font-size:2.45rem; font-weight:700; letter-spacing:-.06em; }
.hero-panel .panel-meta { position:relative; z-index:1; display:flex; justify-content:space-between; gap:.5rem; padding-top:.75rem; border-top:1px solid var(--line); color:var(--muted); font-size:.72rem; }
.hero-actions, .st-key-hero-actions { display:flex; flex-wrap:wrap; gap:.65rem; margin:.2rem 0 1.1rem; }
.hero-actions .stButton, .st-key-hero-actions .stButton { margin:0; }
.hero-actions .stButton > button, .st-key-hero-actions .stButton > button { min-height:2.8rem; padding:.45rem .9rem; border-radius:999px; }
.section-heading { display:flex; align-items:end; justify-content:space-between; gap:1rem; margin:2.3rem 0 .8rem; }
.section-heading .section-label { margin:0; }
.section-heading .helper { max-width:520px; margin:0; text-align:right; }
.card { background: linear-gradient(145deg, rgba(27,60,87,.98), rgba(16,34,53,.98)); border: 1px solid var(--line); border-radius: 18px; padding: 1.25rem; min-height: 175px; box-shadow: 0 14px 30px rgba(0,0,0,.18); }
.card h3 { margin-top: .8rem; color: var(--text) !important; }
.card p { color: var(--muted) !important; line-height: 1.5; }
.tag { display:inline-block; background:var(--orange-soft); color:#6f2410 !important; border-radius:999px; padding:.25rem .6rem; font-size:.72rem; font-weight:700; }
.stat-card { position:relative; overflow:hidden; background:linear-gradient(145deg, var(--surface), color-mix(in srgb, var(--surface-2) 62%, var(--surface))); border:1px solid var(--line); border-radius:16px; padding:1rem 1.05rem; }
.stat-card::before { content:""; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--team-display, var(--orange)); }
.stat-label { color:var(--muted) !important; font-size:.76rem; text-transform:uppercase; letter-spacing:.08em; }
.stat-value { color:var(--text) !important; font-family:'Space Grotesk', sans-serif; font-size:1.65rem; font-weight:700; margin-top:.35rem; }
.helper { color:var(--muted) !important; font-size:.86rem; line-height:1.5; }
.stButton > button { background:var(--surface-2); color:var(--text) !important; border:1px solid var(--line); border-radius:10px; }
.stButton > button:hover { border-color:var(--orange); color:var(--text) !important; }
.stButton > button[kind="primary"] { background:var(--orange); color:var(--ink) !important; border-color:var(--orange); font-weight:700; }
.stButton > button[kind="primary"] p { color:var(--ink) !important; }
.stSelectbox label, .stRadio label, .stTextInput label { color:var(--muted) !important; }
.stApp input, .stApp textarea, .stApp [data-baseweb="select"] * { color:var(--text) !important; background-color:var(--surface-2) !important; }
.stApp [data-baseweb="popover"] { background:var(--surface) !important; }
.stApp [data-testid="stCaptionContainer"] { color:var(--muted) !important; }
.stApp [data-testid="stMetricValue"], .stApp [data-testid="stMetricValue"] *, .stApp [data-testid="stMetricLabel"], .stApp [data-testid="stMetricLabel"] * { color:var(--text) !important; }
.stApp [data-testid="stAlert"] { background:var(--surface-2); border:1px solid var(--line); }
.stApp [data-testid="stAlert"] p, .stApp [data-testid="stAlert"] div { color:var(--text) !important; }
.stApp [data-testid="stDataFrame"] { background:#f7f3ec; border-radius:12px; }
.stApp [data-testid="stDataFrame"] * { color:#142434 !important; }
.stApp [data-testid="stExpander"] { background:var(--surface); border:1px solid var(--line); }
div[data-testid="stPopover"] button { min-width: 88px; }
@media (max-width: 1280px) {
  .block-container { padding: .9rem 1.1rem 3rem; }
  .st-key-desktop-navigation { display:none; }
  .st-key-mobile-navigation { display:block; }
  .st-key-desktop-tools { display:none; }
  div[data-testid="column"]:has(.st-key-desktop-navigation-slot) { display:none; }
  div[data-testid="column"]:has(.st-key-desktop-tools) { display:none; }
  .st-key-account-actions { display:none; }
  div[data-testid="column"]:has(.st-key-account-actions) { display:none; }
  .cookie-banner { left:.7rem; right:.7rem; bottom:.7rem; align-items:flex-start; flex-direction:column; }
  .st-key-cookie-banner-container { left:auto; right:.7rem; bottom:.7rem; width:min(390px, calc(100vw - 1.4rem)); grid-template-columns:1fr auto; gap:.5rem; }
  .scroll-top { right:.7rem; bottom:.7rem; }
  .floating-contact { right:.7rem; bottom:4rem; }
  .hero { padding-top:2.4rem; }
}
@media (max-width: 1080px) {
  .hero-shell { grid-template-columns:1fr; gap:.3rem; }
  .st-key-hero-shell { padding-top:1rem; }
  .hero-panel { min-height:0; }
  .brand-status { display:none; }
}
@media (max-width: 600px) {
  .block-container { padding-left:.75rem; padding-right:.75rem; }
  .topbar { justify-content:center; }
  .hero h1 { font-size:clamp(2.55rem, 13vw, 4rem); }
  .hero p { font-size:1rem; }
  .hero-shell { padding-top:.6rem; }
  .st-key-hero-shell { padding-top:.6rem; }
  .hero-panel { padding:1.1rem; border-radius:17px; }
  .section-heading { display:block; }
  .section-heading .helper { margin-top:.35rem; text-align:left; }
  .st-key-cookie-banner-container { grid-template-columns:1fr; }
  .card { min-height:0; margin-bottom:.8rem; }
  .st-key-mobile-navigation .stButton > button { min-width:3.2rem; }
  .st-key-account-actions { display:none; }
  div[data-testid="column"]:has(.st-key-account-actions) { display:none; }
  .auth-shell { margin-top: 3vh; padding: 1.4rem 1.2rem 1rem; }
  .stApp [data-testid="stForm"] { padding: 1.1rem 1.2rem 1.25rem; }
}

/* Two-row navigation reserves space for branding at every viewport. */
.brand-copy { flex:0 0 auto; }
.brand-lockup { flex-wrap:wrap; }
.brand-mark-wrap { color:white; }
.st-key-topbar-row { position:relative; top:0; }
.st-key-desktop-navigation, .st-key-desktop-tools { display:block !important; }
.st-key-desktop-navigation [data-testid="stHorizontalBlock"] { flex-wrap:wrap; gap:.3rem; }
.st-key-desktop-navigation [data-testid="stColumn"] { min-width:85px; flex:1 1 85px; }
.st-key-desktop-navigation button { width:100%; }
.floating-contact, .scroll-top { display:none; }
.stApp a:focus-visible, .stApp button:focus-visible { outline:3px solid var(--team-display); outline-offset:3px; }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation:none !important; transition:none !important; } }
@media (max-width: 700px) { .st-key-topbar-row [data-testid="stColumn"] { min-width:0; } .brand-status { display:none; } }
@media (max-width: 700px) {
 .st-key-topbar-row > div:first-child > [data-testid="stHorizontalBlock"] { flex-wrap:wrap; }
 .st-key-topbar-row > div:first-child > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { flex:1 1 140px; min-width:140px; }
 .st-key-topbar-row > div:first-child > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child { flex-basis:100%; }
}
@media print {
  @page { margin: .65in; }
  body, .stApp, .stAppViewContainer, .main { background:#ffffff !important; color:#102a43 !important; }
  .st-key-topbar-row, .skip-link, .scroll-top, .floating-contact, #scroll-progress, .cookie-banner,
  [data-testid="stHeader"], [data-testid="stToolbar"], .stButton, [data-testid="stPopover"] { display:none !important; }
  .block-container { max-width:none !important; padding:0 !important; }
  .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp p, .stApp label, .stApp [data-testid="stMarkdownContainer"] { color:#102a43 !important; }
  .card, .stat-card, [data-testid="stDataFrame"] { background:#ffffff !important; border:1px solid #b8c7d3 !important; box-shadow:none !important; }
}
</style>
""",
    unsafe_allow_html=True,
)


# Public read-only dashboard: data refresh is a separate command, never a UI action.
try:
    data = load_outputs()
except SnapshotError:
    st.error("Forecast data is temporarily unavailable. Please try again later.")
    st.stop()

@st.fragment(run_every=60)
def check_new_snapshot():
    if st.session_state.get("page") == "Creative Lab":
        return
    data_root = Path(os.environ.get("NBA_FORECAST_DATA_ROOT", ROOT / "data"))
    try:
        if str(resolve_snapshot(data_root)) != data["snapshot_root"]:
            st.rerun(scope="app")
    except SnapshotError:
        pass

check_new_snapshot()

features = data["features"]
forecasts = data["forecasts"]
simulations = data["simulations"]
next_forecast = data["next_forecast"]
next_simulation = data["next_simulation"]
rosters = data["rosters"]
injuries = data["injuries"]
moves = data["moves"]
manifest = data["manifest"]
current_live_status = live_status(manifest, rosters)
refreshed_at = pd.to_datetime(manifest.get("fetched_at_utc"), errors="coerce", utc=True)
refresh_label = refreshed_at.strftime("%b %d, %Y") if pd.notna(refreshed_at) else "Awaiting snapshot"

if next_forecast.empty:
    st.error("No next-season forecast is available. Refresh the pipeline before opening the app.")
    st.stop()

if "holistic_predicted_wins" not in next_forecast.columns:
    next_forecast["holistic_predicted_wins"] = next_forecast["predicted_wins"]
if "independent_predicted_wins" not in next_forecast.columns:
    next_forecast["independent_predicted_wins"] = next_forecast["predicted_wins"]
if "roster_aware_predicted_wins" not in next_forecast.columns:
    next_forecast["roster_aware_predicted_wins"] = next_forecast["predicted_wins"]
for column in [
    "market_win_total",
    "live_roster_projection_wins",
    "live_injury_count",
    "live_roster_count",
    "live_active_roster_count",
    "live_injury_burden",
    "live_transactions_since_july",
    "live_schedule_source_available",
]:
    if column not in next_forecast.columns:
        next_forecast[column] = pd.NA

teams = sorted(next_forecast["team_abbr"].dropna().unique())
team_options = ["ALL"] + teams
st.session_state.setdefault("page", "Home")
st.session_state.setdefault("focus_team", st.session_state.get("team_focus", "ALL"))
st.session_state.setdefault("focus_team_widget", st.session_state["focus_team"])
if st.session_state["page"] not in PAGES:
    st.session_state["page"] = "Home"
if st.session_state["focus_team"] not in team_options:
    st.session_state["focus_team"] = "ALL"
if st.session_state["focus_team_widget"] not in team_options:
    st.session_state["focus_team_widget"] = st.session_state["focus_team"]
st.session_state.setdefault("dark_mode", True)
st.session_state.setdefault("site_search_query", "")
st.session_state.setdefault("site_search_desktop", st.session_state["site_search_query"])
st.session_state.setdefault("site_search_mobile", st.session_state["site_search_query"])
st.session_state.setdefault("dark_mode_desktop", st.session_state["dark_mode"])
st.session_state.setdefault("dark_mode_mobile", st.session_state["dark_mode"])


def go_to(page: str) -> None:
    st.session_state["page"] = page


def team_label(value: str) -> str:
    return "League-wide" if value == "ALL" else value


def persist_focus_team() -> None:
    st.session_state["focus_team"] = st.session_state["focus_team_widget"]


def sync_search(source_key: str) -> None:
    st.session_state["site_search_query"] = st.session_state.get(source_key, "")


def sync_dark_mode(source_key: str) -> None:
    st.session_state["dark_mode"] = bool(st.session_state.get(source_key, True))


def capture_utm_parameters() -> None:
    captured: dict[str, str] = {}
    for key in UTM_KEYS:
        value = st.query_params.get(key)
        if value:
            captured[key] = str(value)
    if captured:
        st.session_state["utm_params"] = captured


def render_search_results() -> None:
    query = str(st.session_state.get("site_search_query", "")).strip()
    if not query:
        return
    needle = query.casefold()
    matches = [(page_name, description) for page_name, description in SEARCH_INDEX.items() if needle in f"{page_name} {description}".casefold()]
    for team_code in teams:
        if needle in team_code.casefold():
            matches.append((team_code, f"Focus the workspace on the {team_code} forecast."))
    st.markdown(f'<div class="section-label">Search results for {escape(query)}</div>', unsafe_allow_html=True)
    if not matches:
        st.info("No pages, topics, or teams matched that search.")
        return
    for result_name, description in matches[:8]:
        result_col, action_col = st.columns([5, 1], vertical_alignment="center")
        with result_col:
            st.markdown(f"**{escape(result_name)}**  \n<span class=\"helper\">{escape(description)}</span>", unsafe_allow_html=True)
        with action_col:
            if st.button("Open", key=f"search_open_{result_name}", use_container_width=True):
                if result_name in PAGES:
                    go_to(result_name)
                elif result_name in teams:
                    st.session_state["focus_team"] = result_name
                    st.session_state["focus_team_widget"] = result_name
                st.session_state["site_search_query"] = ""
                st.rerun()


def dark_theme(theme: dict[str, str]) -> dict[str, str]:
    """Keep team accents while moving team-focused themes onto dark surfaces."""

    return {
        **theme,
        "background": "#08131f",
        "surface": "#102235",
        "surface_2": "#153149",
        "surface_3": "#1b3c57",
        "text": "#f7f3ec",
        "muted": "#b9c8d3",
        "line": "rgba(233, 242, 248, .18)",
        "display": "#" + "".join(f"{round(int(theme["primary"][i:i+2], 16) * .45 + 255 * .55):02x}" for i in (1, 3, 5)),
        "app_background": "radial-gradient(circle at 82% 4%, #1d4b68 0, transparent 32%), #08131f",
        "topbar_background": "rgba(16,34,53,.94)",
        "card_background": "linear-gradient(145deg, rgba(27,60,87,.98), rgba(16,34,53,.98))",
        "dataframe_background": "#f7f3ec",
        "dataframe_text": "#142434",
    }


capture_utm_parameters()
page = st.session_state["page"]
selected_team = None if st.session_state["focus_team"] == "ALL" else st.session_state["focus_team"]
east = EAST & set(teams)
west = WEST & set(teams)
dark_mode = bool(st.session_state["dark_mode"])
theme = get_team_theme(selected_team)
if dark_mode:
    theme = dark_theme(theme)
elif selected_team is None:
    theme = {
        **theme,
        "background": "#f3f7fa",
        "surface": "#ffffff",
        "surface_2": "#e7eef4",
        "surface_3": "#dce7ef",
        "text": "#102a43",
        "muted": "#516679",
        "line": "rgba(16, 42, 67, .18)",
        "app_background": "linear-gradient(135deg, #ffffff 0%, #edf4f8 70%, #dce7ef 100%)",
        "topbar_background": "rgba(255,255,255,.96)",
        "card_background": "linear-gradient(145deg, #ffffff, #e7eef4)",
        "dataframe_background": "#ffffff",
        "dataframe_text": "#102a43",
        "button": "#ff7345",
        "button_text": "#08131f",
        "soft_button": "#ffd1bf",
        "soft_button_text": "#6f2410",
        "display": "#d9572b",
        "display_text": "#ffffff",
    }
st.markdown(
    f"""
<style>
:root {{
  --ink: {theme["background"]};
  --surface: {theme["surface"]};
  --surface-2: {theme["surface_2"]};
  --surface-3: {theme["surface_3"]};
  --text: {theme["text"]};
  --muted: {theme["muted"]};
  --line: {theme["line"]};
  --orange: {theme["display"]};
  --orange-soft: {theme["soft_button"]};
  --orange-soft-text: {theme["soft_button_text"]};
  --team-primary: {theme["primary"]};
  --team-secondary: {theme["secondary"]};
  --team-accent: {theme["accent"]};
  --team-display: {theme["display"]};
  --team-display-text: {theme["display_text"]};
  --team-accent-text: {theme["accent_text"]};
  --team-button: {theme["button"]};
  --team-button-text: {theme["button_text"]};
  --dataframe-background: {theme["dataframe_background"]};
  --dataframe-text: {theme["dataframe_text"]};
}}
.stApp {{ background: {theme["app_background"]} !important; color:var(--text) !important; }}
.topbar {{ background:{theme["topbar_background"]} !important; border-color:var(--line) !important; }}
.card {{ background:{theme["card_background"]} !important; border-color:var(--line) !important; }}
.stApp [data-testid="stDataFrame"] {{ background:var(--dataframe-background) !important; }}
.stApp [data-testid="stDataFrame"] * {{ color:var(--dataframe-text) !important; }}
.brand-mark, .eyebrow, .section-label {{ color:var(--team-display) !important; }}
.stButton > button:hover {{ border-color:var(--team-display) !important; }}
.stButton > button[kind="primary"] {{ background:var(--team-button) !important; border-color:var(--team-button) !important; color:var(--team-button-text) !important; }}
.stButton > button[kind="primary"] p {{ color:var(--team-button-text) !important; }}
.tag {{ background:var(--orange-soft) !important; color:var(--orange-soft-text) !important; }}
</style>
""",
    unsafe_allow_html=True,
)


st.session_state["site_search_desktop"] = st.session_state.get("site_search_query", "")
st.session_state["site_search_mobile"] = st.session_state.get("site_search_query", "")
st.session_state["dark_mode_desktop"] = bool(st.session_state.get("dark_mode", True))
st.session_state["dark_mode_mobile"] = bool(st.session_state.get("dark_mode", True))

live_badge_class = "" if current_live_status == "Current" else " is-degraded"
live_badge_label = "Live" if current_live_status == "Current" else current_live_status

st.html(
    f"""
    <div id="app-top"></div>
    <a class="skip-link" href="#main-content">Skip to content</a>
    <a class="floating-contact" href="{CONTACT_URL}" target="_blank" rel="noreferrer">Feedback</a>
    <a class="scroll-top" href="#app-top" aria-label="Scroll to top">Top</a>
    <div id="scroll-progress" role="progressbar" aria-label="Page scroll progress"></div>
    <script>
    (() => {{
      const bar = document.getElementById("scroll-progress");
      if (!bar) return;
      const update = () => {{
        const max = document.documentElement.scrollHeight - window.innerHeight;
        const progress = max > 0 ? Math.min(100, Math.max(0, (window.scrollY / max) * 100)) : 0;
        bar.style.width = progress + "%";
      }};
      window.addEventListener("scroll", update, {{ passive: true }});
      window.addEventListener("resize", update);
      update();

    }})();
    </script>
    """,
    unsafe_allow_javascript=True,
)


with st.container(key="topbar-row"):
    brand_col, focus_col, tools_col = st.columns([3, 2, 1], gap="medium", vertical_alignment="center")
    with brand_col:
        st.markdown(f'''
        <div class="brand-lockup" aria-label="NBA Forecast Lab">
          <span class="brand-mark-wrap" aria-hidden="true">
            <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="5" y="5" width="54" height="54" rx="15" stroke="currentColor" stroke-width="3"/>
              <path d="M16 43L27 31L37 37L49 20" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M16 48H49" stroke="currentColor" stroke-width="3" stroke-linecap="round" opacity=".62"/>
              <circle cx="49" cy="20" r="4" fill="currentColor"/>
            </svg>
          </span>
          <span class="brand-copy">
            <span class="brand-name">NBA Forecast</span>
            <span class="brand-subtitle">Lab · 2026–27</span>
          </span>
          <span class="brand-status{live_badge_class}"><span class="brand-status-dot"></span>{escape(live_badge_label)}</span>
        </div>
        ''', unsafe_allow_html=True)
    with focus_col:
        st.selectbox("Focus team", team_options, format_func=team_label, key="focus_team_widget", on_change=persist_focus_team)
    with tools_col:
        with st.container(key="desktop-tools"):
            with st.popover("Tools", use_container_width=True):
                st.markdown("### Workspace tools")
                st.text_input("Search pages, topics, or teams", key="site_search_desktop", on_change=sync_search, args=("site_search_desktop",), placeholder="Try methodology or PHI")
                st.toggle("Dark mode", key="dark_mode_desktop", on_change=sync_dark_mode, args=("dark_mode_desktop",))
    with st.container(key="desktop-navigation"):
        nav_buttons = st.columns(len(PAGES), gap="small")
        for button_col, nav_page in zip(nav_buttons, PAGES):
            with button_col:
                if st.button(NAV_LABELS.get(nav_page, nav_page), key=f"top_nav_{nav_page}", type="primary" if st.session_state["page"] == nav_page else "secondary", use_container_width=True):
                    go_to(nav_page)
                    st.rerun()

st.html('<div id="main-content" tabindex="-1"></div>')

if current_live_status != "Current":
    st.warning(f"Live context: {current_live_status.lower()}. Updates older than 24 hours are marked stale; forecasts remain the last published snapshot.")

if pd.notna(refreshed_at):
    st.markdown(f'<div class="last-updated">Live context last updated <strong>{refreshed_at.strftime("%b %d, %Y at %I:%M %p UTC")}</strong></div>', unsafe_allow_html=True)

render_search_results()

def safe_float(row: pd.Series, key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    return default if pd.isna(value) else float(value)


def safe_int(row: pd.Series, key: str, default: int = 0) -> int:
    value = row.get(key, default)
    return default if pd.isna(value) else int(value)


def selected_row(frame: pd.DataFrame, team: str | None) -> pd.Series | None:
    if team is None or frame.empty or "team_abbr" not in frame.columns:
        return None
    rows = frame.loc[frame["team_abbr"].eq(team)]
    return rows.iloc[0] if not rows.empty else None


forecast = selected_row(forecasts, selected_team)
simulation = selected_row(simulations, selected_team)
team_features = selected_row(features, selected_team)
next_team = selected_row(next_forecast, selected_team)
future_simulation = selected_row(next_simulation, selected_team)


def rank_for_team(team: str) -> tuple[str, int]:
    conference_name = "East" if team in east else "West"
    conference = next_forecast[next_forecast.team_abbr.isin(east if team in east else west)].sort_values("holistic_predicted_wins", ascending=False).reset_index(drop=True)
    matches = conference.index[conference.team_abbr.eq(team)]
    return conference_name, int(matches[0] + 1) if len(matches) else 0


def metric_card(label: str, value: str) -> None:
    safe_label = escape(str(label))
    safe_value = escape(str(value))
    st.markdown(f'<div class="stat-card"><div class="stat-label">{safe_label}</div><div class="stat-value">{safe_value}</div></div>', unsafe_allow_html=True)


def league_metric_strip() -> None:
    top_team = next_forecast.sort_values("holistic_predicted_wins", ascending=False).iloc[0]
    mean_wins = next_forecast.holistic_predicted_wins.mean()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Teams modeled", f"{len(next_forecast)}")
    with c2:
        metric_card("League mean wins", f"{mean_wins:.1f}")
    with c3:
        metric_card("Current projection leader", str(top_team.team_abbr))
    with c4:
        metric_card("Live data status", current_live_status)


def team_metric_strip() -> None:
    if next_team is None or forecast is None:
        league_metric_strip()
        return
    conference_name, seed = rank_for_team(selected_team)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("2026-27 holistic wins", f"{safe_float(next_team, 'holistic_predicted_wins'):.1f}")
    with c2:
        metric_card(f"Projected {conference_name} rank", f"#{seed}")
    with c3:
        metric_card("2025-26 wins", f"{safe_float(forecast, 'target_wins'):.0f}")
    with c4:
        metric_card("Live injury burden", "Unavailable" if pd.isna(next_team.get("live_injury_burden")) else f"{safe_float(next_team, 'live_injury_burden'):.1f}")


def team_overview() -> str:
    if next_team is None:
        return "Select a team with the Focus team selector when you want a team-specific explanation. The league views remain fully usable without a selection."
    conference_name, rank = rank_for_team(selected_team)
    form = safe_float(next_team, "predicted_wins")
    roster = safe_float(next_team, "roster_aware_predicted_wins")
    rotation = safe_float(next_team, "live_roster_projection_wins")
    ensemble = safe_float(next_team, "holistic_predicted_wins")
    market = safe_float(next_team, "market_win_total", float("nan"))
    overview = f"{selected_team} projects to {ensemble:.1f} wins, ranking {rank}th in the {conference_name}. The independent historical model is {form:.1f} wins, while the roster-aware model is {roster:.1f}; the ensemble also incorporates a {market:.1f}-win market benchmark."
    if pd.isna(market):
        overview = f"{selected_team} projects to {ensemble:.1f} wins, ranking {rank} in the {conference_name}. Historical form is {form:.1f} wins. No market benchmark is available for this snapshot."
    elif form < market - 3:
        overview += f" The main discount versus the market is the historical form signal, which is {market - form:.1f} wins lower and reflects the team’s prior performance rather than the full offseason reset."
    elif form > market + 3:
        overview += f" The model is more optimistic than the market by {form - market:.1f} wins because recent team performance is stronger than the external benchmark."
    else:
        overview += " The historical and market signals are relatively close, so the ranking is not being driven by a single source."
    if abs(rotation - roster) > 3:
        overview += f" A separate live top-rotation calculation is {rotation:.1f} wins, so the roster model and the transparent minutes-weighted roster diagnostic are not interchangeable."
    injury_count = safe_int(next_team, "live_injury_count")
    burden = safe_float(next_team, "live_injury_burden")
    if burden > 0:
        overview += f" The live injury snapshot lists {injury_count} issue(s), with a weighted burden of {burden:.1f}; this is shown as risk context rather than an uncalibrated win penalty."
    movement_count = safe_int(next_team, "live_transactions_since_july")
    if movement_count > 0:
        overview += f" The team has {movement_count} recorded movement item(s) since July, reinforcing that roster continuity is an important uncertainty in this projection."
    return overview


def forecast_chart() -> None:
    chart_data = next_forecast[["team_abbr", "holistic_predicted_wins"]].copy().sort_values("holistic_predicted_wins")
    highlight = selected_team if selected_team is not None else "__none__"
    chart = alt.Chart(chart_data).mark_bar().encode(
        y=alt.Y("team_abbr:N", sort="-x", title=None),
        x=alt.X("holistic_predicted_wins:Q", title="Projected wins"),
        color=alt.condition(alt.datum.team_abbr == highlight, alt.value(theme["display"]), alt.value("#6e8798")),
        tooltip=[alt.Tooltip("team_abbr:N", title="Team"), alt.Tooltip("holistic_predicted_wins:Q", title="Wins", format=".1f")],
    ).properties(height=700)
    st.altair_chart(chart, width="stretch")


def standings_table(conference_choice: str | None = None) -> None:
    if conference_choice is None:
        display_frame = next_forecast.copy()
        display_frame["projected_rank"] = display_frame["holistic_predicted_wins"].rank(method="first", ascending=False).astype(int)
    else:
        conference_teams = east if conference_choice == "East" else west
        display_frame = next_forecast[next_forecast.team_abbr.isin(conference_teams)].sort_values("holistic_predicted_wins", ascending=False).reset_index(drop=True).copy()
        display_frame.insert(0, "projected_seed", display_frame.index + 1)
    columns = ["projected_seed" if conference_choice else "projected_rank", "team_abbr", "holistic_predicted_wins", "market_win_total", "predicted_wins", "live_roster_projection_wins", "live_injury_count"]
    display = display_frame[columns].rename(columns={
        "team_abbr": "team",
        "holistic_predicted_wins": "holistic wins",
        "market_win_total": "market prior",
        "predicted_wins": "historical form",
        "live_roster_projection_wins": "roster estimate",
        "live_injury_count": "injuries",
    })
    display = display.round({column: 1 for column in ["holistic wins", "market prior", "historical form", "roster estimate"] if column in display.columns})

    def highlight(row: pd.Series) -> list[str]:
        return [f"background-color: {theme['soft_button']}; color: {theme['soft_button_text']}; font-weight: 700" if selected_team and row["team"] == selected_team else "" for _ in row]

    st.dataframe(display.style.apply(highlight, axis=1), hide_index=True, width="stretch")


def normalized_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def roster_view() -> pd.DataFrame:
    if rosters.empty:
        return rosters
    view = rosters.copy()
    if not injuries.empty:
        injury_view = injuries[["team_abbr", "player_name", "injury_status", "estimated_return_date", "comment"]].copy()
        injury_view["name_key"] = injury_view["player_name"].map(normalized_name)
        injury_view = injury_view.drop(columns=["player_name"])
        view["name_key"] = view["player_name"].map(normalized_name)
        view = view.merge(injury_view.drop_duplicates(["team_abbr", "name_key"]), on=["team_abbr", "name_key"], how="left")
        view = view.drop(columns=["name_key"])
    else:
        view["injury_status"] = pd.NA
        view["estimated_return_date"] = pd.NA
        view["comment"] = pd.NA
    return view


if page == "Home":
    top_team = next_forecast.sort_values("holistic_predicted_wins", ascending=False).iloc[0]
    with st.container(key="hero-shell"):
        hero_copy, hero_status = st.columns([1.4, .6], gap="large", vertical_alignment="bottom")
        with hero_copy:
            st.markdown('<div class="hero"><div class="eyebrow">NBA 2026-27 / MODEL CONTROL ROOM</div><h1>Forecast the league.<br>Interrogate the assumptions.</h1><p>NBA Forecast Lab combines historical team performance, player-level production, game-log trends, and live roster context. Browse the league first, then focus on a team only when you need a deeper read.</p></div>', unsafe_allow_html=True)
        with hero_status:
            st.markdown(f'''
            <div class="hero-panel">
              <div class="panel-kicker">Published snapshot</div>
              <h3>League outlook</h3>
              <div class="panel-value">{escape(str(top_team.team_abbr))} <span style="font-size:1rem;letter-spacing:0;color:var(--muted)">leads the board</span></div>
              <p>The current leader sits at <strong>{float(top_team.holistic_predicted_wins):.1f} projected wins</strong> across the blended model.</p>
              <div class="panel-meta"><span>{escape(live_badge_label)} context</span><span>{escape(refresh_label)}</span></div>
            </div>
            ''', unsafe_allow_html=True)
    with st.container(key="hero-actions"):
        cta_forecast, cta_standings, cta_moves = st.columns([1, 1, 1], gap="small")
        with cta_forecast:
            if st.button("Open forecast →", key="home_cta_forecast", type="primary", use_container_width=True):
                go_to("Forecast")
                st.rerun()
        with cta_standings:
            if st.button("Compare standings", key="home_cta_standings", use_container_width=True):
                go_to("Standings")
                st.rerun()
        with cta_moves:
            if st.button("Track roster moves", key="home_cta_moves", use_container_width=True):
                go_to("Recent Moves")
                st.rerun()
    a, b, c = st.columns(3)
    with a:
        st.markdown('<div class="card"><span class="tag">Explore</span><h3>Forecast</h3><p>Compare projected wins and live context across every team. Use Focus team to set an optional team focus and highlight it in charts.</p></div>', unsafe_allow_html=True)
    with b:
        st.markdown('<div class="card"><span class="tag">Track</span><h3>Rosters & moves</h3><p>Inspect the current 30-team roster snapshot and the transaction ledger behind the live offseason context.</p></div>', unsafe_allow_html=True)
    with c:
        st.markdown('<div class="card"><span class=\"tag\">Understand</span><h3>Methodology & diagnostics</h3><p>Follow the feature construction, validation, uncertainty logic, and data limitations behind each output.</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-heading"><div class="section-label">Current system snapshot</div><p class="helper">A quick read of the published model and live context.</p></div>', unsafe_allow_html=True)
    if selected_team is None:
        league_metric_strip()
        st.markdown('<p class="helper">No team selected. Use Focus team to focus the workspace on a team.</p>', unsafe_allow_html=True)
    else:
        team_metric_strip()
        st.markdown(f'<p class="helper">Focused on {escape(selected_team)}. Change or clear the focus with the Focus team selector.</p>', unsafe_allow_html=True)
    st.markdown('<div class="section-heading"><div class="section-label">League leaders</div><p class="helper">The five highest blended projections in the current snapshot.</p></div>', unsafe_allow_html=True)
    leaders = next_forecast.sort_values("holistic_predicted_wins", ascending=False).head(5)[["team_abbr", "holistic_predicted_wins", "market_win_total"]].rename(columns={"team_abbr": "team", "holistic_predicted_wins": "projected wins", "market_win_total": "market prior"}).round(1)
    st.dataframe(leaders, hide_index=True, width="stretch")
    st.markdown('<div class="section-label">FAQ</div>', unsafe_allow_html=True)
    with st.expander("Why can the model differ from another projection?"):
        st.write("NBA Forecast Lab blends historical form, roster-aware talent, live context, and a dated market prior. Other systems may use different priors, projected minutes, injury assumptions, or schedule timing.")
    with st.expander("Does live injury context directly lower wins?"):
        st.write("The injury snapshot is shown as risk context and feeds the live rotation diagnostic. It is not silently converted into an uncalibrated win penalty.")
    with st.expander("How often should I refresh the forecast?"):
        st.write("Run the refresh script after meaningful transactions, injury updates, or schedule changes. The app displays the timestamp of the most recent live snapshot.")
    with st.expander("Can I use this as a betting recommendation?"):
        st.write("No. This is an analytical portfolio project. Forecast ranges and diagnostics communicate uncertainty rather than guarantee outcomes.")

elif page == "Creative Lab":
    render_lab(data, ROOT, selected_team)

elif page == "Forecast":
    st.markdown('<div class="eyebrow">FORECAST</div>', unsafe_allow_html=True)
    st.title(f"{selected_team + ' / ' if selected_team else ''}2026-27 outlook")
    st.caption("Forecasts are a published snapshot. Live context is timestamped separately.")
    if "market_source_date" in next_forecast.columns:
        dates = ", ".join(sorted(next_forecast.market_source_date.dropna().astype(str).unique()))
        sources = ", ".join(sorted(next_forecast.market_source.dropna().astype(str).unique())) if "market_source" in next_forecast else "Unknown source"
        st.caption(f"Market prior: {sources}; dated {dates}. Publication requires a matching season and a source date within {MARKET_MAX_AGE_DAYS} days.")
    else:
        st.warning("This bundled forecast predates market provenance tracking. Its market date and season were not validated by the new publication checks.")
    team_metric_strip()
    view = st.radio("Output", ["Predicted wins", "Live context"], horizontal=True, label_visibility="collapsed")
    if view == "Predicted wins":
        forecast_chart()
    else:
        live_chart_data = next_forecast[["team_abbr", "live_injury_burden"]].dropna(subset=["live_injury_burden"]).sort_values("live_injury_burden")
        highlight = selected_team if selected_team is not None else "__none__"
        live_chart = alt.Chart(live_chart_data).mark_bar().encode(
            y=alt.Y("team_abbr:N", sort="-x", title=None),
            x=alt.X("live_injury_burden:Q", title="Weighted burden"),
            color=alt.condition(alt.datum.team_abbr == highlight, alt.value(theme["display"]), alt.value("#6e8798")),
            tooltip=[alt.Tooltip("team_abbr:N", title="Team"), alt.Tooltip("live_injury_burden:Q", title="Burden", format=".1f")],
        ).properties(height=700)
        st.altair_chart(live_chart, width="stretch")
        cols = ["team_abbr", "live_roster_count", "live_active_roster_count", "live_injury_count", "live_injury_burden", "live_transactions_since_july", "live_schedule_source_available"]
        st.dataframe(next_forecast[cols].sort_values("live_injury_burden", ascending=False), hide_index=True, width="stretch")
    if selected_team is not None and next_team is not None:
        st.markdown('<div class="section-label">Selected team context</div>', unsafe_allow_html=True)
        left, right = st.columns(2)
        with left:
            st.dataframe(pd.DataFrame([{"independent model": safe_float(next_team, "independent_predicted_wins"), "roster-aware model": safe_float(next_team, "roster_aware_predicted_wins"), "live rotation": safe_float(next_team, "live_roster_projection_wins"), "market prior": next_team.get("market_win_total"), "ensemble": safe_float(next_team, "holistic_predicted_wins")}]).round(1), hide_index=True, width="stretch")
        with right:
            st.dataframe(pd.DataFrame([{"roster players": safe_int(next_team, "live_roster_count"), "injuries listed": next_team.get("live_injury_count"), "transactions since July": safe_int(next_team, "live_transactions_since_july"), "schedule provider": next_team.get("live_schedule_provider", "n/a")}]), hide_index=True, width="stretch")
        if future_simulation is not None:
            st.markdown('<div class="section-label">Future uncertainty</div>', unsafe_allow_html=True)
            st.write(f"The simulation centers {selected_team} at {safe_float(future_simulation, 'expected_wins'):.1f} wins, with a 10th-90th percentile scenario range of {safe_int(future_simulation, 'wins_p10')}-{safe_int(future_simulation, 'wins_p90')}. These ranges are not yet empirically calibrated.")
            if pd.notna(future_simulation.get("playoff_probability")):
                st.write(f"Simulated conference top-10 frequency: {safe_float(future_simulation, 'playoff_probability'):.1%}. This includes play-in positions and is not the probability of reaching the final playoff bracket.")
            elif pd.notna(future_simulation.get("playoff_proxy_probability")):
                st.write(f"Independent-win proxy: {safe_float(future_simulation, 'playoff_proxy_probability'):.1%} of runs reach 45 wins. This is not a conference qualification probability.")
            st.caption(str(future_simulation.get("simulation_note", "")))
        st.markdown('<div class="section-label">Model summary</div>', unsafe_allow_html=True)
        overview = team_overview()
        st.info(overview)
        st.caption("Copy-ready summary")
        st.code(overview, language="text")
    else:
        st.markdown('<div class="section-label">League view</div>', unsafe_allow_html=True)
        st.info("This is a league-wide view. Set a team focus with the Focus team selector to see a team-specific component breakdown, uncertainty range, and Model summary.")

elif page == "Standings":
    st.markdown('<div class="eyebrow">STANDINGS / LEAGUE TABLE</div>', unsafe_allow_html=True)
    st.title("Projected standings")
    st.caption("Choose a conference to view seeds, or keep the view league-wide to compare all 30 teams. The focused team is highlighted when one is selected.")
    conference_choice = st.radio("Conference", ["League-wide", "East", "West"], horizontal=True, label_visibility="collapsed")
    standings_table(None if conference_choice == "League-wide" else conference_choice)

elif page == "Rosters":
    st.markdown('<div class="eyebrow">LIVE ROSTERS / PLAYER CONTEXT</div>', unsafe_allow_html=True)
    st.title("Rosters")
    st.caption("Current roster rows are refreshed from the live NBA data pipeline and joined to the active injury snapshot where names and teams match.")
    roster_data = roster_view()
    roster_teams = ["All teams"] + teams
    default_roster = selected_team if selected_team in teams else "All teams"
    filter_col, position_col, status_col = st.columns(3)
    with filter_col:
        roster_team = st.selectbox("Team", roster_teams, index=roster_teams.index(default_roster))
    with position_col:
        positions = sorted({str(value) for value in roster_data.get("position", pd.Series(dtype=str)).dropna()})
        position = st.selectbox("Position", ["All positions"] + positions)
    with status_col:
        roster_statuses = sorted({str(value) for value in roster_data.get("roster_status", pd.Series(dtype=str)).dropna()})
        roster_status = st.selectbox("Roster status", ["All statuses"] + roster_statuses)
    filtered = roster_data.copy()
    if roster_team != "All teams":
        filtered = filtered[filtered.team_abbr.eq(roster_team)]
    if position != "All positions":
        filtered = filtered[filtered.position.eq(position)]
    if roster_status != "All statuses":
        filtered = filtered[filtered.roster_status.eq(roster_status)]
    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card("Players shown", f"{len(filtered)}")
    with c2:
        metric_card("Teams represented", f"{filtered.team_abbr.nunique() if not filtered.empty else 0}")
    with c3:
        metric_card("Injury rows joined", f"{filtered.injury_status.notna().sum() if 'injury_status' in filtered else 0}")
    display_columns = ["team_abbr", "player_name", "position", "roster_status", "injury_status", "estimated_return_date", "comment"]
    display = filtered[[column for column in display_columns if column in filtered.columns]].sort_values(["team_abbr", "player_name"])
    st.dataframe(display.rename(columns={"team_abbr": "team", "player_name": "player", "roster_status": "status", "injury_status": "injury", "estimated_return_date": "return", "comment": "injury note"}), hide_index=True, width="stretch", height=650)

elif page == "Recent Moves":
    st.markdown('<div class="eyebrow">TRANSACTION LEDGER / OFFSEASON CONTEXT</div>', unsafe_allow_html=True)
    st.title("Recent moves")
    refreshed_at = pd.to_datetime(manifest.get("fetched_at_utc"), errors="coerce", utc=True)
    refresh_note = f" Last live refresh: {refreshed_at.strftime('%b %d, %Y %I:%M %p UTC')}." if pd.notna(refreshed_at) else ""
    st.caption(f"Trades, signings, waives, releases, and other movement captured by the live transaction feed. The ledger is deduplicated across refreshes.{refresh_note}")
    moves_view = moves.copy()
    if moves_view.empty:
        st.warning("No transaction ledger is available yet. Run the live refresh to populate this page.")
    else:
        moves_view["transaction_date"] = pd.to_datetime(moves_view["transaction_date"], errors="coerce")
        moves_view = moves_view.sort_values(["transaction_date", "group_sort"], ascending=[False, False])
        latest_date = moves_view["transaction_date"].max()
        period_col, team_col, type_col = st.columns(3)
        with period_col:
            period = st.selectbox("Window", ["Since July 1", "Last 90 days", "All tracked"])
        with team_col:
            move_teams = ["All teams"] + teams
            move_team = st.selectbox("Team", move_teams, index=move_teams.index(selected_team) if selected_team in teams else 0)
        with type_col:
            move_types = ["All types"] + sorted({str(value) for value in moves_view.transaction_type.dropna()})
            move_type = st.selectbox("Move type", move_types)
        if period == "Since July 1":
            cutoff = pd.Timestamp(year=latest_date.year, month=7, day=1)
            moves_view = moves_view[moves_view.transaction_date >= cutoff]
        elif period == "Last 90 days":
            moves_view = moves_view[moves_view.transaction_date >= latest_date - pd.Timedelta(days=90)]
        if move_team != "All teams":
            moves_view = moves_view[moves_view.team_abbr.eq(move_team)]
        if move_type != "All types":
            moves_view = moves_view[moves_view.transaction_type.eq(move_type)]
        c1, c2, c3 = st.columns(3)
        with c1:
            metric_card("Moves shown", f"{len(moves_view)}")
        with c2:
            metric_card("Teams represented", f"{moves_view.team_abbr.nunique() if not moves_view.empty else 0}")
        with c3:
            metric_card("Latest source date", latest_date.strftime("%b %d, %Y"))
        display = moves_view[["transaction_date", "transaction_type", "team_abbr", "description"]].copy()
        display["transaction_date"] = display["transaction_date"].dt.strftime("%b %d, %Y")
        st.dataframe(display.rename(columns={"transaction_date": "date", "transaction_type": "type", "team_abbr": "team", "description": "description"}), hide_index=True, width="stretch", height=650)

elif page == "Methodology":
    st.markdown('<div class="eyebrow">METHODS / MODEL CARD</div>', unsafe_allow_html=True)
    st.title("What the system actually computes")
    st.write("The pipeline predicts next-season wins from information available before that season. For historical rows, season t-1 features predict season t wins. For the live 2026-27 run, the completed 2025-26 team season supplies the form estimate and the current roster supplies a player-talent estimate.")
    st.markdown("### Feature construction")
    st.latex(r"X_{t-1} = [W, ORtg, DRtg, NRtg, pace, player\\ production, game\\ trends]")
    st.write("Team aggregates come from historical team summaries. Player aggregates include minutes, points, plus-minus, efficiency, usage, and top-three player concentration. Game-log features include full-season and last-20-game net rating, offense, defense, pace, and win rate.")
    st.markdown("### Forecast model")
    st.latex(r"\\hat{W}_{t} = \\beta_0 + \\sum_j \\beta_j X_{t-1,j}")
    st.write("The production model is standardized Ridge regression. Regularization reduces coefficient instability when team, player, and game features overlap. Predictions are clipped to the valid 0-82 range.")
    st.markdown("### Live information and ensemble")
    st.info("The 25/25/50 blend is a chosen benchmark-informed weighting, not a demonstrated optimal weighting. Component backtests do not measure this final ensemble. Roster backtests use retrospective evidence.")
    st.latex(r"\\hat{W}_{holistic} = 0.25\\hat{W}_{form} + 0.25\\hat{W}_{roster} + 0.50\\hat{W}_{market}")
    st.write("The independent model uses prior team, player, and game-log features. The roster-aware model adds a transparent season-roster transition proxy built from player IDs, prior production, returning-player shares, incoming-player shares, and prior expected rotation strength. A separate live top-rotation calculation adjusts expected minutes for current injuries and is displayed as a diagnostic. The holistic forecast blends independent form, roster-aware model output, and a dated market prior with explicit weights. Current rosters, injury reports, transaction records, and the published schedule are timestamped alongside the forecast. The simulation uses game-level log5 probabilities, home court, and neutral fills for unresolved games.")

else:
    st.markdown('<div class="eyebrow">VALIDATION / FAILURE MODES</div>', unsafe_allow_html=True)
    st.title("Diagnostics before confidence")
    st.warning("The final market-weighted ensemble has no measured forward accuracy yet. The historical metrics below evaluate components, not the headline ensemble.")
    st.caption("Roster-aware results use retrospective season rosters. They are diagnostic comparisons, not a verified preseason backtest. Simulation ranges describe model scenarios and have not been calibrated against held-out seasons.")
    record = data.get("forecast_record", {})
    if record:
        st.caption(f"Forecast archived at {record.get('recorded_at_utc')}. Preseason evaluation eligible: {record.get('preseason_eligible', False)}.")
        if record.get("ineligibility_reasons"):
            st.info("; ".join(record["ineligibility_reasons"]))
    else:
        st.caption("This bundled snapshot has no forward publication record and cannot establish preseason ensemble accuracy.")
    metrics = data["metrics"]
    if metrics:
        a, b, c = st.columns(3)
        with a:
            metric_card("Backtest rows", f"{metrics.get('test_rows', 0):,}")
        with b:
            metric_card("Historical form MAE", f"{metrics.get('mae', 0):.2f} wins")
        with c:
            metric_card("Historical form RMSE", f"{metrics.get('rmse', 0):.2f} wins")
        d, e = st.columns(2)
        with d:
            metric_card("Retrospective roster MAE", f"{metrics.get('roster_aware_mae', 0):.2f} wins")
        with e:
            metric_card("Retrospective roster RMSE", f"{metrics.get('roster_aware_rmse', 0):.2f} wins")
    st.markdown("### Current limitations")
    st.warning("The live system now attaches current roster rows, injury context, transaction history, a roster-aware diagnostic, and a schedule-aware simulation. The remaining uncertainty is provider-dependent: the historical roster transition table is a season-level proxy rather than a complete historical transaction ledger, market priors are dated snapshots, player aging and lineup fit are not fully modeled, and Cup-dependent schedule games use neutral-opponent fills until official opponents are resolvable.")
    if manifest:
        st.markdown("### Data provenance")
        st.write(f"Live snapshot fetched: {manifest.get('fetched_at_utc', 'unknown')}")
        st.json(manifest.get("sources", {}))
    st.markdown("### Session campaign context")
    utm_params = st.session_state.get("utm_params", {})
    if utm_params:
        st.caption("UTM parameters are retained for this browser session only and are not sent to an analytics provider.")
        st.json(utm_params)
    else:
        st.caption("No UTM campaign parameters were present in the current URL.")
    quality_path = Path(data["snapshot_root"]) / "processed" / "data_quality_report.json"
    if quality_path.exists():
        quality = json.loads(quality_path.read_text(encoding="utf-8"))
        st.markdown("### Data contract")
        status = quality.get("status", "unknown").upper()
        st.write(f"Current artifact status: {status}. {quality.get('error_count', 0)} errors and {quality.get('warning_count', 0)} warnings.")
        checks = pd.DataFrame(quality.get("checks", []))
        if not checks.empty:
            quality_display = checks[["name", "status", "observed", "expected", "detail"]].astype(str)
            st.dataframe(quality_display, hide_index=True, width="stretch")
    st.markdown("### Next defensible upgrades")
    st.write("Backtest offseason roster changes across prior seasons, add aging and projected-minute curves, estimate lineup fit, and calibrate game-level probabilities. External projections should remain benchmarks rather than labels to copy.")
