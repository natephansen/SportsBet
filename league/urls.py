from django.urls import path, include
from . import views

urlpatterns = [
    path("", views.landing, name="home"),
    path("after-login/", views.after_login, name="after_login"),  # <— new
    path("week/<int:season_year>/<int:week>/", views.week_view, name="week_view"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("pick/<int:season_year>/<int:week>/submit/", views.submit_pick, name="submit_pick"),
    path("dashboard/<int:season_year>/", views.league_dashboard, name="league_dashboard"),
    path("standings/<int:season_year>/", views.standings, name="standings"),
    path("submit/<int:season_year>/", views.submit_pick_week_picker, name="submit_pick_week_picker"),
    path("stats/<str:username>/", views.user_stats, name="user_stats"),
    path("accounts/profile/", views.landing, name="profile_redirect"),
    path("futures/<int:season_year>/", views.futures_board,  name="futures_board"),
    path("futures/<int:season_year>/edit/", views.submit_futures, name="submit_futures"),
]

