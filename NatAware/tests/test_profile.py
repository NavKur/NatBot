from nataware.profile import Capacity, Tendency, extract_profile, strip_profile

REPLY = """Thanks! You're scrappy but comfort spending trips you up.
<profile>
{"capacity": "The Scrapper", "tendency": "The Comfort-Buyer",
 "optimal_baseline": {"needs": 55, "wants": 25, "savings": 20},
 "rationale": "Little buffer, stress-driven delivery orders."}
</profile>"""


def test_extracts_profile():
    p = extract_profile(REPLY)
    assert p.capacity is Capacity.SCRAPPER
    assert p.tendency is Tendency.COMFORT_BUYER
    assert p.optimal_baseline.savings == 20


def test_strip_removes_block():
    assert strip_profile(REPLY) == "Thanks! You're scrappy but comfort spending trips you up."


def test_baseline_is_normalised_to_100():
    p = extract_profile(REPLY.replace('"needs": 55', '"needs": 65'))
    b = p.optimal_baseline
    assert round(b.needs + b.wants + b.savings, 1) == 100.0


def test_invalid_or_missing_profile_returns_none():
    assert extract_profile("No block here.") is None
    assert extract_profile('<profile>{"capacity": "The Wizard"}</profile>') is None


def test_fenced_json_is_accepted():
    fenced = REPLY.replace("<profile>\n", "<profile>\n```json\n").replace("\n</profile>", "\n```\n</profile>")
    assert extract_profile(fenced) is not None
