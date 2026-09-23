from dataclasses import dataclass
from functools import partial
from collections.abc import Callable

from .adapters import ieeevis, sigchi
from .models import Paper

Fetcher = Callable[[str], str]


@dataclass(frozen=True)
class Source:
    """One conference the tool can harvest.

    ``parse`` is the whole contract for an adapter: turn a fetched body into
    papers. ``url_for_year`` names the page the listing lives on, which is
    what gets fetched — unless the source sets ``payload_for_year``, for data
    that is not a single page (an API reached through a lookup). ``years``
    lets the TUI offer a menu instead of asking for a year blind.
    """

    name: str
    description: str
    default_year: int
    url_for_year: Callable[[int], str]
    parse: Callable[[str, str, int], list[Paper]]
    payload_for_year: Callable[[int, Fetcher], tuple[str, str]] | None = None
    years: Callable[[Fetcher], list[int]] | None = None

    def gather(self, year: int, fetch: Fetcher) -> tuple[str, str]:
        """Return the body to parse and the page it came from."""
        if self.payload_for_year is not None:
            return self.payload_for_year(year, fetch)
        url = self.url_for_year(year)
        return fetch(url), url


SOURCES = {
    "chi": Source(
        name="ACM CHI",
        description="人机交互 · 2018–2026",
        default_year=2026,
        url_for_year=partial(sigchi.page_url, "CHI"),
        parse=sigchi.parse,
        payload_for_year=partial(sigchi.loader, "CHI"),
        years=partial(sigchi.year_lister, "CHI"),
    ),
    "uist": Source(
        name="ACM UIST",
        description="用户界面软件与技术 · 2018–2025",
        default_year=2025,
        url_for_year=partial(sigchi.page_url, "UIST"),
        parse=sigchi.parse,
        payload_for_year=partial(sigchi.loader, "UIST"),
        years=partial(sigchi.year_lister, "UIST"),
    ),
    "iui": Source(
        name="ACM IUI",
        description="智能用户界面 · 2018–2026",
        default_year=2026,
        url_for_year=partial(sigchi.page_url, "IUI"),
        parse=sigchi.parse,
        payload_for_year=partial(sigchi.loader, "IUI"),
        years=partial(sigchi.year_lister, "IUI"),
    ),
    "vis": Source(
        name="IEEE VIS",
        description="可视化 · 2026",
        default_year=2026,
        url_for_year=lambda year: f"https://ieeevis.org/year/{year}/info/program/papers_list",
        parse=ieeevis.parse,
    ),
}
