# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```powershell
uv sync                                              # install deps
uv run python -m paperharvest                        # interactive TUI
uv run python -m paperharvest --conference chi --year 2026 --output chi-2026.csv
uv run python -m paperharvest --conference uist      # source's default year
uv run paperharvest --conference iui --year 2026     # installed console script
```

Run from the **repository root**. The inner `paperharvest/` directory is a package, not a runnable root — `cd`-ing into it yields `No module named paperharvest`.

There is no test suite, no linter config and no CI beyond the build workflow. Verification is manual: run the tool against a live source, or save a page to `fixtures/<name>.html` and iterate on the parser offline (see Adapter development below).

Build a binary locally (the same command CI runs — see `.github/workflows/build.yml`):

```powershell
uv run --with pyinstaller pyinstaller --onefile --console --name paperharvest `
  --icon paperharvest\assets\icon.ico `
  --collect-all questionary --collect-all prompt_toolkit entry.py
```

## Architecture

Three layers, and the boundary between them is strict.

**Adapters** (`paperharvest/adapters/<conf>.py`) parse a raw response body and know nothing about networking, CSV or the UI. The whole contract is:

```python
def parse(text: str, source_url: str, year: int) -> list[Paper]
```

`text` is the **raw response body**, so an adapter may call `json.loads` itself. Adapters fill in `source_url`, `conference` and `year` on every `Paper` they return.

**Registry** (`registry.py`) binds an adapter to a conference via the frozen `Source` dataclass in `SOURCES`. Adding a key there makes it appear in both `--conference` and the TUI menu automatically. Two optional hooks cover sources that are not a single page:

- `payload_for_year(year, fetch) -> (body, source page URL)` — overrides the single-URL path in `Source.gather`. SIGCHI uses it to resolve conference id and version before the real request. When set, `url_for_year` is still used to name the human-readable page.
- `years(fetch) -> list[int]` — lets the TUI offer a year menu instead of a free-text prompt.

**Shared layer** — `fetch.py` (one HTTP GET, 60 s timeout), `export.py` (CSV), `tui.py` (questionary menus), `__main__.py` (argparse CLI). `__main__.py` and `tui.py` follow the same sequence: `source.gather(year, fetch)` → `source.parse(payload, source_url, year)` → `write_csv(...)`.

Consequences worth remembering:

- A new field on `Paper` (`models.py`) must also be added to `FIELDS` in `export.py`, or it silently never reaches the CSV.
- `tui.py` memoizes the fetcher (`_memoize`) so SIGCHI's listing is fetched once per run rather than once for the year menu and again for the programme.
- Both front-ends treat an empty parse result as an error and write no file, rather than emitting an empty CSV.
- `entry.py` exists only for PyInstaller: it imports the package properly first because PyInstaller runs its entry script as a top-level `__main__` with no package context, which breaks the relative imports in `__main__.py`.

## Source-fetching constraints

`README.md` documents the data sources in depth; the rules that constrain implementation choices:

- **Never invent a `paper_url`.** Empty means the source offers no link (IEEE VIS provides none; SIGCHI years before ~2023 and unpublished proceedings carry no DOI). Do not construct a URL from a guessed DOI or a search result.
- **No browser or crawler disguise.** `programs.sigchi.org` is an Angular app whose HTML shell is empty; it is solved by reading the public JSON the app loads (`files.sigchi.org/conference/cache/...`, three requests: program-list → version-2 → program). When a target page is client-rendered, look for the data it loads publicly instead of adding a headless browser or claiming to be a search engine.
- **One page per run, never concurrent.** Respect the target site's terms and rate limits.
- **Paper detection in SIGCHI** checks the item's own content type *and* the type of the session it sits in — older programmes (CHI 2018) leave most contents untyped and classify only the session. Only papers are exported; posters, demos and workshops are not.
- Titles, sections and author names are copied verbatim. SIGCHI authors are joined `first middle last`, matching the programme.

## Adapter development

1. Save the target page to `fixtures/<name>.html` (create the directory) and develop offline:
   ```powershell
   uv run python -c "from paperharvest.fetch import fetch_html; open('fixtures/example.html','w',encoding='utf-8').write(fetch_html('https://example.org/2026/papers'))"
   ```
2. Implement `parse` in `paperharvest/adapters/<conference>.py`, reusing `Paper`.
3. Register the source in `registry.py`.
4. Check links, sections, authors and Unicode titles against the saved fixture before going online.

## UI language

All user-facing strings — argparse help, TUI labels, error messages — are **Chinese**; everything written to the CSV is not. This is deliberate. `_use_utf8_output()` in `__main__.py` reconfigures stdout/stderr to UTF-8 because redirected output on Windows gets the ANSI code page (cp936/cp1252) and would otherwise raise `UnicodeEncodeError` on the Chinese text.
