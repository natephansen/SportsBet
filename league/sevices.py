from functools import reduce
from operator import mul
from .models import Bet, TeamParlay, Team, Season
from decimal import Decimal
from django.db import transaction

def american_to_decimal(odds: int) -> Decimal:
    if odds is None:
        return Decimal("1")
    return Decimal("1") + (Decimal(odds) / Decimal("100")) if odds >= 100 \
           else Decimal("1") + (Decimal("100") / Decimal(abs(odds)))

@transaction.atomic
def recompute_team_parlay(team, season_year: int, week: int) -> TeamParlay:
    season = team.season if getattr(team, "season_id", None) else Season.objects.get(year=season_year)

    legs = list(Bet.objects.filter(
        team=team, season=season, week=week, parlay_selected=True
    ).select_related("team", "season"))

    parlay, _ = TeamParlay.objects.get_or_create(team=team, season=season, week=week)

    # (A) BOOKED price: product of ALL legs’ quoted prices (sportsbook-style),
    #     regardless of status. This is what we ALWAYS show.
    dec_all = Decimal("1")
    for b in legs:
        try:
            dec_all *= american_to_decimal(int(b.american_odds))
        except Exception:
            # be defensive if odds are missing
            dec_all *= Decimal("1")

    parlay.decimal_odds = float(round(dec_all, 4))  # <- THIS is the one you display

    # (B) Status logic (unchanged semantics)
    lost = any(l.status == "LOST" for l in legs)
    pending = any(l.status == "PENDING" for l in legs)
    all_push = len(legs) > 0 and all(l.status == "PUSH" for l in legs)

    if not legs:
        parlay.status = "PENDING"
    elif lost:
        parlay.status = "LOST"
    elif pending:
        parlay.status = "PENDING"
    elif all_push:
        parlay.status = "PUSH"
    else:
        # no lost, no pending, and not all push -> at least one WON (others may be PUSH)
        parlay.status = "WON"

    parlay.save()
    return parlay
