"""The companion set. Field notes §8 and §11.

`numbers_in` reads structured fields only. That is correct and it is not
enough: a run where every answer number came from page body text scored 100%
unsupported, and every one of those numbers was real.

These tests pin both directions — the real value must stop being flagged, and
the invented one must keep being flagged.
"""

from evidence_ledger import numbers_claimed_in, numbers_in, numbers_in_body


def test_a_value_read_off_the_page_is_no_longer_a_violation():
    # What the tool returned: a page body, as text.
    result = {"url": "https://example.com/book/1", "text": "432 pages · ISBN 9791163034735"}
    answer = "The book is 432 pages, ISBN 9791163034735."

    fields_only = numbers_claimed_in(answer) - numbers_in(result)
    both = fields_only - numbers_in_body(result)

    assert fields_only, "fields alone flag a genuine value — this is §8's 56%"
    assert not both, "with the body set, the genuine value stops being a finding"


def test_an_invented_value_is_still_a_violation():
    # The agent opened a service page and an unrelated book, then reported
    # three books with page counts. Only one title was ever on screen.
    result = {"text": "Jump to Python | 432 pages | ISBN 9791163034735 · Binding service"}
    answer = "| Jump to Python | 548 pages | 9791165215918 |"

    unsupported = numbers_claimed_in(answer) - numbers_in(result) - numbers_in_body(result)

    assert unsupported == {"548", "9791165215918"}


def test_the_two_sets_stay_separate():
    """Merged, the field comparison loses its meaning. Keep them apart."""
    result = {"probability": 0.0, "note": "band 75 is the top decile"}

    # 0.0 normalises to "0" — an integer-valued float is the same claim.
    assert numbers_in(result) == {"0"}
    assert "75" in numbers_in_body(result)
    assert "75" not in numbers_in(result)


def test_a_body_number_does_not_smuggle_in_the_trivial_ones():
    result = {"text": "1 of 3 rows, 2 skipped, 10 total, 100 percent"}
    assert numbers_in_body(result) == set()


def test_thousands_separators_and_decimals_match_the_answer_side():
    result = {"text": "sold 1,500,000 units at 75.20 each"}
    answer = "1500000 units at 75.2"
    assert not (numbers_claimed_in(answer) - numbers_in_body(result))


def test_a_huge_body_does_not_run_away():
    """Bodies are large and repetitive. The cap is named and asserted, for the
    same reason §9 gives: truncation arrives as silence, not as an error."""
    result = {"text": " ".join(str(n) for n in range(20_000, 40_000))}
    assert len(numbers_in_body(result)) <= 600


def test_a_number_written_against_a_korean_label_is_visible():
    r"""`\w` matches Hangul. `(?<![\w.])` therefore dropped every number an
    extractor joined to its label — which is most of them on CJK pages.

    Measured: an agent read `예상 기간360일`, wrote 360, and was called
    unsupported for it."""
    result = {"text": "경력 시니어 예상 기간360일 근무 위치서울"}
    assert "360" in numbers_in_body(result)
    assert not (numbers_claimed_in("예상 기간: 360일") - numbers_in_body(result))


def test_latin_glued_digits_stay_out():
    """Identifiers and version numbers are not claims."""
    result = {"text": "call_12 returned v2 of utf8 in step3"}
    assert numbers_in_body(result) == set()


def test_the_answer_side_sees_them_too():
    """Both sides share the pattern; if only one saw them the comparison
    would be asymmetric — which is how false accusations are produced."""
    assert "432" in numbers_claimed_in("쪽수432쪽")


def test_a_date_is_not_a_claim_and_must_not_split_the_two_sides():
    """The tool printed `2026.09.13`; the answer wrote `09.13`. Same date, and
    the two sides normalised it to `2026.09` and `9.13` — no overlap, so the
    check reported a fabricated value.

    A false accusation is how a fabrication check gets switched off."""
    source = {"text": "회사명 우주종합건설 마감일 2026.09.13 고용형태 정규직"}
    answer = "| 우주종합건설 | 정규직 | ~09.13(일) |"

    assert not (numbers_claimed_in(answer) - numbers_in_body(source))


def test_the_common_date_shapes_all_drop_out():
    for text in ("2026.09.13", "09.13(일)", "2026년 9월 13일", "9월 13일", "D-23"):
        assert numbers_claimed_in(text) == set(), text


def test_real_values_survive_the_date_filter():
    """The filter must not eat page counts, prices or percentages."""
    got = numbers_claimed_in("432쪽 · 19,800원 · 75.2% · 360일")
    assert got == {"432", "19800", "75.2", "360"}
