"""A ledger of what tools *actually did* — one row per tool result.

An agent's step trace tells you a tool ran and returned ``ok``. It does not
tell you the difference between these four:

    opened a page          vs  read its body
    a new source           vs  the same source again
    a read-only run        vs  a write that happened inside it
    which claim the evidence supports

That last line is not hypothetical. On 2026-09-02 an agent opened and read
three job postings, then wrote a table that stated employment type, required
experience and application deadline for **two other companies it had only seen
in the result list**. The count check passed: three sources read. The number
was right and the content was invented.

This module only *measures*. It does not decide whether a run succeeded. Count
first, gate later — a gate built before you can measure is a gate you cannot
back-test.

Why the ledger is built at one chokepoint
-----------------------------------------
An earlier version attached bookkeeping to each tool that produced artifacts.
It leaked the first time an agent produced a file through a different tool.
Tools multiply and people forget to register them, so the record is made at the
single place every tool result must pass through.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit

__all__ = [
    "TYPE_BODY_READ",
    "TYPE_PAGE_OPEN",
    "TYPE_LISTING",
    "TYPE_ARTIFACT",
    "TYPE_MUTATION",
    "TYPE_VERIFICATION",
    "EFFECT_READ_LOCAL",
    "EFFECT_READ_WEB",
    "EFFECT_WRITE_LOCAL",
    "WRITE_EFFECTS",
    "Spec",
    "EvidenceRecord",
    "Ledger",
    "canonical_source",
    "numbers_in",
    "numbers_claimed_in",
]

#: Kinds of evidence. Separating ``page_open`` from ``body_read`` is the entire
#: reason this ledger exists.
TYPE_BODY_READ = "body_read"
TYPE_PAGE_OPEN = "page_open"
#: **Saw a list.** Neither opened nor read — only candidate names were visible.
#:
#: This is the exact location of the 2026-09-02 failure. The agent saw two
#: companies in a result list, never opened them, and still wrote their
#: employment type and deadline into the answer. Those values are not on a list
#: row. Without this kind, that run looks like "used its tools well".
TYPE_LISTING = "listing"
TYPE_ARTIFACT = "artifact"
TYPE_MUTATION = "mutation"
TYPE_VERIFICATION = "verification"

#: What was touched.
EFFECT_READ_LOCAL = "read_local"
EFFECT_READ_WEB = "read_web"
EFFECT_WRITE_LOCAL = "write_local"

#: Effects that count as writes. If one of these appears in a run declared
#: read-only, the policy was broken.
WRITE_EFFECTS = frozenset({EFFECT_WRITE_LOCAL})


@dataclass(frozen=True)
class Spec:
    """What one tool does, so its result can be turned into a record.

    Args:
        effect: One of the ``EFFECT_*`` constants.
        type: One of the ``TYPE_*`` constants.
        source_keys: Keys that may hold the source. Tried in order, result
            first and arguments second.
        body_keys: Keys that may hold the body text. If none match, the record
            carries no content hash.
        source_kind: How to normalise the source — ``path``, ``url`` or
            ``query``. A search has no address: *what was asked* is the
            identity of that list.
        candidate_open: Did this open a **candidate**, or merely navigate?

            Measured 2026-09-03: "opened but never read: 1" turned out to be
            ``https://example-shop.com/`` — the site's front page, entered in order to
            search. That is not a candidate. Counting navigation makes this
            metric lie.
    """

    effect: str
    type: str
    source_keys: tuple[str, ...]
    body_keys: tuple[str, ...] = ()
    source_kind: str = "path"
    candidate_open: bool = False


#: Hashes a tool computed itself. Even with no body key, this tells us whether
#: the content is the same. If a tool offers one and we ignore it, that is a
#: hole.
_HASH_KEYS = ("sha256", "content_sha256", "hash", "digest")


@dataclass(frozen=True)
class EvidenceRecord:
    """One row: this tool touched this source, in this way, at this step."""

    evidence_id: str
    type: str
    effect: str
    #: Normalised source. Whether the same place was read twice is decided
    #: **here**, not by comparing raw strings.
    source_id: str
    tool: str
    ok: bool
    #: Body hash. Same source, changed content is separated by this. Empty when
    #: there is no body.
    content_hash: str = ""
    #: Was a **candidate** opened from a list, rather than navigation? "Opened
    #: but never read" must only be asked of candidates.
    candidate: bool = False
    #: **Whose eyes saw it.** The run and step that produced this evidence.
    #:
    #: This is the key to multi-agent setups. Grounding checks usually read the
    #: parent's transcript; when a sub-agent does the reading, that tool result
    #: never enters the parent transcript and the check passes with no warning
    #: at all. An owner has to be recorded for the body to be retrievable.
    run_id: str = ""
    step: int = 0
    #: Numbers this tool returned as structured fields.
    numbers: tuple[str, ...] = ()
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


#: Some tools hand back the source as a **list**. Join it into one identity.
#:
#: Found 2026-09-05 while counting keys in real traces instead of guessing
#: them: two tools returned ``["pytest", "tests/...", "-v"]`` and
#: ``["Example University, Computer Science"]``. The extractor only accepted
#: ``str``, so those tools were **registered and silently inert** — the same
#: trap, met again on the shape of the value rather than the name of the key.
_SOURCE_LIST_MAX = 8


def _as_source_text(value: Any) -> str:
    """A usable source string: a string, or a list of strings."""
    if isinstance(value, str):
        return value if value.strip() else ""
    if isinstance(value, (list, tuple)):
        parts = [
            item.strip()
            for item in value[:_SOURCE_LIST_MAX]
            if isinstance(item, str) and item.strip()
        ]
        return " ".join(parts)
    return ""


#: Cap on numbers collected from one tool result. A ledger nobody reads is not
#: a ledger.
_NUMBERS_MAX = 400
#: Do not descend past this. Numbers this deep do not reach the answer.
_NUMBERS_DEPTH = 4

#: Numbers that are not claims. Ordinals, coordinates, timings, identifiers.
_NOT_A_CLAIM = frozenset(
    {
        "step", "rank", "index", "limit", "offset", "count", "polls", "ms",
        "took_ms", "elapsed_sec", "ready_ms", "element_count", "char_count",
        "line_start", "line_end", "x", "y", "width", "height", "id",
        "step_number", "status_code", "port", "pid", "timestamp",
    }
)


def numbers_in(result: Mapping[str, Any] | None) -> set[str]:
    """Numbers a tool returned **as structured fields**. Body text is ignored.

    Why only these
    --------------
    A run once received ``probability=0.0, band="high risk"`` from a lookup
    tool and wrote ``75.2%`` in its answer table — then fed twelve such
    invented values into a code sandbox and reported "mean 73.69%". It passed
    every check: grounding compared names, the ledger only knew whether
    something was read, and no verifier was triggered. None of them look at
    numbers.

    The first attempt to gate this failed for an instructive reason: **it could
    not be measured.** Most answer numbers come from page *body* text, and body
    text is not in the step trace. Counting "numbers not found in tool results"
    gave 56%, and most of that was the measurement's own blindness.

    So this collects only what a tool returned in a field, where the meaning is
    unambiguous. Accumulate it per run, and "the tool said 0.0 and the answer
    said 75.2" becomes countable.
    """
    found: set[str] = set()

    def walk(node: Any, depth: int, key: str = "") -> None:
        if len(found) >= _NUMBERS_MAX or depth > _NUMBERS_DEPTH:
            return
        if isinstance(node, bool):
            # In Python ``True`` is 1. Left alone it puts "1" in every run.
            return
        if isinstance(node, (int, float)):
            if key.lower() in _NOT_A_CLAIM:
                return
            # Integers as integers, floats as floats. Collapsing ``1`` and
            # ``1.0`` makes the comparison leak.
            found.add(str(int(node)) if float(node).is_integer() else repr(float(node)))
            return
        if isinstance(node, dict):
            for name, value in node.items():
                walk(value, depth + 1, str(name))
            return
        if isinstance(node, (list, tuple)):
            for value in node[:50]:
                walk(value, depth + 1, key)

    walk(dict(result or {}), 0)
    return found


#: Dates. Not claims, and the main source of format asymmetry between the two
#: sides of the comparison.
#
# ★ Measured 2026-09-09. A tool returned `마감일 2026.09.13`; the answer wrote
#   `~09.13(일)`. Same date, and the two sides normalised it differently:
#
#       source "2026.09.13"  ->  {"2026.09"}    (the dotted tail is skipped)
#       answer "09.13"       ->  {"9.13"}
#
#   No overlap, so the check reported a fabricated value. It was a rendering
#   difference. A false accusation in a fabrication check is how the check gets
#   switched off, so dates are removed from both sides before counting.
#
#   Deliberately not clever: these four shapes cover what a page and an answer
#   actually print, and date formats do not drift the way vocabulary does.
_DATE_SHAPES = re.compile(
    r"\d{4}\s*[.\-/]\s*\d{1,2}\s*[.\-/]\s*\d{1,2}"      # 2026.09.13
    r"|\d{1,2}\s*[.\-/]\s*\d{1,2}\s*\("                   # 09.13(일)
    r"|\d{4}년\s*\d{1,2}월(?:\s*\d{1,2}일)?"                 # 2026년 9월 13일
    r"|\d{1,2}월\s*\d{1,2}일"                                # 9월 13일
    r"|(?<![A-Za-z0-9])D\s*-\s*\d{1,3}"                     # D-23
)


#: A number in prose. Handles thousands separators and decimals.
#
# ★ The lookbehind rejects **ASCII** word characters, not `\w`. In Python `\w`
#   matches Hangul — and every CJK script — so `(?<![\w.])` silently dropped
#   every number written against a label with no space:
#
#       "예상 기간360일"   -> nothing        (the extractor joins DOM nodes)
#       "쪽수432쪽"        -> nothing
#       "예상 기간: 360일" -> 360            (only because a colon intervened)
#
#   Measured 2026-09-07: an agent read a page carrying `예상 기간360일`, wrote
#   **360** in its answer, and the check called it unsupported. The reading was
#   correct and the instrument was not. Latin-glued digits stay excluded —
#   those are identifiers and version numbers (`v2`, `call_12`).
_NUMBER_IN_TEXT = re.compile(
    r"(?<![0-9A-Za-z_.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?"
)

#: Values so common they carry no evidentiary weight. Flagging them buries the
#: real finding in noise — the same reason ordinals are excluded above.
_TRIVIAL = frozenset({"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "100"})


def numbers_claimed_in(answer: str) -> set[str]:
    """Numbers an answer asserts, normalised to compare against tool output.

    ``1,500,000`` and ``1500000`` are the same claim. ``75.2%`` claims
    ``75.2``. Single digits and round anchors are dropped: they appear in
    ordinary prose and would drown the signal.
    """
    found: set[str] = set()
    for whole, frac in _NUMBER_IN_TEXT.findall(_DATE_SHAPES.sub(" ", answer or "")):
        digits = whole.replace(",", "")
        if frac:
            value = f"{digits}.{frac}".rstrip("0").rstrip(".")
            if "." in value:
                found.add(repr(float(value)))
                continue
            # "3.0" is the claim "3". It has to be dropped by the same rule,
            # or the filter depends on how the author typed it.
            digits = value
        if digits not in _TRIVIAL:
            found.add(str(int(digits)))
    return found


#: How deep to walk, and how many to keep, when reading numbers out of body
#: text. Separate from the field limits: bodies are large and repetitive.
_BODY_NUMBERS_MAX = 600
#: How much of one string to read. An extracted page body can be 30,000 chars.
_BODY_TEXT_MAX = 40_000


def numbers_in_body(result: Mapping[str, Any] | None) -> set[str]:
    """Numbers a tool returned **inside its text**. The companion to `numbers_in`.

    Why this exists
    ---------------
    `numbers_in` reads only structured fields, deliberately: the meaning there
    is unambiguous. Field notes §8 records what that cost — 56% of answer
    numbers looked "unsupported" and the finding was the measurement's own
    blindness, because answer numbers come from page *body* text.

    Shipping only the field collector left that blindness in place. A later run
    made it plain: three deliverables, and the grounding check reported

        6 of 6 · 34 of 34 · 10 of 10 unsupported

    Every one of those values was then found, by hand, on the live page. A
    100% violation rate that is entirely instrument error is worse than no
    measurement, because it looks like a finding.

    So collect body numbers too — **in a separate set**. Merged, the field
    comparison loses its meaning; omitted, the comparison cannot run at all.

        field numbers   the tool said ``applicants: 5``      unambiguous
        body numbers    ``432`` appeared in text it returned  weak, but real

    A number in the answer that is in **neither** set came from somewhere the
    tools never went.

    Measured, on the run that motivated this: with fields alone, three
    deliverables scored 100% unsupported. With both sets, 0% — and on a
    separate run where the agent genuinely invented six values, 6 of 6 were
    still flagged. The signal survived; the noise did not.
    """
    found: set[str] = set()

    def take(text: str) -> None:
        # 날짜는 양쪽에서 **같은 방식으로** 지운다. 한쪽만 지우면 비대칭이 생기고,
        # 비대칭은 거짓 고발이 된다.
        for whole, frac in _NUMBER_IN_TEXT.findall(
            _DATE_SHAPES.sub(" ", text[:_BODY_TEXT_MAX])
        ):
            if len(found) >= _BODY_NUMBERS_MAX:
                return
            digits = whole.replace(",", "")
            if frac:
                value = f"{digits}.{frac}".rstrip("0").rstrip(".")
                if "." in value:
                    found.add(repr(float(value)))
                    continue
                digits = value
            if digits not in _TRIVIAL:
                found.add(str(int(digits)))

    def walk(node: Any, depth: int) -> None:
        if len(found) >= _BODY_NUMBERS_MAX or depth > _NUMBERS_DEPTH:
            return
        if isinstance(node, str):
            take(node)
        elif isinstance(node, Mapping):
            for value in node.values():
                walk(value, depth + 1)
        elif isinstance(node, (list, tuple)):
            for value in node[:50]:
                walk(value, depth + 1)

    walk(dict(result or {}), 0)
    return found


def canonical_source(value: str, *, kind: str = "path") -> str:
    """Call the same place by the same name.

    Files differ by case and relative path; URLs differ by fragment and
    trailing slash. Without normalisation you read one place twice and report
    "read 2 sources".

    A search has no address. **What was asked** is the identity of that list.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    if kind == "query":
        return "q:" + " ".join(text.split()).lower()
    if kind == "path":
        try:
            return os.path.normcase(os.path.abspath(text))
        except (OSError, ValueError):
            return text
    try:
        parts = urlsplit(text)
    except ValueError:
        return text
    if not parts.scheme:
        return text
    path = parts.path.rstrip("/") or "/"
    # Keep the query: for a search results URL the query *is* the identity.
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, parts.query, "")
    )


def _body_hash(result: Mapping[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        body = result.get(key)
        if isinstance(body, str) and body.strip():
            return hashlib.sha256(body.encode("utf-8", "replace")).hexdigest()[:16]
    # A tool that does not ship the body can still supply a hash. Ignoring one
    # that exists is a hole.
    for key in _HASH_KEYS:
        digest = result.get(key)
        if isinstance(digest, str) and digest.strip():
            return digest.strip()[:16]
    return ""


class Ledger:
    """Records what tools did during one run, then reports it.

    Register your own tools by passing a manifest — a mapping of tool name to
    :class:`Spec`. Presets for common stacks live in
    :mod:`evidence_ledger.presets`.

        >>> from evidence_ledger import Ledger
        >>> from evidence_ledger.presets import CLAUDE_CODE
        >>> ledger = Ledger(CLAUDE_CODE, run_id="run-1")
        >>> _ = ledger.record("Read", {"content": "hi"}, ok=True, step=1,
        ...                   arguments={"file_path": "/tmp/a.txt"})
        >>> ledger.summarize()["sources_read"]
        1

    Unregistered tools are skipped in silence, and that silence is dangerous:
    a ledger built for four tools reported "0 sources read" on its first live
    run because the model reached for a fifth. Use :meth:`unregistered` to see
    what it did not understand.
    """

    def __init__(
        self,
        manifest: Mapping[str, Spec],
        *,
        run_id: str = "",
        split: "Callable[[str, Spec, Mapping[str, Any]], Spec] | None" = None,
    ) -> None:
        """
        Args:
            manifest: tool name -> :class:`Spec`.
            run_id: identifies this run; recorded on every row so bodies can
                be retrieved later, including across agent boundaries.
            split: optional hook for tools that do **two jobs**. It receives
                ``(tool, spec, result)`` and returns the spec to use.

                A site-automation tool that both searched and bookmarked was
                registered as a listing, so every write done through it fell
                out of "read-only violations: 0" and the metric lied. Split on
                the **result**, not the arguments: the presence of an undo
                handle means something became undoable, and that is a write.
        """
        self.manifest = dict(manifest)
        self.run_id = str(run_id or "")
        self._split = split
        self.records: list[EvidenceRecord] = []
        self._unregistered: dict[str, int] = {}

    def record(
        self,
        tool: str,
        result: Mapping[str, Any] | None,
        *,
        ok: bool,
        step: int,
        arguments: Mapping[str, Any] | None = None,
    ) -> EvidenceRecord | None:
        """Turn one tool result into a record. Returns ``None`` when skipped.

        **No source, no record.** Evidence without a source says nothing when
        counted, and inventing one is worse than having none.

        ``arguments`` is a fallback, and it matters more than it looks. A
        file-reading tool that returns ``char_count`` and ``content`` but not
        ``path`` produced no source at all — **890 reads were missing** and
        "0 sources actually read" was a lie. What was read often lives in the
        request, not the response. The result is tried first because it is
        closer to the truth (redirected URLs, the file actually opened).
        """
        spec = self.manifest.get(tool)
        if spec is None:
            self._unregistered[tool] = self._unregistered.get(tool, 0) + 1
            return None
        payload: Mapping[str, Any] = result or {}
        if self._split is not None:
            spec = self._split(tool, spec, payload)
        raw = ""
        for source in (payload, arguments or {}):
            for key in spec.source_keys:
                raw = _as_source_text(source.get(key))
                if raw:
                    break
            if raw:
                break
        source_id = canonical_source(raw, kind=spec.source_kind)
        if not source_id:
            return None
        fingerprint = hashlib.sha256(
            f"{tool}|{source_id}|{step}".encode()
        ).hexdigest()[:8]
        entry = EvidenceRecord(
            evidence_id=f"e{step}-{fingerprint}",
            type=spec.type,
            effect=spec.effect,
            source_id=source_id,
            tool=tool,
            ok=bool(ok),
            content_hash=_body_hash(payload, spec.body_keys),
            candidate=spec.candidate_open,
            run_id=self.run_id,
            step=int(step),
            numbers=tuple(sorted(numbers_in(payload))),
        )
        self.records.append(entry)
        return entry

    def unregistered(self) -> dict[str, int]:
        """Tools this ledger did not understand, and how often they ran.

        Check this on every new agent. A ledger that knows 19 of 83 tools will
        report "read-only violations: 0" and mean nothing by it.
        """
        return dict(self._unregistered)

    def numbers(self) -> set[str]:
        """Every number the tools returned as structured fields."""
        found: set[str] = set()
        for entry in self.records:
            found.update(entry.numbers)
        return found

    def unsupported_numbers(self, answer: str) -> set[str]:
        """Numbers the answer asserts that **no tool returned**.

        This is a signal, not a verdict. Numbers legitimately arrive from page
        body text, which is not a structured field, so a non-empty result is a
        prompt to look — not proof of fabrication. Read
        :meth:`answered_without_reading` alongside it: an answer full of
        unsupported numbers *from a run that never read a body* is a different
        thing entirely.
        """
        return numbers_claimed_in(answer) - self.numbers()

    def bodies(self, resolve: "Callable[[str, int], str]") -> str:
        """Collect the text of everything this run **read to the body**.

        Grounding checks should take their material from here rather than from
        the transcript, for two reasons:

        1. **Transcripts get truncated.** A context-window trimmer folds older
           tool results away, and then a name that *was* read is scored as
           unread.
        2. **Transcripts do not cross agent boundaries.** When a sub-agent does
           the reading, the parent transcript has nothing — and the check
           passes silently. The ledger carries an owner, so the body can be
           retrieved.

        ``resolve(run_id, step)`` returning empty simply skips that record.
        Bodies are never carried out of the process: compare where the text is.
        """
        chunks: list[str] = []
        for entry in self.records:
            if entry.type != TYPE_BODY_READ or not entry.ok:
                continue
            try:
                body = resolve(entry.run_id, entry.step)
            except Exception:  # noqa: BLE001 - a missing body must not kill the run
                body = ""
            if body:
                chunks.append(body)
        return "\n".join(chunks)

    def answered_without_reading(self) -> bool:
        """Saw lists, opened nothing to the body. The 2026-09-02 shape."""
        return self.summarize()["answered_from_listing_only"]

    def summarize(self, *, read_only: bool = False) -> dict[str, Any]:
        """What this run actually did.

        ``opened_never_read`` is why the ledger exists. How many sources were
        clicked into from a list and never read — there was no way to count
        that at all.
        """
        opened: set[str] = set()
        read: set[str] = set()
        listed: set[str] = set()
        reads_by_source: dict[str, int] = {}
        writes = 0
        for entry in self.records:
            if not entry.ok:
                continue
            if entry.type == TYPE_PAGE_OPEN:
                # Navigation is not counted. "Opened but never read" is asked
                # of **candidates** only — a site's front page showed up as
                # "never read: 1" until this was separated.
                if entry.candidate:
                    opened.add(entry.source_id)
            elif entry.type == TYPE_LISTING:
                listed.add(entry.source_id)
            elif entry.type == TYPE_BODY_READ:
                read.add(entry.source_id)
                reads_by_source[entry.source_id] = (
                    reads_by_source.get(entry.source_id, 0) + 1
                )
            if entry.effect in WRITE_EFFECTS:
                writes += 1
        return {
            "records": len(self.records),
            "sources_opened": len(opened),
            "sources_read": len(read),
            "sources_listed": len(listed),
            # **Did this run answer from a list alone?** It saw lists and read
            # no body. The 2026-09-02 failure had exactly this shape, and the
            # count check passed it. Some requests legitimately end here
            # ("just give me the titles"), so this is a signal, not a fault.
            "answered_from_listing_only": bool(listed) and not read,
            # Clicked in, never read. This is where "I read three" turns false.
            "opened_never_read": sorted(opened - read),
            # Read the same place twice. Where opening one thing twice used to
            # report "2 sources".
            "reread_sources": sorted(s for s, n in reads_by_source.items() if n > 1),
            "write_effects": writes,
            # Declared read-only and then wrote. Must be 0.
            "read_only_violations": writes if read_only else 0,
            "unregistered_tools": dict(self._unregistered),
        }

    def to_rows(self) -> list[dict[str, Any]]:
        """Every record as a plain dict, for storage or transport."""
        return [entry.to_dict() for entry in self.records]
