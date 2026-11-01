"""Gazetteer-based entity extraction for players, teams, competitions and seasons.

The entity guard compares the entities in a new question with those in a cached
question. If any of the four sets differ, the cache is skipped, because questions
like "Haaland goals this season" and "Mbappe goals this season" embed almost
identically but need different answers.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from rapidfuzz import fuzz

CURRENT_SEASON = "2026-27"
PREVIOUS_SEASON = "2025-26"

COMPETITIONS: dict[str, list[str]] = {
    "ENG-Premier League": ["premier league", "epl", "pl", "prem", "english league"],
    "ESP-La Liga": ["la liga", "laliga", "spanish league"],
    "ITA-Serie A": ["serie a", "italian league"],
    "GER-Bundesliga": ["bundesliga", "german league", "buli"],
    "FRA-Ligue 1": ["ligue 1", "ligue un", "french league"],
    "UEFA-Champions League": ["champions league", "ucl", "cl"],
    "UEFA-Europa League": ["europa league", "uel", "europa"],
}

THIS_SEASON_PHRASES = [
    "this season", "current season", "this year", "is season", "iss season",
    "intha season", "indha season", "is saal",
]
LAST_SEASON_PHRASES = [
    "last season", "previous season", "last year", "pichle season", "pichhle season",
    "pichla season", "pona season", "poana season", "kadantha season", "pichle saal",
]


FUZZY_STOPWORDS = {
    "goals", "assists", "season", "scored", "score", "matches", "games", "minutes", "shots",
    "expected", "player", "players", "league", "table", "top", "against", "which", "where",
    "there", "their", "about", "should", "would", "could", "tactics", "formation", "position",
    "points", "clean", "sheets", "keeper", "striker", "winger", "midfielder", "defender",
    "evlo", "evvalavu", "kitne", "kitna", "kaun", "yaaru", "adichaan", "adichirukaan",
    "panniruk", "kiya", "kiye", "milega", "better", "compare", "versus", "stats", "record",
}


def fold(text: str) -> str:
    """Lowercase and strip accents: 'Mbappé' -> 'mbappe'."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower()


@dataclass(frozen=True)
class Entities:
    players: frozenset[str] = field(default_factory=frozenset)
    teams: frozenset[str] = field(default_factory=frozenset)
    competitions: frozenset[str] = field(default_factory=frozenset)
    seasons: frozenset[str] = field(default_factory=frozenset)

    def as_dict(self) -> dict:
        return {k: sorted(getattr(self, k)) for k in ("players", "teams", "competitions", "seasons")}

    @classmethod
    def from_dict(cls, d: dict) -> "Entities":
        return cls(**{k: frozenset(d.get(k, [])) for k in ("players", "teams", "competitions", "seasons")})

    def differs_from(self, other: "Entities") -> str | None:
        """Return the first differing field name, or None if all four match.

        Seasons are compared after defaulting: a question with no season mentioned
        means the current season.
        """
        for name in ("players", "teams", "competitions"):
            if getattr(self, name) != getattr(other, name):
                return name
        mine = self.seasons or frozenset({CURRENT_SEASON})
        theirs = other.seasons or frozenset({CURRENT_SEASON})
        if mine != theirs:
            return "seasons"
        return None


class Gazetteer:
    def __init__(self, players: list[dict], teams: list[dict]):
        # alias -> set of canonical names. Ambiguous aliases (e.g. a common surname) map to several.
        self.player_aliases: dict[str, set[str]] = {}
        self.team_aliases: dict[str, set[str]] = {}
        self.player_team: dict[str, str] = {}
        self.team_league: dict[str, str] = {}
        for p in players:
            self.player_team[p["name"]] = p.get("team", "")
            for alias in {p["name"], *p.get("aliases", [])}:
                self.player_aliases.setdefault(fold(alias), set()).add(p["name"])
        for t in teams:
            self.team_league[t["name"]] = t.get("league", "")
            for alias in {t["name"], *t.get("aliases", [])}:
                self.team_aliases.setdefault(fold(alias), set()).add(t["name"])
        self.comp_aliases = {fold(a): c for c, aliases in COMPETITIONS.items() for a in [*aliases, c]}
        # Longest aliases first so "manchester united" wins over "united".
        self._player_keys = sorted(self.player_aliases, key=len, reverse=True)
        self._team_keys = sorted(self.team_aliases, key=len, reverse=True)
        self._fuzzy_players = [a for a in self.player_aliases if " " not in a and len(a) >= 5]

    @classmethod
    def load(cls, path: Path) -> "Gazetteer":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data.get("players", []), data.get("teams", []))

    @staticmethod
    def _find(text: str, keys: list[str], table: dict[str, set[str]]) -> tuple[set[str], str]:
        """Match aliases on word boundaries, longest first, blanking out each match."""
        found: set[str] = set()
        for key in keys:
            pattern = rf"(?<![\w]){re.escape(key)}(?![\w])"
            if re.search(pattern, text):
                candidates = table[key]
                # An ambiguous alias is kept as one combined token so two questions
                # naming the same ambiguous surname still compare equal.
                found.add(next(iter(candidates)) if len(candidates) == 1 else "|".join(sorted(candidates)))
                text = re.sub(pattern, " ", text)
        return found, text

    def extract(self, question: str) -> Entities:
        text = fold(question)
        text = re.sub(r"(\w)'s\b", r"\1", text)  # "Haaland's" -> "Haaland"

        seasons: set[str] = set()
        for m in re.finditer(r"\b(20\d{2})\s*[-/]\s*(\d{2,4})\b", text):
            start = int(m.group(1))
            seasons.add(f"{start}-{str(start + 1)[2:]}")
        if any(p in text for p in THIS_SEASON_PHRASES):
            seasons.add(CURRENT_SEASON)
        if any(p in text for p in LAST_SEASON_PHRASES):
            seasons.add(PREVIOUS_SEASON)

        competitions: set[str] = set()
        for alias in sorted(self.comp_aliases, key=len, reverse=True):
            pattern = rf"(?<![\w]){re.escape(alias)}(?![\w])"
            if re.search(pattern, text):
                competitions.add(self.comp_aliases[alias])
                text = re.sub(pattern, " ", text)

        teams, text = self._find(text, self._team_keys, self.team_aliases)
        players, text = self._find(text, self._player_keys, self.player_aliases)

        # Fuzzy pass for misspelt single-word player names ("mbape", "halaand").
        for token in re.findall(r"[a-z]{5,}", text):
            if token in FUZZY_STOPWORDS:
                continue
            best, best_score = None, 0.0
            for alias in self._fuzzy_players:
                if abs(len(alias) - len(token)) > 2:
                    continue
                score = fuzz.ratio(token, alias)
                if score > best_score:
                    best, best_score = alias, score
            if best and best_score >= 85:
                candidates = self.player_aliases[best]
                players.add(next(iter(candidates)) if len(candidates) == 1 else "|".join(sorted(candidates)))

        return Entities(frozenset(players), frozenset(teams), frozenset(competitions), frozenset(seasons))

    def verified_team(self, player: str) -> str | None:
        return self.player_team.get(player)

    def resolve_team(self, mention: str) -> set[str]:
        return self.team_aliases.get(fold(mention).strip(), set())
