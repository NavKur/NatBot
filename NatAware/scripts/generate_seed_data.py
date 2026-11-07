"""Regenerate the fake transaction history in data/seed/transactions.json.

    python scripts/generate_seed_data.py

Deterministic (fixed random seed): ~3 months of a Manchester-based user's spending,
1 Aug 2026 - 6 Nov 2026. All data is synthetic.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "seed" / "transactions.json"
START, END = date(2026, 8, 1), date(2026, 11, 6)
rng = random.Random(20261107)

rows: list[dict] = []


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
    dom, wd = d.day, d.weekday()  # wd: 0=Mon
    weekend = wd >= 4  # Fri-Sun

    # ---- fixed monthly items
    if dom == 1:
        add(d, "Ancoats Lettings Ltd", 850.00, "Rent", "06:10", ["rent", "standing-order"])
        add(d, "Manchester City Council", 118.00, "Council Tax", "06:12", ["council tax", "direct-debit"])
        add(d, "PureGym Manchester", 24.99, "Fitness", "06:20", ["gym", "subscription"])
    if dom == 2:
        add(d, "Barclaycard Repayment", 120.00, "Debt Repayment", "07:00", ["credit card", "debt"])
    if dom == 3:
        add(d, "Netflix", 12.99, "Subscriptions", "03:14", ["streaming", "subscription"])
    if dom == 5:
        add(d, "Octopus Energy", 72.00 if d.month < 10 else 96.00, "Utilities", "08:00", ["energy", "gas", "electric"])
    if dom == 9:
        add(d, "Spotify", 11.99, "Subscriptions", "04:02", ["music", "subscription"])
    if dom == 10:
        add(d, "United Utilities", 34.00, "Utilities", "08:00", ["water"])
    if dom == 12:
        add(d, "Virgin Media", 38.00, "Phone & Internet", "08:00", ["broadband"])
    if dom == 14:
        add(d, "Amazon Prime", 8.99, "Subscriptions", "02:40", ["amazon", "subscription"])
    if dom == 15:
        add(d, "Vodafone", 22.00, "Phone & Internet", "08:00", ["mobile"])
    if dom == 20:
        add(d, "Disney+", 8.99, "Subscriptions", "01:11", ["streaming", "subscription"])
    if dom == 22:
        add(d, "Audible", 7.99, "Subscriptions", "05:30", ["audiobooks", "subscription"])
    if dom == 28:
        add(d, "Northwind Logistics Ltd - Salary", 2850.00, "Income", "00:01", ["salary"], direction="credit")
    if dom == 29:
        add(d, "Monzo Savings Pot", 50.00 if d.month != 9 else 20.00, "Savings Transfer", "09:00", ["savings"])

    # ---- groceries (2-3 a week)
    if wd in (1, 4) or (wd == 6 and rng.random() < 0.5):
        shop = rng.choice(["Tesco Express Ancoats", "Aldi Ardwick", "Sainsbury's Local Piccadilly", "Co-op Northern Quarter"])
        big = wd == 6
        add(d, shop, rng.uniform(38, 72) if big else rng.uniform(7, 26), "Groceries", t(17, 20), ["supermarket"])

    # ---- commuting (weekdays)
    if wd < 5 and rng.random() < 0.8:
        add(d, "Bee Network - Metrolink", rng.choice([2.0, 2.0, 4.0, 5.0]), "Transport", t(7, 8), ["tram", "commute"])
    if rng.random() < 0.06:
        add(d, "Northern Rail", rng.uniform(9, 22), "Transport", t(9, 16), ["train"])

    # ---- eating out at lunch
    if wd < 5 and rng.random() < 0.35:
        add(d, rng.choice(["Pret A Manger", "Greggs", "Leon Piccadilly Gardens"]), rng.uniform(3.2, 9.5), "Eating Out", t(12, 13), ["lunch"])
    if weekend and rng.random() < 0.25:
        add(d, rng.choice(["Nando's Printworks", "Rudy's Pizza Ancoats", "Mowgli Spinningfields"]), rng.uniform(16, 38), "Eating Out", t(18, 20), ["dinner"])

    # ---- takeaway / delivery (comfort-buyer pattern: evenings, worse late in the week)
    p_takeaway = 0.22 + (0.18 if wd in (3, 4, 6) else 0)
    if rng.random() < p_takeaway:
        add(d, rng.choice(["Deliveroo", "Just Eat", "Uber Eats"]), rng.uniform(14, 33), "Takeaway & Delivery", t(19, 23), ["takeaway", "delivery", "food"])

    # ---- alcohol & nightlife (mostly Fri/Sat, plus occasional off-licence)
    if wd in (4, 5) and rng.random() < 0.55:
        venue = rng.choice([
            "The Moon Under Water (Wetherspoon)", "Albert's Schloss", "Cloudwater Tap Room",
            "Night & Day Cafe", "The Pilcrow Pub", "Port Street Beer House",
        ])
        hour_lo = 19 if rng.random() < 0.6 else 21
        add(d, venue, rng.uniform(9, 48), "Alcohol & Nightlife", t(hour_lo, 23), ["alcohol", "pub", "bar", "nightlife", "drinks"])
        if rng.random() < 0.45:
            add(d, "Uber", rng.uniform(9, 19), "Transport", t(23, 25), ["taxi", "late-night"])
    if rng.random() < 0.06:
        add(d, rng.choice(["Bargain Booze", "Majestic Wine", "Tesco Express Ancoats - Wine & Beer"]), rng.uniform(8, 26),
            "Alcohol & Nightlife", t(17, 21), ["alcohol", "off-licence", "wine", "beer", "drinks"])

    # ---- online shopping (late-night retail therapy)
    if rng.random() < 0.13:
        late = rng.random() < 0.6
        add(d, rng.choice(["Amazon", "ASOS", "Shein", "Amazon Marketplace"]), rng.uniform(9, 68), "Shopping - Online",
            t(22, 25) if late else t(12, 20), ["online"] + (["late-night"] if late else []))

    # ---- misc
    if rng.random() < 0.04:
        add(d, rng.choice(["Primark Market Street", "Zara Arndale", "JD Sports Arndale"]), rng.uniform(14, 55), "Shopping - Clothing", t(12, 17), ["clothes"])
    if rng.random() < 0.05:
        add(d, rng.choice(["Boots Piccadilly", "Superdrug Arndale"]), rng.uniform(4, 16), "Health & Pharmacy", t(11, 18), ["pharmacy"])
    if rng.random() < 0.035:
        add(d, "ATM Withdrawal - Piccadilly", rng.choice([20.0, 40.0]), "Cash Withdrawal", t(18, 22), ["cash", "atm"])
    if rng.random() < 0.04:
        add(d, rng.choice(["ODEON Great Northern", "Steam Games"]), rng.uniform(8, 24), "Entertainment", t(15, 22), ["cinema" if rng.random() < .5 else "games"])

# ---- one-off notable events
add(date(2026, 8, 23), "Ticketmaster - Co-op Live", 68.50, "Entertainment", "21:47", ["concert", "tickets"])
add(date(2026, 9, 12), "Trainline - Manchester to London", 48.20, "Travel", "10:05", ["train", "trip"])
add(date(2026, 9, 13), "Booking.com - London hotel", 118.00, "Travel", "11:30", ["hotel", "trip"])
add(date(2026, 10, 31), "Albert Hall Halloween - tickets & bar", 54.00, "Alcohol & Nightlife", "22:15", ["alcohol", "nightlife", "halloween"])

rows.sort(key=lambda r: (r["date"], r["time"] or ""))
for i, r in enumerate(rows, start=1):
    r_id = {"id": f"txn_{i:04d}"}
    r.update({"tagged": False, "is_flagged": False, "highlight_reason": None})
    rows[i - 1] = {**r_id, **r}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Wrote {len(rows)} transactions to {OUT}")
