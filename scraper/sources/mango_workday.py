"""Fuente: Mango — endpoint JSON de Workday (no autenticado).

Mango publica sus vacantes en un portal Workday (mango.wd3.myworkdayjobs.com).
Estos portales exponen un endpoint JSON no autenticado que usa su propio
frontend para listar ofertas (POST a /wday/cxs/{tenant}/{site}/jobs). Es
mucho más fiable que renderizar la SPA con un navegador, y nos da el tipo de
jornada (timeType) de forma directa en vez de tener que adivinarlo del texto.
"""

import requests

from normalize import build_job

TENANT = "mango"
SITE = "Mango_Work_Your_Passion"
API_URL = f"https://mango.wd3.myworkdayjobs.com/wday/cxs/{TENANT}/{SITE}/jobs"
JOB_BASE_URL = f"https://mango.wd3.myworkdayjobs.com/es/{SITE}"
TIMEOUT = 20
PAGE_SIZE = 20
MAX_RESULTS = 100

TIME_TYPE_MAP = {
    "Full time": "full",
    "Part time": "part",
}


def fetch():
    jobs = []
    offset = 0

    while offset < MAX_RESULTS:
        payload = {
            "appliedFacets": {},
            "limit": PAGE_SIZE,
            "offset": offset,
            "searchText": "Tenerife",
        }
        try:
            resp = requests.post(API_URL, json=payload, timeout=TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException:
            break

        data = resp.json()
        postings = data.get("jobPostings", [])
        if not postings:
            break

        for posting in postings:
            title = posting.get("title")
            external_path = posting.get("externalPath")
            if not title or not external_path:
                continue
            url = JOB_BASE_URL + external_path
            bullets = posting.get("bulletFields") or []
            city_raw = bullets[0] if bullets else ""
            contract_hint = TIME_TYPE_MAP.get(posting.get("timeType"))

            job = build_job(
                source="mango",
                title=title,
                company="Mango",
                url=url,
                city_raw=city_raw,
                description="",
                contract_type_hint=contract_hint,
            )
            if job:
                jobs.append(job)

        offset += PAGE_SIZE
        if offset >= data.get("total", 0):
            break

    return jobs
