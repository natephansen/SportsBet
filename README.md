Betting League

A production-ready Django web app for running a friendly, season-long betting league. Players join teams, submit weekly picks (Spread, Total, Player Prop), optionally designate one pick for the team parlay, and track standings with clean tables and interactive charts (Chart.js). Dark mode included. Deployed on Render with PostgreSQL.

⚠️ For recreational/educational use only. No real money is handled or implied.

Highlights

Clear domain model: Seasons → Teams → TeamMemberships; per-user weekly Bets; per-team weekly TeamParlay; optional season-long FuturePicks.

Solid validation:

Exactly one pick per type (Spread / Total / Prop) per user per week.

Over/Under is required for Total & Prop (not for Spread).

One “Parlay selected” checkbox across the three picks.

Accurate odds math: converts American odds to decimal and computes parlay odds as a product of legs.

Standings + Analytics:

Team & Individual tables (units).

Cumulative line charts by week (teams & individuals).

“STINKER” (0–3) & “HEATER” (3–0) weekly bar charts.

Charts auto-truncate to the last settled week and start from week 0.

Reveal rules:

Weekly dashboard can reveal picks at Sunday 1:00 PM ET (configurable).

Futures board reveals Thu Sep 4 @ 8:00 PM ET (per season year).

Admin workflows: one-click actions to mark bets WON/LOST/PUSH/PENDING, recompute parlays, and update parlay status from legs.

Responsive UI + Dark Mode with CSS variables; Chart.js theme adapts live.

Tech Stack

Backend: Python 3.12+, Django 5.x

DB: PostgreSQL (Render), SQLite for local dev

Static: WhiteNoise

Frontend: Bootstrap 5, Chart.js (CDN)

Deploy: Render (Web Service + PostgreSQL)

Config: Environment-driven via .env / Render env vars

Data Model (overview)

Season(year, start_date, end_date)

Team(season, name)

TeamMembership(user, team) – user belongs to exactly one team per season

Bet(user, team, season, week, bet_type, pick_text, line, american_odds, over_under?, parlay_selected, status)

TeamParlay(team, season, week, decimal_odds, stake_units, status)

FuturePick(team, season, index, pick_text, american_odds, status) – three per team, settled at season end

over_under only applies to TOTAL and PROP. Spread ignores it by design.

Screenshots (suggested)

(Add a few screenshots/GIFs here: Submit Picks, Week Picker, Standings with charts, Dashboard with filters, Dark mode.)

Getting Started (Local)
1) Clone & set up environment
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>

python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

pip install -r requirements.txt

2) Configure environment

Copy the example and edit as needed:

cp .env.example .env


Minimal .env for local dev:

DEBUG=1
SECRET_KEY=dev-secret-change-me
ALLOWED_HOSTS=127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000
# optional: DATABASE_URL=postgres://USER:PASS@HOST:5432/DBNAME


If DATABASE_URL is omitted locally, the app falls back to SQLite at db.sqlite3.

3) Migrate & create admin
python manage.py migrate
python manage.py createsuperuser

4) Run
python manage.py runserver


Open http://127.0.0.1:8000
 — log in via /admin to seed data.

Seeding Data

Create a Season (e.g., 2025).

Create Teams under that season.

Create Users (or let them register if you add a signup flow).

Add TeamMembership so each user is on exactly one team for the season.

(Optional) Create Future Picks per team (three per team) or let teams submit from the UI.

Key Features in the UI

Submit Picks (per week): three forms (Spread, Total, Player Prop).

Over/Under dropdown appears for Total & Prop only.

Exactly one “Parlay selected” across the three picks.

After saving, you’re returned to a Week Picker showing:

Green = completed (3/3).

Checkmark badge if parlay was selected.

Dashboard:

Filter by Week, User, Team, Parlay (All/Yes/No).

Reveal picks at 1:00 PM ET on Sunday even if not settled (configurable in view).

Standings:

Two tables (Teams, Individuals).

Charts:

Team cumulative units (line).

Individual cumulative units (line).

STINKER 0–3 weeks (bar).

HEATER 3–0 weeks (bar).

Charts auto-adapt to light/dark mode.

Futures:

Public Futures Board shows every team’s futures in separate tables.

Board reveals Sep 4 @ 8:00 PM ET.

Teams edit their own futures from the Submit Picks page.

Admin Workflows

Mark selected bets WON/LOST/PUSH/PENDING (admin actions).

Recompute parlay odds (product of all legs’ decimal odds, regardless of win/loss).

Set parlay status from legs: LOST if any leg lost; PENDING if any pending; WON if ≥1 won and none pending/lost; PUSH if all push.

Bets and parlay changes auto-recompute the corresponding TeamParlay via signals.

Production (Render)
1) Provision

Create a PostgreSQL instance (1 GB is plenty for this app).

Create a Web Service from this repo.

2) Environment variables (Render → Settings → Environment)

Set at minimum:

SECRET_KEY=...                  # strong random string
DEBUG=0
ALLOWED_HOSTS=grouplay.onrender.com
CSRF_TRUSTED_ORIGINS=https://grouplay.onrender.com
DATABASE_URL=postgres://...     # from your Render Postgres
SECURE_SSL_REDIRECT=1
SECURE_HSTS_SECONDS=31536000
LOG_LEVEL=INFO

3) Build & start

Render installs dependencies and runs your start command (e.g., gunicorn betting_league.wsgi).

Open a Shell on the Web Service once deployed:

python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser


Visit your Render URL and log in.

Design Notes & Trade-offs

Environment-driven config: Safe defaults for local dev (SQLite) with a clean switch to Postgres via DATABASE_URL.

Security: HSTS/HTTPS/cookie settings auto-enabled when DEBUG=0.

Reveal logic implemented in views with zoneinfo to avoid cron/dependencies.

Charts delivered via CDN to keep the build lightweight and simple.

No external betting API: All inputs are user-entered; validations enforce consistency.

Testing & Quality

Django admin actions and database signals provide clear, auditable pathways for state changes.

Queries use annotate + conditional Case/When for repeatable units/odds math.

Roadmap includes test coverage for critical calculations (parlay math, units aggregation, stinker/heater logic).

Roadmap

✅ Dark mode with live chart theming

✅ Reveal policies (weekly, futures)

⏳ PWA support (installable icon, offline shell, notifications for reminders)

⏳ Daily/weekly email reminders (pick deadlines, results)

⏳ Slack/Discord webhooks for big wins & team parlays

⏳ More analytics: player “heater” streak charts; team momentum, ROI per bet type

⏳ Permissions & roles (captains, commissioners)

Running the Lint/Test Suite

(Add when you introduce linters/tests)

# examples
ruff check .
pytest

Contributing

PRs welcome. Please open an issue to discuss larger changes (data model, UX, deployment). Keep features behind settings flags when possible.

License

MIT © You

Contact

Questions or feedback? Open an issue in this repo.
