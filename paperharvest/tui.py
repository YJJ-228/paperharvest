"""Interactive terminal front-end.

Uses questionary (prompt_toolkit) for the arrow-key menus, the way
create-vue / create-react-app ask which preset you want.
"""

from collections.abc import Callable

from .export import write_csv
from .fetch import fetch_html
from .registry import SOURCES

ACCENT = "#5fafff"
MUTED = "#808080"

_WIDTH = 46
_TITLE = "P A P E R H A R V E S T"


def _style():
    from questionary import Style

    return Style([
        ("qmark", f"fg:{ACCENT} bold"),
        ("question", "bold"),
        ("answer", f"fg:{ACCENT} bold"),
        ("pointer", f"fg:{ACCENT} bold"),
        ("highlighted", f"fg:{ACCENT} bold"),
        ("selected", "fg:#87d787"),
        ("instruction", f"fg:{MUTED}"),
    ])


def _render(parts) -> None:
    """Write styled text through prompt_toolkit so the colours survive on
    Windows consoles, falling back to plain output when there is no console
    to style (piped stdout, captured output)."""
    try:
        from prompt_toolkit import print_formatted_text
        from prompt_toolkit.formatted_text import FormattedText

        print_formatted_text(FormattedText(parts))
    except Exception:
        print("".join(text for _, text in parts), end="")


def _emit(text: str = "", color: str = "") -> None:
    _render([(f"fg:{color}" if color else "", text)])


def _banner() -> None:
    rule = "─" * _WIDTH
    _render([
        ("", "\n"),
        (f"fg:{ACCENT} bold", f"  ╭{rule}╮\n"),
        (f"fg:{ACCENT} bold", f"  │  {_TITLE.ljust(_WIDTH - 2)}│\n"),
        (f"fg:{ACCENT} bold", f"  ╰{rule}╯\n"),
        (f"fg:{MUTED}", "     会议论文目录采集器 · 选好来源后导出 CSV\n\n"),
    ])


def _abort() -> int:
    _emit("\n已取消。")
    return 130


def _memoize(fetch: Callable[[str], str]) -> Callable[[str], str]:
    """Reuse identical URLs within one run (the SIGCHI listing is fetched
    once for the year menu and again to resolve the programme)."""
    cache: dict[str, str] = {}

    def wrapped(url: str) -> str:
        if url not in cache:
            cache[url] = fetch(url)
        return cache[url]

    return wrapped


def _ask_source():
    import questionary

    choices = [
        questionary.Choice(
            title=f"{key:<6}{source.name:<10}{source.description}",
            value=key,
        )
        for key, source in SOURCES.items()
    ]
    answer = questionary.select(
        "选择会议来源", choices=choices, style=_style(), instruction="(↑↓ 选择, Enter 确认)"
    ).ask()
    return SOURCES[answer] if answer else None


def _ask_year(source, fetch):
    import questionary

    if source.years is not None:
        _emit(f"  正在获取 {source.name} 的可选年份…\n", color=MUTED)
        try:
            years = source.years(fetch)
        except Exception as exc:
            _emit(f"  取不到年份列表（{exc}），请手动输入。\n")
            years = []
        if years:
            answer = questionary.select(
                "选择年份",
                choices=[str(year) for year in years],
                style=_style(),
                instruction="(↑↓ 选择, Enter 确认)",
            ).ask()
            return int(answer) if answer else None

    answer = questionary.text(
        "年份",
        default=str(source.default_year),
        style=_style(),
        validate=lambda value: value.strip().isdigit() or "请输入数字年份",
    ).ask()
    return int(answer) if answer else None


def run_tui() -> int:
    try:
        import questionary
    except ImportError:
        print("缺少 questionary，无法启动交互界面。请运行：uv sync")
        return 2

    fetch = _memoize(fetch_html)
    _banner()

    source = _ask_source()
    if source is None:
        return _abort()

    year = _ask_year(source, fetch)
    if year is None:
        return _abort()

    output = questionary.text(
        "CSV 输出路径",
        default=f"{source.name.split()[-1].lower()}-{year}.csv",
        style=_style(),
    ).ask()
    if output is None:
        return _abort()

    _emit(f"\n  正在读取 {source.name} {year} 的节目单…\n", color=MUTED)
    try:
        payload, source_url = source.gather(year, fetch)
        papers = source.parse(payload, source_url, year)
    except Exception as exc:
        _emit(f"\n  采集失败：{exc}")
        return 1
    if not papers:
        _emit("\n  没有解析到论文条目；网站结构可能已变更，未写入 CSV。")
        return 1

    count = write_csv(papers, output)
    linked = sum(bool(paper.paper_url) for paper in papers)
    _emit(f"\n  已导出 {count} 条到 {output}")
    _emit(f"  有独立链接：{linked} · 无链接：{count - linked}")
    return 0
