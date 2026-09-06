"""Ways a ledger reports zero and means nothing by it.

Each of these produced a metric that read clean while the thing it measured was
happening. They are tested first because a measuring instrument with a hole is
worse than no instrument: it ends the investigation.
"""

from __future__ import annotations

from evidence_ledger import Ledger, Spec
from evidence_ledger.core import (
    EFFECT_READ_LOCAL,
    EFFECT_WRITE_LOCAL,
    TYPE_BODY_READ,
    TYPE_VERIFICATION,
)
from evidence_ledger.presets import CLAUDE_CODE, split_on_result


def test_the_source_can_live_in_the_arguments():
    """**890 reads were missing.** The reader returned ``content`` and
    ``char_count`` but no path, so no source could be built and every record
    was dropped. "0 sources actually read" was a lie about a run that read all
    day. What was read often lives in the request, not the response.
    """
    ledger = Ledger(CLAUDE_CODE, run_id="r1")
    entry = ledger.record(
        "Read",
        {"content": "hello", "char_count": 5},  # no path here
        ok=True,
        step=1,
        arguments={"file_path": "src/app.py"},
    )
    assert entry is not None
    assert ledger.summarize()["sources_read"] == 1


def test_the_result_wins_over_the_arguments():
    """The response is closer to the truth: redirects, the file actually opened."""
    ledger = Ledger(CLAUDE_CODE, run_id="r1")
    entry = ledger.record(
        "WebFetch",
        {"url": "https://final.example/page", "content": "x"},
        ok=True,
        step=1,
        arguments={"url": "https://short.example/abc"},
    )
    assert entry is not None
    assert entry.source_id == "https://final.example/page"


def test_a_source_that_is_a_list_still_counts():
    """2026-09-05. Counting keys in real traces instead of guessing them showed
    two tools returning the source as a **list**. The extractor only accepted
    ``str``, so both were registered and silently inert.
    """
    manifest = {
        "run_tests": Spec(
            EFFECT_READ_LOCAL, TYPE_VERIFICATION, ("command",), ("stdout",), "query"
        )
    }
    ledger = Ledger(manifest, run_id="r1")
    entry = ledger.record(
        "run_tests",
        {"command": ["pytest", "tests/test_a.py", "-v"], "stdout": "2 passed"},
        ok=True,
        step=1,
    )
    assert entry is not None
    assert "pytest" in entry.source_id


def test_no_source_makes_no_record():
    """Evidence without a source says nothing when counted. Better absent than
    invented.
    """
    ledger = Ledger(CLAUDE_CODE, run_id="r1")
    assert ledger.record("Read", {"content": "x"}, ok=True, step=1) is None
    assert ledger.summarize()["records"] == 0


def test_unregistered_tools_are_reported_not_hidden():
    """A ledger built for four tools reported "0 sources read" on its first
    live run because the model reached for a fifth. Silence is the failure
    mode; make it visible.
    """
    ledger = Ledger(CLAUDE_CODE, run_id="r1")
    ledger.record("some_custom_tool", {"path": "/x"}, ok=True, step=1)
    ledger.record("some_custom_tool", {"path": "/y"}, ok=True, step=2)

    assert ledger.unregistered() == {"some_custom_tool": 2}
    assert ledger.summarize()["unregistered_tools"] == {"some_custom_tool": 2}


def test_a_tool_doing_two_jobs_is_split_by_its_result():
    """A site tool that both searched and bookmarked was registered as a
    listing, so every write through it fell out of "read-only violations: 0".
    Split on the result: an undo handle means something became undoable.
    """
    ledger = Ledger(CLAUDE_CODE, run_id="r1", split=split_on_result)
    ledger.record(
        "Bash",
        {"stdout": "ok", "files_written": ["out/report.csv"]},
        ok=True,
        step=1,
        arguments={"command": "python make_report.py"},
    )
    report = ledger.summarize(read_only=True)
    assert report["write_effects"] == 1
    assert report["read_only_violations"] == 1


def test_a_shell_that_only_ran_tests_is_not_a_write():
    ledger = Ledger(CLAUDE_CODE, run_id="r1", split=split_on_result)
    ledger.record(
        "Bash", {"stdout": "2 passed"}, ok=True, step=1, arguments={"command": "pytest"}
    )
    assert ledger.summarize(read_only=True)["read_only_violations"] == 0


def test_bodies_survive_a_missing_resolver():
    """A body that cannot be retrieved must not kill the run."""
    ledger = Ledger(CLAUDE_CODE, run_id="r1")
    ledger.record("Read", {"content": "a"}, ok=True, step=1, arguments={"file_path": "a.py"})

    def broken(run_id: str, step: int) -> str:
        raise RuntimeError("store is gone")

    assert ledger.bodies(broken) == ""


def test_bodies_come_back_with_their_owner():
    """The owner is what makes multi-agent grounding possible: when a sub-agent
    does the reading, the parent transcript has nothing and the check passes
    silently.
    """
    ledger = Ledger(CLAUDE_CODE, run_id="sub-7")
    ledger.record("Read", {"content": "x"}, ok=True, step=3, arguments={"file_path": "a.py"})

    seen: list[tuple[str, int]] = []

    def resolve(run_id: str, step: int) -> str:
        seen.append((run_id, step))
        return "the actual body"

    assert ledger.bodies(resolve) == "the actual body"
    assert seen == [("sub-7", 3)]


def test_a_manifest_spec_can_be_added_by_hand():
    manifest = dict(CLAUDE_CODE)
    manifest["fetch_invoice"] = Spec(
        EFFECT_WRITE_LOCAL, TYPE_BODY_READ, ("invoice_id",), ("body",), "query"
    )
    ledger = Ledger(manifest, run_id="r1")
    entry = ledger.record("fetch_invoice", {"invoice_id": "INV-9", "body": "..."}, ok=True, step=1)
    assert entry is not None and entry.source_id == "q:inv-9"
