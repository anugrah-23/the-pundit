"""Common names fans use for Top 5 clubs, keyed by the team name Understat uses.

Aliases that are ambiguous on their own ("United", "City", "Real") are deliberately left out:
the entity guard would rather miss a team than match the wrong one.
"""

# Nicknames and short forms for players, keyed by the name Understat uses. Surnames are added
# automatically; this is only for names fans use that can't be derived. Entries for players not in
# the season's data are ignored.
PLAYER_ALIASES: dict[str, list[str]] = {
    "Kylian Mbappe-Lottin": ["Mbappe", "Kylian Mbappe", "Kylian"],
    "Vinícius Júnior": ["Vinicius", "Vini Jr", "Vini"],
    "Khvicha Kvaratskhelia": ["Kvara", "Kvaradona"],
    "Trent Alexander-Arnold": ["Trent", "TAA"],
    "Lautaro Martínez": ["Lautaro"],
    "Lamine Yamal": ["Lamine"],
    "Erling Haaland": ["Erling"],
    "Bukayo Saka": ["Bukayo", "Saka"],
    "Jude Bellingham": ["Jude"],
    "Harry Kane": ["Harry Kane"],
    "Mohamed Salah": ["Mo Salah", "Egyptian King"],
    "Robert Lewandowski": ["Lewa"],
    "Rafael Leão": ["Leao"],
    "Ousmane Dembélé": ["Dembele"],
    "Victor Osimhen": ["Osimhen"],
}

TEAM_ALIASES: dict[str, list[str]] = {
    # Premier League
    "Arsenal": ["gunners", "afc"],
    "Aston Villa": ["villa", "avfc"],
    "Bournemouth": ["cherries", "afc bournemouth"],
    "Brentford": ["bees"],
    "Brighton": ["brighton and hove albion", "brighton & hove albion", "seagulls"],
    "Burnley": ["clarets"],
    "Chelsea": ["blues", "cfc"],
    "Crystal Palace": ["palace", "eagles"],
    "Everton": ["toffees"],
    "Fulham": ["cottagers"],
    "Leeds": ["leeds united"],
    "Liverpool": ["lfc", "reds", "pool"],
    "Manchester City": ["man city", "mcfc", "citizens", "cityzens"],
    "Manchester United": ["man utd", "man united", "manchester utd", "mufc", "red devils"],
    "Newcastle United": ["newcastle", "nufc", "magpies", "toon"],
    "Nottingham Forest": ["forest", "nottm forest", "nffc"],
    "Sunderland": ["black cats"],
    "Tottenham": ["spurs", "tottenham hotspur", "thfc"],
    "West Ham": ["west ham united", "hammers", "irons"],
    "Wolverhampton Wanderers": ["wolves"],
    # La Liga
    "Real Madrid": ["madrid", "los blancos", "rmcf"],
    "Barcelona": ["barca", "barça", "fc barcelona", "blaugrana"],
    "Atletico Madrid": ["atletico", "atleti", "atlético madrid", "atlético de madrid"],
    "Athletic Club": ["athletic bilbao", "bilbao"],
    "Real Sociedad": ["la real", "sociedad"],
    "Real Betis": ["betis"],
    "Villarreal": ["yellow submarine"],
    "Sevilla": ["sevilla fc"],
    "Valencia": ["los che"],
    "Celta Vigo": ["celta"],
    "Rayo Vallecano": ["rayo"],
    # Serie A
    "Inter": ["inter milan", "internazionale", "nerazzurri"],
    "AC Milan": ["milan", "rossoneri"],
    "Juventus": ["juve", "old lady", "bianconeri"],
    "Napoli": ["partenopei"],
    "Roma": ["as roma", "giallorossi"],
    "Lazio": ["ss lazio", "biancocelesti"],
    "Atalanta": ["la dea"],
    "Fiorentina": ["viola"],
    "Bologna": ["rossoblu"],
    "Torino": ["toro"],
    # Bundesliga
    "Bayern Munich": ["bayern", "bayern munchen", "bayern münchen", "fcb bayern"],
    "Borussia Dortmund": ["dortmund", "bvb"],
    "Bayer Leverkusen": ["leverkusen", "bayer 04"],
    "RasenBallsport Leipzig": ["rb leipzig", "leipzig", "rbl"],
    "Eintracht Frankfurt": ["frankfurt", "eintracht"],
    "VfB Stuttgart": ["stuttgart"],
    "Borussia M.Gladbach": ["gladbach", "monchengladbach", "mönchengladbach", "borussia monchengladbach"],
    "Wolfsburg": ["vfl wolfsburg"],
    "Freiburg": ["sc freiburg"],
    "Werder Bremen": ["bremen", "werder"],
    "Union Berlin": ["union", "fc union berlin"],
    # Ligue 1
    "Paris Saint Germain": ["psg", "paris sg", "paris saint-germain", "paris"],
    "Marseille": ["om", "olympique marseille", "olympique de marseille"],
    "Lyon": ["ol", "olympique lyonnais", "olympique lyon"],
    "Monaco": ["as monaco"],
    "Lille": ["losc", "lille osc"],
    "Nice": ["ogc nice"],
    "Lens": ["rc lens"],
    "Rennes": ["stade rennais"],
}
