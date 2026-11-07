"""Regenerate the fake demo data in data/seed/ (transactions.json + account.json).

    python scripts/generate_seed_data.py

Deterministic (fixed random seed): 14 months of a Manchester-based user's spending,
1 Sep 2025 - 6 Nov 2026, with realistic seasonality (Christmas, winter heating, cold &
flu season, the January squeeze) so the forecasting has a previous winter to learn from.
All data is synthetic.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "seed"
START, END = date(2025, 9, 1), date(2026, 11, 6)
OPENING_BALANCE = 1000.00  # current account on START
SAVINGS_POT_BALANCE = 2550.00  # Monzo pot balance on END (split across goals)
rng = random.Random(20261107)

rows: list[dict] = []

# Monthly Octopus Energy direct debit: (year, month) -> amount. Winter is dearer; the
# Nov 2026 rise (96 -> 118) is what "bill change detected" picks up.
ENERGY = {
    (2025, 9): 68.0, (2025, 10): 82.0, (2025, 11): 104.0, (2025, 12): 122.0,
    (2026, 1): 128.0, (2026, 2): 118.0, (2026, 3): 96.0, (2026, 4): 72.0, (2026, 5): 72.0,
    (2026, 6): 72.0, (2026, 7): 72.0, (2026, 8): 72.0, (2026, 9): 72.0, (2026, 10): 96.0,
    (2026, 11): 118.0,
}


def add(d: date, merchant: str, amount: float, category: str, time: str | None = None,
        tags: list[str] | None = None, direction: str = "debit") -> None:
    rows.append({
        "date": d.isoformat(),
        "time": time,
        "merchant": merchant,
        "amount": round(amount, 2),
        "currency": "GBP",
        "direction": direction,
        "category": category,
        "tags": tags or [],
        "source": "seed",
    })


def t(h_lo: int, h_hi: int) -> str:
    h = rng.randint(h_lo, h_hi) % 24
    return f"{h:02d}:{rng.randint(0, 59):02d}"


def days():
    d = START
    while d <= END:
        yield d
        d += timedelta(days=1)


for d in days():
    dom, wd, mon = d.day, d.weekday(), d.month  # wd: 0=Mon
    weekend = wd >= 4  # Fri-Sun
    winter = mon in (11, 12, 1, 2)
    xmas = mon == 12 and dom <= 24
    january = mon == 1
    fun = 0.6 if january else (1.25 if xmas else 1.0)  # January squeeze / December splurge

    # ---- fixed monthly items
    if dom == 1:
        add(d, "Ancoats Lettings Ltd", 850.00, "Rent", "06:10", ["rent", "standing-order"])
        add(d, "Manchester City Council", 118.00 if d < date(2026, 4, 1) else 124.00, "Council Tax", "06:12",
            ["council tax", "direct-debit"])
        add(d, "PureGym Manchester", 24.99, "Fitness", "06:20", ["gym", "subscription"])
    if dom == 2:
        add(d, "Barclaycard Repayment", 120.00, "Debt Repayment", "07:00", ["credit card", "debt"])
    if dom == 3:
        add(d, "Netflix", 12.99, "Subscriptions", "03:14", ["streaming", "subscription"])
    if dom == 5:
        add(d, "Octopus Energy", ENERGY[(d.year, mon)], "Utilities", "08:00", ["energy", "gas", "electric"])
    if dom == 9:
        add(d, "Spotify", 10.99 if d < date(2026, 7, 1) else 11.99, "Subscriptions", "04:02", ["music", "subscription"])
    if dom == 10:
        add(d, "United Utilities", 34.00, "Utilities", "08:00", ["water"])
    if dom == 12:
        add(d, "Virgin Media", 38.00, "Phone & Internet", "08:00", ["broadband"])
    if dom == 14:
        add(d, "Amazon Prime", 8.99, "Subscriptions", "02:40", ["amazon", "subscription", "streaming"])
    if dom == 15:
        add(d, "Vodafone", 22.00, "Phone & Internet", "08:00", ["mobile"])
    if dom == 20 and d >= date(2026, 3, 1):
        add(d, "Disney+", 8.99, "Subscriptions", "01:11", ["streaming", "subscription"])
    if dom == 22:
        add(d, "Audible", 7.99, "Subscriptions", "05:30", ["audiobooks", "subscription"])
    if dom == 28:
        add(d, "Northwind Logistics Ltd - Salary", 2850.00, "Income", "00:01", ["salary"], direction="credit")
    if dom == 29:
        add(d, "Monzo Savings Pot", 120.00 if mon not in (9, 12) else 40.00, "Savings Transfer", "09:00", ["savings"])

    # ---- groceries (2-3 a week; bigger shops before Christmas)
    if wd in (1, 4) or (wd == 6 and rng.random() < 0.5):
        shop = rng.choice(["Tesco Express Ancoats", "Aldi Ardwick", "Sainsbury's Local Piccadilly", "Co-op Northern Quarter"])
        big = wd == 6 or (mon == 12 and 18 <= dom <= 23)
        add(d, shop, rng.uniform(38, 72) * (1.3 if xmas else 1) if big else rng.uniform(7, 26), "Groceries", t(17, 20), ["supermarket"])

    # ---- commuting (weekdays)
    if wd < 5 and rng.random() < 0.8 and not (mon == 12 and dom >= 24) and not (mon == 1 and dom == 1):
        add(d, "Bee Network - Metrolink", rng.choice([2.0, 2.0, 4.0, 5.0]), "Transport", t(7, 8), ["tram", "commute"])
    if rng.random() < 0.06:
        add(d, "Northern Rail", rng.uniform(9, 22), "Transport", t(9, 16), ["train"])
    if winter and rng.random() < 0.05:  # bad-weather taxis
        add(d, "Uber", rng.uniform(8, 16), "Transport", t(7, 9), ["taxi", "weather"])

    # ---- eating out at lunch
    if wd < 5 and rng.random() < 0.35:
        add(d, rng.choice(["Pret A Manger", "Greggs", "Leon Piccadilly Gardens"]), rng.uniform(3.2, 9.5), "Eating Out", t(12, 13), ["lunch"])
    if weekend and rng.random() < 0.25 * fun:
        add(d, rng.choice(["Nando's Printworks", "Rudy's Pizza Ancoats", "Mowgli Spinningfields"]), rng.uniform(16, 38), "Eating Out", t(18, 20), ["dinner"])

    # ---- takeaway / delivery (comfort-buyer pattern: evenings, worse late in the week and in winter)
    p_takeaway = (0.22 + (0.18 if wd in (3, 4, 6) else 0)) * (1.15 if winter else 1.0) * (0.85 if january else 1.0)
    if rng.random() < p_takeaway:
        add(d, rng.choice(["Deliveroo", "Just Eat", "Uber Eats"]), rng.uniform(14, 33), "Takeaway & Delivery", t(19, 23), ["takeaway", "delivery", "food"])

    # ---- alcohol & nightlife (mostly Fri/Sat, plus occasional off-licence)
    if wd in (4, 5) and rng.random() < 0.55 * fun:
        venue = rng.choice([
            "The Moon Under Water (Wetherspoon)", "Albert's Schloss", "Cloudwater Tap Room",
            "Night & Day Cafe", "The Pilcrow Pub", "Port Street Beer House",
        ])
        hour_lo = 19 if rng.random() < 0.6 else 21
        add(d, venue, rng.uniform(9, 48), "Alcohol & Nightlife", t(hour_lo, 23), ["alcohol", "pub", "bar", "nightlife", "drinks"])
        if rng.random() < 0.45:
            add(d, "Uber", rng.uniform(9, 19), "Transport", t(23, 25), ["taxi", "late-night"])
    if rng.random() < 0.06 * fun:
        add(d, rng.choice(["Bargain Booze", "Majestic Wine", "Tesco Express Ancoats - Wine & Beer"]), rng.uniform(8, 26),
            "Alcohol & Nightlife", t(17, 21), ["alcohol", "off-licence", "wine", "beer", "drinks"])

    # ---- online shopping (late-night retail therapy; Christmas gifts in December)
    if rng.random() < (0.24 if xmas else 0.13 * fun):
        late = rng.random() < 0.6
        lo, hi = (15, 70) if xmas else (9, 68)
        add(d, rng.choice(["Amazon", "ASOS", "Shein", "Amazon Marketplace"]), rng.uniform(lo, hi), "Shopping - Online",
            t(22, 25) if late else t(12, 20), ["online"] + (["late-night"] if late else []) + (["christmas", "gifts"] if xmas else []))

    # ---- misc
    if rng.random() < (0.08 if xmas else 0.04):
        add(d, rng.choice(["Primark Market Street", "Zara Arndale", "JD Sports Arndale"]), rng.uniform(14, 55), "Shopping - Clothing", t(12, 17),
            ["clothes"] + (["christmas", "gifts"] if xmas else []))
    if rng.random() < (0.08 if winter else 0.04):
        add(d, rng.choice(["Boots Piccadilly", "Superdrug Arndale"]), rng.uniform(4, 16), "Health & Pharmacy", t(11, 18),
            ["pharmacy"] + (["cold & flu"] if winter else []))
    if rng.random() < 0.035:
        add(d, "ATM Withdrawal - Piccadilly", rng.choice([20.0, 40.0]), "Cash Withdrawal", t(18, 22), ["cash", "atm"])
    if rng.random() < 0.04:
        add(d, rng.choice(["ODEON Great Northern", "Steam Games"]), rng.uniform(8, 24), "Entertainment", t(15, 22), ["cinema" if rng.random() < .5 else "games"])
    # Manchester Christmas Markets (mid-Nov to Dec 22, weekends)
    if (mon == 11 and dom >= 14 or mon == 12 and dom <= 22) and weekend and rng.random() < 0.5:
        add(d, "Manchester Christmas Markets", rng.uniform(9, 28), "Eating Out", t(16, 20), ["christmas", "market", "drinks"])

# ---- one-off notable events
add(date(2025, 10, 31), "Halloween party - Albert Hall", 38.00, "Alcohol & Nightlife", "22:05", ["alcohol", "nightlife", "halloween"])
add(date(2025, 12, 12), "Work Christmas do - Albert's Schloss", 64.00, "Alcohol & Nightlife", "21:40", ["alcohol", "nightlife", "christmas"])
add(date(2025, 12, 13), "Argos - Christmas presents", 96.00, "Shopping - Online", "11:20", ["christmas", "gifts"])
add(date(2025, 12, 23), "Trainline - Manchester to Leeds", 34.60, "Travel", "09:15", ["train", "christmas", "trip"])
add(date(2026, 2, 14), "Hawksmoor Manchester", 88.00, "Eating Out", "20:30", ["dinner", "valentines"])
add(date(2026, 5, 2), "Ticketmaster - AO Arena", 72.40, "Entertainment", "10:02", ["concert", "tickets"])
add(date(2026, 7, 18), "Jet2 - Manchester to Malaga", 214.00, "Travel", "13:40", ["flights", "holiday"])
add(date(2026, 8, 23), "Ticketmaster - Co-op Live", 68.50, "Entertainment", "21:47", ["concert", "tickets"])
add(date(2026, 9, 12), "Trainline - Manchester to London", 48.20, "Travel", "10:05", ["train", "trip"])
add(date(2026, 9, 13), "Booking.com - London hotel", 118.00, "Travel", "11:30", ["hotel", "trip"])
add(date(2026, 10, 31), "Albert Hall Halloween - tickets & bar", 54.00, "Alcohol & Nightlife", "22:15", ["alcohol", "nightlife", "halloween"])

rows.sort(key=lambda r: (r["date"], r["time"] or ""))
for i, r in enumerate(rows, start=1):
    r.update({"tagged": False, "is_flagged": False, "highlight_reason": None})
    rows[i - 1] = {"id": f"txn_{i:04d}", **r}

balance = OPENING_BALANCE + sum(r["amount"] if r["direction"] == "credit" else -r["amount"] for r in rows)
account = {
    "_note": "SYNTHETIC demo account. Generated by scripts/generate_seed_data.py.",
    "display_name": "Alex Johnson",
    "first_name": "Alex",
    "account_type": "Personal account",
    "city": "Manchester",
    "currency": "GBP",
    "balance": round(balance, 2),
    "balance_as_of": END.isoformat(),
    "savings_balance": SAVINGS_POT_BALANCE,
    "payday_day": 28,
}

SEED_DIR.mkdir(parents=True, exist_ok=True)
(SEED_DIR / "transactions.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
(SEED_DIR / "account.json").write_text(json.dumps(account, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {len(rows)} transactions; closing balance £{balance:,.2f}")
