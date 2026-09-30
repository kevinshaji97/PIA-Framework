"""Download a privacy policy and reduce it to plain text."""

import re
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
TIMEOUT = 20
MIN_POLICY_CHARS = 4000  # shorter pages are usually overviews or link hubs
NOISE_TAGS = ["script", "style", "noscript", "svg", "nav", "header", "footer",
              "form", "aside", "iframe", "button", "template"]


class FetchError(RuntimeError):
    pass


@dataclass
class PolicyDocument:
    source: str
    title: str
    text: str
    truncated: bool = False


def http_get(url: str) -> requests.Response:
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise FetchError(f"Could not fetch {url}: {e}") from e
    return resp


def html_to_text(html: str) -> tuple[str, str]:
    """Return (title, readable text) for an HTML page."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    for tag in soup(NOISE_TAGS):
        tag.decompose()

    root = soup.body or soup
    # Prefer the main content region when the page marks one up.
    for main in soup.find_all(["main", "article"]):
        if len(main.get_text(strip=True)) >= MIN_POLICY_CHARS:
            root = main
            break

    lines = (re.sub(r"\s+", " ", line).strip() for line in root.get_text("\n").splitlines())
    return title, "\n".join(line for line in lines if line)


def looks_like_policy(text: str) -> bool:
    lower = text.lower()
    return (
        len(text) >= MIN_POLICY_CHARS
        and lower.count("privacy") >= 2
        and ("personal data" in lower or "personal information" in lower or "information we collect" in lower)
    )


def _truncate(doc: PolicyDocument, max_chars: int) -> PolicyDocument:
    if len(doc.text) > max_chars:
        doc.text, doc.truncated = doc.text[:max_chars], True
    return doc


def fetch_policy(url: str, max_chars: int) -> PolicyDocument:
    resp = http_get(url)
    content_type = resp.headers.get("Content-Type", "")
    if "pdf" in content_type:
        raise FetchError(f"{url} is a PDF; save it as text and pass it with --policy-file")
    if "html" in content_type or not content_type:
        title, text = html_to_text(resp.text)
    else:
        title, text = "", resp.text
    return _truncate(PolicyDocument(resp.url, title, text), max_chars)


def load_policy_file(path: str, max_chars: int) -> PolicyDocument:
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    if path.lower().endswith((".html", ".htm")):
        title, text = html_to_text(raw)
    else:
        title, text = Path(path).name, raw
    return _truncate(PolicyDocument(str(Path(path).resolve()), title, text), max_chars)
