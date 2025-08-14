
# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import F, Q, Sum, Case, When, FloatField, Count
from django.core.exceptions import ValidationError

# Odds helpers
def american_to_decimal(american_odds: int) -> float:
    # +150 -> 2.50 ; -120 -> 1.8333
    if american_odds >= 100:
        return 1 + (american_odds / 100.0)
    elif american_odds <= -100:
        return 1 + (100.0 / abs(american_odds))
    else:
        raise ValueError("American odds must be >= +100 or <= -100")

class Season(models.Model):
    year = models.IntegerField(unique=True)  # e.g., 2025
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return str(self.year)

class Team(models.Model):
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="teams")
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ("season", "name")

    def __str__(self):
        return f"{self.name} ({self.season.year})"

class TeamMembership(models.Model):
    """Allows users to be on different teams each season."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    joined_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("user", "team")

    def __str__(self):
        return f"{self.user.username} -> {self.team}"

BET_STATUS = (
    ("PENDING", "Pending"),
    ("WON", "Won"),
    ("LOST", "Lost"),
    ("PUSH", "Push"),
)

BET_TYPE = (
    ("SPREAD", "Spread"),
    ("TOTAL", "Total"),
    ("PROP", "Player Prop"),
)

OVER_UNDER_CHOICES = (
    ("OVER", "Over"),
    ("UNDER", "Under"),
)

class Bet(models.Model):
    """One pick per user per NFL week (per season)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bets")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="bets")  # redundant but handy
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="bets")
    week = models.PositiveIntegerField()  # 1..18 regular season
    # free-text now; later replace with structured matchup model fed by an API
    bet_type = models.CharField(max_length=10, choices=BET_TYPE,default='SPREAD')
    pick_text = models.CharField(max_length=255)         # e.g., "KC -3.5 @ LAC"
    line = models.FloatField(help_text="Spread or total number (e.g., -3.5, 47.5)")
    american_odds = models.IntegerField(help_text="e.g., -110, +150")
    stake_units = models.FloatField(default=1.0)  # 1 unit per pick (adjust if you allow variable stakes)
    parlay_selected = models.BooleanField(default=False)        
    over_under = models.CharField(
        max_length=5,
        choices=OVER_UNDER_CHOICES,
        null=True,
        blank=True,
        help_text="Required for Totals/Player Props; leave empty for Spreads."
    )
    status = models.CharField(max_length=10, choices=BET_STATUS, default="PENDING")
    settled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    def clean(self):
        super().clean()
        if self.bet_type in ("TOTAL", "PROP") and not self.over_under:
            raise ValidationError({"over_under": "Select Over or Under for Totals/Player Props."})
        if self.bet_type == "SPREAD":
            # ignore any O/U accidentally sent
            self.over_under = None

    class Meta:
        unique_together = ("user", "season", "week", "bet_type")  # enforce one pick per week per user

    def __str__(self):
        return f"{self.user.username} W{self.week} {self.bet_type} {self.pick_text}"

    @property
    def decimal_odds(self) -> float:
        return american_to_decimal(self.american_odds)

    @property
    def potential_return_units(self) -> float:
        # stake * decimal_odds
        return self.stake_units * self.decimal_odds

    @property
    def pnl_units(self) -> float:
        if self.status == "WON":
            return self.stake_units * (self.decimal_odds - 1.0)  # profit only
        if self.status == "LOST":
            return -self.stake_units
        if self.status == "PUSH":
            return 0.0
        return 0.0  # pending

class TeamParlay(models.Model):
    """Represents the team parlay for a given week."""
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="parlays")
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="parlays")
    week = models.PositiveIntegerField()
    # cache odds for display; recompute when legs change if desired
    decimal_odds = models.FloatField(default=1.0)
    stake_units = models.FloatField(default=1.0)
    status = models.CharField(max_length=10, choices=BET_STATUS, default="PENDING")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("team", "season", "week")

    def __str__(self):
        return f"Parlay {self.team.name} W{self.week}"

    @property
    def pnl_units(self) -> float:
        if self.status == "WON":
            return self.stake_units * (self.decimal_odds - 1.0)
        if self.status == "LOST":
            return -self.stake_units
        return 0.0