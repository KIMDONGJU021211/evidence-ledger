# Field notes

Failures from a production agent that browses live commerce, jobs and booking
sites, fills forms, and writes files. Each one is why some line in this library
exists. Dates are when the failure was measured, not when it started.

Half of these are failures of the **instrument**. Those are the expensive ones:
a broken tool reports a problem, but a broken measurement ends the
investigation.

---

## 1. The list was mistaken for a read

**2026-09-02.** The agent opened three job postings, read them, and produced a
table of five. For the other two — seen only as rows in a search result list —
it stated employment type, required experience and an application deadline.

None of those values appear on a list row.

The count check passed: three sources read, matching the requirement. **The
number was right and the content was invented.** Nothing in the trace could
distinguish "saw the name" from "read the page", because the trace records tool
names and `ok`.

→ `TYPE_LISTING`, and `answered_from_listing_only`.

---

## 2. The ledger knew 19 of 83 tools

**2026-09-04.** The first version registered four tools, then grew to nineteen.
Against a live run this produced:

```
body reads recorded:      0
body reads that happened: 890
read-only violations:     0        ← and this was false
```

The model reached for tools nobody had registered. Reads through them recorded
nothing, so a coding run that read all day reported "0 sources actually read".
Worse: the file-**writing** tool was also unregistered, so writes through it
never reached the violation count. The clean `0` was the ledger not looking.

→ `Ledger.unregistered()`, surfaced in `summarize()` output. Silence is the
failure mode, so it had to become visible.

---

## 3. What was read lived in the request, not the response

**2026-09-04.** The file reader returned `content`, `char_count`,
`line_start` — and no path. The source extractor read only results, found
nothing, and dropped the record. Silently: a dropped record looks exactly like
a tool that was never called.

→ `arguments` as a fallback source. The result is still tried first, because it
is closer to the truth (redirects, the file actually opened).

---

## 4. Two tools returned the source as a list

**2026-09-05.** Following a rule we had written down — *don't guess the keys,
count them in real traces* — turned up two tools handing back:

```python
command       = ["pytest", "tests/test_a.py", "-v"]
target_labels = ["Example University, Computer Science"]
```

The extractor checked `isinstance(value, str)`. Both tools were **registered and
completely inert**, and would have stayed that way indefinitely, because a tool
that produces no records is indistinguishable from a tool that was not used.

The trap we had guarded against on the *name* of the key met us again on the
*shape* of the value.

→ `_as_source_text()`.

---

## 5. "Opened but never read: 1" was a front page

**2026-09-03.** The first live reading of `opened_never_read` showed one
source. Opening it revealed the site's own home page — navigated to in order to
reach the search box. Not a candidate. Not a finding.

One false positive in the first row of a new metric is enough to make people
stop reading it.

→ `Spec.candidate_open`. Navigation and candidate-opening are different events;
counting both makes the metric lie in the direction of alarm.

---

## 6. One tool doing two jobs fell out of the count

**2026-09-03.** A site-automation tool ran recorded interaction paths. Some
searched. Some bookmarked, applied, or saved — writes. It was registered once,
as a listing, so every write performed through it was invisible to
`read_only_violations`.

The first instinct was to classify by the arguments: *this code looks like it
writes a file*. That is wrong in a specific way — runs where the write **failed**
got recorded as artifacts that do not exist.

→ `split_on_result`. Classify on what came back. An undo handle means something
became undoable, and that is the definition of a write.

---

## 7. Numbers passed every check because nothing looked at numbers

**2026-09-06.** A lookup tool returned, for three universities:

```
probability = 0.0    band = "high risk"
```

The answer's table read `75.2%`, `92.9%`, `66.9%` — twelve rows in all. The
agent then fed those twelve invented values into a code sandbox and computed
**"mean 73.69%, σ 24.72%"** — fabrication wearing the clothes of statistics.

Every check passed. Grounding compared names. The ledger knew only whether
something had been read. No verifier had a reason to fire. All three were
correct within their own scope and all three were blind to the same thing.

→ `numbers_in()` and `unsupported_numbers()`.

---

## 8. The first attempt to gate it measured 56% and meant nothing

Same day, immediately after. Building the gate required samples, so we
measured:

```
runs that used tools:                   1,002
runs whose answer contains numbers:       565
answer numbers absent from tool results:  319   (56%)
```

56% is not a fabrication rate. Most answer numbers come from page **body
text**; body text is not in the step trace (it lives in an in-memory
observation store that a restart clears). A genuine price, read off a real
page, showed up as "unsupported".

Confirmed fabrication cases: **one**.

A gate built on `n=1` is a gate nobody can back-test — and untestable gates get
disabled the first time they misfire, which is worse than not having built one.

→ Ship the measurement, not the gate. `numbers_in()` collects *only*
structured fields, where the meaning is unambiguous, so the samples that
accumulate are real.

---

## 9. A cap in a third place hid everything above it

**2026-08-13.** Four times in one day, a limit was raised and nothing changed,
because a *different* limit was doing the cutting. A sort control that the
agent "could not find" sat at position 4,255 of a scan capped at 700 — scanning
all 7,157 elements turned out to take 30 ms.

Limits live in three places: the dataclass default, the environment loader, and
**a hard-coded constant inside a function**. The third is the one nobody finds.

Not this library's bug, but the reason `_NUMBERS_MAX` and `_NUMBERS_DEPTH` are
module-level, named, and asserted in tests. Truncation does not arrive as an
error. It arrives as silence.

---

## 10. Notices don't work; structure does

**2026-08-13.** Guidance had been written into the prompt and into tool
responses: *use the search tool rather than building a URL by hand*. Across 260
runs, twelve built the URL by hand anyway — one of them hand-writing percent
encoding, getting it wrong, and searching for a corrupted string. Which returns
an **empty result list**, not a 404.

"Scroll when you need more" was followed in 9 of 142 runs. "Open several and
read them" produced 165 detail-page opens and exactly 1 scroll on a detail page.

If a rule can be enforced deterministically, it belongs in code, not in a
notice. This library is an instance of that: rather than instructing a model to
be honest about what it read, record what it read.

---

## What we would tell you to check first

1. **Your denominator.** Before believing any agent metric, ask what is being
   skipped. Runs with no tool calls. Tools that are not in your table. Records
   dropped for a missing source.
2. **Both directions.** A metric that only ever fires one way has not been
   tested. Feed it a run you know is clean and a run you know is dirty.
3. **Whether a clean zero is a real zero.** `read_only_violations: 0` from a
   ledger that knows 19 of your 83 tools is not information.
