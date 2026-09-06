"""Normalising sources.

Without it you read one place twice and report "2 sources read" — which is how
a count check passes over an answer that only ever saw one page.
"""

from __future__ import annotations

import os

import pytest

from evidence_ledger import canonical_source


@pytest.mark.parametrize(
    "a, b",
    [
        ("https://a.example/p/1", "https://a.example/p/1/"),
        ("https://a.example/p/1", "https://a.example/p/1#reviews"),
        ("https://A.Example/p/1", "https://a.example/p/1"),
        ("HTTPS://a.example/p/1", "https://a.example/p/1"),
    ],
)
def test_urls_that_are_the_same_place(a, b):
    assert canonical_source(a, kind="url") == canonical_source(b, kind="url")


def test_the_query_is_kept():
    """For a search results URL the query *is* the identity — dropping it
    merges every search on a site into one source.
    """
    one = canonical_source("https://a.example/s?q=cat", kind="url")
    two = canonical_source("https://a.example/s?q=dog", kind="url")
    assert one != two


def test_a_search_is_identified_by_what_was_asked():
    """A search has no address."""
    assert canonical_source("  Blue   Shoes ", kind="query") == "q:blue shoes"
    assert canonical_source("blue shoes", kind="query") == canonical_source(
        "BLUE  SHOES", kind="query"
    )


def test_relative_and_absolute_paths_meet():
    here = canonical_source("./setup.py", kind="path")
    there = canonical_source(os.path.abspath("setup.py"), kind="path")
    assert here == there


def test_a_non_url_string_survives_untouched():
    """Not everything with a scheme-less shape is broken input."""
    assert canonical_source("just-a-name", kind="url") == "just-a-name"


def test_empty_is_empty():
    assert canonical_source("", kind="url") == ""
    assert canonical_source(None, kind="path") == ""
