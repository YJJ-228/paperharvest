# PaperHarvest

An extensible terminal tool for harvesting HCI conference paper listings. It ships with adapters for ACM CHI, ACM UIST, ACM IUI and IEEE VIS, and exports title, paper link, source page, conference, year, section and authors to CSV. Run it with no arguments and you get an arrow-key menu: pick a source, pick a year, export.

## Running

Requires Python 3.10+. Dependencies are managed with [uv](https://docs.astral.sh/uv/) (there is currently one third-party library, questionary, which drives the interactive menus):

```powershell
uv sync
uv run python -m paperharvest
```

Run this from the **repository root** (the directory holding this README). Do not `cd` into the inner `paperharvest/` package directory — there is no runnable module there and you will get `No module named paperharvest`.

With no arguments you get the interactive interface:

```
  ╭──────────────────────────────────────────────╮
  │  P A P E R H A R V E S T                     │
  ╰──────────────────────────────────────────────╯
     会议论文目录采集器 · 选好来源后导出 CSV

  选择会议来源  (↑↓ 选择, Enter 确认)
   ❯ chi   ACM CHI   人机交互 · 2018–2026
     uist  ACM UIST  用户界面软件与技术 · 2018–2025
     iui   ACM IUI   智能用户界面 · 2018–2026
     vis   IEEE VIS  可视化 · 2026
```

The menu labels are Chinese; nothing written to the CSV is. Titles, authors and section names are copied from the source site verbatim.

The year menu only lists years that actually have a published programme (CHI's years come from SIGCHI's conference list; for IEEE VIS you type the year in directly).

You can skip the interaction entirely:

```powershell
uv run python -m paperharvest --conference chi --year 2026 --output chi-2026.csv
uv run python -m paperharvest --conference uist          # the source's default year
```

Installed as a command, it works from any directory:

```powershell
uv run paperharvest --conference iui --year 2026
```

It fetches the target page over the network. A changed page structure, a year that does not exist, or a network failure raises an error rather than writing a misleading empty file. Respect the target site's terms of service and rate limits; a single run requests one page (the SIGCHI sources need three queries, see below) and never scrapes concurrently.

## Prebuilt binaries

Every push to `main` builds standalone executables for Windows, Linux and macOS; see the **Actions** tab. Tagging a release (`git tag v0.1.0 && git push origin v0.1.0`) publishes them on the **Releases** page, where anyone can download one without installing Python.

Two things to know before handing a binary to someone else:

- **Windows** will likely show a SmartScreen warning ("Windows protected your PC") because the executable is unsigned. *More info → Run anyway*. Signing requires a paid code-signing certificate.
- **macOS** blocks unsigned binaries from unidentified developers. The downloader has to clear the quarantine flag once: `xattr -dr com.apple.quarantine ./paperharvest-macos-arm64`, or right-click → Open instead of double-clicking.

The binaries are built per platform and are **not** cross-compiled — a Windows `.exe` is produced on Windows, the macOS binary on macOS. Each release asset is named after its target (`paperharvest-windows-x86_64.exe`, `paperharvest-linux-x86_64`, `paperharvest-macos-arm64`), so pick the one matching your machine. See [Building a binary locally](#building-a-binary-locally) if you want to build one yourself.

## CSV fields

`title, paper_url, source_url, conference, year, section, authors`

`section` is the conference session the paper belongs to (e.g. `Driving Innovation`). `conference` is one of `ACM CHI`, `ACM UIST`, `ACM IUI`, `IEEE VIS`.

`paper_url` is **only filled in when the source provides a link**. Empty means the source offers none, not that harvesting failed:

| Source | Link availability |
| --- | --- |
| IEEE VIS 2026 | The listing page provides no per-paper links; all empty |
| ACM CHI / UIST / IUI | Programmes from around 2023 onward carry DOIs; earlier years, and years whose proceedings are not yet published (e.g. IUI 2026), are empty |

Links are never invented from a guessed DOI or a search result. Titles are kept exactly as the source has them: papers submitted to a journal track keep their `(TVCG)` and similar suffixes, and SIGCHI authors are joined as `first middle last`, matching the programme.

## How each source is fetched

**IEEE VIS** is a straightforward scrape of the paper listing page on `ieeevis.org`, parsed as HTML.

**ACM CHI / UIST / IUI** publish their programmes on `programs.sigchi.org`, an Angular application: a plain HTTP request returns an empty shell, and the paper data is rendered client-side. The prerendered version served to search engine crawlers is incomplete (in testing, CHI 2026 rendered only Monday; Tuesday through Friday were empty), and the API behind it requires credentials baked into the application. Neither route was taken.

Instead the tool reads **the same public JSON the application loads**, which is byte-for-byte what a browser receives when it visits the page — no credentials, no browser:

```
files.sigchi.org/conference/cache/program-list           ← each conference and its numeric id
files.sigchi.org/conference/cache/<id>/version-2         ← the current scheduleVersion
files.sigchi.org/conference/cache/<id>/<version>/program ← sessions / contents / people
```

One harvest makes three requests (CHI 2026's programme is about 8 MB). `source_url` records the human-readable programme page, `programs.sigchi.org/<conference>/<year>/program`.

Deciding what counts as a paper looks at both the item's own type **and** the type of the session it sits in: programmes after 2020 type every item, while older ones mostly type only the session (CHI 2018 has exactly one item carrying the `Paper` type, with another 716 identifiable only through their session). Only papers are exported — no posters, demos or workshops.

## Adding a conference source

1. Add `paperharvest/adapters/<conference>.py`.
2. Implement `parse(text: str, source_url: str, year: int) -> list[Paper]`, reusing `paperharvest.models.Paper`. An adapter is only responsible for parsing its source's HTML/API; networking, CSV writing and the TUI belong to the shared layer.
3. Register the conference ID, name, default-year URL and adapter in `paperharvest/registry.py`.
4. Add samples under `fixtures/` (create it yourself) and confirm links, sections, authors and Unicode titles are handled.

An adapter receives the **raw response body**, so JSON APIs work too (call `json.loads` inside the adapter). When you return `list[Paper]`, fill in `source_url`, `conference` and `year`. A skeleton:

```python
# paperharvest/adapters/example.py
import json
from ..models import Paper

def parse(text: str, source_url: str, year: int) -> list[Paper]:
    records = json.loads(text)
    return [
        Paper(
            title=item["title"],
            paper_url=item.get("url", ""),      # no dedicated link? leave it empty, never guess
            source_url=source_url,
            conference="ExampleConf",
            year=year,
            section=item.get("track", ""),
            authors=", ".join(item.get("authors", [])),
        )
        for item in records
    ]
```

Once registered in `registry.py`, the new value shows up in both `--conference` and the TUI menu automatically:

```python
from .adapters import example, ieeevis

SOURCES = {
    "vis": Source(
        name="IEEE VIS", description="可视化 · 2026", default_year=2026,
        url_for_year=lambda year: f"https://ieeevis.org/year/{year}/info/program/papers_list",
        parse=ieeevis.parse,
    ),
    "example": Source(
        name="ExampleConf", description="示例 · 2026", default_year=2026,
        url_for_year=lambda year: f"https://example.org/{year}/papers",
        parse=example.parse,
    ),
}
```

`Source` has two optional hooks for sources whose data is not a single page:

- `payload_for_year(year, fetch) -> (body, source page URL)`: use it when the body takes several queries to assemble; `gather()` then takes this path instead (SIGCHI uses it to resolve the conference id and version). Unset, a single page is fetched from `url_for_year`.
- `years(fetch) -> list[int]`: when the source can enumerate its years, the TUI offers a menu instead of making the user type a year blind.

While developing an adapter, save the target page to `fixtures/<name>.html` and iterate on the parsing logic offline; go online only once it works. That avoids hammering the target site:

```powershell
uv run python -c "from paperharvest.fetch import fetch_html; open('fixtures/example.html','w',encoding='utf-8').write(fetch_html('https://example.org/2026/papers'))"
```

If the target page has no dependable structure (client-rendered, lazy-loaded), look for the data it **loads publicly** (same-origin JSON, a public cache endpoint) rather than adding a browser dependency or masquerading as a search engine crawler — that is how SIGCHI was solved. If `Paper` needs a new field, update `FIELDS` in `export.py` too, or it will not be written to the CSV.

Directory layout:

```
paperharvest/
  models.py       the shared paper record
  fetch.py        single-page HTTP fetch with a timeout
  export.py       CSV writing
  registry.py     the source adapter registry
  tui.py          terminal interaction (questionary arrow-key menus)
  adapters/       per-conference/year source parsers
entry.py          entry point used by the frozen (PyInstaller) build
```

## Building a binary locally

The workflow in `.github/workflows/build.yml` is the supported path, but the same command works on your own machine:

```powershell
uv run --with pyinstaller pyinstaller --onefile --console --name paperharvest `
  --icon paperharvest\assets\icon.ico `
  --collect-all questionary --collect-all prompt_toolkit entry.py
# → dist\paperharvest.exe
```

`--console` is required: the TUI needs a real console, so a windowed build would fail immediately. `entry.py` exists rather than `paperharvest/__main__.py` because PyInstaller runs its entry script as a top-level `__main__` with no package context, which breaks `__main__.py`'s relative imports. `--collect-all` guards the platform-specific backends prompt_toolkit selects at runtime.

`--icon` is Windows-only. PyInstaller writes the icon into the executable's PE resource there, but a Linux ELF has nowhere to put one, and this build produces a bare Mach-O on macOS rather than an `.app` bundle — a bundle needs `--windowed`, which would detach the console the TUI needs. The workflow passes the flag on Windows alone, and only when `paperharvest/assets/icon.ico` exists, so a checkout without the artwork still builds.

Downloading full texts is deliberately not implemented: licensing, authentication and open-access rules differ too much between publishers. It should arrive as a separate, explicitly opt-in OA downloader that records licence and provenance and enforces rate limits.
