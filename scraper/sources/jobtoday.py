"""Fuente: Job Today — sin API pública, pero sus páginas de búsqueda son
Next.js server-renderizado y llevan los resultados completos incrustados en
un <script id="__NEXT_DATA__"> como JSON, así que los leemos de ahí en vez
de parsear HTML (más simple y más robusto a cambios de diseño).

Best-effort: si Job Today cambia esta estructura interna, esta fuente
simplemente devuelve una lista vacía / lanza y run.py lo aísla.
"""

import json
import re
import time
import unicodedata
from datetime import datetime, timezone

import requests

from config_loader import all_search_keywords, load_config
from normalize import build_job

BASE_URL = "https://jobtoday.com/es/trabajos-{keyword}/{city}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
TIMEOUT = 20
NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S
)

EMPLOYMENT_TYPE_MAP = {
    "FULL_TIME": "full",
    "PART_TIME": "part",
}


def _slugify(text):
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    ascii_text = ascii_text.lower().strip()
    ascii_text = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return ascii_text


def _extract_items(html):
    match = NEXT_DATA_RE.search(html)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    sections = (
        data.get("props", {}).get("pageProps", {}).get("feed", {}).get("sections", [])
    )
    items = []
    for section in sections:
        if isinstance(section.get("items"), list):
            items.extend(section["items"])
    return items


def _parse_items(items):
    jobs = []
    for item in items:
        payload = item.get("payload")
        if not payload:
            continue
        title = payload.get("role")
        company = payload.get("companyName")
        path = payload.get("canonicalUrl")
        if not title or not path:
            continue
        url = "https://jobtoday.com" + path

        address_display = payload.get("addressInfo", {}).get("display", {})
        city_raw = address_display.get("city") or payload.get("address") or ""

        posted_date = None
        update_ms = payload.get("updateDate")
        if update_ms:
            try:
                posted_date = datetime.fromtimestamp(
                    update_ms / 1000, tz=timezone.utc
                ).isoformat(timespec="seconds")
            except (OSError, OverflowError, ValueError):
                posted_date = None

        contract_hint = EMPLOYMENT_TYPE_MAP.get(payload.get("employmentType"))

        job = build_job(
            source="jobtoday",
            title=title,
            company=company,
            url=url,
            city_raw=city_raw,
            description=payload.get("description") or "",
            posted_date=posted_date,
            salary_raw=None,
            contract_type_hint=contract_hint,
        )
        if job:
            jobs.append(job)
    return jobs


def fetch():
    cfg = load_config()
    keywords = all_search_keywords(cfg)
    city_slugs = ["la-laguna", "santa-cruz-de-tenerife"]

    jobs = []
    for city_slug in city_slugs:
        for keyword in keywords:
            url = BASE_URL.format(keyword=_slugify(keyword), city=city_slug)
            try:
                resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
                resp.raise_for_status()
            except requests.RequestException:
                continue
            items = _extract_items(resp.text)
            jobs.extend(_parse_items(items))
            time.sleep(1)

    return jobs
