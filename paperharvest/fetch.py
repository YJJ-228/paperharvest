from urllib.request import Request, urlopen


def fetch_html(url: str, timeout: int = 60) -> str:
    request = Request(url, headers={"User-Agent": "PaperHarvest/0.1 (academic list export)"})
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(content_type, errors="replace")
