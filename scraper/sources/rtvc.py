"""Fuente: RTVC (Radio Televisión Canaria) — scraping ligero de HTML estático.

La página "trabaja con nosotros" (https://rtvc.es/trabaja-con-nosotros/) no
tiene protección anti-bot y publica enlaces directos a cada proceso de
selección con un texto de enlace muy regular:

    "Redactor/a (TVPC 008/26)(Proceso Cerrado) -  Televisión Pública de
     Canarias, S.A./ Santa Cruz de Tenerife"

De ahí sacamos título, empresa y ciudad sin necesidad de abrir cada oferta.
Los procesos marcados "(Proceso Cerrado)" ya no aceptan candidaturas, así
que se descartan aquí mismo.
"""

import re

import requests
from bs4 import BeautifulSoup

from normalize import build_job

LIST_URL = "https://rtvc.es/trabaja-con-nosotros/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
TIMEOUT = 20

ENTRY_LINK_RE = re.compile(r"^https://rtvc\.es/oferta-de-empleo")


def _parse_entry_text(raw_text):
    text = " ".join(raw_text.split())
    if "proceso cerrado" in text.lower():
        return None

    title_match = re.match(r"^(.*?)\s*\(", text)
    title = title_match.group(1).strip() if title_match else text

    tail = text.split(" - ", 1)[1] if " - " in text else ""
    if "/" in tail:
        company, city = tail.rsplit("/", 1)
    else:
        company, city = tail, ""

    return {
        "title": title,
        "company": company.strip() or "RTVC",
        "city": city.strip(),
    }


def fetch():
    try:
        resp = requests.get(LIST_URL, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    jobs = []
    seen_urls = set()

    for link in soup.find_all("a", href=ENTRY_LINK_RE):
        url = link["href"].split("?")[0]
        if url in seen_urls:
            continue
        seen_urls.add(url)

        entry = _parse_entry_text(link.get_text(" "))
        if not entry:
            continue

        job = build_job(
            source="rtvc",
            title=entry["title"],
            company=entry["company"],
            url=url,
            city_raw=entry["city"],
        )
        if job:
            jobs.append(job)

    return jobs
