"""Fuente: InfoJobs — scraping ligero de HTML server-renderizado.

InfoJobs no ofrece una API pública sencilla, pero sus páginas de resultados
de búsqueda (https://www.infojobs.net/ofertas-trabajo/{keyword}/{ciudad})
son HTML estático con toda la info necesaria (título, empresa, ubicación,
tipo de jornada, salario si lo hay), así que no hace falta navegador headless.

Esta búsqueda general ya saca ofertas de las marcas objetivo (Zara, Mango,
El Corte Inglés, Springfield, Koala Bay...) porque InfoJobs es donde la
mayoría de estas cadenas publican sus vacantes de tienda.
"""

import re
import time
import unicodedata

import requests
from bs4 import BeautifulSoup

from config_loader import all_search_keywords, load_config
from normalize import build_job

BASE_URL = "https://www.infojobs.net/ofertas-trabajo/{keyword}/{city}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
TIMEOUT = 20


def _slugify(text):
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    ascii_text = ascii_text.lower().strip()
    ascii_text = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return ascii_text


def _parse_listing(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    for card in soup.select("div.ij-OfferCardContent"):
        title_link = card.select_one("a.ij-OfferCardContent-description-link")
        if not title_link:
            continue
        title = title_link.get_text(strip=True)
        href = title_link.get("href", "")
        url = "https:" + href if href.startswith("//") else href
        url = url.split("?")[0]

        subtitle = card.select_one("h3.ij-OfferCardContent-description-subtitle a")
        if not subtitle:
            subtitle = card.select_one("h3.ij-OfferCardContent-description-subtitle")
        company = subtitle.get_text(strip=True) if subtitle else ""

        info_lists = card.select("ul.ij-OfferCardContent-description-list")
        location = ""
        extra_bits = []
        salary_raw = None
        if info_lists:
            first_items = [li.get_text(strip=True) for li in info_lists[0].find_all("li")]
            if first_items:
                location = first_items[0]
            extra_bits.extend(first_items)
        if len(info_lists) > 1:
            for li in info_lists[1].find_all("li"):
                text = li.get_text(strip=True)
                extra_bits.append(text)
                if "salario no disponible" not in text.lower() and re.search(r"\d", text):
                    salary_raw = text

        description_el = card.select_one("p.ij-OfferCardContent-description-description")
        description = description_el.get_text(" ", strip=True) if description_el else ""
        description = description + " " + " ".join(extra_bits)

        job = build_job(
            source="infojobs",
            title=title,
            company=company,
            url=url,
            city_raw=location,
            description=description,
            posted_date=None,
            salary_raw=salary_raw,
        )
        if job:
            jobs.append(job)

    return jobs


def fetch():
    cfg = load_config()
    keywords = all_search_keywords(cfg)
    city_slugs = cfg["sources"]["infojobs"]["city_slugs"]

    jobs = []
    for city_slug in city_slugs:
        for keyword in keywords:
            url = BASE_URL.format(keyword=_slugify(keyword), city=city_slug)
            try:
                resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
                resp.raise_for_status()
            except requests.RequestException:
                continue
            jobs.extend(_parse_listing(resp.text))
            time.sleep(1)

    return jobs
