from pathlib import Path

import pandas as pd

from nba_forecast import live


def test_nba_team_signings_reads_signed_on_rows(monkeypatch):
    page = """
    <table>
      <tr><td class="primary"><a href="/player/1629605/tacko-fall/">Tacko Fall</a></td>
          <td> C </td><td>Signed on 09/01/26</td></tr>
      <tr><td class="primary"><a href="/player/203484/kentavious-caldwell-pope/">Kentavious Caldwell-Pope</a></td>
          <td> G </td><td>Signed on 08/05/26</td></tr>
      <tr><td class="primary"><a href="/player/1643148/saint-thomas/">Saint Thomas</a></td>
          <td> F </td><td>Signed on 09/26/25</td></tr>
    </table>
    """
    monkeypatch.setattr(live, "_get_text", lambda *args, **kwargs: page)

    rows = live._nba_team_signings("PHI")

    assert {(row["player_id"], row["transaction_date"]) for row in rows} == {
        ("1629605", "2026-09-01"),
        ("203484", "2026-08-05"),
    }
    tacko = next(row for row in rows if row["player_id"] == "1629605")
    assert tacko["transaction_type"] == "Signing"
    assert tacko["source"] == "NBA.com team roster"


def test_transaction_ledger_prefers_official_signing_source(tmp_path: Path):
    movement = pd.DataFrame([{
        "transaction_type": "Signing",
        "transaction_date": "2026-09-01",
        "description": "Philadelphia signed Tacko Fall",
        "team_abbr": "PHI",
        "player_id": "1629605",
        "player_slug": "tacko-fall",
        "group_sort": "Signing 1629605",
        "source": "NBA player movement feed",
        "source_url": live.NBA_MOVEMENT_URL,
    }])
    roster = movement.assign(
        description="Signed Tacko Fall (NBA.com roster signing date)",
        group_sort="NBA roster signing 1629605",
        source="NBA.com team roster",
        source_url="https://www.nba.com/team/1610612755",
    )

    result = live._update_transaction_ledger(tmp_path, pd.concat([movement, roster], ignore_index=True))

    tacko = result[result["player_id"].astype(str).eq("1629605")]
    assert len(tacko) == 1
    assert tacko.iloc[0]["source"] == "NBA.com team roster"
    assert (tmp_path / "transaction_ledger.csv").exists()
