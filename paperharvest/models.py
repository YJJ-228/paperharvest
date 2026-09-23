from dataclasses import dataclass


@dataclass
class Paper:
    title: str
    paper_url: str = ""
    source_url: str = ""
    conference: str = ""
    year: int = 0
    section: str = ""
    authors: str = ""
