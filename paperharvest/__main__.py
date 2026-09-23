import argparse
import sys

from .export import write_csv
from .fetch import fetch_html
from .registry import SOURCES


def _use_utf8_output():
    """Keep the Chinese output alive on a non-UTF-8 stdout.

    Redirecting or piping on Windows hands the program the ANSI code page
    instead of the console's: cp936 on a Chinese desktop, but cp1252 on a
    Western one, and the whole help text, the export summary and the failure
    messages are Chinese. Writing them there raises UnicodeEncodeError rather
    than printing. A real Windows console is already UTF-8 (PEP 528), so this
    only changes the redirected case; other platforms are unaffected.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            # None under a windowed build, or not a TextIOWrapper at all.
            pass


def main():
    _use_utf8_output()
    parser = argparse.ArgumentParser(description="Collect conference paper listings into CSV")
    parser.add_argument("--conference", choices=SOURCES, help="来源 ID；省略则进入交互界面")
    parser.add_argument("--year", type=int, default=None, help="年份；省略则用该来源的默认年份")
    parser.add_argument("--output", default="", help="CSV 路径；省略则用 <来源>-<年份>.csv")
    args = parser.parse_args()

    if not args.conference:
        from .tui import run_tui

        raise SystemExit(run_tui())

    source = SOURCES[args.conference]
    year = args.year or source.default_year
    try:
        payload, source_url = source.gather(year, fetch_html)
        papers = source.parse(payload, source_url, year)
        if not papers:
            raise RuntimeError("没有解析到论文条目；网站结构可能已变更")
        path = args.output or f"{args.conference}-{year}.csv"
        count = write_csv(papers, path)
        print(f"导出 {count} 条至 {path}（含链接 {sum(bool(p.paper_url) for p in papers)} 条）")
    except Exception as exc:
        raise SystemExit(f"采集失败：{exc}")


if __name__ == "__main__":
    main()
