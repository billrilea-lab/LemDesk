"""Aggressive public scrape of local-AI stack docs (Model Runner, Sandboxes, agents, MCP).

Fetch backends (--backend):
  httpx    — fast HTTP
  crawl4ai — headless browser (Playwright)
  auto     — httpx first, crawl4ai if body too small (default)

Outputs under lemdesk/:
  incoming/*.json   — per-URL worker staging
  data/knowledge.json — merged corpus
  data/raw/         — HTML snapshots
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse

import certifi
import httpx

ROOT = Path(__file__).parent
HUB = ROOT / "lemdesk"
DATA_DIR = HUB / "data"
INCOMING_DIR = HUB / "incoming"
DEFAULT_OUT = DATA_DIR / "knowledge.json"

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Curated seeds — BFS expands within allowed prefixes
SEED_URLS = [
    "https://docs.docker.com/ai-overview/",
    "https://docs.docker.com/ai/model-runner/",
    "https://docs.docker.com/ai/model-runner/get-started/",
    "https://docs.docker.com/ai/model-runner/api-reference/",
    "https://docs.docker.com/ai/model-runner/ide-integrations/",
    "https://docs.docker.com/ai/model-runner/configuration/",
    "https://docs.docker.com/ai/model-runner/inference-engines/",
    "https://docs.docker.com/ai/model-runner/open-webui/",
    "https://docs.docker.com/ai/model-runner/models-and-compose/",
    "https://docs.docker.com/ai/gordon/",
    "https://docs.docker.com/ai/gordon/desktop/",
    "https://docs.docker.com/ai/gordon/cli/",
    "https://docs.docker.com/ai/gordon/permissions/",
    "https://docs.docker.com/ai/sandboxes/",
    "https://docs.docker.com/ai/sandboxes/get-started/",
    "https://docs.docker.com/ai/sandboxes/agents/",
    "https://docs.docker.com/ai/sandboxes/customize/",
    "https://docs.docker.com/ai/sandboxes/architecture/",
    "https://docs.docker.com/ai/sandboxes/security/isolation/",
    "https://docs.docker.com/ai/sandboxes/governance/local/",
    "https://docs.docker.com/ai/sandboxes/troubleshooting/",
    "https://docs.docker.com/ai/sandboxes/faq/",
    "https://docs.docker.com/ai/docker-agent/",
    "https://docs.docker.com/ai/docker-agent/tutorial/",
    "https://docs.docker.com/ai/docker-agent/reference/config/",
    "https://docs.docker.com/ai/mcp-catalog-and-toolkit/",
    "https://docs.docker.com/ai/mcp-catalog-and-toolkit/mcp-gateway/",
    "https://docs.docker.com/ai/mcp-catalog-and-toolkit/mcp-toolkit/",
    "https://docker.github.io/docker-agent/configuration/agents/",
]

# Second-pass seeds (Gordon blog, examples) — use --extra-seeds to fetch without full BFS
EXTRA_SEED_URLS = [
    "https://www.docker.com/blog/gordon-dockers-ai-agent-just-got-an-update/",
    "https://docs.docker.com/ai/model-runner/examples/",
    "https://docs.docker.com/ai/gordon/desktop/",
    "https://docs.docker.com/ai/sandboxes/usage/",
    "https://docs.docker.com/ai/docker-agent/integrations/mcp/",
]

ALLOWED_PREFIXES = (
    ("docs.docker.com", "/ai"),
    ("docker.github.io", "/docker-agent"),
    ("www.docker.com", "/blog/"),
)

HREF_RE = re.compile(r'href="([^"]+)"', re.I)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", text))).strip()


def _strip_scripts(html: str) -> str:
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.S | re.I)
    return html


def _url_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    if not path.endswith("/") and "." not in path.rsplit("/", 1)[-1]:
        path = path + "/"
    return f"{parsed.scheme}://{parsed.netloc.lower()}{path}" + (
        f"?{parsed.query}" if parsed.query else ""
    )


def _url_allowed(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path or "/"
    for allowed_host, prefix in ALLOWED_PREFIXES:
        if host == allowed_host or host.endswith(f".{allowed_host}"):
            if path.startswith(prefix) or prefix in path:
                return True
    return False


def _topic_tag(url: str) -> str:
    u = url.lower()
    if "gordon" in u:
        return "gordon"
    if "sandbox" in u or "sbx" in u:
        return "sandbox"
    if "model-runner" in u or "model_runner" in u:
        return "model-runner"
    if "mcp" in u:
        return "mcp"
    if "docker-agent" in u:
        return "docker-agent"
    if "ai-overview" in u:
        return "overview"
    if "docker.com/blog" in u:
        return "blog"
    return "general"


@dataclass
class FetchResult:
    url: str
    status: int
    bytes: int
    html: str = ""
    markdown: str = ""
    error: str | None = None
    backend: str | None = None


class _Crawl4AISession:
    def __init__(self) -> None:
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._crawler = None

    def start(self) -> None:
        if self._crawler is not None:
            return
        from crawl4ai import AsyncWebCrawler, BrowserConfig

        self._event_loop = asyncio.new_event_loop()

        async def _open() -> None:
            cfg = BrowserConfig(headless=True, verbose=False, user_agent=BROWSER_UA)
            self._crawler = AsyncWebCrawler(config=cfg)
            await self._crawler.__aenter__()

        self._event_loop.run_until_complete(_open())

    def fetch(self, url: str, min_bytes: int = 300) -> FetchResult:
        from crawl4ai import CacheMode, CrawlerRunConfig

        self.start()
        assert self._event_loop is not None and self._crawler is not None

        async def _run():
            run_cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, word_count_threshold=10)
            return await self._crawler.arun(url=url, config=run_cfg)

        try:
            result = self._event_loop.run_until_complete(_run())
        except Exception as exc:  # noqa: BLE001
            return FetchResult(url=url, status=0, bytes=0, error=str(exc), backend="crawl4ai")

        if not result.success:
            return FetchResult(
                url=url,
                status=0,
                bytes=0,
                error=result.error_message or "crawl4ai failed",
                backend="crawl4ai",
            )

        html = result.html or result.cleaned_html or ""
        md = ""
        if result.markdown:
            md = getattr(result.markdown, "raw_markdown", None) or str(result.markdown)
        nbytes = len(html.encode("utf-8"))
        err = f"short body ({nbytes} bytes)" if nbytes < min_bytes else None
        return FetchResult(
            url=url, status=200, bytes=nbytes, html=html, markdown=md, error=err, backend="crawl4ai"
        )

    def close(self) -> None:
        if self._crawler is None or self._event_loop is None:
            return
        crawler = self._crawler
        loop = self._event_loop
        self._crawler = None
        self._event_loop = None

        async def _close() -> None:
            await crawler.__aexit__(None, None, None)

        try:
            loop.run_until_complete(_close())
        finally:
            loop.close()


class Scraper:
    def __init__(self, backend: str = "auto") -> None:
        if backend not in {"auto", "httpx", "crawl4ai"}:
            raise ValueError(f"unknown backend: {backend!r}")
        self.backend = backend
        self.client = httpx.Client(
            timeout=90,
            verify=certifi.where(),
            follow_redirects=True,
            headers={"User-Agent": BROWSER_UA, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"},
        )
        self._c4a: _Crawl4AISession | None = None

    def close(self) -> None:
        self.client.close()
        if self._c4a is not None:
            self._c4a.close()
            self._c4a = None

    def _crawl4ai(self) -> _Crawl4AISession:
        if self._c4a is None:
            self._c4a = _Crawl4AISession()
        return self._c4a

    def _fetch_curl(self, url: str) -> FetchResult:
        try:
            proc = subprocess.run(
                ["curl", "-sL", "--compressed", "-A", BROWSER_UA, "--max-time", "90", url],
                capture_output=True,
                timeout=100,
                check=False,
            )
            if proc.returncode != 0:
                err = proc.stderr.decode("utf-8", errors="replace")[:500]
                return FetchResult(url=url, status=0, bytes=0, error=f"curl exit {proc.returncode}: {err}")
            html = proc.stdout.decode("utf-8", errors="replace")
            return FetchResult(url=url, status=200, bytes=len(proc.stdout), html=html, backend="curl")
        except Exception as exc:  # noqa: BLE001
            return FetchResult(url=url, status=0, bytes=0, error=str(exc))

    def _fetch_httpx_curl(self, url: str, min_bytes: int = 300, retries: int = 3) -> FetchResult:
        last = FetchResult(url=url, status=0, bytes=0, error="no attempts")
        for attempt in range(retries):
            try:
                resp = self.client.get(url)
                html = resp.text
                nbytes = len(resp.content)
                if resp.status_code == 200 and nbytes >= min_bytes:
                    return FetchResult(url=url, status=resp.status_code, bytes=nbytes, html=html, backend="httpx")
                last = FetchResult(
                    url=url,
                    status=resp.status_code,
                    bytes=nbytes,
                    html=html,
                    error=f"short body ({nbytes} bytes)" if nbytes < min_bytes else None,
                    backend="httpx",
                )
            except Exception as exc:  # noqa: BLE001
                last = FetchResult(url=url, status=0, bytes=0, error=str(exc), backend="httpx")

            curl_result = self._fetch_curl(url)
            curl_result.backend = "curl"
            if curl_result.status == 200 and curl_result.bytes >= min_bytes:
                return curl_result
            last = curl_result if curl_result.bytes >= last.bytes else last
            time.sleep(0.5 * (attempt + 1))
        return last

    def _fetch_crawl4ai(self, url: str, min_bytes: int = 300, retries: int = 2) -> FetchResult:
        last = FetchResult(url=url, status=0, bytes=0, error="no attempts", backend="crawl4ai")
        for attempt in range(retries):
            last = self._crawl4ai().fetch(url, min_bytes=min_bytes)
            if last.status == 200 and last.bytes >= min_bytes:
                return last
            time.sleep(0.5 * (attempt + 1))
        return last

    def fetch(self, url: str, min_bytes: int = 300, retries: int = 3) -> FetchResult:
        if self.backend == "crawl4ai":
            return self._fetch_crawl4ai(url, min_bytes=min_bytes, retries=retries)

        last = self._fetch_httpx_curl(url, min_bytes=min_bytes, retries=retries)
        if self.backend == "auto" and (last.error or last.bytes < min_bytes):
            c4 = self._fetch_crawl4ai(url, min_bytes=min_bytes, retries=2)
            if c4.status == 200 and c4.bytes >= min_bytes:
                return c4
            if c4.bytes > last.bytes:
                return c4
        return last

    def discover_links(self, html: str, base_url: str) -> list[str]:
        found: set[str] = set()
        base_parsed = urlparse(base_url)
        for href in HREF_RE.findall(html):
            if href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
                continue
            abs_url = urljoin(base_url, href)
            parsed = urlparse(abs_url)
            if parsed.scheme not in ("http", "https"):
                continue
            path = parsed.path or "/"
            if path.endswith((".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2", ".pdf")):
                continue
            norm = _normalize_url(f"{parsed.scheme}://{parsed.netloc}{path}" + (f"?{parsed.query}" if parsed.query else ""))
            if _url_allowed(norm):
                found.add(norm)
        return sorted(found)


def _parse_page(url: str, result: FetchResult) -> dict:
    html = result.html
    title_m = TITLE_RE.search(html)
    h1_m = H1_RE.search(html)
    text = _clean(_strip_scripts(html))
    markdown = result.markdown or text[:12000]
    return {
        "url": url,
        "title": _clean(title_m.group(1)) if title_m else "",
        "h1": _clean(h1_m.group(1)) if h1_m else "",
        "topic": _topic_tag(url),
        "text_sample": text[:4000],
        "markdown": markdown[:20000],
        "bytes": result.bytes,
        "backend": result.backend,
    }


def _raw_path_for_url(url: str) -> Path:
    parsed = urlparse(url)
    safe = re.sub(r"[^\w.-]+", "_", (parsed.netloc + parsed.path).strip("/"))[:120]
    return DATA_DIR / "raw" / f"{safe}.html"


def _write_incoming(url: str, payload: dict) -> Path:
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    path = INCOMING_DIR / f"{_url_key(url)}.json"
    path.write_text(json.dumps(payload, indent=2))
    return path


def _load_incoming() -> list[dict]:
    if not INCOMING_DIR.exists():
        return []
    out: list[dict] = []
    for p in sorted(INCOMING_DIR.glob("*.json")):
        try:
            out.append(json.loads(p.read_text()))
        except json.JSONDecodeError:
            continue
    return out


def _merge_incoming_into_knowledge(knowledge: dict) -> dict:
    for item in _load_incoming():
        url = item.get("url")
        if not url:
            continue
        if item.get("error"):
            knowledge.setdefault("errors", []).append({"url": url, "error": item["error"]})
            continue
        page = item.get("page")
        if page:
            knowledge["pages"][url] = page
    return knowledge


def _bfs_urls(seeds: list[str], scraper: Scraper, max_depth: int) -> list[str]:
    seen: set[str] = set()
    queue: list[tuple[str, int]] = []
    for s in seeds:
        norm = _normalize_url(s)
        if _url_allowed(norm):
            queue.append((norm, 0))
            seen.add(norm)

    ordered: list[str] = []
    idx = 0
    while idx < len(queue):
        url, depth = queue[idx]
        idx += 1
        ordered.append(url)
        if depth >= max_depth:
            continue
        # prefetch for link discovery only if we don't have html yet
        result = scraper.fetch(url, min_bytes=200)
        if result.status != 200 or not result.html:
            continue
        for link in scraper.discover_links(result.html, url):
            if link not in seen:
                seen.add(link)
                queue.append((link, depth + 1))
    return ordered


def _worker_fetch(
    url: str,
    backend: str,
    save_raw: bool,
    scraped_at: str,
) -> dict:
    scraper = Scraper(backend=backend)
    try:
        result = scraper.fetch(url, min_bytes=200)
        payload: dict = {
            "url": url,
            "scraped_at": scraped_at,
            "status": result.status,
            "bytes": result.bytes,
            "backend": result.backend,
            "error": result.error,
        }
        if result.error or result.status != 200:
            _write_incoming(url, payload)
            return payload

        if save_raw:
            raw_path = _raw_path_for_url(url)
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(result.html)

        page = _parse_page(url, result)
        payload["page"] = page
        _write_incoming(url, payload)
        return payload
    finally:
        scraper.close()


async def _supervisor_fetch_many(
    urls: list[str],
    backend: str,
    workers: int,
    save_raw: bool,
    scraped_at: str,
) -> list[dict]:
    """Async supervisor: semaphore-limited parallel fetches (own scraper per worker)."""
    loop = asyncio.get_event_loop()
    sem = asyncio.Semaphore(max(1, workers))

    async def _one(url: str) -> dict:
        async with sem:
            return await loop.run_in_executor(
                None, _worker_fetch, url, backend, save_raw, scraped_at
            )

    return await asyncio.gather(*[_one(u) for u in urls])


def _merge_knowledge_from_incoming(
    knowledge: dict,
    url_filter: set[str] | None = None,
) -> dict:
    for item in _load_incoming():
        url = item.get("url", "")
        if url_filter is not None and url not in url_filter:
            continue
        knowledge.setdefault("fetch_log", []).append(
            {
                "url": url,
                "status": item.get("status"),
                "bytes": item.get("bytes"),
                "error": item.get("error"),
                "backend": item.get("backend"),
            }
        )
        if item.get("error") or not item.get("page"):
            if item.get("error"):
                knowledge.setdefault("errors", []).append({"url": url, "error": item["error"]})
            continue
        knowledge.setdefault("pages", {})[url] = item["page"]
    knowledge["page_count"] = len(knowledge.get("pages", {}))
    knowledge["topics"] = _summarize_topics(knowledge)
    return knowledge


def build_knowledge_extra(
    backend: str = "httpx",
    workers: int = 4,
    save_raw: bool = True,
    extra_urls: list[str] | None = None,
) -> dict:
    """Fetch extra seed URLs and merge into existing knowledge.json."""
    scraped_at = datetime.now(timezone.utc).isoformat()
    raw_urls = extra_urls or EXTRA_SEED_URLS
    urls = sorted({_normalize_url(u) for u in raw_urls if _url_allowed(_normalize_url(u))})
    url_set = set(urls)

    if DEFAULT_OUT.exists():
        try:
            knowledge = json.loads(DEFAULT_OUT.read_text())
        except json.JSONDecodeError:
            knowledge = {}
    else:
        knowledge = {}

    knowledge.setdefault("pages", {})
    knowledge.setdefault("errors", [])
    knowledge.setdefault("fetch_log", [])
    knowledge["hub"] = str(HUB)
    knowledge["extra_seeds_at"] = scraped_at
    knowledge["extra_urls"] = urls

    asyncio.run(_supervisor_fetch_many(urls, backend, workers, save_raw, scraped_at))
    knowledge = _merge_knowledge_from_incoming(knowledge, url_filter=url_set)
    return knowledge


def build_knowledge_base(
    backend: str = "auto",
    max_depth: int = 2,
    workers: int = 6,
    save_raw: bool = True,
    seeds: list[str] | None = None,
    merge_only: bool = False,
) -> dict:
    scraped_at = datetime.now(timezone.utc).isoformat()
    seed_list = seeds or SEED_URLS

    if merge_only:
        knowledge = {
            "scraped_at": scraped_at,
            "hub": str(HUB),
            "pages": {},
            "errors": [],
            "fetch_log": [],
        }
        knowledge = _merge_incoming_into_knowledge(knowledge)
        knowledge["page_count"] = len(knowledge["pages"])
        return knowledge

    # BFS with single scraper for discovery
    discover_scraper = Scraper(backend=backend)
    try:
        urls = _bfs_urls(seed_list, discover_scraper, max_depth)
    finally:
        discover_scraper.close()

    asyncio.run(_supervisor_fetch_many(urls, backend, workers, save_raw, scraped_at))

    knowledge = {
        "scraped_at": scraped_at,
        "hub": str(HUB),
        "seeds": seed_list,
        "max_depth": max_depth,
        "workers": workers,
        "pages": {},
        "errors": [],
        "fetch_log": [],
    }
    knowledge = _merge_knowledge_from_incoming(knowledge)
    return knowledge


def _summarize_topics(knowledge: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for page in knowledge.get("pages", {}).values():
        t = page.get("topic", "general")
        counts[t] = counts.get(t, 0) + 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape Docker AI documentation into lemdesk/")
    parser.add_argument(
        "--backend",
        choices=["auto", "httpx", "crawl4ai"],
        default="auto",
        help="Fetch backend",
    )
    parser.add_argument("--workers", type=int, default=6, help="Parallel fetch workers")
    parser.add_argument("--max-depth", type=int, default=2, help="BFS link discovery depth")
    parser.add_argument("-o", type=Path, default=DEFAULT_OUT, help="Output knowledge.json path")
    parser.add_argument("--no-raw", action="store_true", help="Skip saving raw HTML")
    parser.add_argument("--merge-only", action="store_true", help="Merge incoming/*.json without fetching")
    parser.add_argument(
        "--extra-seeds",
        action="store_true",
        help="Fetch EXTRA_SEED_URLS only and merge into existing knowledge.json",
    )
    parser.add_argument("--post-process", action="store_true", help="Run lemdesk_brief post-process after scrape")
    parser.add_argument(
        "--cleanup-incoming",
        action="store_true",
        help="Delete incoming/*.json for URLs present in merged knowledge",
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)

    if args.extra_seeds:
        knowledge = build_knowledge_extra(
            backend=args.backend if args.backend != "auto" else "httpx",
            workers=args.workers,
            save_raw=not args.no_raw,
        )
    else:
        knowledge = build_knowledge_base(
            backend=args.backend,
            max_depth=args.max_depth,
            workers=args.workers,
            save_raw=not args.no_raw,
            merge_only=args.merge_only,
        )

    out_path = args.o
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(knowledge, indent=2))

    print(f"Pages: {knowledge.get('page_count', len(knowledge.get('pages', {})))}")
    print(f"Errors: {len(knowledge.get('errors', []))}")
    print(f"Written → {out_path}")

    if args.post_process:
        from lemdesk_brief import post_process_all

        post_process_all(knowledge)
        print("Post-process → setup_facts, gordon_playbook, topology, logs")

    if args.cleanup_incoming:
        from lemdesk_auto import cleanup_incoming

        n = cleanup_incoming(knowledge)
        print(f"Cleaned {n} incoming staging files")

    return 0 if knowledge.get("page_count", 0) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
