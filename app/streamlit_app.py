"""NBA Forecast Lab analytical interface."""

from __future__ import annotations

import json
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

from nba_forecast.auth import (
    clear_auth_state,
    load_auth_config,
    login_is_allowed,
    mark_authenticated,
    record_failed_login,
    session_is_valid,
    verify_password,
)
from nba_forecast.team_colors import get_team_theme

PAGES = [
    "Home",
    "Forecast",
    "Standings",
    "Rosters",
    "Recent Moves",
    "Methodology",
    "Diagnostics",
]
EAST = {"ATL", "BOS", "BRK", "CHO", "CLE", "DET", "IND", "MIA", "MIL", "NYK", "ORL", "PHI", "TOR", "WAS"}


def load_outputs() -> dict[str, pd.DataFrame | dict]:
    processed = ROOT / "data" / "processed"
    live = ROOT / "data" / "raw" / "live"
    manifest_path = live / "source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    def read_csv(path: Path) -> pd.DataFrame:
        return pd.read_csv(path) if path.exists() else pd.DataFrame()

    return {
        "features": read_csv(processed / "team_model_features.csv"),
        "forecasts": read_csv(processed / "baseline_forecasts.csv"),
        "simulations": read_csv(processed / "simulation_summary.csv"),
        "next_forecast": read_csv(processed / "next_season_forecast.csv"),
        "next_simulation": read_csv(processed / "next_season_simulation.csv"),
        "rosters": read_csv(live / "current_rosters.csv"),
        "injuries": read_csv(live / "current_injuries.csv"),
        "moves": read_csv(live / "transaction_ledger.csv"),
        "manifest": manifest,
    }


st.set_page_config(
    page_title="NBA Forecast Lab",
    page_icon="N",
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
.block-container { max-width: 1440px; padding: 1.2rem 3rem 4rem; }
[data-testid="stSidebar"] { display: none; }
.topbar { display:flex; align-items:center; gap:1rem; background:rgba(16,34,53,.94); border:1px solid var(--line); border-radius:16px; padding:.7rem .9rem; box-shadow:0 14px 35px rgba(0,0,0,.18); }
.brand { font-family:'Space Grotesk', sans-serif; font-size:1.05rem; font-weight:700; letter-spacing:-.03em; white-space:nowrap; }
.brand-mark { color:var(--orange); }
.st-key-desktop-navigation { display:block; }
.st-key-mobile-navigation { display:none; }
.st-key-desktop-navigation .stButton > button { min-height:2.65rem; padding:.25rem .35rem; font-size:.78rem; white-space:nowrap; }
.st-key-mobile-navigation .stButton > button { min-height:2.65rem; padding:.25rem .5rem; font-size:.9rem; }
.st-key-account-actions .stButton > button { min-height:2.65rem; padding:.25rem .5rem; font-size:.74rem; }
.auth-shell { max-width: 540px; margin: 8vh auto 1.25rem; padding: 2.2rem 2.3rem 1.4rem; background: linear-gradient(145deg, rgba(27,60,87,.98), rgba(16,34,53,.98)); border: 1px solid var(--line); border-radius: 20px; box-shadow: 0 20px 50px rgba(0,0,0,.24); }
.auth-shell h1 { margin: .45rem 0 .8rem; color: var(--text) !important; }
.auth-shell p { color: var(--muted) !important; line-height: 1.55; }
.auth-shell .auth-kicker { color: var(--orange) !important; font-size: .74rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }
.stApp [data-testid="stForm"] { max-width: 540px; margin: 0 auto; padding: 1.3rem 2.3rem 1.5rem; background: var(--surface); border: 1px solid var(--line); border-radius: 0 0 20px 20px; }
.hero { padding: 3.3rem 0 1.8rem; }
.eyebrow, .section-label { color: var(--orange) !important; font-size: .74rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }
.hero h1 { font-size: clamp(2.8rem, 6vw, 5.3rem); line-height: .94; margin: .45rem 0 1.1rem; color: var(--text) !important; }
.hero p { max-width: 760px; color: var(--muted) !important; font-size: 1.08rem; line-height: 1.65; }
.card { background: linear-gradient(145deg, rgba(27,60,87,.98), rgba(16,34,53,.98)); border: 1px solid var(--line); border-radius: 18px; padding: 1.25rem; min-height: 175px; box-shadow: 0 14px 30px rgba(0,0,0,.18); }
.card h3 { margin-top: .8rem; color: var(--text) !important; }
.card p { color: var(--muted) !important; line-height: 1.5; }
.tag { display:inline-block; background:var(--orange-soft); color:#6f2410 !important; border-radius:999px; padding:.25rem .6rem; font-size:.72rem; font-weight:700; }
.stat-card { background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:1rem 1.05rem; }
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
  div[data-testid="column"]:has(.st-key-desktop-navigation-slot) { display:none; }
  .st-key-account-actions { display:none; }
  div[data-testid="column"]:has(.st-key-account-actions) { display:none; }
  .hero { padding-top:2.4rem; }
}
@media (max-width: 600px) {
  .block-container { padding-left:.75rem; padding-right:.75rem; }
  .topbar { justify-content:center; }
  .hero h1 { font-size:clamp(2.55rem, 13vw, 4rem); }
  .hero p { font-size:1rem; }
  .card { min-height:0; margin-bottom:.8rem; }
  .st-key-mobile-navigation .stButton > button { min-width:3.2rem; }
  .st-key-account-actions { display:none; }
  div[data-testid="column"]:has(.st-key-account-actions) { display:none; }
  .auth-shell { margin-top: 3vh; padding: 1.4rem 1.2rem 1rem; }
  .stApp [data-testid="stForm"] { padding: 1.1rem 1.2rem 1.25rem; }
}
</style>
""",
    unsafe_allow_html=True,
)


def render_auth_gate() -> None:
    config = load_auth_config()
    if config is None:
        st.markdown(
            '<div class="auth-shell"><div class="auth-kicker">Private workspace</div><h1>Sign in to NBA Forecast Lab</h1><p>This app requires an administrator-configured account. Credentials stay outside the repository and are never hardcoded into the forecast code.</p></div>',
            unsafe_allow_html=True,
        )
        st.error("Authentication is not configured for this environment.")
        st.markdown("Run the one-time setup command below, then reload the app:")
        st.code('& ".venv\\Scripts\\python.exe" scripts\\setup_auth.py', language="powershell")
        st.stop()

    now = time.time()
    if session_is_valid(st.session_state, config, now=now):
        return

    st.markdown(
        '<div class="auth-shell"><div class="auth-kicker">Private workspace</div><h1>Sign in to NBA Forecast Lab</h1><p>Use the workspace credentials configured by the administrator to access forecasts, live context, rosters, and diagnostics.</p></div>',
        unsafe_allow_html=True,
    )
    allowed, seconds_remaining = login_is_allowed(st.session_state, now=now)
    if not allowed:
        st.warning(f"Too many failed attempts. Try again in {seconds_remaining} seconds.")
        st.stop()

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", autocomplete="username")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)

    if submitted:
        normalized_username = username.strip()
        if normalized_username == config.username and verify_password(password, config.password_hash):
            mark_authenticated(st.session_state, normalized_username, config, now=now)
            st.rerun()
        remaining_attempts = record_failed_login(st.session_state, config, now=now)
        if remaining_attempts:
            st.error(f"Sign-in failed. {remaining_attempts} attempt(s) remain before a temporary lockout.")
        else:
            st.warning(f"Too many failed attempts. Try again in {config.lockout_seconds} seconds.")
    st.stop()


render_auth_gate()

try:
    data = load_outputs()
except FileNotFoundError:
    st.error("Run the pipeline first: python -m nba_forecast.cli --input <workbook> --output data/processed")
    st.stop()

features = data["features"]
forecasts = data["forecasts"]
simulations = data["simulations"]
next_forecast = data["next_forecast"]
next_simulation = data["next_simulation"]
rosters = data["rosters"]
injuries = data["injuries"]
moves = data["moves"]
manifest = data["manifest"]

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


def go_to(page: str) -> None:
    st.session_state["page"] = page


def team_label(value: str) -> str:
    return "League-wide" if value == "ALL" else value


def persist_focus_team() -> None:
    st.session_state["focus_team"] = st.session_state["focus_team_widget"]


page = st.session_state["page"]
selected_team = None if st.session_state["focus_team"] == "ALL" else st.session_state["focus_team"]
east = EAST & set(teams)
west = set(teams) - east
theme = get_team_theme(selected_team)
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


with st.container():
    brand_col, nav_col, focus_col, mobile_col, account_col = st.columns([1.8, 8.4, 2.5, .7, 1.0], gap="small", vertical_alignment="center")
    with brand_col:
        st.markdown('<div class="topbar"><span class="brand"><span class="brand-mark">N</span>BA Forecast Lab</span></div>', unsafe_allow_html=True)
    with nav_col:
        with st.container(key="desktop-navigation-slot"):
            with st.container(key="desktop-navigation"):
                nav_buttons = st.columns(len(PAGES), gap="small")
                for button_col, nav_page in zip(nav_buttons, PAGES):
                    with button_col:
                        if st.button(nav_page, key=f"top_nav_{nav_page}", type="primary" if st.session_state["page"] == nav_page else "secondary", use_container_width=True):
                            go_to(nav_page)
                            st.rerun()
    with focus_col:
        st.selectbox("Focus team", team_options, format_func=team_label, key="focus_team_widget", on_change=persist_focus_team)
    with mobile_col:
        with st.container(key="mobile-navigation"):
            with st.popover("☰", use_container_width=True):
                st.markdown("### Navigate")
                st.caption("Choose a workspace page. A team focus is optional.")
                for nav_page in PAGES:
                    if st.button(nav_page, key=f"menu_nav_{nav_page}", use_container_width=True):
                        go_to(nav_page)
                        st.rerun()
                st.caption("The team focus is available in the header on every screen.")
                if st.button("Sign out", key="mobile_sign_out", use_container_width=True):
                    clear_auth_state(st.session_state)
                    st.rerun()
    with account_col:
        with st.container(key="account-actions"):
            if st.button("Sign out", key="desktop_sign_out", use_container_width=True):
                clear_auth_state(st.session_state)
                st.rerun()

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
        metric_card("Live data status", "Attached")


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
        metric_card("Live injury burden", f"{safe_float(next_team, 'live_injury_burden'):.1f}")


def team_overview() -> str:
    if next_team is None:
        return "Select a team from MENU when you want a team-specific explanation. The league views remain fully usable without a selection."
    conference_name, rank = rank_for_team(selected_team)
    form = safe_float(next_team, "predicted_wins")
    roster = safe_float(next_team, "roster_aware_predicted_wins")
    rotation = safe_float(next_team, "live_roster_projection_wins")
    ensemble = safe_float(next_team, "holistic_predicted_wins")
    market = safe_float(next_team, "market_win_total")
    overview = f"{selected_team} projects to {ensemble:.1f} wins, ranking {rank}th in the {conference_name}. The independent historical model is {form:.1f} wins, while the roster-aware model is {roster:.1f}; the ensemble also incorporates a {market:.1f}-win market benchmark."
    if form < market - 3:
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
    st.markdown('<div class="hero"><div class="eyebrow">NBA 2026-27 / MODEL CONTROL ROOM</div><h1>Forecast the league.<br>Interrogate the assumptions.</h1><p>NBA Forecast Lab combines historical team performance, player-level production, game-log trends, and live roster context. Browse the league first, then focus on a team only when you need a deeper read.</p></div>', unsafe_allow_html=True)
    a, b, c = st.columns(3)
    with a:
        st.markdown('<div class="card"><span class="tag">Explore</span><h3>Forecast</h3><p>Compare projected wins and live context across every team. Use MENU to set an optional team focus and highlight it in charts.</p></div>', unsafe_allow_html=True)
    with b:
        st.markdown('<div class="card"><span class="tag">Track</span><h3>Rosters & moves</h3><p>Inspect the current 30-team roster snapshot and the transaction ledger behind the live offseason context.</p></div>', unsafe_allow_html=True)
    with c:
        st.markdown('<div class="card"><span class=\"tag\">Understand</span><h3>Methodology & diagnostics</h3><p>Follow the feature construction, validation, uncertainty logic, and data limitations behind each output.</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Current system snapshot</div>', unsafe_allow_html=True)
    if selected_team is None:
        league_metric_strip()
        st.markdown('<p class="helper">No team selected. Open MENU any time to focus the workspace on a team.</p>', unsafe_allow_html=True)
    else:
        team_metric_strip()
        st.markdown(f'<p class="helper">Focused on {escape(selected_team)}. Change or clear the focus from MENU.</p>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">League leaders</div>', unsafe_allow_html=True)
    leaders = next_forecast.sort_values("holistic_predicted_wins", ascending=False).head(5)[["team_abbr", "holistic_predicted_wins", "market_win_total"]].rename(columns={"team_abbr": "team", "holistic_predicted_wins": "projected wins", "market_win_total": "market prior"}).round(1)
    st.dataframe(leaders, hide_index=True, width="stretch")

elif page == "Forecast":
    st.markdown('<div class="eyebrow">FORECAST</div>', unsafe_allow_html=True)
    st.title(f"{selected_team + ' / ' if selected_team else ''}2026-27 outlook")
    st.caption("The headline forecast uses the corrected latest-season feature frame. Live roster, injury, transaction, and schedule data are shown alongside it.")
    team_metric_strip()
    view = st.radio("Output", ["Predicted wins", "Live context"], horizontal=True, label_visibility="collapsed")
    if view == "Predicted wins":
        forecast_chart()
    else:
        live_chart_data = next_forecast[["team_abbr", "live_injury_burden"]].fillna(0).sort_values("live_injury_burden")
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
            st.dataframe(pd.DataFrame([{"independent model": safe_float(next_team, "independent_predicted_wins"), "roster-aware model": safe_float(next_team, "roster_aware_predicted_wins"), "live rotation": safe_float(next_team, "live_roster_projection_wins"), "market prior": safe_float(next_team, "market_win_total"), "ensemble": safe_float(next_team, "holistic_predicted_wins")}]).round(1), hide_index=True, width="stretch")
        with right:
            st.dataframe(pd.DataFrame([{"roster players": safe_int(next_team, "live_roster_count"), "injuries listed": safe_int(next_team, "live_injury_count"), "transactions since July": safe_int(next_team, "live_transactions_since_july"), "schedule provider": next_team.get("live_schedule_provider", "n/a")}]), hide_index=True, width="stretch")
        if future_simulation is not None:
            st.markdown('<div class="section-label">Future uncertainty</div>', unsafe_allow_html=True)
            st.write(f"The game-level simulation centers {selected_team} at {safe_float(future_simulation, 'expected_wins'):.1f} wins, with a 10th-90th percentile range of {safe_int(future_simulation, 'wins_p10')}-{safe_int(future_simulation, 'wins_p90')}. It places the team in the simulated top-10 of its conference in {safe_float(future_simulation, 'playoff_probability'):.1%} of runs.")
            st.caption(str(future_simulation.get("simulation_note", "")))
        st.markdown('<div class="section-label">AI overview</div>', unsafe_allow_html=True)
        st.info(team_overview())
    else:
        st.markdown('<div class="section-label">League view</div>', unsafe_allow_html=True)
        st.info("This is a league-wide view. Set a team focus from MENU to see a team-specific component breakdown, uncertainty range, and AI overview.")

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
    st.latex(r"\\hat{W}_{holistic} = 0.25\\hat{W}_{form} + 0.25\\hat{W}_{roster} + 0.50\\hat{W}_{market}")
    st.write("The independent model uses prior team, player, and game-log features. The roster-aware model adds a transparent season-roster transition proxy built from player IDs, prior production, returning-player shares, incoming-player shares, and prior expected rotation strength. A separate live top-rotation calculation adjusts expected minutes for current injuries and is displayed as a diagnostic. The holistic forecast blends independent form, roster-aware model output, and a dated market prior with explicit weights. Current rosters, injury reports, transaction records, and the published schedule are timestamped alongside the forecast. The simulation uses game-level log5 probabilities, home court, and neutral fills for unresolved games.")

else:
    st.markdown('<div class="eyebrow">VALIDATION / FAILURE MODES</div>', unsafe_allow_html=True)
    st.title("Diagnostics before confidence")
    metrics_path = ROOT / "data" / "processed" / "backtest_metrics.json"
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        a, b, c = st.columns(3)
        with a:
            metric_card("Backtest rows", f"{metrics.get('test_rows', 0):,}")
        with b:
            metric_card("MAE", f"{metrics.get('mae', 0):.2f} wins")
        with c:
            metric_card("RMSE", f"{metrics.get('rmse', 0):.2f} wins")
        d, e = st.columns(2)
        with d:
            metric_card("Roster-aware MAE", f"{metrics.get('roster_aware_mae', 0):.2f} wins")
        with e:
            metric_card("Roster-aware RMSE", f"{metrics.get('roster_aware_rmse', 0):.2f} wins")
    st.markdown("### Current limitations")
    st.warning("The live system now attaches current roster rows, injury context, transaction history, a roster-aware diagnostic, and a schedule-aware simulation. The remaining uncertainty is provider-dependent: the historical roster transition table is a season-level proxy rather than a complete historical transaction ledger, market priors are dated snapshots, player aging and lineup fit are not fully modeled, and Cup-dependent schedule games use neutral-opponent fills until official opponents are resolvable.")
    if manifest:
        st.markdown("### Data provenance")
        st.write(f"Live snapshot fetched: {manifest.get('fetched_at_utc', 'unknown')}")
        st.json(manifest.get("sources", {}))
    quality_path = ROOT / "data" / "processed" / "data_quality_report.json"
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
