"""A run that failed still left files behind, and the report should say which.

Measured on an agent using a small local model, over three series of 16-18 runs:
5 of the 15 jobs that ended ``failed`` had written files a grader scored as
passing. The status the caller saw said only ``failed``.

What the list must get right is mostly what it must **leave out**: scripts the
run wrote to check itself and then deleted, calls that failed, and files that
were never this run's to report.
"""

from __future__ import annotations

from evidence_ledger import (
    EFFECT_DELETE_LOCAL,
    EFFECT_WRITE_LOCAL,
    TYPE_MUTATION,
    WRITE_EFFECTS,
    Ledger,
    Spec,
    canonical_source,
)

MANIFEST = {
    "write": Spec(EFFECT_WRITE_LOCAL, TYPE_MUTATION, ("path",)),
    "delete": Spec(EFFECT_DELETE_LOCAL, TYPE_MUTATION, ("path",)),
}


def _names(*paths: str) -> list[str]:
    """The ledger stores normalised sources; compare in the same form so this passes on any OS."""
    return [canonical_source(path) for path in paths]


def _run(*calls) -> Ledger:
    ledger = Ledger(MANIFEST, run_id="r")
    for step, (tool, path, ok) in enumerate(calls, start=1):
        ledger.record(tool, {"path": path}, ok=ok, step=step)
    return ledger


def test_the_files_a_run_wrote_are_listed_in_the_order_it_wrote_them() -> None:
    ledger = _run(("write", "/w/index.html", True), ("write", "/w/style.css", True))

    assert ledger.surviving_writes() == _names("/w/index.html", "/w/style.css")


def test_a_script_the_run_wrote_to_check_itself_and_then_deleted_is_not_a_result() -> None:
    """Listing it would hand the caller a file that no longer exists."""
    ledger = _run(
        ("write", "/w/index.html", True),
        ("write", "/w/verify.py", True),
        ("delete", "/w/verify.py", True),
    )

    assert ledger.surviving_writes() == _names("/w/index.html")


def test_a_failed_delete_leaves_the_file_in_the_list() -> None:
    ledger = _run(("write", "/w/verify.py", True), ("delete", "/w/verify.py", False))

    assert ledger.surviving_writes() == _names("/w/verify.py")


def test_a_failed_write_is_not_a_file() -> None:
    ledger = _run(("write", "/w/index.html", False))

    assert ledger.surviving_writes() == []


def test_deleting_something_the_run_never_wrote_says_nothing_about_the_list() -> None:
    """It was not ours to report — and it must not remove an unrelated entry either."""
    ledger = _run(("write", "/w/a.txt", True), ("delete", "/w/old-cache.tmp", True))

    assert ledger.surviving_writes() == _names("/w/a.txt")


def test_a_file_written_deleted_and_written_again_exists() -> None:
    ledger = _run(
        ("write", "/w/a.txt", True), ("delete", "/w/a.txt", True), ("write", "/w/a.txt", True),
    )

    assert ledger.surviving_writes() == _names("/w/a.txt")


def test_rewriting_a_file_lists_it_once() -> None:
    ledger = _run(("write", "/w/a.txt", True), ("write", "/w/b.txt", True), ("write", "/w/a.txt", True))

    assert ledger.surviving_writes() == _names("/w/b.txt", "/w/a.txt")  # at its last write


def test_deleting_counts_as_a_write_in_a_run_declared_read_only() -> None:
    """A read-only run that removed a file broke the policy as much as one that created it."""
    assert EFFECT_DELETE_LOCAL in WRITE_EFFECTS
    ledger = _run(("delete", "/w/a.txt", True))

    assert ledger.summarize(read_only=True)["read_only_violations"] == 1


def test_an_empty_run_left_nothing() -> None:
    assert Ledger(MANIFEST).surviving_writes() == []
