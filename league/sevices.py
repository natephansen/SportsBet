from functools import reduce
from operator import mul
from .models import Bet, TeamParlay,Team, Season
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

    # Compute product of non-push legs (push contributes 1.0)
    dec = Decimal("1")
    pending = lost = won = push = 0
    for b in legs:
        if b.status == "PENDING":
            pending += 1
        elif b.status == "LOST":
            lost += 1
        elif b.status == "WON":
            won += 1
            dec *= american_to_decimal(int(b.american_odds))
        elif b.status == "PUSH":
            push += 1
            # multiply by 1 → no change
        else:
            # treat unknown as pending
            pending += 1

    parlay.decimal_odds = float(round(dec, 4))  # stake stays as-is

    # Status rules:
    # - any LOST → LOST
    # - else any PENDING → PENDING
    # - else if won >= 1 → WON (with reduced legs if any PUSH)
    # - else if push == len(legs) and len(legs) > 0 → PUSH (full refund)
    # - else if no legs selected → PENDING (not formed yet)
    if lost >= 1:
        parlay.status = "LOST"
    elif pending >= 1:
        parlay.status = "PENDING"
    elif len(legs) == 0:
        parlay.status = "PENDING"
    elif won >= 1:
        parlay.status = "WON"
    elif push == len(legs):
        parlay.status = "PUSH"
    else:
        parlay.status = "PENDING"

    parlay.save()
    return parlay