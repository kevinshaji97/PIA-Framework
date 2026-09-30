"""Locate a dependency's privacy policy on the web.

Strategy: look the package up in its registry (PyPI / npm) to learn the vendor's
homepage, collect privacy links from that homepage, search the web, rank the
candidate URLs, and return the first one that actually reads like a policy.
"""

import re
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import parse_qs, quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .fetch import TIMEOUT, USER_AGENT, FetchError, PolicyDocument, fetch_policy, http_get, looks_like_policy

MAX_FETCH_ATTEMPTS = 5
MIN_CANDIDATE_SCORE = 5  # a privacy page (3+) that is also tied to the vendor or name (2+)

# The privacy policy of the site hosting the code is not the dependency's policy.
CODE_HOSTS = ("github.com", "githubusercontent.com", "github.io", "gitlab.com", "bitbucket.org",
              "pypi.org", "npmjs.com", "npmjs.org", "readthedocs.io", "readthedocs.org",
              "sourceforge.net", "codeberg.org")
LOW_QUALITY_HOSTS = ("reddit.com", "stackoverflow.com", "stackexchange.com", "medium.com",
                     "wikipedia.org", "youtube.com", "linkedin.com", "quora.com", "x.com",
                     "twitter.com", "facebook.com", "termly.io", "iubenda.com",
                     "privacypolicies.com", "termsfeed.com")
GENERIC_NAME_PARTS = {"sdk", "python", "py", "js", "node", "api", "client", "lib", "core",
                      "the", "for", "plugin", "cli", "official"}


class PolicyNotFound(RuntimeError):
    pass


@dataclass
class PackageInfo:
    ecosystem: str
    name: str
    version_found: bool
    homepages: list[str] = field(default_factory=list)


@dataclass
class Candidate:
    url: str
    title: str = ""


def _get_json(url: str) -> dict | None:
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def _http_urls(urls) -> list[str]:
    seen = []
    for url in urls:
        if isinstance(url, str) and url.startswith(("http://", "https://")) and url not in seen:
            seen.append(url)
    return seen


def _pypi(name: str, version: str) -> PackageInfo | None:
    data = _get_json(f"https://pypi.org/pypi/{quote(name)}/json")
    if not data:
        return None
    info = data.get("info") or {}
    urls = [info.get("home_page"), *(info.get("project_urls") or {}).values()]
    return PackageInfo("pypi", info.get("name") or name, version in (data.get("releases") or {}), _http_urls(urls))


def _npm(name: str, version: str) -> PackageInfo | None:
    data = _get_json(f"https://registry.npmjs.org/{quote(name, safe='@')}")
    if not data or "versions" not in data:
        return None
    repo = data.get("repository")
    urls = [data.get("homepage"), repo.get("url") if isinstance(repo, dict) else repo]
    return PackageInfo("npm", data.get("name") or name, version in data["versions"], _http_urls(urls))


def lookup_package(name: str, version: str, ecosystem: str) -> PackageInfo | None:
    lookups = {"pypi": _pypi, "npm": _npm}
    order = list(lookups) if ecosystem == "auto" else [ecosystem] if ecosystem in lookups else []
    for eco in order:
        info = lookups[eco](name, version)
        if info:
            return info
    return None


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def domain_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def registrable_domain(host: str) -> str:
    """Best-effort eTLD+1, e.g. docs.sentry.io -> sentry.io, www.bbc.co.uk -> bbc.co.uk."""
    labels = host.split(".")
    if len(labels) >= 3 and len(labels[-1]) == 2 and len(labels[-2]) <= 3:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def vendor_domains(homepages: list[str]) -> list[str]:
    domains = []
    for url in homepages:
        host = _host(url)
        if host and not any(domain_matches(host, h) for h in CODE_HOSTS):
            domain = registrable_domain(host)
            if domain not in domains:
                domains.append(domain)
    return domains


def github_orgs(homepages: list[str]) -> list[str]:
    """Owners of GitHub repos, e.g. https://github.com/mixpanel/mixpanel-js -> mixpanel."""
    orgs = []
    for url in homepages:
        parsed = urlparse(url)
        segments = [s for s in parsed.path.split("/") if s]
        if _host(url) == "github.com" and segments and segments[0].lower() not in orgs:
            orgs.append(segments[0].lower())
    return orgs


def name_tokens(name: str) -> list[str]:
    parts = re.split(r"[^a-z0-9]+", name.lower())
    return [p for p in parts if len(p) >= 3 and p not in GENERIC_NAME_PARTS]


def score_candidate(c: Candidate, tokens: list[str], vendors: list[str]) -> int:
    host, path = _host(c.url), urlparse(c.url).path.lower()
    score = 0
    if "privacy" in path or "privacy" in c.title.lower():
        score += 3
    if re.search(r"privacy[-_]?(policy|notice|statement)|/privacy/?$", path):
        score += 1
    if any(domain_matches(host, v) for v in vendors):
        score += 3
    if any(t in host for t in tokens):
        score += 2
    if any(domain_matches(host, h) for h in CODE_HOSTS):
        score -= 4
    if any(domain_matches(host, h) for h in LOW_QUALITY_HOSTS):
        score -= 3
    if host.startswith("docs.") or "/docs/" in path or "/blog/" in path:
        score -= 1
    return score


def rank_candidates(candidates: list[Candidate], name: str, vendors: list[str],
                    extra_tokens: list[str] = ()) -> list[Candidate]:
    tokens = name_tokens(name) + [t for t in extra_tokens if len(t) >= 3]
    unique: dict[str, Candidate] = {}
    for c in candidates:
        unique.setdefault(c.url, c)
    scored = [(score_candidate(c, tokens, vendors), i, c) for i, c in enumerate(unique.values())]
    # Stable on original order: registry/homepage links first, then search rank.
    return [c for s, i, c in sorted(scored, key=lambda t: (-t[0], t[1])) if s >= MIN_CANDIDATE_SCORE]


def homepage_privacy_links(homepage: str) -> list[Candidate]:
    resp = http_get(homepage)
    soup = BeautifulSoup(resp.text, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        if "privacy" in (a["href"] + " " + text).lower():
            url = urljoin(resp.url, a["href"]).split("#")[0]
            if url.startswith(("http://", "https://")):
                links.append(Candidate(url, text))
    return links


def _unwrap_redirect(href: str) -> str | None:
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if parsed.hostname and parsed.hostname.endswith("duckduckgo.com"):
        if parsed.path.startswith("/y.js"):  # sponsored result
            return None
        target = parse_qs(parsed.query).get("uddg")
        return target[0] if target else None
    return href


def _search_brave(query: str) -> list[Candidate]:
    resp = requests.get("https://search.brave.com/search", params={"q": query, "source": "web"},
                        headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    resp.raise_for_status()
    results = []
    for snippet in BeautifulSoup(resp.text, "html.parser").select('div.snippet[data-type="web"]'):
        link, title = snippet.find("a", href=True), snippet.select_one(".title")
        if link and link["href"].startswith("http"):
            results.append(Candidate(link["href"], title.get_text(" ", strip=True) if title else ""))
    return results


def _search_duckduckgo(query: str) -> list[Candidate]:
    resp = requests.post("https://html.duckduckgo.com/html/", data={"q": query},
                         headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    resp.raise_for_status()
    if resp.status_code == 202 or "anomaly" in resp.text:
        raise requests.RequestException("DuckDuckGo returned a bot challenge")
    results = []
    for a in BeautifulSoup(resp.text, "html.parser").select("a.result__a"):
        url = _unwrap_redirect(a.get("href", ""))
        if url:
            results.append(Candidate(url, a.get_text(" ", strip=True)))
    return results


SEARCH_BACKENDS = {"brave": _search_brave, "duckduckgo": _search_duckduckgo}


def search_web(query: str, max_results: int = 10) -> list[Candidate]:
    """Query each search backend in turn and return the first non-empty result list."""
    errors = []
    for name, backend in SEARCH_BACKENDS.items():
        try:
            results = backend(query)
        except requests.RequestException as e:
            errors.append(f"{name}: {e}")
            continue
        if results:
            return results[:max_results]
    if errors:
        raise FetchError("Web search failed (" + "; ".join(errors) + ")")
    return []


def find_candidates(name: str, pkg: PackageInfo | None, log: Callable[[str], None]) -> list[Candidate]:
    homepages = pkg.homepages if pkg else []
    vendors, orgs = vendor_domains(homepages), github_orgs(homepages)
    candidates: list[Candidate] = []

    for home in homepages:
        if vendor_domains([home]):
            try:
                candidates += homepage_privacy_links(home)
            except FetchError as e:
                log(f"Skipping homepage: {e}")

    queries = [f"site:{v} privacy policy" for v in vendors[:1]] + [f"{name} privacy policy"]
    # Package names like "mixpanel-browser" search poorly; the publishing org is a better fallback.
    fallbacks = [f"{org} privacy policy" for org in orgs[:1] if org not in name.lower()]

    ranked: list[Candidate] = []
    for query in queries + fallbacks:
        if ranked and query in fallbacks:
            break
        log(f"Searching the web: {query}")
        try:
            candidates += search_web(query)
        except FetchError as e:
            log(str(e))
        ranked = rank_candidates(candidates, name, vendors, orgs)
    return ranked


def locate_policy(name: str, pkg: PackageInfo | None, max_chars: int,
                  log: Callable[[str], None]) -> PolicyDocument:
    candidates = find_candidates(name, pkg, log)
    if not candidates:
        raise PolicyNotFound(f"No privacy policy candidates found for '{name}'")
    for c in candidates[:MAX_FETCH_ATTEMPTS]:
        log(f"Checking {c.url}")
        try:
            doc = fetch_policy(c.url, max_chars)
        except FetchError as e:
            log(str(e))
            continue
        if looks_like_policy(doc.text):
            return doc
        log("  does not look like a privacy policy, skipping")
    raise PolicyNotFound(f"None of the top candidates for '{name}' looked like a privacy policy")
