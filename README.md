# Betting League (Grouplay)

A Django web app for running a friendly sports-betting league. Teams submit weekly picks (spreads, moneylines, totals, and player props) and a one-time set of futures picks that settle at season end. Standings are tracked in units, with transparent scoring, interactive charts and an admin workflow for settling results.

Built with Python 3.12 and Django 5.2.

Running at: grouplay.onrender.com
Demo Credentials: 
- Username: Demo
- Password: Grouplay123

## ✨ Features

- Weekly picks: spread, moneyline, totals (O/U), and player props

- Futures picks: each team submits exactly one set (e.g., 3 futures) that lock after a configurable deadline and settle at season end

- Units-based scoring: American odds → units won/lost, tracked per team and season

- Clean team flow: users join/own teams, submit/edit picks before cutoffs

- Mobile-friendly forms: line/odds inputs accept + and − signs (no “numeric keypad only” traps)

- Admin dashboard: create weeks/games, lock windows, settle results atomically, view all picks

- Auditability: timestamps, one-set-per-team constraint for futures, atomic DB updates

## 🧱 Tech Stack

- Backend: Django 5.2, Python 3.12

- DB: SQLite (dev) / PostgreSQL (prod)

- Auth: Django auth (email/username + password)

- Styling: Django templates + CSS 

- Ops: .env-driven settings, transactions for critical writes

- Render for deployment

## Ongoing
Working on connecting API to autopopulate options for bets and automatically settle bets
