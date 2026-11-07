from nataware.conversation.tools import TOOL_DEFINITIONS, execute_tool


def test_every_tool_has_a_handler():
    from nataware.conversation.tools import _HANDLERS

    assert {t["name"] for t in TOOL_DEFINITIONS} == set(_HANDLERS)


def test_alcohol_search_and_highlight():
    found = execute_tool("search_transactions", {"categories": ["Alcohol & Nightlife"], "date_from": "2026-10-01", "date_to": "2026-10-31"})
    assert found["match_count"] > 0
    assert all(t["category"] == "Alcohol & Nightlife" for t in found["transactions"])

    ids = [t["id"] for t in found["transactions"]]
    hl = execute_tool("highlight_transactions", {"transaction_ids": ids + ["txn_9999"], "label": "Alcohol - October"})
    assert hl["highlighted_count"] == len(ids)
    assert hl["missing_ids"] == ["txn_9999"]
    assert round(hl["total"], 2) == found["total"]


def test_keyword_search():
    assert execute_tool("search_transactions", {"query": "deliveroo"})["match_count"] > 0
    assert execute_tool("search_transactions", {"query": "pub"})["match_count"] > 0


def test_no_matches_is_a_clean_zero():
    res = execute_tool("search_transactions", {"query": "casino"})
    assert res == {**res, "match_count": 0, "total": 0, "transactions": []}


def test_flags_follow_comfort_buyer_profile():
    flags = execute_tool("get_behavioural_flags", {"limit": 200})
    assert flags["tendency"] == "The Comfort-Buyer"
    assert flags["flag_count"] > 0
    assert {t["category"] for t in flags["transactions"]} <= {
        "Takeaway & Delivery", "Shopping - Online", "Subscriptions", "Transport"
    }


def test_summary_budget_threats_plan():
    summary = execute_tool("get_spending_summary", {"group_by": "month"})
    months = [r["group"] for r in summary["rows"]]
    assert months[0] == "2025-09" and months[-1] == "2026-11" and len(months) == 15

    budget = execute_tool("get_budget_status", {})
    assert budget["month"] == "2026-10" and budget["income"] > 0

    threats = execute_tool("get_active_threats", {})["threats"]
    assert threats and all("estimated_dollar_burden" in t and "recommended_budget_shift" in t for t in threats)

    plan = execute_tool("get_coaching_plan", {})
    assert plan["stage"]["name"] == "Plug the leaks"  # 3 weeks after the 2026-10-17 onboarding


def test_log_transaction_fires_transaction_trigger_when_over_limit():
    result = None
    for _ in range(4):
        result = execute_tool("log_transaction", {"merchant": "Deliveroo", "amount": 30, "category": "Takeaway & Delivery", "time": "22:30"})
    assert result["transaction"]["is_flagged"]
    assert result["plan"]["over_limit"]
    assert result["nudge"]["trigger"] == "transaction"


def test_time_travel_tools():
    goals = execute_tool("get_goals_and_strategies", {})["goals"]
    house = next(g for g in goals if g["kind"] == "house")
    assert house["plan_months"] < house["current_path_months"]
    assert {s["id"] for s in house["strategies"]} >= {"lisa", "habit-swap"}

    forecast = execute_tool("get_spending_forecast", {})
    december = next(p for p in forecast["forecast"] if p["month"] == "2026-12")
    assert december["predicted"] > forecast["baseline_monthly"]  # Christmas, learned from last year

    events = {e["id"]: e for e in execute_tool("get_seasonal_outlook", {})["events"]}
    assert events["christmas"]["impact"] == "high" and events["christmas"]["weekly_save"] > 0

    kinds = {i["kind"] for i in execute_tool("get_insights", {})["insights"]}
    assert {"cash_flow", "bill_change"} <= kinds


def test_set_aside_and_update_goal():
    assert execute_tool("set_aside_for_event", {"event_id": "christmas", "weekly": 40})["total_weekly"] == 40
    res = execute_tool("update_goal", {"name": "Driving lessons", "target": 1200, "kind": "car"})
    assert any(g["name"] == "Driving lessons" for g in res["goals"])
