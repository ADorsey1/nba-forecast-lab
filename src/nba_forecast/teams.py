"""Canonical team abbreviations and conference membership for the current league."""
EAST = frozenset({'ATL', 'BOS', 'BRK', 'CHO', 'CHI', 'CLE', 'DET', 'IND', 'MIA', 'MIL', 'NYK', 'ORL', 'PHI', 'TOR', 'WAS'})
WEST = frozenset({'DAL', 'DEN', 'GSW', 'HOU', 'LAC', 'LAL', 'MEM', 'MIN', 'NOP', 'OKC', 'PHO', 'POR', 'SAC', 'SAS', 'UTA'})
TEAMS = EAST | WEST
CONFERENCES = {**dict.fromkeys(EAST, 'East'), **dict.fromkeys(WEST, 'West')}


def conference_for(team: str) -> str:
    """Reject unknown codes rather than silently assigning them to the West."""
    try:
        return CONFERENCES[team]
    except KeyError as error:
        raise ValueError(f'Unknown NBA team: {team}') from error
