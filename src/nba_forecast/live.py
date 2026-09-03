"""Live 2026-27 roster, injury, schedule, and transaction ingestion."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup


ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
NBA_MOVEMENT_URL = "https://stats.nba.com/js/data/playermovement/NBA_Player_Movement.json"
INJURY_WEIGHTS = {
    "out": 1.0,
    "inactive": 1.0,
    "doubtful": 0.8,
    "questionable": 0.5,
    "day-to-day": 0.3,
    "probable": 0.1,
}

NBA_TEAM_REGISTRY = [
    (1, "ATL", "atlanta-hawks"), (2, "BOS", "boston-celtics"), (17, "BRK", "brooklyn-nets"),
    (30, "CHO", "charlotte-hornets"), (4, "CHI", "chicago-bulls"), (5, "CLE", "cleveland-cavaliers"),
    (6, "DAL", "dallas-mavericks"), (7, "DEN", "denver-nuggets"), (8, "DET", "detroit-pistons"),
    (9, "GSW", "golden-state-warriors"), (10, "HOU", "houston-rockets"), (11, "IND", "indiana-pacers"),
    (12, "LAC", "la-clippers"), (13, "LAL", "los-angeles-lakers"), (29, "MEM", "memphis-grizzlies"),
    (14, "MIA", "miami-heat"), (15, "MIL", "milwaukee-bucks"), (16, "MIN", "minnesota-timberwolves"),
    (3, "NOP", "new-orleans-pelicans"), (18, "NYK", "new-york-knicks"), (25, "OKC", "oklahoma-city-thunder"),
    (19, "ORL", "orlando-magic"), (20, "PHI", "philadelphia-76ers"), (21, "PHO", "phoenix-suns"),
    (22, "POR", "portland-trail-blazers"), (23, "SAC", "sacramento-kings"), (24, "SAS", "san-antonio-spurs"),
    (28, "TOR", "toronto-raptors"), (26, "UTA", "utah-jazz"), (27, "WAS", "washington-wizards"),
]
NBA_TEAM_IDS = {
    "ATL": 1610612737, "BOS": 1610612738, "BRK": 1610612751, "CHO": 1610612766,
    "CHI": 1610612741, "CLE": 1610612739, "DAL": 1610612742, "DEN": 1610612743,
    "DET": 1610612765, "GSW": 1610612744, "HOU": 1610612745, "IND": 1610612754,
    "LAC": 1610612746, "LAL": 1610612747, "MEM": 1610612763, "MIA": 1610612748,
    "MIL": 1610612749, "MIN": 1610612750, "NOP": 1610612740, "NYK": 1610612752,
    "OKC": 1610612760, "ORL": 1610612753, "PHI": 1610612755, "PHO": 1610612756,
    "POR": 1610612757, "SAC": 1610612758, "SAS": 1610612759, "TOR": 1610612761,
    "UTA": 1610612762, "WAS": 1610612764,
}
BBR_CODES = {"BRK": "BRK", "CHO": "CHO", "PHO": "PHO"}
TEAM_NAME_TO_ABBR = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BRK", "Charlotte Hornets": "CHO",
    "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE", "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET", "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHO", "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR", "Utah Jazz": "UTA", "Washington Wizards": "WAS",
}
MAX_JSON_RESPONSE_BYTES = 20_000_000
MAX_HTML_RESPONSE_BYTES = 10_000_000


def _get_json(url: str) -> dict[str, Any]:
    response = requests.get(
        url,
        headers={"User-Agent": "nba-forecast/0.1", "Referer": "https://www.espn.com/"},
        timeout=45,
    )
    response.raise_for_status()
    if len(response.content) > MAX_JSON_RESPONSE_BYTES:
        raise requests.RequestException(f"Provider response exceeded {MAX_JSON_RESPONSE_BYTES} bytes: {url}")
    try:
        return response.json()
    except ValueError as exc:
        raise requests.RequestException(f"Provider returned invalid JSON: {url}") from exc


def _get_text(url: str, headers: dict[str, str] | None = None) -> str:
    response = requests.get(url, headers=headers or {"User-Agent": "nba-forecast/0.1"}, timeout=45)
    response.raise_for_status()
    if len(response.content) > MAX_HTML_RESPONSE_BYTES:
        raise requests.RequestException(f"Provider response exceeded {MAX_HTML_RESPONSE_BYTES} bytes: {url}")
    return response.text


def _team_list() -> list[dict[str, Any]]:
    try:
        payload = _get_json(f"{ESPN_BASE}/teams")
        wrappers = payload["sports"][0]["leagues"][0]["teams"]
        return [wrapper["team"] for wrapper in wrappers]
    except requests.RequestException:
        return [{"id": str(team_id), "abbreviation": abbreviation, "slug": slug} for team_id, abbreviation, slug in NBA_TEAM_REGISTRY]


def _roster_rows(team: dict[str, Any], payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rosters = []
    injuries = []
    for athlete in payload.get("athletes", []):
        contract = athlete.get("contract") or {}
        position = athlete.get("position") or {}
        injury_items = athlete.get("injuries") or []
        status = athlete.get("status") or {}
        rosters.append({
            "team_abbr": team["abbreviation"],
            "team_id": team["id"],
            "season": payload.get("season", {}).get("displayName", "2026-27"),
            "player_id": athlete.get("id"),
            "player_name": athlete.get("fullName"),
            "age": athlete.get("age"),
            "position": position.get("abbreviation") or position.get("displayName"),
            "roster_status": status.get("name") or status.get("type"),
            "experience_years": (athlete.get("experience") or {}).get("years"),
            "salary": contract.get("salary"),
            "years_remaining": contract.get("yearsRemaining"),
            "roster_injury_count": len(injury_items),
        })
        for injury in injury_items:
            injury_status = str(injury.get("status", "Unknown"))
            injuries.append({
                "team_abbr": team["abbreviation"],
                "team_id": team["id"],
                "player_id": athlete.get("id"),
                "player_name": athlete.get("fullName"),
                "injury_status": injury_status,
                "injury_date": injury.get("date"),
                "status_weight": INJURY_WEIGHTS.get(injury_status.lower(), 0.25),
            })
    return rosters, injuries


def _nba_players_page() -> dict[str, list[dict[str, Any]]]:
    page = _get_text("https://www.nba.com/players", headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(page, "html.parser")
    next_data = soup.find("script", id="__NEXT_DATA__")
    if next_data and next_data.string:
        payload = json.loads(next_data.string)
        embedded_players = payload.get("props", {}).get("pageProps", {}).get("players", [])
        result: dict[str, list[dict[str, Any]]] = {}
        for player in embedded_players:
            team_abbr = {"BKN": "BRK", "CHA": "CHO", "PHX": "PHO"}.get(player.get("TEAM_ABBREVIATION"), player.get("TEAM_ABBREVIATION"))
            if not team_abbr or not player.get("PERSON_ID") or player.get("ROSTER_STATUS") != 1 or player.get("IS_DEFUNCT"):
                continue
            result.setdefault(team_abbr, []).append({
                "team_abbr": team_abbr,
                "team_id": player.get("TEAM_ID"),
                "season": "2026-27",
                "player_id": str(player.get("PERSON_ID")),
                "player_name": f"{player.get('PLAYER_FIRST_NAME', '')} {player.get('PLAYER_LAST_NAME', '')}".strip(),
                "age": np.nan,
                "position": player.get("POSITION"),
                "roster_status": "Active",
                "experience_years": np.nan,
                "salary": np.nan,
                "years_remaining": np.nan,
                "roster_injury_count": 0,
            })
        return result
    result: dict[str, list[dict[str, Any]]] = {}
    for row in soup.select("tr"):
        player_link = row.select_one("a[href^='/player/']")
        team_link = row.select_one("a[href^='/team/']")
        cells = row.find_all("td")
        if not player_link or not team_link or len(cells) < 4:
            continue
        href = player_link.get("href", "")
        match = re.search(r"/player/(\d+)/", href)
        if not match:
            continue
        name = player_link.get_text(" ", strip=True)
        team_abbr = {"BKN": "BRK", "CHA": "CHO", "PHX": "PHO"}.get(team_link.get_text(" ", strip=True), team_link.get_text(" ", strip=True))
        result.setdefault(team_abbr, []).append({
            "team_abbr": team_abbr,
            "team_id": team_link.get("href", "").split("/")[2] if len(team_link.get("href", "").split("/")) > 2 else None,
            "season": "2026-27",
            "player_id": match.group(1),
            "player_name": name,
            "age": np.nan,
            "position": cells[3].get_text(" ", strip=True),
                    "roster_status": "Active",
            "experience_years": np.nan,
            "salary": np.nan,
            "years_remaining": np.nan,
            "roster_injury_count": 0,
        })
    return result


def _schedule_rows(team: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for event in payload.get("events", []):
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors") or []
        if len(competitors) != 2:
            continue
        home = next((item for item in competitors if item.get("homeAway") == "home"), None)
        away = next((item for item in competitors if item.get("homeAway") == "away"), None)
        if not home or not away:
            continue
        rows.append({
            "event_id": event.get("id"),
            "game_date": event.get("date"),
            "season": (event.get("season") or {}).get("displayName", "2026-27"),
            "home_team": (home.get("team") or {}).get("abbreviation"),
            "away_team": (away.get("team") or {}).get("abbreviation"),
            "source_team": team["abbreviation"],
        })
    return rows


def _bbr_roster(team_abbr: str, season: int) -> list[dict[str, Any]]:
    code = BBR_CODES.get(team_abbr, team_abbr)
    page = _get_text(f"https://www.basketball-reference.com/teams/{code}/{season}.html")
    tables = pd.read_html(StringIO(page))
    table = tables[0]
    rows = []
    for row in table.to_dict("records"):
        name = row.get("Player")
        if not isinstance(name, str) or not name.strip() or name.strip() == "Player":
            continue
        rows.append({
            "team_abbr": team_abbr,
            "team_id": NBA_TEAM_IDS.get(team_abbr),
            "season": f"{season - 1}-{str(season)[-2:]}",
            "player_id": name.lower().replace(" ", "-"),
            "player_name": name,
            "age": np.nan,
            "position": row.get("Pos"),
            "roster_status": "Current roster",
            "experience_years": row.get("Exp"),
            "salary": np.nan,
            "years_remaining": np.nan,
            "roster_injury_count": 0,
        })
    return rows


def _bbr_schedule(team_abbr: str, season: int) -> list[dict[str, Any]]:
    code = BBR_CODES.get(team_abbr, team_abbr)
    page = _get_text(f"https://www.basketball-reference.com/teams/{code}/{season}_games.html")
    table = pd.read_html(StringIO(page))[0]
    rows = []
    for row in table.to_dict("records"):
        game_number = pd.to_numeric(row.get("G"), errors="coerce")
        opponent = row.get("Opponent")
        if pd.isna(game_number) or not isinstance(opponent, str) or not opponent.strip():
            continue
        is_away = row.get("Unnamed: 5") == "@"
        opponent_abbr = next((abbr for name, abbr in TEAM_NAME_TO_ABBR.items() if name == opponent), opponent)
        rows.append({
            "event_id": f"bbr-{team_abbr}-{int(game_number)}",
            "game_date": row.get("Date"),
            "season": f"{season - 1}-{str(season)[-2:]}",
            "home_team": opponent_abbr if is_away else team_abbr,
            "away_team": team_abbr if is_away else opponent_abbr,
            "source_team": team_abbr,
        })
    return rows


def _espn_injury_page() -> tuple[pd.DataFrame, bool]:
    try:
        page = _get_text("https://www.espn.com/nba/injuries", headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(page, "html.parser")
        rows = []
        for section in soup.select(".ResponsiveTable.Table__league-injuries"):
            title = section.select_one(".injuries__teamName")
            team_abbr = TEAM_NAME_TO_ABBR.get(title.get_text(" ", strip=True) if title else "")
            if not team_abbr:
                continue
            table = section.find("table")
            for tr in table.select("tbody tr") if table else []:
                cells = [cell.get_text(" ", strip=True) for cell in tr.select("td")]
                if len(cells) < 5:
                    continue
                rows.append({
                    "team_abbr": team_abbr,
                    "player_id": f"{team_abbr}-{cells[0].lower().replace(' ', '-')}",
                    "player_name": cells[0],
                    "position": cells[1],
                    "estimated_return_date": cells[2],
                    "injury_status": cells[3],
                    "comment": cells[4],
                    "status_weight": INJURY_WEIGHTS.get(cells[3].lower(), 0.25),
                })
        return pd.DataFrame(rows), True
    except requests.RequestException:
        return pd.DataFrame(), False


def _transaction_rows(payload: dict[str, Any], team_by_id: dict[int, str]) -> pd.DataFrame:
    rows = []
    for item in payload.get("NBA_Player_Movement", {}).get("rows", []):
        date = pd.to_datetime(item.get("TRANSACTION_DATE"), errors="coerce")
        if pd.notna(date) and date.year < 2026:
            continue
        team_id = item.get("TEAM_ID")
        rows.append({
            "transaction_type": item.get("Transaction_Type"),
            "transaction_date": date,
            "description": item.get("TRANSACTION_DESCRIPTION"),
            "team_abbr": team_by_id.get(int(team_id)) if pd.notna(team_id) else None,
            "player_id": item.get("PLAYER_ID"),
            "player_slug": item.get("PLAYER_SLUG"),
            "group_sort": item.get("GroupSort"),
        })
    return pd.DataFrame(rows)


def _update_transaction_ledger(output: Path, transactions: pd.DataFrame) -> None:
    """Append new movements without losing prior snapshots."""
    ledger_path = output / "transaction_ledger.csv"
    if ledger_path.exists():
        prior = pd.read_csv(ledger_path)
        transactions = pd.concat([prior, transactions], ignore_index=True)
    if transactions.empty:
        transactions = pd.DataFrame(columns=["transaction_type", "transaction_date", "description", "team_abbr", "player_id", "player_slug", "group_sort"])
    transactions["transaction_date"] = pd.to_datetime(transactions["transaction_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    transactions["dedupe_key"] = (
        transactions["transaction_date"].fillna("").astype(str) + "|" +
        transactions["team_abbr"].fillna("").astype(str) + "|" +
        transactions["player_id"].fillna("").astype(str) + "|" +
        transactions["transaction_type"].fillna("").astype(str) + "|" +
        transactions["description"].fillna("").astype(str)
    )
    transactions.drop_duplicates("dedupe_key", keep="last").sort_values(["transaction_date", "team_abbr"], na_position="last").to_csv(ledger_path, index=False)


def fetch_live_context(output_dir: str | Path, season: int = 2027) -> dict[str, str]:
    """Fetch and persist current league context with source timestamps."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc).isoformat()
    teams = _team_list()
    team_by_id = {int(team["id"]): team["abbreviation"] for team in teams}
    team_by_id.update({team_id: abbreviation for abbreviation, team_id in NBA_TEAM_IDS.items()})
    roster_rows: list[dict[str, Any]] = []
    injury_rows: list[dict[str, Any]] = []
    schedule_rows: list[dict[str, Any]] = []
    raw_rosters: dict[str, Any] = {}
    raw_schedules: dict[str, Any] = {}
    try:
        nba_page_rosters = _nba_players_page()
    except requests.RequestException:
        nba_page_rosters = {}
    schedule_source_available = True
    schedule_fallback_allowed = True
    schedule_provider = None

    for team in teams:
        abbr = team["abbreviation"]
        team_code = str(team["abbreviation"]).lower()
        try:
            roster_payload = _get_json(f"{ESPN_BASE}/teams/{team_code}/roster")
            raw_rosters[abbr] = roster_payload
            roster, injuries = _roster_rows(team, roster_payload)
        except requests.RequestException:
            try:
                roster = nba_page_rosters.get(abbr) or _bbr_roster(abbr, season)
            except Exception:
                roster = []
            injuries = []
            raw_rosters[abbr] = {"source": "basketball-reference", "rows": roster}
        try:
            schedule_payload = _get_json(f"{ESPN_BASE}/teams/{team_code}/schedule?season={season}&seasontype=2")
            raw_schedules[abbr] = schedule_payload
            schedule = _schedule_rows(team, schedule_payload)
            if schedule:
                schedule_provider = "ESPN"
        except requests.RequestException:
            try:
                schedule = _bbr_schedule(abbr, season) if schedule_fallback_allowed else []
                if schedule:
                    schedule_provider = "Basketball-Reference"
            except Exception:
                schedule = []
                schedule_fallback_allowed = False
                schedule_source_available = False
            raw_schedules[abbr] = {"source": "basketball-reference", "rows": schedule}
        roster_rows.extend(roster)
        injury_rows.extend(injuries)
        schedule_rows.extend(schedule)

    movement_payload = _get_json(NBA_MOVEMENT_URL)
    roster = pd.DataFrame(roster_rows)
    injuries = pd.DataFrame(injury_rows)
    if injuries.empty:
        injuries, injury_source_available = _espn_injury_page()
    else:
        injury_source_available = True
    schedule = pd.DataFrame(schedule_rows)
    if schedule.empty:
        schedule = pd.DataFrame(columns=["event_id", "game_date", "season", "home_team", "away_team", "source_team"])
    else:
        schedule["game_key"] = (
            schedule["game_date"].astype(str) + "|" +
            schedule["home_team"].astype(str) + "|" +
            schedule["away_team"].astype(str)
        )
        schedule = schedule.drop_duplicates("game_key")
    transactions = _transaction_rows(movement_payload, team_by_id)
    if transactions.empty:
        transactions = pd.DataFrame(columns=["transaction_type", "transaction_date", "description", "team_abbr", "player_id", "player_slug", "group_sort"])
    _update_transaction_ledger(output, transactions)

    roster_summary = roster.groupby("team_abbr", as_index=False).agg(
        live_roster_count=("player_id", "nunique"),
        live_active_roster_count=("roster_status", lambda values: (values.astype(str).str.lower() == "active").sum()),
        live_avg_age=("age", "mean"),
        live_salary_total=("salary", "sum"),
        live_salary_player_count=("salary", "count"),
    )
    top3 = roster.sort_values(["team_abbr", "salary"], ascending=[True, False]).groupby("team_abbr").head(3).groupby("team_abbr")["salary"].sum()
    roster_summary = roster_summary.merge(top3.rename("live_salary_top3"), on="team_abbr", how="left")
    roster_summary["live_salary_top3_share"] = roster_summary["live_salary_top3"] / roster_summary["live_salary_total"].replace(0, np.nan)

    if injuries.empty:
        injury_summary = pd.DataFrame({"team_abbr": [team["abbreviation"] for team in teams], "live_injury_count": 0, "live_injury_burden": 0.0})
    else:
        injury_summary = injuries.groupby("team_abbr", as_index=False).agg(
            live_injury_count=("player_id", "nunique"),
            live_injury_burden=("status_weight", "sum"),
        )
    if schedule.empty:
        schedule_summary = pd.DataFrame({"team_abbr": [team["abbreviation"] for team in teams], "scheduled_regular_season_games": 0, "scheduled_home_games": 0})
    else:
        schedule_summary = pd.concat([
            schedule.assign(team_abbr=schedule["home_team"], is_home=1),
            schedule.assign(team_abbr=schedule["away_team"], is_home=0),
        ]).groupby("team_abbr", as_index=False).agg(
            scheduled_regular_season_games=("event_id", "nunique"),
            scheduled_home_games=("is_home", "sum"),
        )
    transaction_summary = transactions.groupby("team_abbr", as_index=False).agg(
        live_transactions_since_july=("transaction_type", "size"),
    ) if not transactions.empty else pd.DataFrame(columns=["team_abbr", "live_transactions_since_july"])

    all_teams = pd.DataFrame({"team_abbr": [team["abbreviation"] for team in teams]})
    context = all_teams.merge(roster_summary, on="team_abbr", how="left").merge(injury_summary, on="team_abbr", how="left").merge(schedule_summary, on="team_abbr", how="left").merge(transaction_summary, on="team_abbr", how="left")
    context[["live_roster_count", "live_active_roster_count", "live_injury_count", "live_injury_burden", "scheduled_regular_season_games", "scheduled_home_games"]] = context[["live_roster_count", "live_active_roster_count", "live_injury_count", "live_injury_burden", "scheduled_regular_season_games", "scheduled_home_games"]].fillna(0)
    context["live_transactions_since_july"] = context["live_transactions_since_july"].fillna(0).astype(int)
    context["live_injury_source_available"] = injury_source_available
    context["live_schedule_source_available"] = schedule_source_available and not schedule.empty
    context["live_schedule_provider"] = schedule_provider or "unavailable"
    context["schedule_unresolved_games"] = (82 - context["scheduled_regular_season_games"]).clip(lower=0)
    context["fetched_at_utc"] = fetched_at

    (output / "source_manifest.json").write_text(json.dumps({
        "fetched_at_utc": fetched_at,
        "season": f"{season - 1}-{str(season)[-2:]}",
        "sources": {
            "nba_players": "https://www.nba.com/players",
            "espn": ESPN_BASE,
            "espn_injuries": "https://www.espn.com/nba/injuries",
            "nba_player_movement": NBA_MOVEMENT_URL,
            "schedule": "https://www.nba.com/schedule",
            "schedule_provider": schedule_provider or "unavailable",
            "market_prior": "data/raw/external_market_wintotals.csv",
        },
    }, indent=2), encoding="utf-8")
    (output / "espn_rosters.json").write_text(json.dumps(raw_rosters), encoding="utf-8")
    (output / "espn_schedules.json").write_text(json.dumps(raw_schedules), encoding="utf-8")
    (output / "nba_player_movement.json").write_text(json.dumps(movement_payload), encoding="utf-8")
    roster.to_csv(output / "current_rosters.csv", index=False)
    injuries.to_csv(output / "current_injuries.csv", index=False)
    schedule.to_csv(output / "current_schedule.csv", index=False)
    transactions.to_csv(output / "current_transactions.csv", index=False)
    context.to_csv(output / "live_team_context.csv", index=False)
    return {"roster": str(output / "current_rosters.csv"), "injuries": str(output / "current_injuries.csv"), "schedule": str(output / "current_schedule.csv"), "transactions": str(output / "current_transactions.csv"), "context": str(output / "live_team_context.csv")}
