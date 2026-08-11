"""Esquema común de oferta y heurísticas de detección (ciudad, marca, jornada).

Cada source module produce jobs pasando por build_job(); si la oferta no
encaja con la zona objetivo o no parece un puesto de moda/retail, se descarta
aquí mismo para que los sources no tengan que reimplementar el filtrado.
"""

import hashlib
import unicodedata
from datetime import datetime, timezone

from config_loader import load_config


def strip_accents(text):
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize_text(text):
    return strip_accents(text or "").lower()


def _haystack(*texts):
    return normalize_text(" ".join(t for t in texts if t))


def detect_city(*texts):
    cfg = load_config()
    haystack = _haystack(*texts)
    for city in cfg["search"]["cities"]:
        for alias in city["aliases"]:
            if normalize_text(alias) in haystack:
                return city["name"], "exact"
    for alias in cfg["search"]["province_fallback_aliases"]:
        if normalize_text(alias) in haystack:
            return "Tenerife", "province"
    return None, None


def detect_contract_type(*texts):
    cfg = load_config()
    haystack = _haystack(*texts)
    for pattern in cfg["contract_type"]["part_time_patterns"]:
        if normalize_text(pattern) in haystack:
            return "part"
    for pattern in cfg["contract_type"]["full_time_patterns"]:
        if normalize_text(pattern) in haystack:
            return "full"
    return "unknown"


def detect_brand(*texts):
    cfg = load_config()
    haystack = _haystack(*texts)
    for brand in cfg["brands"]["excluded"]:
        if normalize_text(brand) in haystack:
            return brand, "excluded"
    for brand in cfg["brands"]["priority"]:
        if normalize_text(brand) in haystack:
            return brand, "priority"
    return None, "normal"


def matches_fashion_keywords(*texts):
    cfg = load_config()
    haystack = _haystack(*texts)
    return any(normalize_text(k) in haystack for k in cfg["fashion_keywords"])


def make_job_id(source, url, title, company):
    basis = url or f"{source}:{title}:{company}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_job(*, source, title, company, url, city_raw=None, description="",
              posted_date=None, salary_raw=None, contract_type_hint=None):
    """Normaliza una oferta cruda de cualquier fuente. Devuelve None si hay
    que descartarla (marca excluida, fuera de zona, o no parece moda/retail).
    """
    title = (title or "").strip()
    company = (company or "").strip()
    if not title or not url:
        return None

    texts = [title, company, city_raw or "", description or ""]

    brand_name, brand_tier = detect_brand(*texts)
    if brand_tier == "excluded":
        return None

    city, city_match = detect_city(*texts)
    if city is None:
        return None

    # Si la empresa ya es una marca de moda conocida, nos fiamos de la
    # curación de config.yaml. Si no, exigimos una señal explícita de moda
    # para no colar dependientes de supermercado, kioscos, etc.
    if brand_tier != "priority" and not matches_fashion_keywords(*texts):
        return None

    contract_type = contract_type_hint or detect_contract_type(*texts)
    timestamp = now_iso()

    return {
        "id": make_job_id(source, url, title, company),
        "title": title,
        "company": company or brand_name or "Empresa sin especificar",
        "brand_name": brand_name,
        "brand_tier": brand_tier,
        "city": city,
        "city_match": city_match,
        "location_raw": city_raw or "",
        "contract_type": contract_type,
        "salary_raw": salary_raw,
        "source": source,
        "url": url,
        "posted_date": posted_date,
        "first_seen_at": timestamp,
        "last_seen_at": timestamp,
        "missed_runs": 0,
        "score": 0,
    }
