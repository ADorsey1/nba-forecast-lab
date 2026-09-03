"""Simple uncertainty engine for scenario ranges."""

from __future__ import annotations

import numpy as np
import pandas as pd


def simulate_outcomes(forecasts: pd.DataFrame, simulations: int = 10000, seed: int = 42) -> pd.DataFrame:
    """Simulate wins independently; replace with schedule simulation once schedules exist."""
    if forecasts.empty:
        return pd.DataFrame()
    rng = np.random.default_rng(seed)
    rows = []
    for row in forecasts.itertuples(index=False):
        expected = float(np.clip(row.best_available_baseline, 0, 82))
        wins = rng.binomial(82, expected / 82, size=simulations)
        rows.append({
            "team_abbr": row.team_abbr,
            "season": row.season,
            "expected_wins": round(float(wins.mean()), 2),
            "wins_p10": int(np.quantile(wins, 0.10)),
            "wins_p25": int(np.quantile(wins, 0.25)),
            "wins_p50": int(np.quantile(wins, 0.50)),
            "wins_p75": int(np.quantile(wins, 0.75)),
            "wins_p90": int(np.quantile(wins, 0.90)),
            "playoff_proxy_probability": round(float((wins >= 45).mean()), 4),
            "simulation_note": "Independent-win proxy; replace with schedule-based simulation when schedule data is added.",
        })
    return pd.DataFrame(rows).sort_values("expected_wins", ascending=False).reset_index(drop=True)


def simulate_schedule_outcomes(
    forecasts: pd.DataFrame,
    schedule: pd.DataFrame,
    simulations: int = 10000,
    seed: int = 42,
) -> pd.DataFrame:
    """Simulate a season using game-level log5 probabilities and home court."""
    if forecasts.empty or schedule.empty:
        return pd.DataFrame()
    teams = forecasts["team_abbr"].dropna().unique().tolist()
    ratings = forecasts.set_index("team_abbr")["holistic_predicted_wins"].fillna(forecasts.set_index("team_abbr")["predicted_wins"])
    win_rates = (ratings / 82).clip(0.05, 0.95)
    valid_games = schedule[schedule["home_team"].isin(teams) & schedule["away_team"].isin(teams)].copy()
    valid_games["game_key"] = valid_games["game_date"].astype(str) + "|" + valid_games["home_team"].astype(str) + "|" + valid_games["away_team"].astype(str)
    valid_games = valid_games.drop_duplicates("game_key")
    if valid_games.empty:
        return pd.DataFrame()
    rng = np.random.default_rng(seed)
    wins = np.zeros((simulations, len(teams)), dtype=np.int16)
    team_index = {team: index for index, team in enumerate(teams)}
    for game in valid_games.itertuples(index=False):
        home_rate = float(win_rates[game.home_team])
        away_rate = float(win_rates[game.away_team])
        home_rate = min(home_rate + 0.03, 0.97)
        probability = (home_rate * (1 - away_rate)) / (home_rate + away_rate - 2 * home_rate * away_rate)
        home_wins = rng.random(simulations) < probability
        wins[:, team_index[game.home_team]] += home_wins
        wins[:, team_index[game.away_team]] += ~home_wins
    scheduled_games = np.zeros(len(teams), dtype=int)
    for game in valid_games.itertuples(index=False):
        scheduled_games[team_index[game.home_team]] += 1
        scheduled_games[team_index[game.away_team]] += 1
    unknown_games = np.maximum(82 - scheduled_games, 0)
    for index, missing in enumerate(unknown_games):
        if missing:
            wins[:, index] += (rng.random((simulations, missing)) < float(win_rates[teams[index]])).sum(axis=1)
    playoff_flags = np.zeros((simulations, len(teams)), dtype=bool)
    if "conference" in forecasts.columns:
        conference_values = forecasts.set_index("team_abbr").loc[teams, "conference"].to_numpy()
        for conference in pd.unique(conference_values):
            conference_indices = np.flatnonzero(conference_values == conference)
            ranked = np.argsort(-wins[:, conference_indices], axis=1)[:, : min(10, len(conference_indices))]
            simulation_indices = np.arange(simulations)
            for rank in range(ranked.shape[1]):
                playoff_flags[simulation_indices, conference_indices[ranked[:, rank]]] = True
    else:
        ranked = np.argsort(-wins, axis=1)[:, : min(20, len(teams))]
        playoff_flags[np.arange(simulations)[:, None], ranked] = True

    rows = []
    for index, team in enumerate(teams):
        team_wins = wins[:, index]
        rows.append({
            "team_abbr": team,
            "expected_wins": round(float(team_wins.mean()), 2),
            "wins_p10": int(np.quantile(team_wins, 0.10)),
            "wins_p25": int(np.quantile(team_wins, 0.25)),
            "wins_p50": int(np.quantile(team_wins, 0.50)),
            "wins_p75": int(np.quantile(team_wins, 0.75)),
            "wins_p90": int(np.quantile(team_wins, 0.90)),
            "playoff_probability": round(float(playoff_flags[:, index].mean()), 4),
            "scheduled_games": int(scheduled_games[index]),
            "unknown_games_filled": int(unknown_games[index]),
            "simulation_note": "Game-level log5 simulation with home court; unresolved games filled against a neutral average opponent.",
        })
    return pd.DataFrame(rows).sort_values("expected_wins", ascending=False).reset_index(drop=True)
