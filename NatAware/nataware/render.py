"""Terminal rendering of tool results (the CLI's stand-in for the front end)."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nataware.profile import Profile

console = Console(highlight=False)


def _gbp(v: float) -> str:
    return f"£{v:,.2f}"


def transactions_table(title: str, txns: list[dict[str, Any]], highlight: bool = False, note: str | None = None) -> Table:
    table = Table(title=title, caption=note, title_style="bold yellow" if highlight else "bold", expand=False)
    table.add_column("Date", no_wrap=True)
    table.add_column("Time", style="dim", no_wrap=True)
    table.add_column("Merchant")
    table.add_column("Category", style="dim")
    table.add_column("Amount", justify="right", no_wrap=True)
    table.add_column("Flag", style="magenta")
    for t in txns:
        sign = "+" if t["direction"] == "credit" else ""
        table.add_row(
            t["date"],
            t.get("time") or "",
            t["merchant"],
            t["category"],
            f"{sign}{_gbp(t['amount'])}",
            (t.get("highlight_reason") or "") if t.get("is_flagged") else "",
            style="on grey15" if highlight else None,
        )
    return table


def render_tool_result(name: str, args: dict[str, Any], result: dict[str, Any]) -> None:
    if "error" in result:
        console.print(f"  [red]! {name} failed: {result['error']}[/]")
        return

    if name == "search_transactions":
        console.print(f"  [dim]🔍 searched {_describe(args)} → {result['match_count']} match(es), {_gbp(result['total'])}[/]")
    elif name == "highlight_transactions":
        console.print()
        console.print(
            transactions_table(
                f"★ {result['label']} — {result['highlighted_count']} transactions, {_gbp(result['total'])}",
                result["transactions"],
                highlight=True,
                note=result.get("reason"),
            )
        )
    elif name == "get_behavioural_flags":
        console.print()
        console.print(
            transactions_table(
                f"Behavioural flags ({result['tendency']}) — {result['flag_count']}, {_gbp(result['total'])}",
                result["transactions"],
            )
        )
    elif name == "get_spending_summary":
        table = Table(title=f"Spending by {result['group_by']} — {_gbp(result['total'])}")
        table.add_column(result["group_by"].title())
        table.add_column("Total", justify="right")
        table.add_column("Count", justify="right", style="dim")
        for r in result["rows"]:
            table.add_row(r["group"], _gbp(r["total"]), str(r["count"]))
        console.print()
        console.print(table)
    elif name == "get_budget_status":
        table = Table(title=f"Budget {result['month']} — income {_gbp(result['income'])}")
        for col in ("Bucket", "Spent", "% of income", "Target %", "Gap"):
            table.add_column(col, justify="right" if col != "Bucket" else "left")
        for k, v in result["actual"].items():
            gap = result["gap_percent"][k]
            table.add_row(k.title(), _gbp(v["amount"]), f"{v['percent_of_income']}%",
                          f"{result['target_percent'].get(k)}%", f"{gap:+}%")
        console.print()
        console.print(table)
    elif name == "get_active_threats":
        table = Table(title=f"Active threats — {result['city']}")
        for col in ("Priority", "Threat", "Est. burden", "Recommended shift"):
            table.add_column(col)
        for th in result["threats"]:
            colour = {"high": "red", "medium": "yellow"}.get(th["priority"], "green")
            table.add_row(f"[{colour}]{th['priority']}[/]", th["threat_name"],
                          _gbp(th["estimated_dollar_burden"]), th["recommended_budget_shift"])
        console.print()
        console.print(table)
    elif name == "get_coaching_plan" and "stage" in result:
        s = result["stage"]
        body = (
            f"Stage {s['number']}/{s['of']}: [bold]{s['name']}[/]\n"
            f"This week: {_gbp(result['spent_this_week'])} of {_gbp(result['weekly_limit'])} "
            f"on {', '.join(result['watch_categories'])}\n"
            + "\n".join(f"• {g}" for g in result["micro_goals"])
            + f"\n[dim]{result['habit_swap']}[/]"
        )
        console.print(Panel(body, title="Coaching plan", expand=False))
    elif name == "log_transaction":
        t = result["transaction"]
        console.print(f"  [dim]📝 logged {_gbp(t['amount'])} at {t['merchant']}"
                      + (" — flagged" if t["is_flagged"] else "") + "[/]")
        if result.get("nudge"):
            render_nudge(result["nudge"])
    elif name == "get_recent_nudges":
        for n in result["nudges"]:
            render_nudge(n)


def render_nudge(n: dict[str, Any]) -> None:
    console.print(Panel(n["message"], title=f"🔔 [{n['channel']}] {n['title']}", border_style="magenta", expand=False))


def render_profile(p: Profile) -> None:
    b = p.optimal_baseline
    console.print(
        Panel(
            f"Capacity: [bold]{p.capacity.value}[/]\nTendency: [bold]{p.tendency.value}[/]\n"
            f"Optimal baseline: Needs {b.needs:g}% · Wants {b.wants:g}% · Savings {b.savings:g}%\n"
            f"[dim]{p.rationale}[/]",
            title="Your NatAware profile",
            border_style="green",
            expand=False,
        )
    )


def _describe(args: dict[str, Any]) -> str:
    bits = []
    if args.get("query"):
        bits.append(f"'{args['query']}'")
    if args.get("categories"):
        bits.append("/".join(args["categories"]))
    if args.get("date_from") or args.get("date_to"):
        bits.append(f"{args.get('date_from', '…')}→{args.get('date_to', '…')}")
    return " ".join(bits) or "all transactions"
