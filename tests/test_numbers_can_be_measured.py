"""Numbers a tool returned, against numbers an answer asserts.

The run this is drawn from received ``probability=0.0`` for three universities
and wrote ``75.2% / 92.9% / 66.9%``, then fed those invented values into a code
sandbox and reported "mean 73.69%". Every check passed: grounding compared
names, the ledger only knew whether something was read, no verifier fired.
None of them look at numbers.

This does not gate. It makes the comparison possible — see the note in
:func:`evidence_ledger.numbers_in` for why the gate came second.
"""

from __future__ import annotations

import pytest

from evidence_ledger import Ledger, Spec, numbers_claimed_in, numbers_in
from evidence_ledger.core import EFFECT_READ_LOCAL, TYPE_BODY_READ

#: The real tool result.
LOOKUP = {
    "ok": True,
    "target_label": "Northvale University, Computer Science",
    "probability": 0.0,
    "band": "high risk",
    "q50": 858.964,
    "q70": 843.8,
    "metric": "conversion_score",
    "student_value": 2.4,
    "evidence": [{"year": 2024, "metric": "conversion_score", "q70": 1035.9}],
}

MANIFEST = {
    "lookup": Spec(EFFECT_READ_LOCAL, TYPE_BODY_READ, ("target_label",), (), "query")
}


def test_numbers_a_tool_returned_are_collected():
    found = numbers_in(LOOKUP)
    assert "0" in found, "probability=0.0 must be here or fabrication is invisible"
    assert {"843.8", "858.964", "2.4"} <= found
    assert "1035.9" in found, "values nested inside a list count too"


def test_the_invented_numbers_are_absent():
    """This comparison becoming possible is the whole point of this layer."""
    found = numbers_in(LOOKUP)
    for invented in ("75.2", "92.9", "66.9", "73.69"):
        assert invented not in found


def test_the_ledger_flags_them_end_to_end():
    ledger = Ledger(MANIFEST, run_id="r1")
    ledger.record("lookup", LOOKUP, ok=True, step=1)

    answer = "Northvale 75.2%, Eastbrook 92.9%, Fairmont 66.9% (mean 73.69%)."
    assert ledger.unsupported_numbers(answer) == {"75.2", "92.9", "66.9", "73.69"}


def test_a_number_the_tool_did_return_is_not_flagged():
    ledger = Ledger(MANIFEST, run_id="r1")
    ledger.record("lookup", LOOKUP, ok=True, step=1)
    assert ledger.unsupported_numbers("The q70 threshold is 843.8.") == set()


@pytest.mark.parametrize(
    "key", ["step", "rank", "index", "took_ms", "element_count", "char_count", "status_code"]
)
def test_ordinals_and_timings_are_not_claims(key):
    """Mixing them in costs the comparison its meaning."""
    assert numbers_in({key: 12345}) == set()


def test_booleans_are_not_numbers():
    """In Python ``True`` is 1. Left alone it puts "1" in every single run."""
    assert numbers_in({"ok": True, "verified": False}) == set()


def test_integers_and_floats_stay_apart():
    """Collapsing ``1`` and ``1.0`` makes the comparison leak."""
    found = numbers_in({"a": 1, "b": 1.5})
    assert "1" in found and "1.5" in found


def test_body_text_is_not_harvested():
    """Mixing body numbers in would destroy the meaning of "the tool said so"."""
    found = numbers_in({"text": "the price is 1,500,000 KRW", "count_shown": 3})
    assert "1500000" not in found and "1,500,000" not in found


def test_thousands_separators_are_the_same_claim():
    assert "1500000" in numbers_claimed_in("It costs 1,500,000 KRW")


def test_a_percentage_claims_its_number():
    assert "75.2" in numbers_claimed_in("about 75.2% chance")


def test_small_and_round_numbers_are_ignored():
    """They appear in ordinary prose and would bury the real finding."""
    claimed = numbers_claimed_in("I checked 3 sites and read 100 pages, top 5.")
    assert claimed == set()


def test_a_trailing_zero_does_not_smuggle_a_trivial_number_through():
    """"3.0" is the claim "3". The filter must not depend on how it was typed."""
    assert numbers_claimed_in("about 3.0 sites") == set()
    assert numbers_claimed_in("about 3 sites") == set()
    # and a real claim still survives the same path
    assert numbers_claimed_in("it was 42.0 percent") == {"42"}


def test_the_cap_holds():
    from evidence_ledger.core import _NUMBERS_MAX

    huge = {"rows": [{"v": float(i) + 0.5} for i in range(5000)]}
    assert len(numbers_in(huge)) <= _NUMBERS_MAX


def test_depth_is_bounded():
    deep: dict = {"v": 1.5}
    for _ in range(12):
        deep = {"nest": deep}
    assert numbers_in(deep) == set()


def test_empty_input_is_safe():
    assert numbers_in({}) == set()
    assert numbers_in(None) == set()
    assert numbers_claimed_in("") == set()
