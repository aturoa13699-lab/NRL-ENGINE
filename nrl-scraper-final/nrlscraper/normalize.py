"""
Team and Venue Normalization (SPEC-1).

Converts various name formats to canonical names.
"""

import re

# =============================================================================
# TEAM ALIASES -> CANONICAL
# =============================================================================

TEAM_ALIASES: dict[str, list[str]] = {
    'Brisbane Broncos': ['broncos', 'brisbane'],
    'Canberra Raiders': ['raiders', 'canberra'],
    'Canterbury Bulldogs': [
        'bulldogs',
        'canterbury',
        'canterbury bankstown',
        'canterbury-bankstown',
        'canterbury bankstown bulldogs',
    ],
    'Cronulla Sharks': [
        'sharks',
        'cronulla',
        'cronulla sutherland',
        'cronulla-sutherland',
        'cronulla sutherland sharks',
    ],
    'Dolphins': ['dolphins', 'the dolphins', 'redcliffe', 'redcliffe dolphins'],
    'Gold Coast Titans': ['titans', 'gold coast'],
    'Manly Sea Eagles': [
        'sea eagles',
        'manly',
        'manly warringah',
        'manly-warringah',
        'manly warringah sea eagles',
    ],
    'Melbourne Storm': ['storm', 'melbourne'],
    'Newcastle Knights': ['knights', 'newcastle'],
    'New Zealand Warriors': [
        'warriors',
        'new zealand',
        'nz warriors',
        'auckland warriors',
    ],
    'North Queensland Cowboys': [
        'cowboys',
        'north queensland',
        'north qld',
        'nth qld',
        'nq cowboys',
    ],
    'Parramatta Eels': ['eels', 'parramatta', 'parra'],
    'Penrith Panthers': ['panthers', 'penrith'],
    'South Sydney Rabbitohs': [
        'rabbitohs',
        'south sydney',
        'souths',
        'bunnies',
    ],
    'St George Illawarra Dragons': [
        'dragons',
        'st george',
        'st george illawarra',
        'st geo illa',
        'sgi',
        'saints',
    ],
    'Sydney Roosters': [
        'roosters',
        'sydney',
        'eastern suburbs',
        'easts',
        'sydney city roosters',
    ],
    'Wests Tigers': ['tigers', 'wests tigers', 'wests', 'west tigers'],
}

# =============================================================================
# VENUE ALIASES -> CANONICAL
# =============================================================================

VENUE_ALIASES: dict[str, list[str]] = {
    'Suncorp Stadium': ['suncorp', 'suncorp stadium', 'lang park', 'brisbane stadium'],
    'Accor Stadium': [
        'accor',
        'accor stadium',
        'stadium australia',
        'anz stadium',
        'homebush',
        'olympic stadium',
        'telstra stadium',
    ],
    'AAMI Park': ['aami', 'aami park', 'melbourne rectangular'],
    'CommBank Stadium': [
        'commbank',
        'commbank stadium',
        'bankwest',
        'bankwest stadium',
        'parramatta stadium',
        'western sydney stadium',
    ],
    '4 Pines Park': [
        '4 pines',
        '4 pines park',
        'brookvale',
        'brookvale oval',
        'lottoland',
    ],
    'BlueBet Stadium': [
        'bluebet',
        'bluebet stadium',
        'penrith stadium',
        'panthers stadium',
        'pepper stadium',
        'penrith park',
    ],
    'PointsBet Stadium': [
        'pointsbet',
        'pointsbet stadium',
        'sharks stadium',
        'shark park',
        'southern cross group stadium',
        'toyota stadium',
    ],
    'McDonald Jones Stadium': [
        'mcdonald jones',
        'mcdonald jones stadium',
        'mcd jones',
        'newcastle stadium',
        'hunter stadium',
        'energyaustralia stadium',
    ],
    'Queensland Country Bank Stadium': [
        'qld country bank',
        'queensland country bank stadium',
        'qcb stadium',
        'qcb',
        'townsville stadium',
        '1300smiles',
        '1300smiles stadium',
        'dairy farmers',
    ],
    'Cbus Super Stadium': [
        'cbus',
        'cbus super stadium',
        'robina',
        'robina stadium',
        'skilled park',
        'metricon stadium',
        'heritage bank stadium',
    ],
    'Go Media Stadium': [
        'go media',
        'go media stadium',
        'mt smart',
        'mt smart stadium',
        'auckland',
        'ericsson stadium',
    ],
    'GIO Stadium': ['gio', 'gio stadium', 'canberra stadium', 'bruce stadium'],
    'WIN Stadium': ['win', 'win stadium', 'wollongong', 'wollongong showground'],
    'Netstrata Jubilee Stadium': [
        'netstrata',
        'netstrata jubilee',
        'netstrata jubilee stadium',
        'kogarah',
        'kogarah oval',
        'jubilee oval',
        'oki jubilee',
    ],
    'Campbelltown Stadium': [
        'campbelltown',
        'campbelltown stadium',
        'campbelltown sports stadium',
    ],
    'Leichhardt Oval': ['leichhardt', 'leichhardt oval'],
    'Allianz Stadium': [
        'allianz',
        'allianz stadium',
        'sfs',
        'sydney football stadium',
        'moore park',
    ],
    'Allegiant Stadium': ['allegiant', 'allegiant stadium', 'las vegas'],
    'Kayo Stadium': ['kayo', 'kayo stadium'],
    'Belmore Sports Ground': ['belmore', 'belmore oval', 'belmore sports ground'],
}


def _canonize(s: str) -> str:
    """Normalize string for lookup: lowercase, remove punctuation, collapse spaces."""
    s = s.lower()
    s = re.sub(r'[^a-z0-9\s]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _make_reverse_map(aliases: dict[str, list[str]]) -> dict[str, str]:
    """Build reverse lookup from aliases to canonical names."""
    result: dict[str, str] = {}
    for canonical, aka_list in aliases.items():
        # Map canonical to itself
        result[_canonize(canonical)] = canonical
        # Map each alias to canonical
        for alias in aka_list:
            result[_canonize(alias)] = canonical
    return result


# Build lookup maps once at import
TEAM_MAP = _make_reverse_map(TEAM_ALIASES)
VENUE_MAP = _make_reverse_map(VENUE_ALIASES)


def normalize_team(s: str) -> str:
    """
    Normalize team name to canonical format.

    Args:
        s: Raw team name

    Returns:
        Canonical team name, or original if not found
    """
    if not s:
        return s
    key = _canonize(s)
    return TEAM_MAP.get(key, s.strip())


def normalize_venue(s: str) -> str | None:
    """
    Normalize venue name to canonical format.

    Args:
        s: Raw venue name

    Returns:
        Canonical venue name, or original if not found
    """
    if not s:
        return None
    key = _canonize(s)
    return VENUE_MAP.get(key, s.strip())


def get_all_teams() -> list[str]:
    """Get sorted list of all canonical team names."""
    return sorted(TEAM_ALIASES.keys())


def get_all_venues() -> list[str]:
    """Get sorted list of all canonical venue names."""
    return sorted(VENUE_ALIASES.keys())
