"""Build a small FICTIONAL demo corpus so the app and tests run before the first real ETL.

Every club and player here is invented. The data_version starts with "demo", which makes the
frontend show a "demo data" banner, so this can never be mistaken for real statistics.

  python -m etl.make_demo --out data/demo_corpus --embedder hashing
"""
from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path

from .build_corpus import build

PLAYERS = [
    # league, team, player, position, matches, minutes, goals, np_goals, xg, np_xg, assists, xa, shots, key_passes, yc, rc, chain, buildup
    ("ENG-Premier League", "Riverside United", "Tomas Ekwueme", "F", 10, 870, 9, 8, 7.4, 6.6, 2, 1.8, 38, 11, 1, 0, 9.1, 1.2),
    ("ENG-Premier League", "Riverside United", "Lucas Silva", "M", 10, 812, 2, 2, 2.9, 2.9, 5, 4.1, 17, 29, 3, 0, 8.4, 4.9),
    ("ENG-Premier League", "Riverside United", "Callum Hart", "D", 10, 900, 1, 1, 0.8, 0.8, 1, 0.9, 6, 4, 2, 0, 3.0, 2.6),
    ("ENG-Premier League", "Northgate City", "Kenji Mori", "F", 10, 845, 11, 9, 9.3, 7.8, 1, 1.5, 44, 9, 0, 0, 10.2, 0.9),
    ("ENG-Premier League", "Northgate City", "Rafael Silva", "M", 9, 720, 3, 3, 2.1, 2.1, 6, 5.2, 14, 31, 1, 0, 9.6, 5.5),
    ("ENG-Premier League", "Northgate City", "Arjun Pillai", "M", 10, 880, 4, 4, 3.6, 3.6, 3, 2.7, 22, 18, 2, 0, 8.8, 4.0),
    ("ENG-Premier League", "Harbour Athletic", "Mateo Ruiz", "F", 10, 790, 6, 5, 6.8, 6.0, 3, 2.2, 35, 12, 4, 1, 7.5, 1.1),
    ("ENG-Premier League", "Harbour Athletic", "Sam Okafor", "D", 10, 900, 0, 0, 0.4, 0.4, 2, 1.1, 5, 7, 3, 0, 2.9, 2.7),
    ("ENG-Premier League", "Kingsmoor Rovers", "Luca Ferraro", "F", 10, 860, 7, 7, 5.1, 5.1, 4, 3.0, 30, 15, 2, 0, 8.0, 1.8),
    ("ENG-Premier League", "Kingsmoor Rovers", "Ibrahim Diallo", "M", 8, 610, 1, 1, 1.4, 1.4, 2, 2.6, 11, 19, 1, 0, 5.2, 3.4),
]

MATCHES = [
    # date, home, away, hg, ag, hxg, axg, hppda, appda, hdeep, adeep
    ("2026-08-22", "Riverside United", "Northgate City", 2, 2, 1.9, 2.3, 9.8, 8.1, 7, 9),
    ("2026-08-23", "Harbour Athletic", "Kingsmoor Rovers", 1, 0, 1.2, 0.7, 11.2, 13.5, 5, 3),
    ("2026-08-29", "Northgate City", "Harbour Athletic", 3, 1, 2.8, 1.0, 7.4, 12.9, 12, 4),
    ("2026-08-30", "Kingsmoor Rovers", "Riverside United", 1, 3, 0.9, 2.6, 14.1, 8.8, 3, 10),
    ("2026-09-13", "Riverside United", "Harbour Athletic", 2, 0, 2.1, 0.6, 8.9, 15.0, 9, 2),
    ("2026-09-14", "Northgate City", "Kingsmoor Rovers", 4, 1, 3.3, 0.8, 7.0, 16.2, 14, 3),
    ("2026-09-20", "Harbour Athletic", "Riverside United", 1, 1, 1.3, 1.5, 10.5, 9.4, 6, 7),
    ("2026-09-21", "Kingsmoor Rovers", "Northgate City", 0, 2, 0.6, 2.0, 15.3, 7.9, 2, 11),
]

P_COLS = ["league", "team", "player", "position", "matches", "minutes", "goals", "np_goals", "xg", "np_xg", "assists",
          "xa", "shots", "key_passes", "yellow_cards", "red_cards", "xg_chain", "xg_buildup"]
M_COLS = ["league", "season", "game_id", "date", "home_team", "away_team", "home_goals", "away_goals", "home_xg", "away_xg",
          "home_ppda", "away_ppda", "home_deep_completions", "away_deep_completions"]


def write_raw(raw: Path) -> None:
    raw.mkdir(parents=True, exist_ok=True)
    with (raw / "players.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(P_COLS)
        w.writerows(PLAYERS)
    with (raw / "matches.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(M_COLS)
        for i, (d, h, a, hg, ag, hx, ax, hp, ap, hd, ad) in enumerate(MATCHES):
            w.writerow(["ENG-Premier League", 2026, i + 1, d, h, a, hg, ag, hx, ax, hp, ap, hd, ad])


def make_demo(out: Path, embedder: str | None, data_version: str = "demo-fictional") -> None:
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp)
        write_raw(raw)
        build(raw, out, data_version, embedder)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("data/demo_corpus"))
    ap.add_argument("--embedder", default="hashing")
    args = ap.parse_args()
    make_demo(args.out, args.embedder)
