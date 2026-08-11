"""Fuente: Jooble — API REST oficial y gratuita.

Requiere una API key gratuita solicitada en https://es.jooble.org/api/about,
guardada como variable de entorno / secret de GitHub Actions JOOBLE_API_KEY.
Si no hay key configurada, esta fuente simplemente se omite (no es un error).
"""

import os
import time

import requests

from config_loader import load_config
from normalize import build_job

API_URL_TEMPLATE = "https://jooble.org/api/{key}"
TIMEOUT = 20
MAX_CALLS = 10  # tope de llamadas por ejecución para no abusar de la API gratuita


class JoobleNotConfigured(Exception):
    pass


def fetch():
    api_key = os.environ.get("JOOBLE_API_KEY", "").strip()
    if not api_key:
        raise JoobleNotConfigured("JOOBLE_API_KEY no está configurada; se omite Jooble.")

    cfg = load_config()
    keywords = cfg["search"]["keywords"]
    cities = [c["name"] for c in cfg["search"]["cities"]]

    url = API_URL_TEMPLATE.format(key=api_key)
    jobs = []
    calls = 0

    for city in cities:
        for keyword in keywords:
            if calls >= MAX_CALLS:
                break
            calls += 1
            payload = {"keywords": keyword, "location": city}
            try:
                resp = requests.post(url, json=payload, timeout=TIMEOUT)
                resp.raise_for_status()
            except requests.RequestException:
                continue
            data = resp.json()
            for raw in data.get("jobs", []):
                job = build_job(
                    source="jooble",
                    title=raw.get("title"),
                    company=raw.get("company"),
                    url=raw.get("link"),
                    city_raw=raw.get("location"),
                    description=raw.get("snippet"),
                    posted_date=raw.get("updated"),
                    salary_raw=raw.get("salary") or None,
                )
                if job:
                    jobs.append(job)
            time.sleep(0.5)

    return jobs
