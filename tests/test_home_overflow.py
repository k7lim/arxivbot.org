"""The home page example URLs must fit a phone-width screen (a2i)."""

import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text()


def _narrow_block() -> str:
    start = CSS.index("@media (max-width: 600px)")
    following = CSS.find("@media", start + 1)
    return CSS[start : following if following != -1 else len(CSS)]


def _rule(block: str, selector: str) -> str:
    match = re.search(r"^\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", block, re.M)
    assert match, f"{selector} rule missing from the 600px media query"
    return match.group(1)


def test_example_urls_wrap_on_narrow_screens():
    url = _rule(_narrow_block(), ".url")
    assert "overflow-wrap: anywhere" in url
    assert "max-width: 100%" in url


def test_url_transform_stacks_on_narrow_screens():
    assert "flex-direction: column" in _rule(_narrow_block(), ".url-transform")


def test_wide_screen_url_rule_is_unchanged():
    base = _rule(CSS[: CSS.index("@media")], ".url")
    assert "font-size: 0.9rem" in base
    assert "overflow-wrap" not in base
