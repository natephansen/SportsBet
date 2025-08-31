# Betting League (Grouplay)

A Django web app for running a friendly sports-betting league. Teams submit weekly picks (spreads, moneylines, totals, and player props) and a one-time set of futures picks that settle at season end. Standings are tracked in units, with transparent scoring, interactive charts and an admin workflow for settling results.

Built with Python 3.12 and Django 5.2.

✨ Features

Weekly picks: spread, moneyline, totals (O/U), and player props

Futures picks: each team submits exactly one set (e.g., 3 futures) that lock after a configurable deadline and settle at season end

Units-based scoring: American odds → units won/lost, tracked per team and season

Clean team flow: users join/own teams, submit/edit picks before cutoffs

Mobile-friendly forms: line/odds inputs accept + and − signs (no “numeric keypad only” traps)

Admin dashboard: create weeks/games, lock windows, settle results atomically, view all picks

Auditability: timestamps, one-set-per-team constraint for futures, atomic DB updates

🧱 Tech Stack

Backend: Django 5.2, Python 3.12

DB: SQLite (dev) / PostgreSQL (prod)

Auth: Django auth (email/username + password)

Styling: Django templates + CSS (swap in Tailwind/Bootstrap if you prefer)

Ops: .env-driven settings, transactions for critical writes

🚀 Quick Start
# 1) Clone
git clone <your-repo-url> betting_league
cd betting_league

# 2) Python 3.12 virtual env
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

# 3) Install deps
pip install -r requirements.txt

# 4) Create an .env file (see below)
copy .env.example .env    # or create manually

# 5) Migrate & create an admin
python manage.py migrate
python manage.py createsuperuser

# 6) Run the app
python manage.py runserver

🔐 Environment Variables

Create a .env in your project root:

# Core
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (use one)
DATABASE_URL=sqlite:///db.sqlite3
# DATABASE_URL=postgres://USER:PASS@HOST:5432/DBNAME

# Security (production)
# CSRF_TRUSTED_ORIGINS=https://yourdomain.com
# SESSION_COOKIE_SECURE=True
# CSRF_COOKIE_SECURE=True

### League settings
LEAGUE_TIME_ZONE=America/Phoenix

### Futures window (example)
FUTURES_OPEN_AT=2025-09-04T20:00:00-04:00   # 8:00 PM EDT
FUTURES_CLOSE_AT=2025-09-05T12:00:00-04:00  # optional close
FUTURES_NUM_PICKS=3                         # per team


Tip: If you prefer, manage open/close windows in the Admin instead of env vars.

🧭 How It Works
Data model (high-level)

User ← Django auth

Team (owner: User, members: Users)

Week (e.g., “Week 1”, lock times, etc.)

Game (home/away, kickoff, line/total reference if you store them)

Bet (user/team, week, type: spread/moneyline/total/prop, line, american_odds, over/under flag, stake, status/result)

FuturesPick (team, pick text, american_odds, submitted once, locked after window)

Units scoring (American odds)

Let stake be 1 unit unless configured otherwise:

Positive odds (+150): units_won = stake * (odds / 100)

Negative odds (-120): units_won = stake * (100 / abs(odds))

Loss = -stake units

Totals across weekly + futures decide standings.

🧑‍💻 Developer Notes
Forms & mobile input

Line and American Odds fields are text inputs to allow - and + on mobile keyboards.

Validation ensures only valid signed numbers make it to the DB.

Atomic updates

If you use DB transactions (recommended), ensure you import:

from django.db import transaction


Wrap multi-step writes (e.g., settling, batch futures save) in @transaction.atomic.

🛠 Admin Workflow

Create Season/Weeks/Games (or just Weeks if you infer games elsewhere).

Configure Futures window (via Admin or .env).

Teams: created by users or admin; enforce “one futures set per team.”

Review/lock: after cutoffs, users can’t edit.

Settle results: assign outcomes → units computed and posted to standings.

✅ Testing
pytest         # if pytest configured
# or
python manage.py test

📦 Deployment

PostgreSQL for production (DATABASE_URL=...).

DEBUG=False, set ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS.

Collect static files:

python manage.py collectstatic


Run with gunicorn/uvicorn behind Nginx (or deploy to Render/Fly/Heroku).

📚 Useful Management Commands (optional)

If included in the repo, you might find commands such as:

python manage.py seed_demo_data   # load a sample season, teams, games
python manage.py lock_week 1      # lock Week 1 submissions
python manage.py settle_week 1    # settle Week 1 bets from a scores feed
python manage.py settle_futures   # settle all futures and post units

🧩 Project Structure (typical)
betting_league/
├─ league/                # app (models, views, forms, admin, urls, templates)
├─ betting_league/        # project settings, urls, wsgi/asgi
├─ templates/             # base.html + pages
├─ static/                # css/js/img
├─ manage.py
├─ requirements.txt
└─ .env.example

🗓 Futures Window Example

Want futures to show up starting Thu, Sept 4, 2025 at 8:00 PM Eastern?
Set:

FUTURES_OPEN_AT=2025-09-04T20:00:00-04:00


You can also expose this in Admin for non-dev changes.

🤝 Contributing

Open an issue or PR with a clear description.

Keep features small and well-tested.

Follow Django best practices and PEP 8.

📄 License

MIT (or your preferred license). Add a LICENSE file at repo root.

💬 Contact

Questions or suggestions? Open an issue or reach out to the maintainer.
