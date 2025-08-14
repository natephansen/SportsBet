# league/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Bet
from .sevices import recompute_team_parlay

@receiver(post_save, sender=Bet)
def bet_saved(sender, instance: Bet, **kwargs):
    recompute_team_parlay(instance.team, instance.season.year, instance.week)

@receiver(post_delete, sender=Bet)
def bet_deleted(sender, instance: Bet, **kwargs):
    recompute_team_parlay(instance.team, instance.season.year, instance.week)
