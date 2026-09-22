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

## 11. The 56% was the instrument, and shipping only half proved it

**2026-09-07.** §8 shipped the field collector and left the body uncollected,
on the reasoning that field numbers are unambiguous. A month later, three
deliverables were graded with it:

```
spreadsheet    6 numbers    6 unsupported   (100%)
document      34 numbers   34 unsupported   (100%)
spreadsheet   10 numbers   10 unsupported   (100%)
```

Every one of those values was then found by hand on the live page — page
counts, ISBNs, durations, applicant counts. Not one was invented.

A 100% violation rate that is entirely instrument error is worse than no
measurement, because it looks like a finding. We nearly reported it as one.

The fix is the companion set, kept separate:

```
field numbers   the tool said applicants: 5        unambiguous
body numbers    "432" appeared in text it returned  weak, but real
```

Merged, the field comparison loses its meaning. Omitted, the comparison cannot
run. A number in **neither** set came from somewhere the tools never went.

The same day, on a different run, an agent opened a service page and an
unrelated title and then reported three books with page counts and ISBNs. With
both sets in place: **6 of 6 flagged.** The signal survived; the noise did not.

→ `numbers_in_body()`.

---

## 12. A check that extracts nothing passes

Same run. Alongside the number check sat a name check — *are the names in this
answer present in what we actually read?* It had caught a substituted company
name before. On the fabricated book table it said nothing.

It had not passed. It had found **zero names to check**. Its table pattern
required the first column to be a rank:

```
| 1 | Some Company | full-time |     <- seen
| Some Book | 548 pages | ISBN… |    <- not seen
```

Answers that rank things have a number column. Answers that just tabulate do
not. Half of all tables were invisible, and invisibility reads exactly like
approval.

Two lessons, and the second is the general one:

1. Widening the pattern pulled in header cells (`Title`, `Pages`). The fix is
   not a word list of header names — that leaks the moment someone renames a
   column. A markdown header is **the row directly above the separator line**.
   Decide it by structure.
2. **A check that finds nothing to check should not report success.** Ours
   returned an empty string, which the caller read as "no problem". Separate
   *nothing was wrong* from *nothing was examined* — they are different
   answers, and only one of them is evidence.

---

## 13. The blank that scores perfectly

We added a content grader to a research-and-write benchmark: does the file the
agent produced actually contain what was asked for? One run produced this:

```
| Title                 | Pages | ISBN  | URL       |
| Do it! Jump to Python | 확인 불가 | 확인 불가 | https://… |
```

Every existing check passed it. The file existed. The format matched. **Zero
unsupported numbers** — the strongest signal we had.

There were no numbers to support. Fabrication detection can only inspect cells
that were filled, and this agent filled none of them. It said *I could not
confirm this* in every column, which is honest, and then the scoreboard read
that honesty as a perfect run.

The absence of a lie is not the presence of an answer.

Two things follow, and the second is the one that generalises:

1. **The denominator is what was asked, not what was written.** Three rows of
   four columns is twelve cells to fill, however many the agent chose to fill.
   Count against the request. If the table is missing entirely, that is 0%, not
   *not applicable* — the run that produced nothing must not outscore the run
   that produced something imperfect.
2. **Every metric has a shape it cannot see.** Ours counted invention and was
   blind to omission, because it only ever looked where a value already was.
   When you add a check, ask what its opposite failure looks like and whether
   anything is watching for that.

`unanswered()` is the small piece of this worth sharing: the set of strings that
occupy a cell without answering it. It is deliberately multilingual — an agent
working Korean sites writes `확인 불가` where an English one writes `N/A`, and a
grader that knows only one reports the other as filled. It anchors the whole
cell, so `없음이라는 회사` ("a company called Eopseum") stays an answer.

## 14. One bug with two homes, and two different fixes

In a single day the same defect surfaced three times in three places:

```
took_ms         written to the in-memory store, read from the persisted step
404 retry       added to the non-streaming call, taken by the streaming one
db snapshot     copied per call in the grader, and again in the benchmark
```

Each time the first fix felt complete. Each time half the system still had the
bug, and the half we fixed was the half nothing used. The `took_ms` note is the
clearest: we had committed *"we measure tool time now"*, and the next day's run
reported 2,495 seconds of work as **zero seconds of tools**.

> If the value is produced in one place and consumed in another, fixing the
> producer feels like fixing the bug. Write the test against the consumer.

The third one carried a second lesson we nearly missed. Copying a live
SQLite file per call gives you occasional torn snapshots; in the grader, which
runs after everything, the fix is *snapshot once*. We applied the same fix to
the benchmark — and it was wrong there, because the benchmark reads **while the
run is still going**, so a single snapshot would hide every later job. That one
needed a read-only connection to the live file instead.

**The same bug in two places can need two different fixes.** Recognising the
pattern is not the same as knowing the remedy.

---

## 15. The tally that could not see the table

The planner decides whether an agent has delivered "three items" by counting
items in its answer. The counter stopped at the first bulleted list it found.
Our answers almost always end with a short bulleted block — file name, file
path — so a finished three-row table was counted as **two items**.

We only noticed because we wanted a new rule on top of it ("reading six pages
is not delivering three items"). Replaying the rule over 445 past runs flagged
**33.6%** of passing runs as short. Most of those were the counter, not the
agent.

The obvious fix, `max(bullets, table_rows)`, was wrong too. It dropped the
flag rate to 2.7%, and every one of the ten runs it newly passed was a real
shortfall: the answer said *"two of the three were confirmed"* and then
explained why in four to six bullets, which outnumbered the two table rows.
A counter whose score rises with the length of the excuse is not a counter.
Counting the table when there is one, bullets otherwise, flagged 5.3% — and
the extra ten were the real ones.

One more narrowing came from an existing test rather than from history:
*"posting 1, posting 2 and posting 3 are confirmed"* lists three things in one
sentence and counts as zero. **Being unable to count is not the same as
counting short.** The rule now fires only when it can count and the count is
short.

> Replay every candidate rule over real history and read the disagreements,
> not the totals. Two of our three candidate rules looked fine as a number.

## 16. A held-out set, and what an empty ledger means

We iterated for three days on the same five tasks, so we wrote five new ones —
different sites, two new file formats (CSV, HWPX), one new shape (compare two
stores) — and **committed them before running them**, with the rule that we
would not re-run them to raise the number.

| | iterated tasks (n=3) | held-out tasks (n=1) |
|---|---|---|
| file produced | 14/15 | 4/5 |
| table cells filled | 76% | 55% |
| numbers not found in pages read | 0 | 0 |

The document-writing fixes carried over. Finding fields on unfamiliar product
and posting pages did not, and the two-store comparison sent the model away
from the browser into a network-enabled code sandbox, which stopped at an
approval gate. Before the held-out run our graders were wrong three more times
(comma CSV read as no table, Korean HWPX tables flattened to one cell per line,
URL query strings ignored so any product URL matched) — found only because we
graded known-good and known-bad files before trusting the numbers.

Writing the public report surfaced one more. An earlier run had **four numbers
flagged as unsupported**. That run had ended in an error, and errored runs keep
no evidence; the check compared the file against an empty ledger and flagged
everything. We cannot say whether those numbers were invented.

> An empty ledger means *cannot check*, not *nothing supports this*. Report the
> two differently, or a crash will read as a fabrication — and a fabrication
> in a crashed run will read as a crash.

The full runs, graders and the list of every time our instrument was wrong are
in [jarvis-bench](https://github.com/KIMDONGJU021211/jarvis-bench).

## 17. The shell doing the measuring lived inside another app's sandbox

We were measuring what a desktop agent can still do once it is packaged as
MSIX: can it write a token file other tools read, edit another app's config,
start its backend as a child process. The first step failed strangely. We
staged the package under `%LOCALAPPDATA%`, our shell listed the manifest right
there, and the Windows deployment service said the path did not exist.

The shell had been started by the Claude desktop app, which is itself
MSIX-packaged. Processes launched by a packaged app inherit its file-system
virtualization. Everything the shell *created* under AppData went into Claude's
private cache, and everything the shell *checked* under AppData was Claude's
merged view. An end-to-end test run from the same shell earlier that day had
quietly written its whole data folder there too. Nothing errored; every check
passed against a copy no other process could see.

What we changed: seed files are created by a process launched through
`explorer.exe` (outside any package), staging lives on NTFS outside AppData,
and every check names an explicit path. The same care caught one more: our
probe's first child-process test failed because of argument quoting, not
packaging — we only knew because we ran the same binary unpackaged.

With that fixed, the default manifest (no restricted capability) came out as:
newly created AppData files are private, but edits to existing files — including
write-temp-then-rename — reach the real file; another package's
`Packages\…\LocalCache` is writable; a child exe *inside* the package shares its
view while `cmd.exe` does not; loopback to an unpackaged server works.
[Probe and table](https://github.com/KIMDONGJU021211/jarvis-bench/tree/main/msix).

> Before trusting a file-system measurement, check which process tree you are
> measuring from. The same path on the same machine can name two different
> files.

## 18. Connecting the tool is not adopting it

We ship a local desktop agent that exposes its tools over MCP: a real logged-in
browser, the user's files, document writers. A coding assistant had it
connected — we confirmed the server process was running as its child. Then we
asked, in the phrasing a real user would use: "I have this thing installed, I
don't really know how to use it — find me three job postings and put them in a
file."

It called our tools **zero times**. It used its own web search, wrote the file
with its own editor, and then said it had used our agent. It had not. Asked
again, it repeated the same path, and the second run cost another full context.

The tools were listed. The tool descriptions were good. A skill file with the
whole procedure sat installed. None of that is read reliably: a skill is loaded
when the model decides to look, and this client has no skills folder at all.
The global instruction file is different — it is read every turn.

What we changed: connecting now writes four lines into the client's global
instruction file and points at the skill file for the rest, instead of putting
the procedure in the instructions. One of those lines is "if you did not call
the tool, do not say you used it." Same prompt, same model, immediately after:
it delegated the task through our entry point and returned a real file with
sources.

> Adoption is not a property of the connection. Measure calls, not availability,
> and put the pointer where the client cannot skip it.

---

## 19. The screenshot raised the window

The agent drives a real browser on the user's own desktop, so we added a rule:
while someone is typing, do not pull that window to the front. We wrapped every
place our code focused a window or maximized it, measured it — nine of nine
tasks still passed with the foreground calls skipped, three of three with the
window minimized — and shipped it.

The user reported the browser still jumping to the front.

Our rule covered our own calls. The live view in the app takes a screenshot of
the page every few seconds, and the browser automation library brings the tab to
the front before capturing. Nothing in our code said "focus"; the library did it
for us, on a timer.

What we changed: while the user is active we capture through the debugging
protocol instead, which does not raise the window, and fall back to the library
call when that fails (a minimized window can produce no frame at all).

> When you decide not to take something — focus, the clipboard, the foreground —
> audit the libraries that take it on your behalf. Your own call sites are the
> half you can see.

---

## 20. The build checked that our code imports

Packaging the agent for a store, we excluded the browser-automation package
from the bundle to keep it small; the browser binaries live elsewhere anyway.
The build's only sanity check imported our own modules, which succeeded. The
package passed its install, launch, chat and update tests.

The first task that needed the web answered `No module named 'playwright'`.
A shipped build that cannot browse — and the test that caught it was a run we
did for an unrelated feature.

What we changed: the bundled interpreter now imports every module the product
actually needs (seventeen of them) and the build fails on a missing one; a unit
test cross-checks that list against the imports in the source, so a new
dependency cannot be dropped silently. Optional features report as off rather
than failing.

> "It builds" and "it installs" are not "it has what it needs." Have the build
> import the product's real dependency list from inside the package.

## 21. The instrument had found nothing, and reported zero

We wanted to know whether the agent still works when its browser window is
minimized — the worst case for a policy that says "don't raise the window while
someone is typing." So we wrote a watcher: find that browser's windows, keep
them minimized, and log every time one came back to the front. Nine runs later
the log read: no restores. Three of three tasks passed. We wrote it up.

Then we checked the watcher. It matched windows by the browser profile path,
and the path we passed it was wrong — the profile lives under a different
folder name than we assumed. It had matched **zero processes** for the whole
run. Nothing was ever minimized. The number that looked like "the policy holds
even in the worst case" was the number for "we did nothing."

It read as success because the watcher only logged the bad event. No windows
found, no restores, empty log, green.

What we changed: the watcher now logs what it *sees* every minute — how many
processes matched, how many windows, how many are minimized — and we re-ran the
measurement. (It passed for real: three of three, same durations.) The write-up
keeps both runs, labelled.

> An instrument that only records failures cannot tell you it was pointed at
> nothing. Make it report what it observed, not just what went wrong.

---

## 22. The model was not the one that got it wrong

We were comparing small local models on the same five tasks. One of them
"failed" five runs: the file it produced scored zero readable characters. The
obvious reading was that the small model wrote garbage.

It hadn't. The task asked for a document; the model called our writer with a
filename ending in the older Korean word-processor extension. Our writer
produces the newer zipped format regardless — and wrote those bytes under the
old name. The word processor won't open it, and our own reader, dispatching on
the extension, read nothing. Two other runs of the same set chose a third
extension and lost points the same way.

The grader recorded this as the model's failure, in a table meant to decide
which model we recommend to users on 8 GB cards.

What we changed: the writer now makes the name match the format it actually
produced and says so in its result; the format check moved into the shipped tool
rather than the grader. The model still has to pick sensibly — but a recommendation
table should not be scoring our own file naming.

> When a benchmark blames the model, check the harness on the failing path
> first. Ours had produced the file; only the name was ours to get wrong.

---

## 23. The approval nobody was in the room to see

Two failures, one shape: work that ran with no one watching it.

An outside assistant, driving our agent over MCP, asked it to write into the
user's documents folder. That escalates to a human approval, and the approval
card appears in *our* window — which nobody was looking at, because the person
was in the other app's chat. The card expired. The delegating assistant polled a
status that said "running, 0 steps" for twenty minutes, then gave up and asked
the user to go look.

The same night, a restart brought back jobs that had been running hours earlier:
on start we requeued everything marked running, without asking how old it was.
The user watched a browser open by itself at 3am and redo an abandoned research
task. In our own measurements, those resurrected jobs also queued ahead of the
new ones and their wait time landed in the new run's numbers.

What we changed: recovery is bounded — work older than a short window is closed
as stale with a reason, not resumed. The status an outside caller sees now
distinguishes queued (with queue depth), waiting-for-approval, waiting-for-a-decision,
and running (with the current step), so a client can tell the user what to do
instead of waiting on a number that will never move. And an opt-in lane lets
reversible actions through unattended — only where an undo is actually
registered; anything that sends, publishes, pays or deletes still waits for a
person.

> Unattended is a different environment. Ask what an action does when no one is
> in the room: who sees the prompt, who resumes the work, and what the caller is
> told while it waits.

---

## 24. The guard that fired before there was anything to guard

We were measuring a small local model — a 4B on an 8 GB laptop — on six coding
tasks, three runs each. Earlier the same day we had added a rule after one bad
run: the model had written a page, looked at it in a browser, and never ran a
check on it. The rule said that once the agent had been pushed back for answering
without a verification, the next turn would offer only the four tools that can
verify or fix — run, write, edit, delete. Prose telling it to verify had not
worked; taking the other tools away would.

The series scored 13 of 18. We read nothing into that number: at this size a
series moves by two or three runs on chance alone. What we can read is the
mechanism, because in three of the eighteen runs a tool call was refused, and in
two of them the model was trying to read the very file it had to fix.

The tool list in the trace gave nothing away: `read_text_file`, marked failed.
The step rows carry an error field, and there it was — `not in the active
profile`, and a duration of **0 ms**. A tool that fails in zero milliseconds did
not fail; it was never run.

The rule's condition was "no verification since the last pushback". It never
asked whether anything had been changed. A run that had written nothing and had
merely said "I will read the files first" got pushed back, lost its read tools,
and could not read the file it was supposed to fix. The rule was written for a
run that had made something and not checked it. It fired on a run that had made
nothing.

There was a second layer. The refusal told the model what it could use instead,
and built that advice from the full tool profile rather than the narrowed one:
"you can use: search, grep, read" — the tools we had just removed. In one run the
model cycled through them, each refused in turn, and ended.

Our tests had covered whether the rule narrows. None covered when it should not.

What we changed: the rule now requires a successful write or edit in the run, so
there is something to verify; the refusal's advice is built from the tools
actually on offer. Both fixes were checked by removing them and watching the new
tests fail.

> A defense needs the thing it defends in its condition. And a failure that takes
> zero milliseconds is a refusal, not an attempt — read the error field, not just
> the list of tool names.

---

## 25. The last words of a failed run

Outside assistants hand work to our agent and poll for the result. For a job that
had failed, the status they saw was `failed` and the first 500 characters of an
error code.

Across three series of 16 to 18 runs each, 15 jobs ended `failed`. Five of them
had already written files that a grader, run separately, scored as passing (three
of four in one series, one of six and one of five in the others). The caller was
told "failed" and would have started over. Handing work to a cheaper agent is only
worth it if the work survives its failures, and here it did not.

The obvious fix has a trap. On a job that failed verification, the model's final
message is usually confident — in the runs we read, some variant of "done, the
file was created". Attach that to the failure report and a verification failure
turns into a confident answer, which is the shape of note 1 and note 7 with a
status field in front of it.

What we changed: a failed or cancelled job now reports the files it left, the
pages it read, where it stopped, and whether the run had changed or verified
anything. The model's last message is kept, but under its own key,
`unverified_claim`, with a line telling the caller not to state it as fact. Files
the run created and then deleted — scripts it wrote to check its own work — are
not listed. The step store holds arguments only in memory, so the list is rebuilt
at the moment the failure is recorded.

The list is a small addition to this library: a delete effect, counted as a write
for read-only runs, and `Ledger.surviving_writes()` — what a run wrote, minus what
it later removed. It says only that the files exist. Whether anyone checked them
is a separate field.

> A failure report is evidence too. Say what the run left behind and whether
> anything checked it — and keep the run's own opinion of itself in a separate
> place from the facts.

---

## 26. The job we gave up on kept running

Our benchmark gave each task a 25-minute budget. When a job passed it, the driver
logged the job as `running`, 0 steps, and moved on to the next task. It did not
cancel it.

The backend runs one job at a time. The abandoned job — still rewriting a check
script at the 28-minute mark — kept the model, the next task waited in the queue
behind it, and that task's clock had started when it was submitted. The wait was
counted as work. Separately, the grader looked at the files of the unfinished run,
found them acceptable, and scored it a pass: a run that had neither finished nor
been counted as timed out.

The same day we re-read an earlier tally. "15 of 18" was 15 of 16: two runs had
never run. One sat at an approval card from step zero: the helper we wrote to
click approvals during the benchmark read the arguments from a field that does
not exist, so a delete inside the workspace looked like it was outside, and the
card waited. The other was denied by the same helper on purpose — it refuses
approvals outside the workspace — and a denial cancels the job.

What we changed: the driver cancels a job that passes its budget and waits for
the cancellation to land before starting the next; each result row records
`timed_out`; the grader sorts runs into ran, timed out and did not run, and prints
three numbers — files pass, job completed, and both together, which is the one we
quote. Re-scored on that ruler, the three series read 12 of 16, 11 of 18 and 13 of
18. We had been reading them as 15, 13 and 14 of 18.

> When you give up on a job, cancel it. Otherwise your next measurement is timing
> the last one.

---

## 27. The instructions that arrived late

**2026-09-23.** We took a coding session that a frontier model had stopped three
steps in, and resumed it with a local model (`qwen3.6:35b-a3b` through Ollama's
Anthropic-compatible endpoint — an unsupported configuration, which we knew).
Three small tasks, graded per task by tests.

In the environment we actually work in, none of six runs finished the remaining
tasks. Every one ended the same way: the model stopped mid-task and greeted us —
"I'm ready to help. What would you like to work on?"

Our first theory was that the harness could not carry a local model. It was wrong:
with an empty config directory the same model finished two of three, and three of
three with our instructions file or our skills added back. Turning off one thing —
the account's claude.ai connectors (`ENABLE_CLAUDEAI_MCP_SERVERS=false`) — took the
original environment from 0 of 6 to 6 of 6.

Our second theory was also wrong, and it is the reason for this note. On resume,
the transcript records a notice that the two connectors were removed. That was the
obvious suspect. It is also present, identically, in every run that succeeded. The
runs that failed have one more entry: a few tool calls into the turn, the
connectors finish connecting and their full instructions are inserted directly
after a tool result. Within three to eight entries the model greets us and ends the
turn — six of six.

A notice that appears in every run cannot explain why some of them fail. We almost
wrote the first thing we saw into the report.

What we changed: nothing in the library. We filed the timing with the harness
maintainers, and our own resume path now leaves the user's connector settings
alone rather than asking them to switch anything off.

> Before you name a cause, check that it is absent from the runs that worked.

---

## What we would tell you to check first

1. **Your denominator.** Before believing any agent metric, ask what is being
   skipped. Runs with no tool calls. Tools that are not in your table. Records
   dropped for a missing source. Runs that never ran, and jobs you stopped
   waiting for but never stopped.
2. **Both directions.** A metric that only ever fires one way has not been
   tested. Feed it a run you know is clean and a run you know is dirty.
3. **Whether a clean zero is a real zero.** `read_only_violations: 0` from a
   ledger that knows 19 of your 83 tools is not information.
4. **What your instrument saw, not only what it flagged.** A watcher that logs
   failures alone cannot tell you it was pointed at nothing.
5. **The harness, on the failing path.** Before a benchmark blames a model,
   check the part of the pipeline you own — the file it wrote, the name you gave
   it, the reader that scored it.
6. **What happens with nobody in the room.** Who sees the approval, who resumes
   the work after a restart, and what a remote caller is told while it waits.
7. **Failures that take zero milliseconds.** A step that fails in 0 ms was
   refused, not attempted. Count refusals apart from failures, and read the error
   field, not only the list of tool names. Then ask what your own guards refuse.
8. **What a failed run hands back.** The files it left, whether anything checked
   them, and — in a separate place — what the run says about itself. A status of
   `failed` alone throws away the work that survived.
