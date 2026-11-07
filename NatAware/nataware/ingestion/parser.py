"""Statement parsing: CSV (pandas) and PDF (PyMuPDF) -> normalised transaction dicts.

DEMO NOTE: the CSV path works on simple bank exports (see `data/seed/sample_statement.csv`).
The PDF path is a best-effort line parser that shows where PyMuPDF plugs in; real bank
PDFs need per-bank layouts. Categorisation uses a keyword map instead of an LLM.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import IO, Any

CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("Income", ("salary", "payroll", "wages")),
    ("Rent", ("rent", "lettings")),
    ("Council Tax", ("council",)),
    ("Utilities", ("octopus", "british gas", "united utilities", "eon", "edf")),
    ("Phone & Internet", ("vodafone", "virgin media", "ee ", "o2", "bt ")),
    ("Groceries", ("tesco", "aldi", "lidl", "sainsbury", "co-op", "asda", "morrisons")),
    ("Transport", ("bee network", "tfgm", "northern", "trainline", "uber trip", "metrolink")),
    ("Takeaway & Delivery", ("deliveroo", "just eat", "uber eats")),
    ("Eating Out", ("pret", "nando", "greggs", "costa", "starbucks", "pizza")),
    ("Alcohol & Nightlife", ("wetherspoon", "bar", "pub", "tap room", "booze", "wine", "brewery", "schloss")),
    ("Shopping - Clothing", ("primark", "zara", "jd sports", "h&m")),
    ("Shopping - Online", ("amazon", "asos", "shein", "ebay")),
    ("Subscriptions", ("netflix", "spotify", "disney", "prime", "audible")),
    ("Entertainment", ("odeon", "ticketmaster", "steam", "cineworld")),
    ("Fitness", ("puregym", "gym")),
    ("Health & Pharmacy", ("boots", "superdrug", "pharmacy")),
    ("Cash Withdrawal", ("atm", "cash")),
    ("Savings Transfer", ("savings", "pot")),
    ("Debt Repayment", ("barclaycard", "credit card", "loan")),
]


def categorise(merchant: str, direction: str = "debit") -> str:
    if direction == "credit":
        return "Income"
    m = merchant.lower()
    for category, keywords in CATEGORY_KEYWORDS:
        if category != "Income" and any(k in m for k in keywords):
            return category
    return "Shopping - Online"


def _parse_date(value: Any) -> str:
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date: {text!r}")


def normalise(date: Any, merchant: str, signed_amount: float, source: str) -> dict[str, Any]:
    """Bank exports use negative numbers for money out; we store positive amounts + direction."""
    direction = "credit" if signed_amount > 0 else "debit"
    merchant = " ".join(str(merchant).split())
    return {
        "date": _parse_date(date),
        "time": None,
        "merchant": merchant,
        "amount": round(abs(float(signed_amount)), 2),
        "currency": "GBP",
        "direction": direction,
        "category": categorise(merchant, direction),
        "tags": [],
        "source": source,
    }


def parse_csv(file: str | Path | IO) -> list[dict[str, Any]]:
    import pandas as pd

    df = pd.read_csv(file)
    cols = {c.lower().strip(): c for c in df.columns}

    def pick(*names: str) -> str | None:
        return next((cols[n] for n in names if n in cols), None)

    date_col = pick("date", "transaction date", "posted date")
    desc_col = pick("description", "merchant", "details", "name", "payee")
    amount_col = pick("amount", "value")
    out_col, in_col = pick("money out", "debit", "paid out"), pick("money in", "credit", "paid in")
    if not date_col or not desc_col or not (amount_col or out_col or in_col):
        raise ValueError(f"Could not find date/description/amount columns in: {list(df.columns)}")

    def num(row: Any, col: str | None) -> float:
        if not col or pd.isna(row[col]):
            return 0.0
        return float(str(row[col]).replace("£", "").replace(",", ""))

    rows = []
    for _, r in df.iterrows():
        signed = num(r, amount_col) if amount_col else num(r, in_col) - num(r, out_col)
        if signed == 0:
            continue
        rows.append(normalise(r[date_col], r[desc_col], signed, source="csv"))
    return rows


_PDF_LINE = re.compile(
    r"^(?P<date>\d{2}[/-]\d{2}[/-]\d{2,4}|\d{1,2} [A-Za-z]{3} \d{4})\s+(?P<desc>.+?)\s+(?P<amount>-?£?[\d,]+\.\d{2})$"
)


def parse_pdf(path: str | Path) -> list[dict[str, Any]]:
    import fitz  # PyMuPDF

    rows = []
    with fitz.open(path) as doc:
        for page in doc:
            for line in page.get_text("text").splitlines():
                m = _PDF_LINE.match(line.strip())
                if not m:
                    continue
                amount = float(m["amount"].replace("£", "").replace(",", ""))
                rows.append(normalise(m["date"], m["desc"], amount, source="pdf"))
    return rows
