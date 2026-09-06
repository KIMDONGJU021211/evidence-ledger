# Contributing

This is a small library with two people behind it, neither of whom does this
full time. Issues and pull requests are welcome; replies may be slow. Saying so
up front seems better than implying otherwise.

## The most useful thing you can send

**A manifest for a stack that has none.** The presets cover three. If you wire
this into a fourth and it works, that mapping is worth more than any feature —
it is the part that cannot be guessed from outside.

Second most useful: **a case where the ledger was wrong.** Not where your agent
was wrong — where the *instrument* was. Half of `docs/FIELD-NOTES.md` is that,
and every one of those was found by looking at a number that seemed fine.

## Ground rules

- **No dependencies.** Standard library only. This has to drop into a loop that
  already has opinions about everything else.
- **A test is named after what broke.** Not `test_record_returns_none` but
  `test_a_read_with_no_path_is_not_a_read`. Read the existing names; they are
  the argument for this rule.
- **A claim in a docstring is a claim.** If a comment says a measurement was
  56%, someone will quote it. Do not write one you have not run.
- Python 3.9 through 3.13. CI runs all three ends.

```bash
pip install -e ".[dev]"
pytest -q
```
