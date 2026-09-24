from dataclasses import dataclass
from datetime import date
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
    lets the TUI offer a menu instead of asking for a year blind, and is also
    what the default year is resolved from, so a source that cannot enumerate
    its own years is left to fall back on the current one.
    """

    name: str
    description: str
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


def newest_year(years: list[int], current: int | None = None) -> int:
    """The newest year that is not in the future.

    The source's own list is authoritative and may have gaps — IUI publishes
    no 2020 and no 2023 programme — so the current year counts only when it
    is really in the list, and otherwise the newest *earlier* year is taken
    rather than simply stepping back one. An empty list, or one entirely in
    the future (next year's programme can appear before the calendar turns),
    still has to name something, so it falls back to the newest entry and
    then to the current year.
    """
    if current is None:
        current = date.today().year
    ordered = sorted(years, reverse=True)
    if not ordered:
        return current
    return next((year for year in ordered if year <= current), ordered[0])


def resolve_year(source: Source, fetch: Fetcher, today: date | None = None) -> int:
    """The year to harvest from ``source`` when the caller named none.

    A source that cannot list its years, or whose listing cannot be reached,
    yields the current year: the failure then surfaces where the harvest
    reports it, instead of being hidden behind a wrong guess that looks like
    a normal result.
    """
    if source.years is not None:
        try:
            years = source.years(fetch)
        except Exception:
            years = []
        if years:
            return newest_year(years, (today or date.today()).year)
    return (today or date.today()).year


SOURCES = {
    "chi": Source(
        name="ACM CHI",
        description="人机交互",
        url_for_year=partial(sigchi.page_url, "CHI"),
        parse=sigchi.parse,
        payload_for_year=partial(sigchi.loader, "CHI"),
        years=partial(sigchi.year_lister, "CHI"),
    ),
    "uist": Source(
        name="ACM UIST",
        description="用户界面软件与技术",
        url_for_year=partial(sigchi.page_url, "UIST"),
        parse=sigchi.parse,
        payload_for_year=partial(sigchi.loader, "UIST"),
        years=partial(sigchi.year_lister, "UIST"),
    ),
    "iui": Source(
        name="ACM IUI",
        description="智能用户界面",
        url_for_year=partial(sigchi.page_url, "IUI"),
        parse=sigchi.parse,
        payload_for_year=partial(sigchi.loader, "IUI"),
        years=partial(sigchi.year_lister, "IUI"),
    ),
    "vis": Source(
        name="IEEE VIS",
        description="可视化",
        url_for_year=ieeevis.page_url,
        parse=ieeevis.parse,
        years=ieeevis.year_lister,
    ),
}
