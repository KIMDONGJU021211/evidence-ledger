"""The distinction the whole library exists for.

Every test here is a real failure, reduced. The docstrings say which one.
"""

from __future__ import annotations

from evidence_ledger import Ledger
from evidence_ledger.presets import BROWSER_AGENT, CLAUDE_CODE


def test_a_list_is_not_a_read():
    """2026-09-02. Three postings were opened and read; the answer's table then
    stated employment type, required experience and a deadline for **two other
    companies seen only in the result list**. The count check passed — three
    sources read. The number was right and the content was invented.
    """
    ledger = Ledger(BROWSER_AGENT, run_id="r1")
    ledger.record("site_search", {"url": "https://jobs.example/list?q=dev"}, ok=True, step=1)

    report = ledger.summarize()
    assert report["sources_listed"] == 1
    assert report["sources_read"] == 0
    assert report["answered_from_listing_only"] is True
    assert ledger.answered_without_reading() is True


def test_reading_one_clears_the_listing_only_flag():
    ledger = Ledger(BROWSER_AGENT, run_id="r1")
    ledger.record("site_search", {"url": "https://jobs.example/list?q=dev"}, ok=True, step=1)
    ledger.record(
        "extract",
        {"url": "https://jobs.example/p/1", "text": "Full-time. 3+ years."},
        ok=True,
        step=2,
    )
    assert ledger.summarize()["answered_from_listing_only"] is False


def test_opened_but_never_read_is_counted():
    """"I read three" turns false right here."""
    ledger = Ledger(BROWSER_AGENT, run_id="r1")
    ledger.record("open_result", {"url": "https://jobs.example/p/1"}, ok=True, step=1)
    ledger.record("open_result", {"url": "https://jobs.example/p/2"}, ok=True, step=2)
    ledger.record(
        "extract", {"url": "https://jobs.example/p/1", "text": "..."}, ok=True, step=3
    )

    report = ledger.summarize()
    assert report["opened_never_read"] == ["https://jobs.example/p/2"]
    assert report["sources_read"] == 1


def test_navigation_is_not_a_candidate():
    """2026-09-03. "Opened but never read: 1" turned out to be the site's front
    page, entered in order to search. Counting navigation makes the metric lie.
    """
    ledger = Ledger(BROWSER_AGENT, run_id="r1")
    ledger.record("navigate", {"url": "https://shop.example/"}, ok=True, step=1)
    ledger.record("site_search", {"url": "https://shop.example/s?q=x"}, ok=True, step=2)

    assert ledger.summarize()["opened_never_read"] == []


def test_the_same_place_read_twice_is_one_source():
    """Opening one thing twice used to report "2 sources read"."""
    ledger = Ledger(BROWSER_AGENT, run_id="r1")
    for step in (1, 2):
        ledger.record(
            "extract",
            {"url": "https://a.example/p/1#section", "text": "body"},
            ok=True,
            step=step,
        )

    report = ledger.summarize()
    assert report["sources_read"] == 1
    assert report["reread_sources"] == ["https://a.example/p/1"]


def test_a_failed_tool_is_not_evidence():
    ledger = Ledger(BROWSER_AGENT, run_id="r1")
    ledger.record("extract", {"url": "https://a.example/p/1"}, ok=False, step=1)
    assert ledger.summarize()["sources_read"] == 0


def test_grep_is_a_listing_not_a_read():
    """A Grep hit gives a path and a matching line. Asserting what the file
    *does* from that is asserting something unread.
    """
    ledger = Ledger(CLAUDE_CODE, run_id="r1")
    ledger.record("Grep", {"matches": 12}, ok=True, step=1, arguments={"pattern": "def run"})
    assert ledger.summarize()["answered_from_listing_only"] is True
