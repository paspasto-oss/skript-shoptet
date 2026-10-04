from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import requests

NS = {
    "lStk": "http://www.stormware.cz/schema/version_2/list_stock.xsd",
    "stk": "http://www.stormware.cz/schema/version_2/stock.xsd",
}

APIFY_ACTOR_SYNC = "https://api.apify.com/v2/acts/searchapi~google-images-scraper/run-sync-get-dataset-items"

OFFICIAL_DOMAINS = {
    "VAILLANT": ["vaillant.sk", "vaillant.com"],
    "STIEBEL ELTRON": ["stiebel-eltron.sk", "stiebel-eltron.com"],
    "ARISTON": ["ariston.com"],
    "DRAŽICE": ["dzd.cz", "drazice.cz"],
    "DRAZICE": ["dzd.cz", "drazice.cz"],
    "CLAGE": ["clage.com"],
    "HAKL": ["hakl.sk"],
    "MORA": ["mora.sk", "mora.cz"],
    "TESY": ["tesy.com"],
    "CONCEPT": ["my-concept.sk", "my-concept.cz"],
}

GENERIC_WORDS = {
    "zasobnikovy", "zasobnik", "ohrievac", "ohrievace", "vody", "elektricky",
    "elektricke", "zavesny", "stacionarny", "prietokovy", "pod", "nad",
    "umyvadlo", "wifi", "plus", "trend", "smart", "eu", "litrov", "liter",
    "beztlakovy", "elektricky", "ohrievac",
}


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
        products.append(PohodaProduct(code, name, infer_brand(name), has_picture))
    return products


def _host_matches(host: str, domains: list[str]) -> bool:
    host = (host or "").lower().split(":")[0].removeprefix("www.")
    return any(host == d or host.endswith("." + d) for d in domains)


def _safe_part(value: str, max_len: int = 90) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return value[:max_len]


def _distinctive_tokens(product: PohodaProduct) -> list[str]:
    return [
        t.lower()
        for t in re.findall(r"[A-Za-z0-9]+", product.name)
        if len(t) >= 3 and t.lower() not in GENERIC_WORDS
    ][:10]


def _query_for(product: PohodaProduct) -> str:
    domains = OFFICIAL_DOMAINS.get(product.brand, [])
    model = " ".join(_distinctive_tokens(product)[:7]) or product.name
    if domains:
        return f'{product.code} {model} site:{domains[0]}'
    return f'{product.code} {model}'


def _score_candidate(product: PohodaProduct, item: dict) -> tuple[int, int, int, int]:
    domains = OFFICIAL_DOMAINS.get(product.brand, [])
    host = (
        item.get("hostPageDomain")
        or item.get("sourceDomain")
        or item.get("domain")
        or ""
    )
    official = 1 if domains and _host_matches(host, domains) else 0

    text = " ".join(
        [
            str(item.get("title") or ""),
            str(item.get("altText") or ""),
            str(item.get("sourceName") or ""),
        ]
    ).lower()
    code_match = 1 if product.code.lower() in text else 0
    token_matches = sum(1 for t in _distinctive_tokens(product) if t in text)
    pixels = int(item.get("sizePixels") or 0)
    if not pixels:
        pixels = int(item.get("width") or 0) * int(item.get("height") or 0)
    return (official, code_match, token_matches, pixels)


def _download_image(url: str, target_base: Path) -> Path:
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=40, allow_redirects=True)
    r.raise_for_status()
    ctype = (r.headers.get("content-type") or "").lower()
    if not ctype.startswith("image/"):
        raise RuntimeError("Odpoved nie je obrazok.")

    ext = ".jpg"
    if "png" in ctype:
        ext = ".png"
    elif "webp" in ctype:
        ext = ".webp"
    elif "jpeg" in ctype or "jpg" in ctype:
        ext = ".jpg"

    target = target_base.with_suffix(ext)
    target.write_bytes(r.content)
    return target


def _chunks(items: list[PohodaProduct], size: int = 20):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _run_apify_batch(api_token: str, batch: list[PohodaProduct], results_per_query: int = 5) -> list[dict]:
    queries = [_query_for(p) for p in batch]
    payload = {
        "mode": "batch",
        "queries": queries,
        "maxItems": max(1, len(queries) * results_per_query),
        "maxConcurrency": 2,
        "imageSize": "large",
        "imageType": "photo",
        "safeSearch": "active",
    }
    response = requests.post(
        APIFY_ACTOR_SYNC,
        params={"token": api_token},
        json=payload,
        timeout=300,
    )
    if response.status_code in (401, 403):
        raise RuntimeError("Apify API token nie je platny alebo nema pristup.")
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise RuntimeError("Apify vratilo necakany format odpovede.")
    return data


def run_downloader(
    xml_path: str | Path,
    out_dir: str | Path,
    missing_only: bool = True,
    limit: int | None = None,
    api_token: str | None = None,
) -> list[ImageResult]:
    if not api_token:
        raise RuntimeError("Zadaj Apify API token.")

    out_dir = Path(out_dir)
    image_dir = out_dir / "obrazky"
    image_dir.mkdir(parents=True, exist_ok=True)

    products = read_pohoda_products(xml_path, missing_only=missing_only)
    if limit:
        products = products[:limit]

    all_results: list[ImageResult] = []
    query_to_product = {_query_for(p): p for p in products}
    grouped_candidates: dict[str, list[dict]] = {q: [] for q in query_to_product}

    for batch in _chunks(products, 20):
        items = _run_apify_batch(api_token, batch, results_per_query=5)
        for item in items:
            q = item.get("query") or item.get("searchQuery")
            if q in grouped_candidates:
                grouped_candidates[q].append(item)

    for product in products:
        query = _query_for(product)
        candidates = grouped_candidates.get(query, [])
        if not candidates:
            all_results.append(
                ImageResult(
                    product.code,
                    product.name,
                    product.brand,
                    "NENAJDENE",
                    note="Apify nenaslo ziadny kandidat.",
                )
            )
            continue

        domains = OFFICIAL_DOMAINS.get(product.brand, [])
        ranked = sorted(candidates, key=lambda x: _score_candidate(product, x), reverse=True)

        chosen = None
        for item in ranked:
            host = (
                item.get("hostPageDomain")
                or item.get("sourceDomain")
                or item.get("domain")
                or ""
            )
            if domains and not _host_matches(host, domains):
                continue
            image_url = item.get("imageUrl") or item.get("originalUrl") or item.get("url")
            if not image_url:
                continue
            chosen = item
            break

        if chosen is None:
            all_results.append(
                ImageResult(
                    product.code,
                    product.name,
                    product.brand,
                    "NENAJDENE",
                    note="Nasli sa kandidati, ale nie z oficialnej domeny vyrobcu.",
                )
            )
            continue

        image_url = chosen.get("imageUrl") or chosen.get("originalUrl") or chosen.get("url")
        host_page = chosen.get("hostPageUrl") or chosen.get("sourceUrl") or ""
        try:
            target = _download_image(
                image_url,
                image_dir / f"{_safe_part(product.code, 40)}__{_safe_part(product.name)}",
            )
            all_results.append(
                ImageResult(
                    product.code,
                    product.name,
                    product.brand,
                    "OK",
                    target.name,
                    image_url,
                    host_page,
                    f"Apify Google Images; zdroj {chosen.get('hostPageDomain') or chosen.get('sourceDomain') or ''}",
                )
            )
        except Exception as exc:
            all_results.append(
                ImageResult(
                    product.code,
                    product.name,
                    product.brand,
                    "CHYBA_STIAHNUTIA",
                    image_url=image_url,
                    source_page=host_page,
                    note=str(exc),
                )
            )

    mapping = out_dir / "parovanie_obrazkov.csv"
    with mapping.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([
            "kod", "nazov", "znacka", "stav", "subor_obrazka",
            "url_obrazka", "zdrojova_stranka", "poznamka"
        ])
        for r in all_results:
            writer.writerow([
                r.code, r.name, r.brand, r.status, r.image_file,
                r.image_url, r.source_page, r.note
            ])

    return all_results
