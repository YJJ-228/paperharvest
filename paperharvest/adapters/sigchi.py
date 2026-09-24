"""Reader for the public SIGCHI conference programme.

CHI, UIST, IUI and the other SIGCHI-sponsored conferences publish their
programmes on programs.sigchi.org. That site is an Angular app: the HTML a
plain HTTP client gets back is an empty shell, so fetching the page is not an
option. The JSON the app renders from is served openly, though:

    files.sigchi.org/conference/cache/program-list
        every conference with its numeric id
    files.sigchi.org/conference/cache/<id>/version-2
        the current scheduleVersion for that conference
    files.sigchi.org/conference/cache/<id>/<version>/program
        sessions, contents, people and content types

Those are public reads of public conference data: no credentials, no browser,
the same bytes a visitor's browser receives. Reading the page instead would
mean either executing JavaScript or claiming to be a search engine crawler;
neither belongs in a metadata harvester.
"""

import json
from collections.abc import Callable
from urllib.parse import urlparse

from ..models import Paper, UnknownYear

CACHE = "https://files.sigchi.org/conference/cache"
PROGRAM_PAGE = "https://programs.sigchi.org/{short}/{year}/program"

Fetcher = Callable[[str], str]


def page_url(short_name: str, year: int) -> str:
    """The page a human would open to read this programme."""
    return PROGRAM_PAGE.format(short=short_name.lower(), year=year)


def _key(entry: dict) -> tuple[str, int]:
    conference = entry.get("conference") or {}
    return (conference.get("shortName") or "").strip().upper(), conference.get("year")  # type: ignore


def _listing(fetch: Fetcher) -> list[dict]:
    return json.loads(fetch(f"{CACHE}/program-list"))


def year_lister(short_name: str, fetch: Fetcher) -> list[int]:
    """Years this conference publishes a programme for, newest first."""
    wanted = short_name.strip().upper()
    years = {
        year for short, year in (_key(e) for e in _listing(fetch)) if short == wanted
    }
    return sorted(years, reverse=True)


def loader(short_name: str, year: int, fetch: Fetcher) -> tuple[str, str]:
    """Fetch one programme, resolving the conference id and version first.

    Returns the raw programme JSON and the page it describes, so the caller
    can hand both straight to :func:`parse`.
    """
    wanted = short_name.strip().upper()
    entries = _listing(fetch)
    years = sorted({y for s, y in (_key(e) for e in entries) if s == wanted})
    conference_id = next(
        (e["conference"]["id"] for e in entries if _key(e) == (wanted, year)), None
    )
    if conference_id is None:
        available = f"{min(years)}–{max(years)}" if years else "无"
        raise UnknownYear(
            f"{short_name} 没有 {year} 年的节目单（可选年份：{available}）"
        )
    version = json.loads(fetch(f"{CACHE}/{conference_id}/version-2"))["scheduleVersion"]
    return fetch(f"{CACHE}/{conference_id}/{version}/program"), page_url(
        short_name, year
    )


def _is_paper(type_name: str | None) -> bool:
    return "paper" in (type_name or "").lower()


def _text(value) -> str:
    return " ".join(str(value or "").split())


def _doi(content: dict) -> str:
    """The DOI the programme links to, if it carries one.

    Programmes roughly from 2023 on include it; earlier ones and not-yet-
    published proceedings do not, and a missing link is left empty rather
    than guessed. Some years store it without a scheme.
    """
    url = ((content.get("addons") or {}).get("doi") or {}).get("url") or ""
    url = url.strip()
    if url and not urlparse(url).scheme:
        url = f"https://{url.lstrip('/')}"
    return url


def _section(session_ids: list, sessions: dict) -> str:
    names: list[str] = []
    for session_id in session_ids:
        name = _text((sessions.get(session_id) or {}).get("name"))
        if name and name not in names:
            names.append(name)
    return "; ".join(names)


def _authors(authors: list, people: dict) -> str:
    names = []
    for author in authors or []:
        person = people.get(author.get("personId")) or {}
        name = " ".join(
            part
            for part in (
                _text(person.get("firstName")),
                _text(person.get("middleInitial")),
                _text(person.get("lastName")),
            )
            if part
        )
        if name:
            names.append(name)
    return ", ".join(names)


def _conference_label(conference: dict) -> str:
    short = _text(conference.get("shortName"))
    return f"ACM {short}" if short else _text(conference.get("fullName"))


def parse(text: str, source_url: str, year: int) -> list[Paper]:
    """Turn one programme payload into papers.

    An entry counts as a paper when its own content type says so, or when the
    session it sits in does. Both halves are needed: programmes from 2020 on
    type every entry, while older ones leave most contents untyped and only
    classify the session (CHI 2018 marks 1 content as a paper and 716 more
    only through their session).
    """
    program = json.loads(text)
    type_names = {
        t["id"]: _text(t.get("name")) for t in program.get("contentTypes") or []
    }
    sessions = {s["id"]: s for s in program.get("sessions") or []}
    people = {p["id"]: p for p in program.get("people") or []}
    label = _conference_label(program.get("conference") or {})

    papers: list[Paper] = []
    seen: set[tuple[str, str]] = set()
    for content in program.get("contents") or []:
        if content.get("isBreak"):
            continue
        session_ids = content.get("sessionIds") or []
        typed_by_session = any(
            _is_paper(type_names.get(sessions[sid].get("typeId")))
            for sid in session_ids
            if sid in sessions
        )
        if not (_is_paper(type_names.get(content.get("typeId"))) or typed_by_session):
            continue
        paper = Paper(
            title=_text(content.get("title")),
            paper_url=_doi(content),
            source_url=source_url,
            conference=label,
            year=year,
            section=_section(session_ids, sessions),
            authors=_authors(content.get("authors"), people),
        )
        key = (paper.title.casefold(), paper.paper_url)
        if paper.title and key not in seen:
            seen.add(key)
            papers.append(paper)
    return papers
