# Register your models here.
from django.contrib import admin
from django.utils import timezone
from .models import Season, Team, TeamMembership, Bet, TeamParlay
from .sevices import recompute_team_parlay

# ---------- Admin actions ----------
def _affected_groups(qs):
    """
    Return distinct (team_id, season_year, week) triplets for a queryset of Bets.
    We pull season__year so we don't need to re-fetch Season objects later.
    """
    return list(qs.values_list("team_id", "season__year", "week").distinct())

def _recompute_from_groups(groups):
    teams = {t.id: t for t in Team.objects.filter(id__in=[g[0] for g in groups])}
    for team_id, season_year, week in groups:
        recompute_team_parlay(teams[team_id], season_year, week)

@admin.action(description="Mark selected bets WON")
def mark_won(modeladmin, request, queryset):
    groups = _affected_groups(queryset)            # collect BEFORE update()
    n = queryset.update(status="WON", settled_at=timezone.now())
    _recompute_from_groups(groups)
    modeladmin.message_user(request, f"Marked {n} bets as WON and updated affected parlays.")

@admin.action(description="Mark selected bets LOST")
def mark_lost(modeladmin, request, queryset):
    groups = _affected_groups(queryset)
    n = queryset.update(status="LOST", settled_at=timezone.now())
    _recompute_from_groups(groups)
    modeladmin.message_user(request, f"Marked {n} bets as LOST and updated affected parlays.")

@admin.action(description="Mark selected bets PENDING")
def mark_pending(modeladmin, request, queryset):
    groups = _affected_groups(queryset)
    n = queryset.update(status="PENDING", settled_at=None)
    _recompute_from_groups(groups)
    modeladmin.message_user(request, f"Marked {n} bets as PENDING and updated affected parlays.")

@admin.action(description="Mark selected bets PUSH")
def mark_push(modeladmin, request, queryset):
    groups = _affected_groups(queryset)
    n = queryset.update(status="PUSH", settled_at=timezone.now())
    _recompute_from_groups(groups)
    modeladmin.message_user(request, f"Marked {n} bets as PUSH and updated parlays.")


@admin.action(description="Recompute parlay odds from selected legs")
def recompute_parlay_odds(modeladmin, request, queryset):
    from .models import Bet
    updated = 0
    for p in queryset:
        legs = Bet.objects.filter(team=p.team, season=p.season, week=p.week, parlay_selected=True)
        dec = 1.0
        for b in legs:
            dec *= b.decimal_odds
        p.decimal_odds = round(dec, 4)
        p.save(update_fields=["decimal_odds"])
        updated += 1
    modeladmin.message_user(request, f"Recomputed odds for {updated} parlays.")

@admin.action(description="Set parlay status from legs (LOST if any LOST; WON if ≥1 WON and none pending/lost; PUSH if all PUSH)")
def settle_parlay_from_legs(modeladmin, request, queryset):
    from .models import Bet
    updated = 0
    for p in queryset:
        legs = list(Bet.objects.filter(team=p.team, season=p.season, week=p.week, parlay_selected=True))
        if any(l.status == "LOST" for l in legs):
            p.status = "LOST"
        elif any(l.status == "PENDING" for l in legs) or not legs:
            p.status = "PENDING"
        elif any(l.status == "WON" for l in legs):
            p.status = "WON"
        elif all(l.status == "PUSH" for l in legs):
            p.status = "PUSH"
        else:
            p.status = "PENDING"
        # also recompute odds product with pushes = 1.0
        dec = 1.0
        for l in legs:
            if l.status == "WON":
                dec *= l.decimal_odds
        p.decimal_odds = round(dec, 4)
        p.save(update_fields=["status", "decimal_odds"])
        updated += 1
    modeladmin.message_user(request, f"Updated {updated} parlays from legs.")
    
@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ("year", "start_date", "end_date")
    ordering = ("-year",)

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "season")
    list_filter = ("season",)

@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "team", "joined_at")
    list_filter = ("team__season", "team")

@admin.register(Bet)
class BetAdmin(admin.ModelAdmin):
    list_display = ("user","team","season","week","bet_type","pick_text","line",
                    "american_odds","parlay_selected","status","settled_at")
    list_filter = ("season","team","week","bet_type","status","parlay_selected")
    search_fields = ("user__username","pick_text")
    actions = [mark_won, mark_lost, mark_pending, mark_push]

@admin.register(TeamParlay)
class TeamParlayAdmin(admin.ModelAdmin):
    list_display = ("team", "season", "week", "decimal_odds", "stake_units", "status", "updated_at")
    list_filter = ("season", "team", "week", "status")
    actions = [recompute_parlay_odds, settle_parlay_from_legs, mark_won, mark_lost, mark_pending]
