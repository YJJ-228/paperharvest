from dataclasses import dataclass


class UnknownYear(LookupError):
    """The source publishes nothing for the requested year.

    Raised by the adapters that resolve a year through a lookup (SIGCHI's
    conference list, IEEE VIS's probed pages) rather than by fetching one URL
    and failing. It carries the years that *are* available, because the list
    is often the only thing the user needs to pick a workable one.
    """


@dataclass
class Paper:
    title: str
    paper_url: str = ""
    source_url: str = ""
    conference: str = ""
    year: int = 0
    section: str = ""
    authors: str = ""
