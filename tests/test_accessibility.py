"""Source-level coverage for accessible names, including hidden form panels."""
from html.parser import HTMLParser
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "static"


class Controls(HTMLParser):
    def __init__(self):
        super().__init__()
        self.labels = set()
        self.controls = []
        self.label_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "label":
            self.label_depth += 1
            self.labels.add(attrs.get("for"))
        if tag in {"input", "select", "textarea"} and attrs.get("type") != "hidden":
            self.controls.append((attrs, self.label_depth > 0))

    def handle_endtag(self, tag):
        if tag == "label":
            self.label_depth -= 1


@pytest.mark.parametrize("path", sorted(STATIC.glob("*.html")), ids=lambda path: path.name)
def test_all_static_form_controls_have_names(path):
    parser = Controls()
    parser.feed(path.read_text(encoding="utf-8"))
    for attrs, wrapped in parser.controls:
        assert wrapped or attrs.get("id") in parser.labels or attrs.get("aria-label") or attrs.get("aria-labelledby"), attrs
