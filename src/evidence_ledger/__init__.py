"""evidence-ledger — tell what an agent *read* from what it merely *opened*.

    from evidence_ledger import Ledger
    from evidence_ledger.presets import CLAUDE_CODE

    ledger = Ledger(CLAUDE_CODE, run_id=job_id)

    # wherever every tool result passes through:
    ledger.record(tool_name, result, ok=ok, step=n, arguments=args)

    # when the answer is ready:
    report = ledger.summarize(read_only=True)
    if report["answered_from_listing_only"]:
        ...  # it saw a list of names and answered as if it had read them
"""

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
    WRITE_EFFECTS,
    EvidenceRecord,
    Ledger,
    Spec,
    canonical_source,
    numbers_claimed_in,
    numbers_in,
)

__version__ = "0.1.0"

__all__ = [
    "Ledger",
    "Spec",
    "EvidenceRecord",
    "canonical_source",
    "numbers_in",
    "numbers_claimed_in",
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
    "__version__",
]
