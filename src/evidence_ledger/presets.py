"""Ready-made manifests for common agent stacks.

These are starting points, not guarantees. **Check
:meth:`Ledger.unregistered` on your first real run.** A ledger built for four
tools once reported "0 sources read" because the model reached for a fifth one
that nobody had registered — and a ledger that knows 19 of your 83 tools will
happily report "read-only violations: 0" and mean nothing by it.

Adding a tool means deciding one thing honestly: *does this tool put the
content in front of the model, or only the name of it?* Listing a search result
is not reading it. That distinction is the whole point.
"""

from __future__ import annotations

from typing import Any, Mapping

from .core import (
    EFFECT_READ_LOCAL,
    EFFECT_READ_WEB,
    EFFECT_WRITE_LOCAL,
    TYPE_ARTIFACT,
    TYPE_BODY_READ,
    TYPE_LISTING,
    TYPE_MUTATION,
    TYPE_PAGE_OPEN,
    TYPE_VERIFICATION,
    Spec,
)

__all__ = ["CLAUDE_CODE", "PLAYWRIGHT_MCP", "BROWSER_AGENT", "split_on_result"]


#: Claude Code / Claude Agent SDK built-in tools.
#:
#: Note what is *not* here. ``Task`` (sub-agent) is deliberately absent: a
#: sub-agent's reading happens in its own context and never reaches the
#: parent's transcript, so registering it as a read would assert something this
#: ledger cannot see. Give the sub-agent its own :class:`Ledger` with the same
#: ``run_id`` and merge the rows.
CLAUDE_CODE: dict[str, Spec] = {
    # --- read the body -------------------------------------------------
    # The path usually arrives in the *arguments*, not the result. A reader
    # that returns ``content`` and ``char_count`` but no ``file_path`` yields
    # no source at all, and every one of its reads vanishes from the ledger.
    "Read": Spec(
        EFFECT_READ_LOCAL, TYPE_BODY_READ, ("file_path", "path"), ("content",), "path"
    ),
    "NotebookRead": Spec(
        EFFECT_READ_LOCAL, TYPE_BODY_READ, ("notebook_path", "path"), ("content",), "path"
    ),
    "WebFetch": Spec(
        EFFECT_READ_WEB, TYPE_BODY_READ, ("url",), ("content", "text"), "url"
    ),
    # --- saw names only ------------------------------------------------
    # Grep and Glob return paths and matching lines. That is a list. An answer
    # asserting what a file *does*, from a Grep hit alone, is asserting
    # something it did not read.
    "Glob": Spec(EFFECT_READ_LOCAL, TYPE_LISTING, ("pattern", "path"), (), "query"),
    "Grep": Spec(EFFECT_READ_LOCAL, TYPE_LISTING, ("pattern",), (), "query"),
    "WebSearch": Spec(EFFECT_READ_WEB, TYPE_LISTING, ("query",), (), "query"),
    # --- wrote ---------------------------------------------------------
    "Write": Spec(
        EFFECT_WRITE_LOCAL, TYPE_ARTIFACT, ("file_path", "path"), (), "path"
    ),
    "Edit": Spec(
        EFFECT_WRITE_LOCAL, TYPE_MUTATION, ("file_path", "path"), (), "path"
    ),
    "NotebookEdit": Spec(
        EFFECT_WRITE_LOCAL, TYPE_MUTATION, ("notebook_path", "path"), (), "path"
    ),
    # --- both, depending on the result ---------------------------------
    # A shell runs tests and it also writes files. Registered as verification
    # alone, every write done through it falls out of "read-only violations"
    # and that number becomes a lie. Pass :func:`split_on_result` to the Ledger
    # to separate them.
    "Bash": Spec(EFFECT_READ_LOCAL, TYPE_VERIFICATION, ("command",), ("stdout",), "query"),
}


#: Playwright MCP server tool names.
#:
#: ``browser_snapshot`` is a **listing**, not a read. It returns an
#: accessibility tree of element labels — the names of things, not their
#: content. Runs that answer from snapshots alone are the exact failure this
#: ledger was written to catch.
PLAYWRIGHT_MCP: dict[str, Spec] = {
    "browser_navigate": Spec(EFFECT_READ_WEB, TYPE_PAGE_OPEN, ("url",), (), "url"),
    "browser_snapshot": Spec(EFFECT_READ_WEB, TYPE_LISTING, ("url",), (), "url"),
    "browser_take_screenshot": Spec(EFFECT_READ_WEB, TYPE_LISTING, ("url",), (), "url"),
    "browser_console_messages": Spec(
        EFFECT_READ_WEB, TYPE_VERIFICATION, ("url",), (), "url"
    ),
    "browser_network_requests": Spec(
        EFFECT_READ_WEB, TYPE_VERIFICATION, ("url",), (), "url"
    ),
    "browser_click": Spec(EFFECT_READ_WEB, TYPE_PAGE_OPEN, ("url", "ref"), (), "url"),
    "browser_type": Spec(EFFECT_WRITE_LOCAL, TYPE_MUTATION, ("url", "ref"), (), "url"),
    "browser_fill_form": Spec(
        EFFECT_WRITE_LOCAL, TYPE_MUTATION, ("url", "ref"), (), "url"
    ),
    "browser_evaluate": Spec(
        EFFECT_READ_WEB, TYPE_BODY_READ, ("url",), ("result", "text"), "url"
    ),
}


#: A generic browser agent, for stacks that name their tools plainly.
#:
#: The pair that matters is ``open_result`` versus ``navigate``. Opening a
#: **candidate** from a list and then never reading it is a finding; navigating
#: to a site's front page in order to search is not. Counting both makes
#: ``opened_never_read`` useless.
BROWSER_AGENT: dict[str, Spec] = {
    "extract": Spec(EFFECT_READ_WEB, TYPE_BODY_READ, ("url",), ("text", "content"), "url"),
    "open_result": Spec(
        EFFECT_READ_WEB, TYPE_PAGE_OPEN, ("url",), (), "url", candidate_open=True
    ),
    "navigate": Spec(EFFECT_READ_WEB, TYPE_PAGE_OPEN, ("url",), (), "url"),
    "search": Spec(EFFECT_READ_WEB, TYPE_LISTING, ("query", "url"), (), "query"),
    "site_search": Spec(EFFECT_READ_WEB, TYPE_LISTING, ("url", "query"), (), "url"),
    "snapshot": Spec(EFFECT_READ_WEB, TYPE_LISTING, ("url",), (), "url"),
    "click": Spec(EFFECT_READ_WEB, TYPE_PAGE_OPEN, ("url",), (), "url"),
    "fill": Spec(EFFECT_WRITE_LOCAL, TYPE_MUTATION, ("url",), (), "url"),
    "submit": Spec(EFFECT_WRITE_LOCAL, TYPE_MUTATION, ("url",), (), "url"),
}


def split_on_result(tool: str, spec: Spec, result: Mapping[str, Any]) -> Spec:
    """Separate tools that do **two jobs**, by looking at what came back.

    Pass this as ``Ledger(manifest, split=split_on_result)``.

    Split on the result, never the arguments. A sandbox invocation was once
    classified by its code — "this looks like it writes a file" — and the runs
    where the write *failed* were recorded as artifacts that do not exist. What
    actually happened is in the response.

    Two rules, both learned the hard way:

    * A shell that produced files wrote; otherwise it verified.
    * A site action that returned an **undo handle** wrote. Something became
      undoable, and that is the definition.
    """
    produced = result.get("files_written") or result.get("saved_to") or result.get("outputs")
    if tool in {"Bash", "shell", "run_command", "sandbox_run"} and produced:
        return Spec(EFFECT_WRITE_LOCAL, TYPE_ARTIFACT, spec.source_keys, (), spec.source_kind)
    if result.get("undo_action") or result.get("undo"):
        return Spec(EFFECT_WRITE_LOCAL, TYPE_MUTATION, spec.source_keys, (), spec.source_kind)
    return spec
