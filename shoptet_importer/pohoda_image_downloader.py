from __future__ import annotations

import csv
import html
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, unquote, urljoin, urlparse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

NS = {
    "lStk": "http://www.stormware.cz/schema/version_2/list_stock.xsd",
    "stk": "http://www.stormware.cz/schema/version_2/stock.xsd",
}

OFFICIAL_DOMAINS = {
    "VAILLANT": ["vaillant.sk", "vaillant.com"],
    "STIEBEL ELTRON": ["stiebel-eltron.sk", "stiebel-eltron.com"],
    "ARISTON": ["ariston.com"],
    "DRAŽICE": ["dzd.cz", "drazice.cz"],
    "DRAZICE": ["dzd.cz", "drazice.cz"],
    "CLAGE": ["clage.com"],
    "HAKL": ["hakl.sk"],
    "MORA": ["mora.cz", "mora.sk"],
    "TESY": ["tesy.com"],
    "CONCEPT": ["my-concept.sk", "my-concept.cz"],
    "SIWELL": [],
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)


@dataclass
class PohodaProduct:
    code: str
    name: str
    brand: str
    has_picture: bool


@dataclass
class ImageResult:
    code: str
    name: str
    brand: str
    status: str
    image_file: str = ""
    image_url: str = ""
    source_page: str = ""
    note: str = ""


def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def infer_brand(name: str) -> str:
    upper = name.upper()
    for brand in sorted(OFFICIAL_DOMAINS, key=len, reverse=True):
        if upper.startswith(brand) or f" {brand} " in f" {upper} ":
            return brand
    return (name.split()[0] if name.split() else "").upper()


def read_pohoda_products(xml_path: str | Path, missing_only: bool = True) -> list[PohodaProduct]:
    tree = ET.parse(xml_path)
    products: list[PohodaProduct] = []
    for stock in tree.findall(".//lStk:stock", NS):
        header = stock.find("stk:stockHeader", NS)
        if header is None:
            continue
        code = _text(header.find("stk:code", NS))
        name = _text(header.find("stk:name", NS))
        if not code or not name:
            continue
        has_picture = header.find("stk:pictures/stk:picture", NS) is not None
        if missing_only and has_picture:
            continue
        products.append(PohodaProduct(code=code, name=name, brand=infer_brand(name), has_picture=has_picture))
    return products


def _clean_result_url(url: str) -> str:
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc:
        uddg = parse_qs(parsed.query).get("uddg")
        if uddg:
            return unquote(uddg[0])
    return url



def _host_matches(url: str, domains: list[str]) -> bool:
    if not domains:
        return False
    host = urlparse(url).netloc.lower().split(":")[0].removeprefix("www.")
    return any(host == d or host.endswith("." + d) for d in domains)


def _is_official_page(product: PohodaProduct, url: str) -> bool:
    domains = OFFICIAL_DOMAINS.get(product.brand, [])
    return _host_matches(url, domains)


def _page_relevance(product: PohodaProduct, page_url: str, page_text: str) -> bool:
    """Require strong product match before accepting an image from a page."""
    text = re.sub(r"\s+", " ", page_text).lower()
    code = product.code.strip().lower()
    if code and len(code) >= 4 and code in text:
        return True

    # Use distinctive model/name tokens, not generic words like zasobnikovy/ohrievac.
    stop = {
        "zasobnikovy", "ohrievac", "ohrievace", "vody", "elektricky", "elektricke",
        "zavesny", "stacionarny", "prietokovy", "pod", "nad", "umyvadlo", "wifi",
        "litrov", "liter", "eu", "plus", "trend", "smart",
    }
    tokens = [
        t.lower() for t in re.findall(r"[A-Za-z0-9]+", product.name)
        if len(t) >= 3 and t.lower() not in stop
    ]
    distinctive = tokens[:8]
    matches = sum(1 for t in distinctive if t in text)
    return matches >= min(3, max(2, len(distinctive) // 2))

def _queries_for(product: PohodaProduct) -> list[str]:
    domains = OFFICIAL_DOMAINS.get(product.brand, [])
    queries: list[str] = []
    if domains:
        for domain in domains[:2]:
            queries.append(f'site:{domain} "{product.code}" "{product.name}"')
            queries.append(f'site:{domain} "{product.name}"')
    queries.extend([
        f'"{product.code}" "{product.name}"',
        f'"{product.code}" {product.brand}',
        f'"{product.name}" product',
    ])
    return queries


def search_pages(session: requests.Session, product: PohodaProduct, max_results: int = 12) -> list[str]:
    """Find product pages. For known brands accept only official manufacturer pages."""
    found: list[str] = []
    domains = OFFICIAL_DOMAINS.get(product.brand, [])

    for query in _queries_for(product):
        # 1) Bing web search
        try:
            response = session.get(
                "https://www.bing.com/search",
                params={"q": query, "count": 10},
                timeout=20,
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for a in soup.select("li.b_algo h2 a"):
                href = a.get("href", "")
                if not href.startswith("http"):
                    continue
                if domains and not _host_matches(href, domains):
                    continue
                if href not in found:
                    found.append(href)
                    if len(found) >= max_results:
                        return found
        except requests.RequestException:
            pass

        # 2) DuckDuckGo fallback
        try:
            response = session.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                timeout=20,
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for a in soup.select("a.result__a"):
                href = _clean_result_url(a.get("href", ""))
                if not href.startswith("http"):
                    continue
                if domains and not _host_matches(href, domains):
                    continue
                if href not in found:
                    found.append(href)
                    if len(found) >= max_results:
                        return found
        except requests.RequestException:
            pass

        time.sleep(0.25)

    return found


def search_direct_images(session: requests.Session, product: PohodaProduct, max_results: int = 16) -> list[tuple[str, str]]:
    """Return (image_url, source_page) pairs, restricted to official source pages."""
    domains = OFFICIAL_DOMAINS.get(product.brand, [])
    if not domains:
        return []

    found: list[tuple[str, str]] = []
    for query in _queries_for(product):
        try:
            response = session.get(
                "https://www.bing.com/images/search",
                params={"q": query, "form": "HDRSC3"},
                timeout=20,
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for a in soup.select("a.iusc"):
                raw = a.get("m")
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                except Exception:
                    continue
                image_url = data.get("murl")
                source_page = data.get("purl") or data.get("surl") or ""
                if not isinstance(image_url, str) or not image_url.startswith("http"):
                    continue
                if not isinstance(source_page, str) or not source_page.startswith("http"):
                    continue
                if not _host_matches(source_page, domains):
                    continue
                pair = (image_url, source_page)
                if pair not in found:
                    found.append(pair)
                    if len(found) >= max_results:
                        return found
        except requests.RequestException:
            pass
        time.sleep(0.25)
    return found

