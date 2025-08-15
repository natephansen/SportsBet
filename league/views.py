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
from django.db.models import Q, Count
from .forms import BetSimpleForm
import json
from django.contrib import messages
from django.conf import settings
from django.db.models import IntegerField, Count
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from django.utils import timezone

class BetForm(forms.ModelForm):
    class Meta:
        model = Bet
        fields = ["pick_text", "line", "american_odds", "parlay_selected"]  # stake_units fixed at 1 for now

def week_reveal_dt(season, week: int, hour: int = 13, minute: int = 0):
    """
    Reveal time for a given NFL week = Sunday 1:00pm ET.
    We anchor to the first Sunday on/after season.start_date, then add N-1 weeks.
    """
    base_date = season.start_date
    # Move to Sunday (weekday: Mon=0 ... Sun=6)
    sunday = base_date + timedelta(days=(6 - base_date.weekday()) % 7)
    return datetime.combine(sunday, time(hour, minute), tzinfo=ZoneInfo("America/New_York")) + timedelta(weeks=week - 1)

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
    membership = (
        TeamMembership.objects
        .filter(user=request.user, team__season=season)
        .select_related("team")
        .first()
    )
    if not membership:
        return HttpResponseForbidden("You are not assigned to a team for this season.")

    bt_types = ["SPREAD", "TOTAL", "PROP"]
    instances = {
        bt: Bet.objects.filter(user=request.user, season=season, week=week, bet_type=bt).first()
        for bt in bt_types
    }

    if request.method == "POST":
        forms = {
            bt: BetSimpleForm(request.POST, prefix=bt, instance=instances[bt], bet_type=bt)
            for bt in bt_types
        }

        # exactly 0 or 1 parlay may be checked; we'll set False if 0
        selected_count = sum(1 for bt in bt_types if request.POST.get(f"{bt}-parlay_selected") == "on")
        if selected_count > 1:
            return render(request, "league/submit_pick.html", {
                "season": season, "week": week, "forms": forms,
                "error": "Select at most one bet to include in the team parlay."
            })

        # STRICT: all three forms must be valid; otherwise nothing saves
        if all(f.is_valid() for f in forms.values()):
            for bt, form in forms.items():
                bet = form.save(commit=False)
                bet.user = request.user
                bet.team = membership.team
                bet.season = season
                bet.week = week
                bet.bet_type = bt
                bet.parlay_selected = (
                    request.POST.get(f"{bt}-parlay_selected") == "on"
                    if selected_count == 1 else False
                )
                bet.save()

            # recompute team parlay
            recompute_team_parlay(membership.team, season_year, week)

            messages.success(request, f"Picks saved for Week {week} ({season_year}).")
            return redirect("submit_pick_week_picker", season_year=season.year)
        else:
            return render(request, "league/submit_pick.html", {
                "season": season, "week": week, "forms": forms
            })
    else:
        forms = {
            bt: BetSimpleForm(prefix=bt, instance=instances[bt], bet_type=bt)
            for bt in bt_types
        }

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

    # ----- small helper: 1:00pm ET Sunday for given week -----
    def _week_reveal_dt(szn: Season, week: int, hour: int = 13, minute: int = 0):
        """
        Reveal time = first Sunday on/after season.start_date, + (week-1) weeks, at 1:00pm ET.
        """
        base = szn.start_date
        first_sunday = base + timedelta(days=(6 - base.weekday()) % 7)  # Mon=0..Sun=6
        return datetime.combine(first_sunday, time(hour, minute), tzinfo=ZoneInfo("America/New_York")) + timedelta(weeks=week - 1)

    # ----- base querysets (do NOT exclude pending yet) -----
    bets = (
        Bet.objects
        .filter(season=season)
        .select_related("team", "user")
    )
    parlays = (
        TeamParlay.objects
        .filter(season=season)
        .select_related("team")
    )

    # ----- reveal logic (only for a specific week) -----
    try:
        week_for_reveal = int(sel_week) if sel_week else None
    except ValueError:
        week_for_reveal = None

    now_et = timezone.now().astimezone(ZoneInfo("America/New_York"))
    reveal_is_open = False
    reveal_at = None

    if week_for_reveal:
        reveal_at = _week_reveal_dt(season, week_for_reveal)
        reveal_is_open = now_et >= reveal_at
        bets    = bets.filter(week=week_for_reveal)
        parlays = parlays.filter(week=week_for_reveal)
        # If reveal not open yet, hide pending for that week
        if not reveal_is_open:
            bets    = bets.exclude(status="PENDING")
            parlays = parlays.exclude(status="PENDING")
    else:
        # "All weeks" view: always hide pending
        bets    = bets.exclude(status="PENDING")
        parlays = parlays.exclude(status="PENDING")

    # ----- remaining filters -----
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

        # reveal info (use in a banner if you want)
        "reveal_is_open": reveal_is_open,
        "reveal_at_et": reveal_at,
        "now_et": now_et,
    })

def standings(request, season_year: int):
    from django.db.models import Count, Q  # local import to keep this drop-in self-contained

    season = get_object_or_404(Season, year=season_year)

    # ---------- existing tables ----------
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
                    When(status="WON", then=(F("stake_units") * (F("decimal_odds") - 1.0)) ),
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
        teams.append({
            "team": t,
            "indiv_units": t.indiv_units or 0.0,
            "parlay_units": pu,
            "total_units": total,
        })
    teams.sort(key=lambda x: x["total_units"], reverse=True)

    # ---------- charts ----------
    # Determine the last week with any settled result (bets or parlays)
    settled_bet_weeks = set(
        Bet.objects.filter(season=season).exclude(status="PENDING")
        .values_list("week", flat=True).distinct()
    )
    settled_parlay_weeks = set(
        TeamParlay.objects.filter(season=season).exclude(status="PENDING")
        .values_list("week", flat=True).distinct()
    )
    last_settled_week = max(settled_bet_weeks | settled_parlay_weeks, default=0)

    # X-axis for charts: start with 0 for visual baseline, then 1..last_settled_week
    weeks = [0] + list(range(1, last_settled_week + 1))

    # Per-bet PnL expression
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

    # Team week deltas (indiv + parlay)
    indiv_by_team_week = (
        Bet.objects.filter(season=season).exclude(status="PENDING")
        .values("team__name", "week")
        .annotate(units=Sum(bet_pnl_expr))
    )
    parlay_by_team_week = (
        TeamParlay.objects.filter(season=season).exclude(status="PENDING")
        .values("team__name", "week")
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
        for w in weeks:
            cum += float(wk_map.get(w, 0.0))
            data.append(round(cum, 4))
        team_series.append({"label": name, "data": data})

    # User week deltas
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

    # ---------- STINKER chart (weeks with exactly 3 settled picks AND all 3 LOST) ----------
    # Build one row per (user, week) with totals of each outcome
    weekly = (
        Bet.objects.filter(season=season)
            .exclude(status="PENDING")
            .values("user__username", "week")
            .annotate(
                total=Count("id"),
                won=Sum(Case(When(status="WON",  then=1), default=0, output_field=IntegerField())),
                lost=Sum(Case(When(status="LOST", then=1), default=0, output_field=IntegerField())),
                push=Sum(Case(When(status="PUSH", then=1), default=0, output_field=IntegerField())),
            )
    )

    # Qualifying weeks (exactly 3 settled picks)
    stinker_weeks = weekly.filter(total=3, lost=3)  # 0–3
    heater_weeks  = weekly.filter(total=3, won=3)   # 3–0

    # Collapse to per-user COUNTS of DISTINCT weeks (protects against any dup rows)
    stinker_counts = (
        stinker_weeks.values("user__username")
        .annotate(n=Count("week", distinct=True))
    )
    heater_counts = (
        heater_weeks.values("user__username")
        .annotate(n=Count("week", distinct=True))
    )

# Include all users, defaulting to 0
    all_usernames = list(
        Bet.objects.filter(season=season)
            .values_list("user__username", flat=True)
            .distinct()
    )

    stinker_map = {row["user__username"]: row["n"] for row in stinker_counts}
    heater_map  = {row["user__username"]: row["n"] for row in heater_counts}

    stinker_labels = sorted(all_usernames)
    stinker_data   = [int(stinker_map.get(u, 0)) for u in stinker_labels]

    heater_labels  = stinker_labels  # same order
    heater_data    = [int(heater_map.get(u, 0)) for u in heater_labels]
    
    return render(request, "league/standings.html", {
        "season": season,
        "teams": teams,
        "individuals": indiv,
        "chart_weeks": weeks,
        "team_chart_series": team_series,
        "user_chart_series": user_series,
        "last_settled_week": last_settled_week,
        "stinker_labels": stinker_labels,
        "stinker_data": stinker_data,
        "heater_labels": heater_labels,
        "heater_data": heater_data,
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
    """
    Root URL:
    - If not logged in → go to login, then to after_login.
    - If logged in → send straight to after_login.
    """
    next_url = reverse("after_login")
    if not request.user.is_authenticated:
        return redirect(f"{settings.LOGIN_URL}?next={next_url}")
    return redirect("after_login")

@login_required
def after_login(request):
    """
    Decide where to land *after* authentication.
    We send users to the Submit Picks week picker for the latest season.
    """
    season = Season.objects.order_by("-year").first()
    if season:
        return redirect("submit_pick_week_picker", season_year=season.year)

    # If no season yet: staff → admin; others → simple landing/standings page
    if request.user.is_staff:
        return redirect("admin:index")
    return redirect("home")  # or a friendly page if you have one

@login_required
def submit_pick_week_picker(request, season_year: int):
    season = get_object_or_404(Season, year=season_year)

    # must be on a team this season
    if not TeamMembership.objects.filter(user=request.user, team__season=season).exists():
        return render(request, "league/submit_week_picker.html", {
            "season": season,
            "weeks": range(1, 19),
            "error": "You are not assigned to a team for this season.",
            "weeks_complete": set(),
            "weeks_parlay": set(),
        })

    # what the user has saved
    rows = (
        Bet.objects
        .filter(user=request.user, season=season)
        .values("week", "bet_type", "parlay_selected")
    )

    per_week_types = {}
    weeks_parlay = set()
    for r in rows:
        w = r["week"]
        per_week_types.setdefault(w, set()).add(r["bet_type"])
        if r["parlay_selected"]:
            weeks_parlay.add(w)

    # complete = has all three bet types saved
    required = {"SPREAD", "TOTAL", "PROP"}
    weeks_complete = {w for w, types in per_week_types.items() if required.issubset(types)}

    return render(request, "league/submit_week_picker.html", {
        "season": season,
        "weeks": range(1, 19),
        "weeks_complete": weeks_complete,
        "weeks_parlay": weeks_parlay,
    })