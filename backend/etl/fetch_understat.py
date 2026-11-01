"""Fetch Top 5 league data for one season from Understat via soccerdata.

Writes two CSVs into the raw directory:
  players.csv   one row per player per team (season aggregates)
  matches.csv   one row per played match (score, xG, PPDA)

Run in GitHub Actions or locally (the build workspace cannot reach Understat):
  python -m etl.fetch_understat --season 2026 --out data/raw
"""
from __future__ import annotations

import argparse
from pathlib import Path

LEAGUES = ["ENG-Premier League", "ESP-La Liga", "ITA-Serie A", "GER-Bundesliga", "FRA-Ligue 1"]

PLAYER_COLS = {
    "league": "league", "season": "season", "team": "team", "player": "player", "position": "position",
    "matches": "matches", "minutes": "minutes", "goals": "goals", "np_goals": "np_goals", "xg": "xg",
    "np_xg": "np_xg", "assists": "assists", "xa": "xa", "shots": "shots", "key_passes": "key_passes",
    "yellow_cards": "yellow_cards", "red_cards": "red_cards", "xg_chain": "xg_chain", "xg_buildup": "xg_buildup",
}
MATCH_COLS = [
    "league", "season", "game_id", "date", "home_team", "away_team", "home_goals", "away_goals",
    "home_xg", "away_xg", "home_ppda", "away_ppda", "home_deep_completions", "away_deep_completions",
]


def fetch(season: int, out: Path) -> None:
    import soccerdata as sd  # imported here so the app does not need it

    out.mkdir(parents=True, exist_ok=True)
    us = sd.Understat(leagues=LEAGUES, seasons=season)

    players = us.read_player_season_stats().reset_index()
    players = players[[c for c in PLAYER_COLS if c in players.columns]].rename(columns=PLAYER_COLS)
    players.to_csv(out / "players.csv", index=False)

    matches = us.read_team_match_stats().reset_index()
    matches = matches[[c for c in MATCH_COLS if c in matches.columns]]
    matches = matches.dropna(subset=["home_goals", "away_goals"])  # played games only
    matches.to_csv(out / "matches.csv", index=False)

    print(f"players: {len(players)} rows, matches: {len(matches)} rows -> {out}")
    missing_p = sorted(set(PLAYER_COLS) - set(players.columns))
    missing_m = sorted(set(MATCH_COLS) - set(matches.columns))
    if missing_p or missing_m:
        print(f"warning: columns not returned by soccerdata: players={missing_p} matches={missing_m}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026, help="start year, 2026 = 2026-27")
    ap.add_argument("--out", type=Path, default=Path("data/raw"))
    args = ap.parse_args()
    fetch(args.season, args.out)
