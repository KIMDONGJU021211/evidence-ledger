# evidence-ledger

[![tests](https://github.com/KIMDONGJU021211/evidence-ledger/actions/workflows/test.yml/badge.svg)](https://github.com/KIMDONGJU021211/evidence-ledger/actions/workflows/test.yml)
[![python](https://img.shields.io/badge/python-3.9%20%7C%203.11%20%7C%203.13-blue)](https://github.com/KIMDONGJU021211/evidence-ledger)
[![license](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

**한국어: [README.ko.md](README.ko.md)**

**Your agent said `75.2%`. The tool returned `0.0`.**

A step trace tells you a tool ran and came back `ok`. It does not tell you
whether the model read the page or only saw its title in a list. Those two runs
look identical in every log, in every dashboard, and in the answer itself.

This is a small, dependency-free Python library that keeps one row per tool
result and can therefore tell them apart:

| | |
|---|---|
| opened a page | **vs** read its body |
| a new source | **vs** the same source again |
| a read-only run | **vs** a write that happened inside it |
| a number a tool returned | **vs** a number the answer invented |

```bash
pip install git+https://github.com/KIMDONGJU021211/evidence-ledger
```

## You're probably here because

- The trace says the tool ran and came back `ok`, and you still cannot tell
  whether the model **read** the page or only saw its title in a list of search
  results.
- An answer quoted a number — a price, a percentage, a count — that is **not in
  any tool result**, and you want to know which numbers to go check.
- Your grounding or citation check reports **100%** and you do not believe it.
- A run you declared read-only **wrote something**, and nothing caught it.
- The agent **opened** a link, spent a step there, and then answered from the
  listing page it came from anyway.
- A sub-agent did the reading, so the parent transcript holds no evidence of it
  and every grounding check passes **in silence**.
- Your agent summarized a document it never fetched, and the summary was
  plausible enough that nobody noticed for a week.
- You want to know **which sources were actually read** in a run, not which
  tools were called.

Every one of those runs is indistinguishable from a good one in a step trace.
They are distinguishable in a per-result ledger, which is all this library is.

It does not know or care which framework you use. It needs one dict per tool
result and a manifest saying what each tool does.

## 30 seconds

```python
from evidence_ledger import Ledger
from evidence_ledger.presets import CLAUDE_CODE

ledger = Ledger(CLAUDE_CODE, run_id=job_id)

# wherever every tool result already passes through:
ledger.record(tool_name, result, ok=ok, step=n, arguments=args)

# when the answer is ready:
report = ledger.summarize(read_only=True)
```

```python
{
  "sources_read": 1,
  "sources_listed": 3,
  "answered_from_listing_only": False,
  "opened_never_read": ["https://jobs.example/p/2"],   # clicked in, never read
  "reread_sources": [],
  "read_only_violations": 0,
  "unregistered_tools": {},                            # ← check this one
}
```

And the number check:

```python
>>> ledger.unsupported_numbers("Northvale 75.2%, Eastbrook 92.9% (mean 73.69%)")
{'75.2', '92.9', '73.69'}
```

Numbers legitimately arrive from page *body* text, so a non-empty result is a
reason to look, not a verdict. Read it next to `answered_from_listing_only`: an
answer full of unsupported numbers **from a run that never read a body** is a
different thing entirely.

## Where the numbers come from

`numbers_in()` collects only what a tool returned **as a structured field** —
never body text. That restraint is deliberate and it cost something to learn.

The first attempt at a fabrication gate measured "answer numbers not found in
tool results" and got **56%**. The number was useless: most answer numbers come
from page body text, body text is not in the step trace, and the measurement
was mostly reporting its own blindness. Confirmed cases: **one**.

So this ships the measurement, not the gate. Accumulate real samples first;
build the gate on them. A gate you cannot back-test is a gate you cannot trust.

### `numbers_in_body()` — the companion set

Shipping only the field collector left that blindness in place. Graded with
fields alone, three real deliverables scored **100% unsupported** — and every
value in them was then found by hand on the live page.

```python
result = {"text": "432 pages · ISBN 9791163034735", "applicants": 5}

numbers_in(result)        # {'5'}                    the tool said so
numbers_in_body(result)   # {'432', '9791163034735'} it was in the text
```

Keep them **separate**. Merged, the field comparison loses its meaning;
omitted, the comparison cannot run at all. A number in neither set came from
somewhere the tools never went — on a run where an agent opened a service page
and an unrelated title, then reported three books with page counts, that check
flagged 6 of 6.

## Presets

```python
from evidence_ledger.presets import CLAUDE_CODE, PLAYWRIGHT_MCP, BROWSER_AGENT
```

They are starting points. **Check `ledger.unregistered()` on your first real
run** — a ledger built for four tools reported "0 sources read" because the
model reached for a fifth, and a ledger that knows 19 of your 83 tools will
report `read_only_violations: 0` and mean nothing by it.

Registering a tool means answering one question honestly: *does this put the
content in front of the model, or only the name of it?*

```python
from evidence_ledger import Spec, TYPE_BODY_READ, EFFECT_READ_WEB

manifest["fetch_invoice"] = Spec(
    EFFECT_READ_WEB, TYPE_BODY_READ,
    source_keys=("invoice_id",),   # tried in the result, then the arguments
    body_keys=("body",),
    source_kind="query",
)
```

## Field notes

Every design decision here is a failure that happened in a production agent
running against live Korean commerce, jobs and booking sites. They are written
up in [`docs/FIELD-NOTES.md`](docs/FIELD-NOTES.md), including the ones where
the *instrument* was the thing that was broken:

- A ledger that knew **19 of 83 tools** — so 890 body reads were recorded as
  "never read", and "read-only violations: 0" was false.
- A file reader that returned `content` and `char_count` but **no path**, so
  every one of its reads produced no source and vanished.
- Two tools that returned the source as a **list**, silently inert for weeks
  because the extractor only accepted `str`.
- "Opened but never read: 1" that turned out to be a site's **front page**,
  entered in order to search.
- A site tool that both searched and bookmarked, registered as a listing, so
  every write through it fell out of the violation count.

These are in the tests, named after what broke.

## What this is not

- **Not a gate.** It measures. Wiring it to pass/fail is your decision, and you
  should have samples before you make it.
- **Not a grounding model.** It does not judge whether a sentence follows from
  a source. It tells you whether the source was ever read. For span-level
  entailment see [LettuceDetect](https://github.com/KRLabsOrg/LettuceDetect).
- **Not a framework.** No agent loop, no LLM calls, no dependencies. One
  chokepoint, one call.
- **Not multi-agent-aware by itself.** Every row carries a `run_id`, which is
  what makes it *possible*: give each sub-agent its own `Ledger` with the same
  id and merge the rows. Otherwise a sub-agent's reading never reaches the
  parent transcript and your grounding check passes in silence.

## Prior work

The finding that harness wiring can dominate model choice is not ours alone —
[Harness-Bench](https://github.com/Qihoo360/harness-bench)
([paper](https://arxiv.org/pdf/2605.27922)) established it across models, and
[Saving SWE-Bench](https://arxiv.org/html/2510.08996v1) shows how much of a
benchmark score survives mutating the benchmark. We arrived at it independently on local models with a
controlled ablation, and this library is one of the instruments that got us
there.

## License

Apache-2.0. See [`LICENSE`](LICENSE).

Copyright 2026 [@KIMDONGJU021211](https://github.com/KIMDONGJU021211) and
[@bohyeon1010](https://github.com/bohyeon1010). See [`AUTHORS`](AUTHORS).
