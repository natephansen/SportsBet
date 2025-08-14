# Create your views here.
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Season, TeamMembership, Bet, TeamParlay
from django.http import HttpResponseForbidden
from django import forms
from .sevices import recompute_team_parlay
from django.db.models import Sum, F, Case, When, FloatField, IntegerField
from django.db.models import Q
from .forms import BetSimpleForm
import json

class BetForm(forms.ModelForm):
    class Meta:
        model = Bet
        fields = ["pick_text", "line", "american_odds", "parlay_selected"]  # stake_units fixed at 1 for now

def home(request):
    seasons = Season.objects.order_by("-year")
    return render(request, "league/home.html", {"seasons": seasons})

def week_view(request, season_year: int, week: int):
    season = get_object_or_404(Season, year=season_year)

    # Always show all SETTLED bets (any team)
    q = Q(status__in=["WON", "LOST"])

    # If the user is on a team this season, also show their own team's PENDING bets
    membership = None
    if request.user.is_authenticated:
        membership = (
            TeamMembership.objects
            .filter(user=request.user, team__season=season)
            .select_related("team")
            .first()
        )
        if membership:
            q |= Q(status="PENDING", team=membership.team)

    bets = (
        Bet.objects
        .filter(season=season, week=week)
        .filter(q)
        .select_related("user", "team")
        .order_by("team__name", "user__username", "bet_type")
    )

    return render(request, "league/week.html", {
        "season": season, "week": week, "bets": bets,
    })

@login_required
def submit_pick(request, season_year: int, week: int):
    season = get_object_or_404(Season, year=season_year)
    membership = TeamMembership.objects.filter(user=request.user, team__season=season).select_related("team").first()
    if not membership:
        return HttpResponseForbidden("You are not assigned to a team for this season.")

    # build or load 3 forms, one per type
    bt_types = ["SPREAD", "TOTAL", "PROP"]
    instances = {bt: Bet.objects.filter(user=request.user, season=season, week=week, bet_type=bt).first()
                 for bt in bt_types}

    if request.method == "POST":
        forms = {}
        selected_count = 0
        for bt in bt_types:
            form = BetSimpleForm(request.POST, prefix=bt, instance=instances[bt], bet_type=bt)
            forms[bt] = form
            # count parlay selections across forms
            if form.data.get(f"{bt}-parlay_selected") == "on":
                selected_count += 1

        if selected_count > 1:
            return render(request, "league/submit_pick.html", {
                "season": season, "week": week, "forms": forms,
                "error": "Select exactly one bet to count toward the team parlay."
            })

        valid = all(f.is_valid() for f in forms.values())
        if valid:
            # save each form (create or update)
            saved = []
            for bt, form in forms.items():
                bet = form.save(commit=False)
                bet.user = request.user
                bet.team = membership.team
                bet.season = season
                bet.week = week
                bet.bet_type = bt
                # ensure only one selected; if none selected, all are False
                if selected_count == 0:
                    bet.parlay_selected = False
                else:
                    # set True only on the one whose checkbox is checked
                    bet.parlay_selected = (form.data.get(f"{bt}-parlay_selected") == "on")
                bet.save()
                saved.append(bet)

            # recompute parlay odds for the team this week
            recompute_team_parlay(membership.team, season_year, week)

            return redirect("week_view", season_year=season.year, week=week)

    else:
        forms = {bt: BetSimpleForm(prefix=bt, instance=instances[bt], bet_type=bt) for bt in bt_types}

    return render(request, "league/submit_pick.html", {
        "season": season, "week": week, "forms": forms
    })

def league_dashboard(request, season_year: int):
    season = get_object_or_404(Season, year=season_year)

    # ----- filter choices (populates dropdowns) -----
    weeks_bets    = set(Bet.objects.filter(season=season).values_list("week", flat=True).distinct())
    weeks_parlays = set(TeamParlay.objects.filter(season=season).values_list("week", flat=True).distinct())
    filter_weeks  = sorted(weeks_bets | weeks_parlays)

    filter_users  = User.objects.filter(bets__season=season).distinct().order_by("username")
    filter_teams  = season.teams.order_by("name")

    # ----- selected filters from query string -----
    sel_week   = request.GET.get("week", "").strip()
    sel_user   = request.GET.get("user", "").strip()
    sel_team   = request.GET.get("team", "").strip()    # team id
    sel_parlay = request.GET.get("parlay", "").strip()  # '', 'yes', 'no'

    # ----- base querysets -----
    bets = (Bet.objects
            .filter(season=season)
            .exclude(status="PENDING")
            .select_related("team", "user"))

    parlays = (TeamParlay.objects
               .filter(season=season)
               .exclude(status="PENDING")
               .select_related("team"))

    # ----- apply filters -----
    if sel_week:
        try:
            w = int(sel_week)
            bets    = bets.filter(week=w)
            parlays = parlays.filter(week=w)
        except ValueError:
            pass

    if sel_user:
        bets = bets.filter(user__username=sel_user)

    if sel_team:
        try:
            t_id = int(sel_team)
            bets    = bets.filter(team_id=t_id)
            parlays = parlays.filter(team_id=t_id)
        except ValueError:
            pass

    if sel_parlay == "yes":
        bets = bets.filter(parlay_selected=True)
    elif sel_parlay == "no":
        bets = bets.filter(parlay_selected=False)
    # else '' (All): no filter

    bets    = bets.order_by("week", "team__name", "user__username", "bet_type")
    parlays = parlays.order_by("week", "team__name")

    return render(request, "league/dashboard.html", {
        "season": season,
        "bets": bets,
        "parlays": parlays,

        # filter widgets
        "filter_weeks": filter_weeks,
        "filter_users": filter_users,
        "filter_teams": filter_teams,
        "sel_week": sel_week,
        "sel_user": sel_user,
        "sel_team": sel_team,
        "sel_parlay": sel_parlay,
    })

def standings(request, season_year: int):
    season = get_object_or_404(Season, year=season_year)

    # ---------- existing tables (unchanged) ----------
    indiv = (
        Bet.objects.filter(season=season).exclude(status="PENDING")
        .values("user__username")
        .annotate(
            units=Sum(
                Case(
                    When(status="WON", then=(F("stake_units") * ((Case(
                        When(american_odds__gte=100, then=(1 + F("american_odds") / 100.0)),
                        default=(1 + 100.0 / (F("american_odds") * -1.0))
                    )) - 1.0)) ),
                    When(status="LOST", then=(-1.0 * F("stake_units"))),
                    default=0.0, output_field=FloatField(),
                )
            )
        )
        .order_by("-units")
    )

    parlay_units = (
        TeamParlay.objects.filter(season=season).exclude(status="PENDING")
        .values("team__id")
        .annotate(
            units=Sum(
                Case(
                    When(status="WON", then=(F("stake_units") * (F("decimal_odds") - 1.0))),
                    When(status="LOST", then=(-1.0 * F("stake_units"))),
                    default=0.0, output_field=FloatField(),
                )
            )
        )
    )
    parlay_map = {row["team__id"]: row["units"] for row in parlay_units}

    team_units = (
        season.teams.all()
        .annotate(
            indiv_units=Sum(
                Case(
                    When(bets__status="WON", then=(F("bets__stake_units") * (
                        Case(
                            When(bets__american_odds__gte=100, then=(1 + F("bets__american_odds") / 100.0)),
                            default=(1 + 100.0 / (F("bets__american_odds") * -1.0))
                        ) - 1.0
                    ))),
                    When(bets__status="LOST", then=(-1.0 * F("bets__stake_units"))),
                    default=0.0, output_field=FloatField(),
                )
            )
        )
    )
    teams = []
    for t in team_units:
        pu = parlay_map.get(t.id, 0.0)
        total = (t.indiv_units or 0.0) + pu
        teams.append({"team": t, "indiv_units": t.indiv_units or 0.0, "parlay_units": pu, "total_units": total})
    teams.sort(key=lambda x: x["total_units"], reverse=True)

    # ---------- charts: build weekly cumulative series ----------
    # Weeks to plot (1..18 regular season)
    weeks = list(range(1, 19))

    # Per-bet PnL expression (same logic as above)
    bet_pnl_expr = Case(
        When(status="WON", then=(F("stake_units") * (
            Case(
                When(american_odds__gte=100, then=(1 + F("american_odds") / 100.0)),
                default=(1 + 100.0 / (F("american_odds") * -1.0))
            ) - 1.0
        ))),
        When(status="LOST", then=(-1.0 * F("stake_units"))),
        default=0.0, output_field=FloatField(),
    )

    # ---- Team totals by week (indiv + parlay) ----
    indiv_by_team_week = (
        Bet.objects.filter(season=season).exclude(status="PENDING")
        .values("team__id", "team__name", "week")
        .annotate(units=Sum(bet_pnl_expr))
    )
    parlay_by_team_week = (
        TeamParlay.objects.filter(season=season).exclude(status="PENDING")
        .values("team__id", "team__name", "week")
        .annotate(
            units=Sum(
                Case(
                    When(status="WON", then=(F("stake_units") * (F("decimal_odds") - 1.0))),
                    When(status="LOST", then=(-1.0 * F("stake_units"))),
                    default=0.0, output_field=FloatField(),
                )
            )
        )
    )

    # Build dict: team_name -> {week -> total_units_that_week}
    team_week_delta = {}
    for row in indiv_by_team_week:
        team_week_delta.setdefault(row["team__name"], {}).setdefault(row["week"], 0.0)
        team_week_delta[row["team__name"]][row["week"]] += float(row["units"] or 0.0)
    for row in parlay_by_team_week:
        team_week_delta.setdefault(row["team__name"], {}).setdefault(row["week"], 0.0)
        team_week_delta[row["team__name"]][row["week"]] += float(row["units"] or 0.0)

    # Convert to cumulative series per team across all weeks
    team_series = []
    for team in season.teams.order_by("name"):
        name = team.name
        cum = 0.0
        data = []
        wk_map = team_week_delta.get(name, {})
        for w in weeks:
            cum += float(wk_map.get(w, 0.0))
            data.append(round(cum, 4))
        team_series.append({"label": name, "data": data})

    # ---- Individual (user) units by week ----
    user_by_week = (
        Bet.objects.filter(season=season).exclude(status="PENDING")
        .values("user__username", "week")
        .annotate(units=Sum(bet_pnl_expr))
    )

    user_week_delta = {}
    for row in user_by_week:
        user_week_delta.setdefault(row["user__username"], {})[row["week"]] = float(row["units"] or 0.0)

    user_series = []
    usernames = (
        Bet.objects.filter(season=season)
        .values_list("user__username", flat=True).distinct()
    )
    for uname in sorted(set(usernames)):
        cum = 0.0
        data = []
        wk_map = user_week_delta.get(uname, {})
        for w in weeks:
            cum += float(wk_map.get(w, 0.0))
            data.append(round(cum, 4))
        user_series.append({"label": uname, "data": data})

    # ---- determine last settled week (bets or parlays) ----
    settled_bet_weeks = set(
        Bet.objects.filter(season=season).exclude(status="PENDING")
        .values_list("week", flat=True).distinct()
    )
    settled_parlay_weeks = set(
        TeamParlay.objects.filter(season=season).exclude(status="PENDING")
        .values_list("week", flat=True).distinct()
    )
    last_settled_week = max(settled_bet_weeks | settled_parlay_weeks, default=0)

    # Weeks to plot = 1..last_settled_week (empty if nothing settled yet)
    weeks = [0] + list(range(1, last_settled_week + 1))

    # ---- charts: build weekly cumulative series (unchanged logic) ----
    bet_pnl_expr = Case(
        When(status="WON", then=(F("stake_units") * (
            Case(
                When(american_odds__gte=100, then=(1 + F("american_odds") / 100.0)),
                default=(1 + 100.0 / (F("american_odds") * -1.0))
            ) - 1.0
        ))),
        When(status="LOST", then=(-1.0 * F("stake_units"))),
        default=0.0, output_field=FloatField(),
    )

    indiv_by_team_week = (
        Bet.objects.filter(season=season).exclude(status="PENDING")
        .values("team__id", "team__name", "week")
        .annotate(units=Sum(bet_pnl_expr))
    )
    parlay_by_team_week = (
        TeamParlay.objects.filter(season=season).exclude(status="PENDING")
        .values("team__id", "team__name", "week")
        .annotate(
            units=Sum(
                Case(
                    When(status="WON", then=(F("stake_units") * (F("decimal_odds") - 1.0))),
                    When(status="LOST", then=(-1.0 * F("stake_units"))),
                    default=0.0, output_field=FloatField(),
                )
            )
        )
    )

    team_week_delta = {}
    for row in indiv_by_team_week:
        team_week_delta.setdefault(row["team__name"], {}).setdefault(row["week"], 0.0)
        team_week_delta[row["team__name"]][row["week"]] += float(row["units"] or 0.0)
    for row in parlay_by_team_week:
        team_week_delta.setdefault(row["team__name"], {}).setdefault(row["week"], 0.0)
        team_week_delta[row["team__name"]][row["week"]] += float(row["units"] or 0.0)

    team_series = []
    for team in season.teams.order_by("name"):
        name = team.name
        cum = 0.0
        data = []
        wk_map = team_week_delta.get(name, {})
        for w in weeks:           # <-- only up to last_settled_week
            cum += float(wk_map.get(w, 0.0))
            data.append(round(cum, 4))
        team_series.append({"label": name, "data": data})

    user_by_week = (
        Bet.objects.filter(season=season).exclude(status="PENDING")
        .values("user__username", "week")
        .annotate(units=Sum(bet_pnl_expr))
    )
    user_week_delta = {}
    for row in user_by_week:
        user_week_delta.setdefault(row["user__username"], {})[row["week"]] = float(row["units"] or 0.0)

    user_series = []
    usernames = Bet.objects.filter(season=season).values_list("user__username", flat=True).distinct()
    for uname in sorted(set(usernames)):
        cum = 0.0
        data = []
        wk_map = user_week_delta.get(uname, {})
        for w in weeks:           # <-- only up to last_settled_week
            cum += float(wk_map.get(w, 0.0))
            data.append(round(cum, 4))
        user_series.append({"label": uname, "data": data})
    
    from django.db.models import IntegerField, Count

    all_usernames = list(
        Bet.objects.filter(season=season)
            .values_list("user__username", flat=True)
            .distinct()
    )

    # Count weeks where a user had 3 settled bets and all 3 LOST
    stinker_raw = (
        Bet.objects.filter(season=season).exclude(status="PENDING")
            .values("user__username", "week")
            .annotate(
                total=Count("id"),
                lost=Sum(Case(When(status="LOST", then=1), default=0, output_field=IntegerField()))
            )
            .filter(total__gte=3, lost=3)
            .values("user__username")
            .annotate(stinks=Count("week"))
    )

    stinker_map = {row["user__username"]: row["stinks"] for row in stinker_raw}

    # Plot ALL users, defaulting to 0
    stinker_labels = sorted(all_usernames)
    stinker_data   = [int(stinker_map.get(u, 0)) for u in stinker_labels]
        

    return render(request, "league/standings.html", {
        "season": season,
        "teams": teams,
        "individuals": indiv,
        "chart_weeks": weeks,                 # may be []
        "team_chart_series": team_series,     # truncated to weeks
        "user_chart_series": user_series,     # truncated to weeks
        "last_settled_week": last_settled_week,
        "stinker_labels": stinker_labels,
        "stinker_data": stinker_data,
    })


def user_stats(request, username: str):
    user = get_object_or_404(User, username=username)
    bets = Bet.objects.filter(user=user).exclude(status="PENDING")
    biggest_hit = max((b.pnl_units for b in bets if b.pnl_units > 0), default=0.0)
    # Simple streak calc (improve later)
    streak = 0
    best_streak = 0
    for b in bets.order_by("created_at"):
        if b.status == "WON":
            streak += 1
            best_streak = max(best_streak, streak)
        elif b.status == "LOST":
            streak = 0
    return render(request, "league/user_stats.html", {"user_profile": user, "bets": bets, "biggest_hit": biggest_hit, "best_streak": best_streak})

def landing(request):
    """Send / straight to the latest season's dashboard (or admin if no season yet)."""
    season = Season.objects.order_by("-year").first()
    if season:
        return redirect("league_dashboard", season_year=season.year)
    # No seasons yet—send the admin (you can change this to a friendly page)
    return redirect("admin:index")

@login_required
def submit_pick_week_picker(request, season_year: int):
    season = get_object_or_404(Season, year=season_year)
    # ensure the user is on a team in this season
    on_team = TeamMembership.objects.filter(user=request.user, team__season=season).exists()
    if not on_team:
        return render(request, "league/submit_week_picker.html", {
            "season": season,
            "weeks": range(1, 19),
            "error": "You are not assigned to a team for this season.",
        })
    return render(request, "league/submit_week_picker.html", {
        "season": season,
        "weeks": range(1, 19),  # regular season weeks 1–18
    })