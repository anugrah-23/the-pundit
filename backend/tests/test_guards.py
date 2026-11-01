import pytest

from app.cache import has_negation
from app.entities import CURRENT_SEASON, PREVIOUS_SEASON


@pytest.mark.parametrize("q", [
    "Has Mori not scored this season?",
    "why didn't Riverside win",
    "Ekwueme goal adikala ah?",          # Tanglish: didn't score?
    "Mori ne goal nahi kiya kya",        # Hinglish
    "Northgate ku win kidaiyadhu",       # Tanglish
    "no goals for Diallo?",
])
def test_negation_detected(q):
    assert has_negation(q)


@pytest.mark.parametrize("q", [
    "How many goals has Mori scored?",
    "no of goals by Ekwueme",
    "no. of assists Lucas Silva",
    "Ekwueme evlo goal adichaan?",
    "Riverside ka xG kitna hai",
    "Kerala Blasters fans asking about Mori",
])
def test_negation_not_detected(q):
    assert not has_negation(q)


def test_extract_player_team_season(gazetteer):
    e = gazetteer.extract("How many goals has Tomas Ekwueme scored for Riverside United this season?")
    assert e.players == {"Tomas Ekwueme"}
    assert e.teams == {"Riverside United"}
    assert e.seasons == {CURRENT_SEASON}


def test_surname_and_possessive(gazetteer):
    assert gazetteer.extract("Ekwueme's xG?").players == {"Tomas Ekwueme"}


def test_ambiguous_surname_is_one_combined_token(gazetteer):
    e = gazetteer.extract("Silva assists")
    assert e.players == {"Lucas Silva|Rafael Silva"}
    assert gazetteer.extract("Lucas Silva assists").players == {"Lucas Silva"}


def test_fuzzy_misspelling(gazetteer):
    assert gazetteer.extract("how many goals for ekwume").players == {"Tomas Ekwueme"}


def test_competition_and_last_season(gazetteer):
    e = gazetteer.extract("Mori goals in the EPL last season")
    assert e.competitions == {"ENG-Premier League"}
    assert e.seasons == {PREVIOUS_SEASON}


def test_explicit_season_formats(gazetteer):
    assert gazetteer.extract("Mori 2025/26").seasons == {"2025-26"}
    assert gazetteer.extract("Mori 2026-2027").seasons == {"2026-27"}


def test_entity_diff_defaults_to_current_season(gazetteer):
    a = gazetteer.extract("Mori goals")
    b = gazetteer.extract("Mori goals this season")
    assert a.differs_from(b) is None
    c = gazetteer.extract("Mori goals last season")
    assert a.differs_from(c) == "seasons"
    d = gazetteer.extract("Ekwueme goals")
    assert a.differs_from(d) == "players"
