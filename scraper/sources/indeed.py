"""Fuente: Indeed — best-effort, prioridad baja.

Indeed bloquea agresivamente el scraping (Cloudflare, robots.txt, ToS) y en
la práctica suele devolver 403 incluso en la primera petición. Se intenta de
todas formas por si la IP del runner de turno no está bloqueada ese día, pero
no merece la pena invertir en mantenerlo fino: si falla (403, captcha, cambio
de HTML), simplemente no aporta resultados esa ejecución y el resto del
pipeline sigue con normalidad.
"""

import time
import unicodedata

import requests
from bs4 import BeautifulSoup

from config_loader import load_config
from normalize import build_job

BASE_URL = "https://es.indeed.com/jobs"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
}
TIMEOUT = 20


class IndeedBlocked(Exception):
    pass


def _clean(text):
    return unicodedata.normalize("NFKC", text).strip() if text else ""


def _parse_listing(html):
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    for card in soup.select("div.job_seen_beacon, td.resultContent"):
        title_el = card.select_one("h2.jobTitle a, h2.jobTitle span")
        if not title_el:
            continue
        title = _clean(title_el.get_text())

        link_el = card.select_one("h2.jobTitle a")
        href = link_el.get("href") if link_el else None
        if not href:
            continue
        url = href if href.startswith("http") else "https://es.indeed.com" + href

        company_el = card.select_one("span.companyName")
        company = _clean(company_el.get_text()) if company_el else ""

        location_el = card.select_one("div.companyLocation")
        location = _clean(location_el.get_text()) if location_el else ""

        snippet_el = card.select_one("div.job-snippet")
        description = _clean(snippet_el.get_text(" ")) if snippet_el else ""

        job = build_job(
            source="indeed",
            title=title,
            company=company,
            url=url,
            city_raw=location,
            description=description,
        )
        if job:
            jobs.append(job)
    return jobs


def fetch():
    cfg = load_config()
    keywords = cfg["search"]["keywords"]
    cities = [c["name"] for c in cfg["search"]["cities"]]

    jobs = []
    any_request_ok = False
    for city in cities:
        for keyword in keywords:
            params = {"q": keyword, "l": city}
            try:
                resp = requests.get(
                    BASE_URL, params=params, headers=HEADERS, timeout=TIMEOUT
                )
                if resp.status_code != 200:
                    continue
                any_request_ok = True
            except requests.RequestException:
                continue
            jobs.extend(_parse_listing(resp.text))
            time.sleep(1.5)

    if not any_request_ok:
        raise IndeedBlocked("Indeed bloqueó todas las peticiones (403/anti-bot).")

    return jobs
