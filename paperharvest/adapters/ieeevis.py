import re
from collections.abc import Callable
from datetime import date
from html.parser import HTMLParser
from urllib.error import HTTPError
from urllib.parse import urljoin

from ..models import Paper

Fetcher = Callable[[str], str]

PAPERS_PAGE = "https://ieeevis.org/year/{year}/info/program/papers_list"

# The listing marks each paper's place with a trailing "· City"; it is not an author.
LOCATION = re.compile(r"\s*·\s*\S+\s*$")


def page_url(year: int) -> str:
    """The page a human would open to read this listing.

    The site's scheme is not stable across years. Up to 2024 the papers lived
    under ``/info/papers-sessions``, served as an Angular app whose paper data
    never reaches the HTML a plain client receives; from 2025 on they are
    static and addressable here. Only the static scheme is used, which is why
    older years are not offered at all (see :func:`year_lister`).
    """
    return PAPERS_PAGE.format(year=year)


def year_lister(fetch: Fetcher, today: date | None = None, lookback: int = 4) -> list[int]:
    """Years with a published listing, newest first.

    IEEE VIS publishes no index of its own years, so this probes the pages
    one at a time rather than reading a list. Probing the static scheme alone
    is what keeps 2018–2024 out: those pages answer 200 with a shell the
    parser cannot read, so an HTTP status on its own would advertise years
    that harvest to nothing.

    A miss at the top is skipped rather than treated as the end — next year's
    page appears before the calendar turns, so an unbroken run has to start
    below it — while a gap *after* the newest hit ends the walk. Either way
    ``lookback`` bounds the requests spent.
    """
    current = (today or date.today()).year
    years: list[int] = []
    for year in range(current, current - lookback, -1):
        try:
            fetch(page_url(year))
        except HTTPError as exc:
            if exc.code != 404:
                raise
            if years:
                break
            continue
        years.append(year)
    return years


class _VisParser(HTMLParser):
    """Read section headings and per-paper blocks without assuming CSS classes.

    Headings give the section; a paper entry is a block carrying a title as an
    <h3>, a <strong>/<b>, or a link label, with the authors as the remaining text.
    """

    def __init__(self, source_url: str, year: int):
        super().__init__(convert_charrefs=True)
        self.source_url = source_url
        self.year = year
        self.section = ""
        self.mode = ""
        self.heading_tag = ""
        self.heading: list[str] = []
        self.heading_links: list[tuple[str, str]] = []
        self.pending_title = ""
        self.pending_url = ""
        self.link: list[str] = []
        self.link_href = ""
        self.link_depth = 0
        # in_block tracks "inside a <p>/<li>" explicitly: block is empty until
        # handle_data fills it, so it cannot double as the flag.
        self.in_block = False
        self.block: list[str] = []
        self.block_links: list[tuple[str, str]] = []
        self.bold: list[str] = []
        self.bold_depth = 0
        # Menu and footer links live in <li> blocks too; skip those containers.
        self.skip_depth = 0
        self.papers: list[Paper] = []

    @staticmethod
    def clean(parts: list[str]) -> str:
        return " ".join(" ".join(parts).split())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("nav", "header", "footer"):
            self.skip_depth += 1
        if tag in ("h1", "h2", "h3", "h4"):
            self.mode = "heading"
            self.heading_tag = tag
            self.heading = []
            self.heading_links = []
        if tag == "a":
            if self.link_depth == 0:
                self.link = []
                self.link_href = attrs.get("href", "")
            self.link_depth += 1
        if tag in ("strong", "b"):
            if self.bold_depth == 0:
                self.bold = []
            self.bold_depth += 1
        if tag in ("p", "li") and not self.in_block and not self.skip_depth:
            self.in_block = True
            self.block = []
            self.block_links = []
            self.bold = []
            self.bold_depth = 0

    def handle_data(self, data):
        if self.mode == "heading":
            self.heading.append(data)
        if self.link_depth:
            self.link.append(data)
        if self.in_block:
            self.block.append(data)
            if self.bold_depth:
                self.bold.append(data)

    def handle_endtag(self, tag):
        if tag in ("nav", "header", "footer"):
            self.skip_depth = max(0, self.skip_depth - 1)
        if tag in ("h1", "h2", "h3", "h4") and self.mode == "heading":
            if not self.skip_depth:
                heading = self.clean(self.heading)
                if self.heading_tag in ("h3", "h4") and heading and not heading.lower().startswith("accepted "):
                    self.pending_title = heading
                    self.pending_url = next((url for label, url in self.heading_links if label == heading), "")
                elif heading.lower().startswith("accepted "):
                    self.section = heading
                elif heading and heading.lower() not in ("accepted papers",):
                    self.section = heading
            self.mode = ""
        if tag in ("strong", "b") and self.bold_depth:
            self.bold_depth -= 1
        if tag == "a" and self.link_depth:
            self.link_depth -= 1
            if self.link_depth == 0 and (self.in_block or self.mode == "heading"):
                label = self.clean(self.link)
                if label:
                    target = self.block_links if self.in_block else self.heading_links
                    target.append((label, urljoin(self.source_url, self.link_href)))
        if tag in ("p", "li") and self.in_block:
            self.in_block = False
            text = self.clean(self.block)
            # Typical entry: an <h3> title followed by an author paragraph, or a
            # single paragraph holding a bold title, a <br>, then the authors.
            bold = self.clean(self.bold)
            linked = self.block_links[0][0] if self.block_links else ""
            # A paper entry carries an <h3>, a bold or a linked title. A plain
            # paragraph is prose (intro or section note), not a paper.
            if text and len(text) > 12 and (self.pending_title or bold or linked):
                title = self.pending_title or bold or linked
                href = self.pending_url or (self.block_links[0][1] if self.block_links else "")
                if self.pending_title:
                    # Paragraph following an h3 title holds only the authors.
                    authors = LOCATION.sub("", text).strip()
                elif text.startswith(title):
                    # Bold title, then the author text, in one paragraph.
                    authors = LOCATION.sub("", text[len(title):]).strip()
                else:
                    authors = ""
                # Navigation and section links are not papers.
                if not title.lower().startswith(("accepted ", "home", "program")):
                    self.papers.append(Paper(title=title, paper_url=href,
                        source_url=self.source_url, conference="IEEE VIS", year=self.year,
                        section=self.section, authors=authors))
            # Consumed or not, an h3 title only ever applies to the next block.
            self.pending_title = ""
            self.pending_url = ""
            self.block = []
            self.block_links = []
            self.bold = []


def parse(html: str, source_url: str, year: int) -> list[Paper]:
    parser = _VisParser(source_url, year)
    parser.feed(html)
    # Deduplicate repeated mobile/desktop or nested markup while preserving order.
    seen: set[tuple[str, str]] = set()
    output = []
    for paper in parser.papers:
        key = (paper.title.casefold(), paper.paper_url)
        if key not in seen:
            seen.add(key)
            output.append(paper)
    return output
