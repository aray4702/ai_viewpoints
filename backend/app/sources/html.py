from html import unescape
from html.parser import HTMLParser

_BLOCK = {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "tr", "pre"}
_SKIP = {"script", "style", "noscript"}


class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self._skip += 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str | None) -> str:
    if not html:
        return ""
    p = _Extractor()
    p.feed(html)
    lines = (" ".join(line.split()) for line in unescape("".join(p.parts)).splitlines())
    return "\n".join(line for line in lines if line)
