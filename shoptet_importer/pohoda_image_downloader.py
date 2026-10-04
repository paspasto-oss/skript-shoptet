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
    """Find product pages. Bing is primary, DuckDuckGo is fallback."""
    found: list[str] = []

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
                if href.startswith("http") and href not in found:
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
                if href.startswith("http") and href not in found:
                    found.append(href)
                    if len(found) >= max_results:
                        return found
        except requests.RequestException:
            pass

        time.sleep(0.25)

    return found


def search_direct_images(session: requests.Session, product: PohodaProduct, max_results: int = 16) -> list[str]:
    """Get direct image URLs from Bing Images. Official-domain queries are tried first."""
    found: list[str] = []
    for query in _queries_for(product):
        try:
            response = session.get(
                "https://www.bing.com/images/search",
                params={"q": query, "form": "HDRSC3"},
                timeout=20,
            )
            response.raise_for_status()

            # Bing embeds original image URL in JSON-like m attributes.
            for match in re.finditer(r'["\\]murl["\\]\s*:\s*["\\](https?://.*?)(?<!\\)["\\]', response.text):
                url = match.group(1).replace("\\/", "/").replace("\\u002f", "/")
                url = html.unescape(url)
                if url.startswith("http") and url not in found:
                    found.append(url)
                    if len(found) >= max_results:
                        return found

            soup = BeautifulSoup(response.text, "html.parser")
            for a in soup.select("a.iusc"):
                raw = a.get("m")
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                except Exception:
                    continue
                url = data.get("murl")
                if isinstance(url, str) and url.startswith("http") and url not in found:
                    found.append(url)
                    if len(found) >= max_results:
                        return found
        except requests.RequestException:
            pass
        time.sleep(0.25)
    return found


def _jsonld_images(soup: BeautifulSoup) -> list[str]:
    out: list[str] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue

        def walk(value):
            if isinstance(value, dict):
                for k, v in value.items():
                    if k.lower() == "image":
                        if isinstance(v, str):
                            out.append(v)
                        elif isinstance(v, list):
                            out.extend(x for x in v if isinstance(x, str))
                        elif isinstance(v, dict):
                            for kk in ("url", "contentUrl"):
                                if isinstance(v.get(kk), str):
                                    out.append(v[kk])
                    walk(v)
            elif isinstance(value, list):
                for x in value:
                    walk(x)

        walk(data)
    return out


def image_candidates(session: requests.Session, page_url: str, product: PohodaProduct) -> list[str]:
    response = session.get(page_url, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    candidates: list[str] = []

    for key in [
        ("property", "og:image"),
        ("property", "og:image:secure_url"),
        ("name", "twitter:image"),
        ("name", "twitter:image:src"),
    ]:
        tag = soup.find("meta", attrs={key[0]: key[1]})
        if tag and tag.get("content"):
            candidates.append(urljoin(page_url, html.unescape(tag["content"])))

    candidates.extend(urljoin(page_url, u) for u in _jsonld_images(soup))

    tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9]+", product.name) if len(t) >= 3]
    for img in soup.find_all("img"):
        src = img.get("data-src") or img.get("data-lazy-src") or img.get("src")
        if not src:
            continue
        full = urljoin(page_url, html.unescape(src))
        descriptor = " ".join([
            img.get("alt", ""),
            img.get("title", ""),
            img.get("class", [""])[0] if img.get("class") else "",
            src,
        ]).lower()
        score = sum(1 for t in tokens[:10] if t in descriptor)
        if score >= 2 or "product" in descriptor:
            candidates.append(full)

    unique: list[str] = []
    for u in candidates:
        if u.startswith("http") and u not in unique:
            unique.append(u)
    return unique


def _ext_from_response(response: requests.Response, url: str) -> str:
    ctype = response.headers.get("content-type", "").split(";")[0].lower()
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    if ctype in mapping:
        return mapping[ctype]
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp"} else ".jpg"


def safe_filename(code: str, name: str, ext: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")[:80]
    safe_code = re.sub(r"[^A-Za-z0-9_-]+", "_", code).strip("_")
    return f"{safe_code}__{slug}{ext}"


def try_download_image(
    session: requests.Session,
    image_url: str,
    product: PohodaProduct,
    image_dir: Path,
) -> Path | None:
    try:
        response = session.get(image_url, timeout=25, stream=True)
        response.raise_for_status()
        ctype = response.headers.get("content-type", "").lower()
        if not ctype.startswith("image/"):
            return None
        data = response.content
        if len(data) < 5000:
            return None
        ext = _ext_from_response(response, image_url)
        target = image_dir / safe_filename(product.code, product.name, ext)
        target.write_bytes(data)
        return target
    except requests.RequestException:
        return None


def download_product_image(
    session: requests.Session,
    product: PohodaProduct,
    image_dir: Path,
) -> ImageResult:
    official = OFFICIAL_DOMAINS.get(product.brand, [])

    # Fast path: direct image search. This also works when a product page blocks scraping.
    direct_images = search_direct_images(session, product)
    if direct_images:
        def image_score(url: str) -> tuple[int, int]:
            host = urlparse(url).netloc.lower().removeprefix("www.")
            return (1 if any(d in host for d in official) else 0, -len(url))

        for image_url in sorted(direct_images, key=image_score, reverse=True):
            saved = try_download_image(session, image_url, product, image_dir)
            if saved:
                return ImageResult(
                    code=product.code,
                    name=product.name,
                    brand=product.brand,
                    status="OK",
                    image_file=saved.name,
                    image_url=image_url,
                    source_page="Bing Images",
                )

    # Fallback: find a product page and extract og:image / JSON-LD / product image.
    pages = search_pages(session, product)

    def page_score(url: str) -> tuple[int, int]:
        host = urlparse(url).netloc.lower().removeprefix("www.")
        return (1 if any(d in host for d in official) else 0, -len(url))

    pages = sorted(pages, key=page_score, reverse=True)

    for page in pages:
        try:
            candidates = image_candidates(session, page, product)
        except requests.RequestException:
            continue
        for image_url in candidates[:8]:
            saved = try_download_image(session, image_url, product, image_dir)
            if saved:
                return ImageResult(
                    code=product.code,
                    name=product.name,
                    brand=product.brand,
                    status="OK",
                    image_file=saved.name,
                    image_url=image_url,
                    source_page=page,
                )
        time.sleep(0.25)

    return ImageResult(
        code=product.code,
        name=product.name,
        brand=product.brand,
        status="NENAJDENE",
        note="Nenasiel sa spolahlivy produktovy obrazok.",
    )


def run_downloader(
    xml_path: str | Path,
    out_dir: str | Path,
    missing_only: bool = True,
    limit: int | None = None,
) -> list[ImageResult]:
    out_dir = Path(out_dir)
    image_dir = out_dir / "obrazky"
    image_dir.mkdir(parents=True, exist_ok=True)

    products = read_pohoda_products(xml_path, missing_only=missing_only)
    if limit:
        products = products[:limit]

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "sk,en;q=0.8"})

    results: list[ImageResult] = []
    for index, product in enumerate(products, start=1):
        print(f"[{index}/{len(products)}] {product.code} - {product.name}")
        result = download_product_image(session, product, image_dir)
        results.append(result)

    mapping = out_dir / "parovanie_obrazkov.csv"
    with mapping.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["kod", "nazov", "znacka", "stav", "subor_obrazka", "url_obrazka", "zdrojova_stranka", "poznamka"])
        for r in results:
            writer.writerow([r.code, r.name, r.brand, r.status, r.image_file, r.image_url, r.source_page, r.note])

    return results
