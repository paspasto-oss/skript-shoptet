from __future__ import annotations

import csv
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from better_bing_image_downloader import Downloader

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

GENERIC_WORDS = {
    "zasobnikovy", "zasobnik", "ohrievac", "ohrievace", "vody", "elektricky",
    "elektricke", "zavesny", "stacionarny", "prietokovy", "pod", "nad",
    "umyvadlo", "wifi", "plus", "trend", "smart", "eu", "litrov", "liter",
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
        products.append(
            PohodaProduct(
                code=code,
                name=name,
                brand=infer_brand(name),
                has_picture=has_picture,
            )
        )
    return products


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().split(":")[0].removeprefix("www.")


def _host_matches(url: str, domains: list[str]) -> bool:
    host = _host(url)
    return any(host == d or host.endswith("." + d) for d in domains)


def _safe_part(value: str, max_len: int = 90) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return value[:max_len]


def _target_filename(product: PohodaProduct, source_path: Path) -> str:
    ext = source_path.suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"
    return f"{_safe_part(product.code, 40)}__{_safe_part(product.name)}{ext}"


def _distinctive_tokens(product: PohodaProduct) -> list[str]:
    tokens = [
        t.lower()
        for t in re.findall(r"[A-Za-z0-9]+", product.name)
        if len(t) >= 3 and t.lower() not in GENERIC_WORDS
    ]
    # first token is usually the brand; preserve model tokens after it
    return tokens[:10]


def _caption_matches(product: PohodaProduct, caption: str | None) -> bool:
    if not caption:
        return True
    text = caption.lower()
    code = product.code.lower()
    if len(code) >= 4 and code in text:
        return True
    tokens = _distinctive_tokens(product)
    if not tokens:
        return True
    matches = sum(1 for t in tokens if t in text)
    return matches >= min(3, max(2, len(tokens) // 2))


def _queries(product: PohodaProduct) -> list[tuple[str, str]]:
    domains = OFFICIAL_DOMAINS.get(product.brand, [])
    model_tokens = " ".join(_distinctive_tokens(product)[:6])
    if not model_tokens:
        model_tokens = product.name

    queries: list[tuple[str, str]] = []
    for domain in domains:
        queries.append((domain, f'site:{domain} "{product.code}" {model_tokens}'))
        queries.append((domain, f'site:{domain} "{product.name}"'))
    return queries


def _clean_temp_dir(path: Path) -> None:
    try:
        if path.exists():
            shutil.rmtree(path)
    except OSError:
        pass


def _try_engine(
    downloader: Downloader,
    product: PohodaProduct,
    domain: str,
    query: str,
    temp_root: Path,
    engine: str,
):
    run_root = temp_root / engine
    run_root.mkdir(parents=True, exist_ok=True)

    result = downloader.search(
        query=query,
        limit=5,
        output_dir=run_root,
        engine=engine,
        name="candidate",
        force_replace=True,
        timeout=30,
        verbose=False,
        image_filter="photo" if engine == "bing" else "",
        mkt="sk-SK" if engine == "bing" else "en-US",
        ddg_region="sk-sk",
        ddg_safe_search="moderate",
        min_dimension=250,
        max_workers=4,
    )

    for image in result.images:
        # Strict rule: the actual image must be hosted on the official domain.
        # This intentionally rejects unrelated search-engine results.
        if not _host_matches(image.source_url, [domain]):
            continue
        if not _caption_matches(product, image.caption):
            continue
        return image
    return None


def download_product_image(
    downloader: Downloader,
    product: PohodaProduct,
    image_dir: Path,
    temp_root: Path,
) -> ImageResult:
    domains = OFFICIAL_DOMAINS.get(product.brand, [])
    if not domains:
        return ImageResult(
            code=product.code,
            name=product.name,
            brand=product.brand,
            status="NENAJDENE",
            note="Pre znacku nie je nastavena oficialna domena; nic sa nestiahlo.",
        )

    product_temp = temp_root / _safe_part(product.code, 50)
    _clean_temp_dir(product_temp)
    product_temp.mkdir(parents=True, exist_ok=True)

    try:
        for domain, query in _queries(product):
            for engine in ("bing", "duckduckgo"):
                try:
                    image = _try_engine(
                        downloader=downloader,
                        product=product,
                        domain=domain,
                        query=query,
                        temp_root=product_temp,
                        engine=engine,
                    )
                except Exception:
                    image = None

                if image is None:
                    continue

                target = image_dir / _target_filename(product, Path(image.path))
                shutil.copy2(image.path, target)
                return ImageResult(
                    code=product.code,
                    name=product.name,
                    brand=product.brand,
                    status="OK",
                    image_file=target.name,
                    image_url=image.source_url,
                    source_page=domain,
                    note=f"Overene cez {engine}; oficialna domena {domain}.",
                )

        return ImageResult(
            code=product.code,
            name=product.name,
            brand=product.brand,
            status="NENAJDENE",
            note="Na oficialnych domenach vyrobcu sa nenasiel spolahlivy obrazok.",
        )
    finally:
        _clean_temp_dir(product_temp)


def run_downloader(
    xml_path: str | Path,
    out_dir: str | Path,
    missing_only: bool = True,
    limit: int | None = None,
) -> list[ImageResult]:
    out_dir = Path(out_dir)
    image_dir = out_dir / "obrazky"
    temp_root = out_dir / "_tmp_candidates"
    image_dir.mkdir(parents=True, exist_ok=True)
    temp_root.mkdir(parents=True, exist_ok=True)

    products = read_pohoda_products(xml_path, missing_only=missing_only)
    if limit:
        products = products[:limit]

    downloader = Downloader()
    results: list[ImageResult] = []

    for index, product in enumerate(products, start=1):
        print(f"[{index}/{len(products)}] {product.code} - {product.name}")
        results.append(
            download_product_image(
                downloader=downloader,
                product=product,
                image_dir=image_dir,
                temp_root=temp_root,
            )
        )

    _clean_temp_dir(temp_root)

    mapping = out_dir / "parovanie_obrazkov.csv"
    with mapping.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(
            [
                "kod",
                "nazov",
                "znacka",
                "stav",
                "subor_obrazka",
                "url_obrazka",
                "oficialna_domena",
                "poznamka",
            ]
        )
        for result in results:
            writer.writerow(
                [
                    result.code,
                    result.name,
                    result.brand,
                    result.status,
                    result.image_file,
                    result.image_url,
                    result.source_page,
                    result.note,
                ]
            )

    return results
