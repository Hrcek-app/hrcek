"""Shared structural parsing for the entry templates' tests."""

from html.parser import HTMLParser


class _Structure(HTMLParser):
    """Record the open-element stack at each element of interest.

    Structural assertions rather than string matching: a list is a list
    because of where the elements sit, not because the source happens to
    contain "<li>".
    """

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.anchors: list[tuple[str, list[str]]] = []
        self.articles: list[list[str]] = []
        self.images: list[tuple[dict[str, str], list[str]]] = []
        self.buttons: list[dict[str, str | None]] = []

    def handle_starttag(self, tag, attrs):
        void = {"br", "img", "meta", "input", "link", "hr"}
        if tag not in void:
            self.stack.append(tag)
        if tag == "a":
            self.anchors.append((dict(attrs).get("href", ""), list(self.stack)))
        if tag == "button":
            self.buttons.append(dict(attrs))
        if tag == "img":
            self.images.append((dict(attrs), list(self.stack)))
        if tag == "article":
            self.articles.append(list(self.stack))

    def handle_endtag(self, tag):
        if tag in self.stack:
            while self.stack and self.stack.pop() != tag:
                pass


def _structure(response) -> _Structure:
    parser = _Structure()
    parser.feed(response.content.decode())
    return parser
