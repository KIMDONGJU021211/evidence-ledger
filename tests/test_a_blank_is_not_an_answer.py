"""A cell that says nothing can still look filled.

Fabrication detection only inspects cells that carry a value. An agent that
writes ``N/A`` into every column fabricates nothing — and scores perfectly.
This is the check that separates *nothing was wrong* from *nothing was said*.
"""
from __future__ import annotations

import pytest

from evidence_ledger import unanswered


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "-",
        "--",
        "\u2013",          # en dash
        "\u2014",          # em dash
        "?",
        "???",
        "N/A",
        "n/a",
        "NA",
        "null",
        "None",
        "TBD",
        "unknown",
        "not found",
        "not available",
        "pending",
        "missing",
        # Korean. An agent working Korean sites writes these, and a grader that
        # only knows the English forms reports them as filled.
        "없음",
        "미상",
        "미확인",
        "확인 불가",
        "확인불가",
        "확인되지 않음",
        "알 수 없음",
        "정보 없음",
        "해당 없음",
        "파악 불가",
    ],
)
def test_a_placeholder_is_not_an_answer(value: str) -> None:
    assert unanswered(value) is True


@pytest.mark.parametrize(
    "value",
    [
        "432",
        "9791163034735",
        "https://example.com/a",
        "Do it! Jump to Python",
        "정규직",
        "2026.10.09",
        0,
        0.0,
        42,
        # ★ The placeholder words appear inside real values too. Anchoring the
        #   whole cell is what keeps these answers.
        "없음이라는 회사",
        "N/A 정책 안내서",
        "Unknown Pleasures (1979)",
        "TBD Records Inc.",
    ],
)
def test_a_real_value_survives(value: object) -> None:
    assert unanswered(value) is False


def test_zero_is_an_answer() -> None:
    """``0`` is a measurement. Treating falsy as blank loses real data — the
    same mistake as counting an empty result and a failed read as one thing."""
    assert unanswered(0) is False
    assert unanswered("0") is False
    assert unanswered(0.0) is False


def test_the_filled_ratio_this_enables() -> None:
    """What the check is for: **the denominator is what was asked, not what was
    written.** Three rows of four columns is twelve cells, however many the
    agent chose to fill.
    """
    asked_rows, asked_cols = 3, 4
    table = [
        ["Do it! Jump to Python", "확인 불가", "확인 불가", "https://a"],
        ["Learning Python Alone", "-", "N/A", "https://b"],
    ]
    filled = sum(
        1
        for index in range(asked_rows)
        for column in range(asked_cols)
        if index < len(table) and not unanswered(
            table[index][column] if column < len(table[index]) else ""
        )
    )
    # Two of twelve. Every other check on this table passes.
    assert filled == 4
    assert round(100 * filled / (asked_rows * asked_cols)) == 33
