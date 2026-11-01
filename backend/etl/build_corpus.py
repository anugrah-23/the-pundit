"""Turn raw stats tables into the RAG corpus, the gazetteer and the embeddings.

  python -m etl.build_corpus --raw data/raw --out data/corpus
  python -m etl.build_corpus --raw data/raw --out data/corpus --no-embed   # skip embeddings

Outputs docs.jsonl, gazetteer.json, meta.json and embeddings.npy in --out.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from .aliases import PLAYER_ALIASES, TEAM_ALIASES
from .glossary import GLOSSARY

LEAGUE_NAMES = {
    "ENG-Premier League": "Premier League",
    "ESP-La Liga": "La Liga",
    "ITA-Serie A": "Serie A",
    "GER-Bundesliga": "Bundesliga",
    "FRA-Ligue 1": "Ligue 1",
}
SEASON_LABEL = "2026-27"
SURNAME_PARTICLES = {"de", "da", "di", "van", "von", "der", "den", "dos", "das", "del", "la", "le", "ten", "ter"}


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def fold_name(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower().strip()


def player_aliases(name: str) -> list[str]:
    parts = name.split()
    aliases = set(PLAYER_ALIASES.get(name, []))
    if len(parts) >= 2:
        # Surname including particles: "Virgil van Dijk" -> "van Dijk".
        i = len(parts) - 1
        while i > 0 and parts[i - 1].lower() in SURNAME_PARTICLES:
            i -= 1
        surname = " ".join(parts[i:])
        if len(surname) >= 4:
            aliases.add(surname)
        # Hyphenated surnames: fans say "Mbappe" for "Mbappe-Lottin", "Calvert-Lewin" stays whole too.
        if "-" in parts[-1]:
            first_part = parts[-1].split("-")[0]
            if len(first_part) >= 4:
                aliases.add(first_part)
            aliases.add(" ".join([*parts[:-1], first_part]))
    return sorted(aliases)


def n(x, digits: int = 0):
    if pd.isna(x):
        return "n/a"
    return f"{float(x):.{digits}f}" if digits else str(int(round(float(x))))


def per90(value, minutes) -> str:
    if pd.isna(value) or pd.isna(minutes) or float(minutes) < 1:
        return "n/a"
    return f"{float(value) * 90 / float(minutes):.2f}"


def build_player_docs(players: pd.DataFrame) -> list[dict]:
    docs = []
    for _, r in players.iterrows():
        if pd.isna(r.get("minutes")) or float(r["minutes"]) < 1:
            continue
        league = LEAGUE_NAMES.get(r["league"], r["league"])
        text = (
            f"{r['player']} ({r['team']}, {league}, {SEASON_LABEL}), position {r.get('position', 'n/a')}: "
            f"{n(r.get('matches'))} matches, {n(r.get('minutes'))} minutes, "
            f"{n(r.get('goals'))} goals ({n(r.get('np_goals'))} non-penalty), {n(r.get('assists'))} assists, "
            f"xG {n(r.get('xg'), 2)}, npxG {n(r.get('np_xg'), 2)}, xA {n(r.get('xa'), 2)}, "
            f"{n(r.get('shots'))} shots, {n(r.get('key_passes'))} key passes, "
            f"xGChain {n(r.get('xg_chain'), 2)}, xGBuildup {n(r.get('xg_buildup'), 2)}, "
            f"{n(r.get('yellow_cards'))} yellow and {n(r.get('red_cards'))} red cards. "
            f"Per 90 minutes: {per90(r.get('goals'), r.get('minutes'))} goals, {per90(r.get('np_xg'), r.get('minutes'))} npxG, "
            f"{per90(r.get('assists'), r.get('minutes'))} assists, {per90(r.get('xa'), r.get('minutes'))} xA."
        )
        docs.append({
            "doc_id": f"player:{slug(r['player'])}:{slug(r['team'])}", "kind": "player", "text": text,
            "league": r["league"], "season": SEASON_LABEL,
            "entities": {"players": [r["player"]], "teams": [r["team"]]}, "volatile": True, "source": "understat",
        })
    return docs


def team_table(matches: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, m in matches.iterrows():
        hg, ag = int(m["home_goals"]), int(m["away_goals"])
        for side, opp, gf, ga in (("home", "away", hg, ag), ("away", "home", ag, hg)):
            rows.append({
                "league": m["league"], "team": m[f"{side}_team"], "gf": gf, "ga": ga,
                "xg": m.get(f"{side}_xg"), "xga": m.get(f"{opp}_xg"), "ppda": m.get(f"{side}_ppda"),
                "deep": m.get(f"{side}_deep_completions"),
                "w": int(gf > ga), "d": int(gf == ga), "l": int(gf < ga), "clean": int(ga == 0),
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    t = df.groupby(["league", "team"]).agg(
        played=("gf", "size"), w=("w", "sum"), d=("d", "sum"), l=("l", "sum"), gf=("gf", "sum"), ga=("ga", "sum"),
        xg=("xg", "sum"), xga=("xga", "sum"), ppda=("ppda", "mean"), deep=("deep", "mean"), clean=("clean", "sum"),
    ).reset_index()
    t["gd"] = t["gf"] - t["ga"]
    t["pts"] = 3 * t["w"] + t["d"]
    t = t.sort_values(["league", "pts", "gd", "gf"], ascending=[True, False, False, False])
    t["pos"] = t.groupby("league").cumcount() + 1
    return t


def build_team_docs(table: pd.DataFrame) -> list[dict]:
    docs = []
    for _, r in table.iterrows():
        league = LEAGUE_NAMES.get(r["league"], r["league"])
        text = (
            f"{r['team']} ({league}, {SEASON_LABEL}): position {int(r['pos'])} with {int(r['pts'])} points from {int(r['played'])} matches "
            f"({int(r['w'])} wins, {int(r['d'])} draws, {int(r['l'])} losses). Goals {int(r['gf'])} scored, {int(r['ga'])} conceded "
            f"(goal difference {int(r['gd']):+d}), {int(r['clean'])} clean sheets. xG for {n(r['xg'], 2)}, xG against {n(r['xga'], 2)}. "
            f"Average PPDA {n(r['ppda'], 2)} (lower means more pressing), average deep completions per match {n(r['deep'], 1)}."
        )
        docs.append({
            "doc_id": f"team:{slug(r['team'])}", "kind": "team", "text": text, "league": r["league"], "season": SEASON_LABEL,
            "entities": {"players": [], "teams": [r["team"]]}, "volatile": True, "source": "understat",
        })
    return docs


def build_table_docs(table: pd.DataFrame) -> list[dict]:
    docs = []
    for league, g in table.groupby("league"):
        name = LEAGUE_NAMES.get(league, league)
        lines = [f"{int(r['pos'])}. {r['team']} {int(r['pts'])} pts ({int(r['played'])} played, GD {int(r['gd']):+d})" for _, r in g.iterrows()]
        docs.append({
            "doc_id": f"table:{slug(league)}", "kind": "table",
            "text": f"{name} {SEASON_LABEL} league table: " + "; ".join(lines) + ".",
            "league": league, "season": SEASON_LABEL, "entities": {"players": [], "teams": list(g["team"])},
            "volatile": True, "source": "understat (computed from results)",
        })
    return docs


LEADER_STATS = [("goals", "goals", 0), ("assists", "assists", 0), ("xg", "xG", 2), ("xa", "xA", 2), ("shots", "shots", 0), ("np_xg", "npxG", 2)]


def build_leader_docs(players: pd.DataFrame) -> list[dict]:
    docs = []
    for league, g in players.groupby("league"):
        name = LEAGUE_NAMES.get(league, league)
        for col, label, digits in LEADER_STATS:
            if col not in g:
                continue
            top = g.sort_values(col, ascending=False).head(10)
            lines = [f"{i}. {r['player']} ({r['team']}) {n(r[col], digits)}" for i, (_, r) in enumerate(top.iterrows(), 1)]
            docs.append({
                "doc_id": f"leaders:{slug(league)}:{col}", "kind": "leaders",
                "text": f"Top {label} in the {name} {SEASON_LABEL}: " + "; ".join(lines) + ".",
                "league": league, "season": SEASON_LABEL,
                "entities": {"players": list(top["player"]), "teams": sorted(set(top["team"]))},
                "volatile": True, "source": "understat",
            })
    return docs


def build_match_docs(matches: pd.DataFrame) -> list[dict]:
    docs = []
    for _, m in matches.iterrows():
        league = LEAGUE_NAMES.get(m["league"], m["league"])
        day = str(m.get("date", ""))[:10]
        text = (
            f"{day}, {league} {SEASON_LABEL}: {m['home_team']} {int(m['home_goals'])}-{int(m['away_goals'])} {m['away_team']}. "
            f"xG {n(m.get('home_xg'), 2)}-{n(m.get('away_xg'), 2)}. PPDA {n(m.get('home_ppda'), 1)}-{n(m.get('away_ppda'), 1)}."
        )
        docs.append({
            "doc_id": f"match:{slug(m['home_team'])}-v-{slug(m['away_team'])}:{day}", "kind": "match", "text": text,
            "league": m["league"], "season": SEASON_LABEL,
            "entities": {"players": [], "teams": [m["home_team"], m["away_team"]]}, "volatile": True, "source": "understat",
        })
    return docs


def build_glossary_docs() -> list[dict]:
    return [
        {"doc_id": f"glossary:{key}", "kind": "glossary", "text": text, "league": "", "season": "",
         "entities": {"players": [], "teams": []}, "volatile": False, "source": "the pundit glossary"}
        for key, text in GLOSSARY
    ]


def build_gazetteer(players: pd.DataFrame, table: pd.DataFrame) -> dict:
    teams = sorted(set(players["team"]) | set(table["team"] if not table.empty else []))
    league_of = dict(zip(players["team"], players["league"]))
    if not table.empty:
        league_of.update(dict(zip(table["team"], table["league"])))
    # Players who moved mid-season appear once per team; the verified club is where they played most recently,
    # approximated by most minutes.
    latest = players.sort_values("minutes").groupby("player").tail(1)
    # A hand-written nickname beats an automatic surname: "Mbappe" means Kylian, not his brother Ethan
    # (whose full name still matches).
    present = set(latest["player"])
    claimed = {fold_name(a) for name, aliases in PLAYER_ALIASES.items() if name in present for a in aliases}
    entries = []
    for _, r in latest.iterrows():
        manual = {fold_name(a) for a in PLAYER_ALIASES.get(r["player"], [])}
        aliases = [a for a in player_aliases(r["player"]) if fold_name(a) in manual or fold_name(a) not in claimed]
        entries.append({"name": r["player"], "aliases": aliases, "team": r["team"], "league": r["league"]})
    return {
        "players": entries,
        "teams": [{"name": t, "aliases": TEAM_ALIASES.get(t, []), "league": league_of.get(t, "")} for t in teams],
    }


def build(raw: Path, out: Path, data_version: str, embed: str | None) -> None:
    players = pd.read_csv(raw / "players.csv")
    matches = pd.read_csv(raw / "matches.csv")
    table = team_table(matches)

    docs = (build_player_docs(players) + build_team_docs(table) + build_table_docs(table)
            + build_leader_docs(players) + build_match_docs(matches) + build_glossary_docs())
    out.mkdir(parents=True, exist_ok=True)
    with (out / "docs.jsonl").open("w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    (out / "gazetteer.json").write_text(json.dumps(build_gazetteer(players, table), ensure_ascii=False, indent=1), encoding="utf-8")

    meta = {"data_version": data_version, "season": SEASON_LABEL, "docs": len(docs), "embedding_model": None}
    if embed:
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from app.embeddings import make_embedder

        from app.config import get_settings

        model = get_settings().embedding_model
        embedder = make_embedder(embed, model)
        matrix = embedder.encode([d["text"] for d in docs])
        np.save(out / "embeddings.npy", matrix.astype(np.float32))
        meta["embedding_model"] = model if embed != "hashing" else "hashing"
    (out / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"{len(docs)} docs -> {out} (data_version {data_version})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=Path("data/raw"))
    ap.add_argument("--out", type=Path, default=Path("data/corpus"))
    ap.add_argument("--data-version", default=date.today().isoformat())
    ap.add_argument("--embedder", default="sentence-transformers", help="sentence-transformers | hashing")
    ap.add_argument("--no-embed", action="store_true")
    args = ap.parse_args()
    build(args.raw, args.out, args.data_version, None if args.no_embed else args.embedder)
