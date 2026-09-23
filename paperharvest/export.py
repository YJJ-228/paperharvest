import csv
from pathlib import Path
from collections.abc import Iterable

from .models import Paper

FIELDS = ["title", "paper_url", "source_url", "conference", "year", "section", "authors"]


def write_csv(papers: Iterable[Paper], path: str | Path) -> int:
    rows = list(papers)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig makes the CSV open cleanly in desktop Excel on Windows.
    with destination.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows({field: getattr(paper, field) for field in FIELDS} for paper in rows)
    return len(rows)
