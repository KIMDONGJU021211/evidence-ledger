"""Reproduce the failure this library was written to catch.

    python examples/quickstart.py
"""

from __future__ import annotations

from evidence_ledger import Ledger
from evidence_ledger.presets import BROWSER_AGENT


def main() -> None:
    ledger = Ledger(BROWSER_AGENT, run_id="demo")

    # The agent searches a jobs site and gets a result list.
    ledger.record(
        "site_search",
        {"url": "https://jobs.example/search?q=backend", "rows": 5},
        ok=True,
        step=1,
    )

    # It opens two candidates...
    ledger.record("open_result", {"url": "https://jobs.example/p/1"}, ok=True, step=2)
    ledger.record("open_result", {"url": "https://jobs.example/p/2"}, ok=True, step=3)

    # ...but only reads one of them to the body.
    ledger.record(
        "extract",
        {
            "url": "https://jobs.example/p/1",
            "text": "Backend engineer. Full-time. 3+ years. Apply by Oct 1.",
        },
        ok=True,
        step=4,
    )

    # The answer describes both, and adds a salary figure from nowhere.
    answer = (
        "Two matches. #1 is full-time, 3+ years, closes Oct 1. "
        "#2 is full-time, 5+ years, closes Oct 15, paying 62,000,000 KRW."
    )

    report = ledger.summarize(read_only=True)
    print("read       :", report["sources_read"])
    print("listed     :", report["sources_listed"])
    print("opened, unread:", report["opened_never_read"])
    print("unsupported numbers:", sorted(ledger.unsupported_numbers(answer)))
    print("unregistered tools :", report["unregistered_tools"])

    # The trace for this run says: 4 tools, all ok. Nothing above is visible
    # from that. The posting at /p/2 was never read, and every detail asserted
    # about it -- plus the salary -- came from somewhere the tools did not go.
    #
    # Note what the number check prints: 62000000 and 15. The salary is the
    # finding. The 15 is "Oct 15" -- a date, not a claim. This is a signal, not
    # a verdict, and it is meant to be read next to answered_from_listing_only.
    # A tool that reports only clean findings is a tool that is hiding some.


if __name__ == "__main__":
    main()
