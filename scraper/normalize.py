"""Esquema común de oferta y heurísticas de detección (ciudad, categoría,
marca, jornada).

Cada source module produce jobs pasando por build_job(); si la oferta no
encaja con la zona objetivo o no parece relevante para ninguna categoría
configurada (ver config.yaml -> categories), se descarta aquí mismo para que
los sources no tengan que reimplementar el filtrado.
"""

import hashlib
import re
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


def _contains_term(haystack, term):
    """Busca `term` en `haystack` como palabra/frase completa, no como
    subcadena suelta (para que "Levis" no salte dentro de "televisión", por
    ejemplo)."""
    needle = normalize_text(term)
    if not needle:
        return False
    return re.search(r"\b" + re.escape(needle) + r"\b", haystack) is not None


def detect_city(*texts):
    cfg = load_config()
    haystack = _haystack(*texts)
    for city in cfg["search"]["cities"]:
        for alias in city["aliases"]:
            if _contains_term(haystack, alias):
                return city["name"], "exact"
    for alias in cfg["search"]["province_fallback_aliases"]:
        if _contains_term(haystack, alias):
            return "Tenerife", "province"
    return None, None


def detect_contract_type(*texts):
    cfg = load_config()
    haystack = _haystack(*texts)
    for pattern in cfg["contract_type"]["part_time_patterns"]:
        if _contains_term(haystack, pattern):
            return "part"
    for pattern in cfg["contract_type"]["full_time_patterns"]:
        if _contains_term(haystack, pattern):
            return "full"
    return "unknown"


def detect_category(*texts):
    """Decide a qué categoría (ver config.yaml -> categories) pertenece una
    oferta, si a alguna.

    Devuelve (category_key, brand_name, brand_tier):
    - brand_tier == "excluded": la oferta menciona una marca excluida de
      alguna categoría y debe descartarse siempre, sin importar lo demás.
    - brand_tier == "priority": coincide con una empresa/marca curada de esa
      categoría (category_key, brand_name rellenos).
    - brand_tier == "normal": no hay marca reconocida, pero sí una palabra
      señal de esa categoría (category_key relleno, brand_name None).
    - category_key is None: no encaja con ninguna categoría configurada.
    """
    cfg = load_config()
    haystack = _haystack(*texts)
    categories = cfg["categories"]

    for cat_key, cat in categories.items():
        for brand in cat.get("excluded_brands") or []:
            if _contains_term(haystack, brand):
                return None, brand, "excluded"

    for cat_key, cat in categories.items():
        for brand in cat.get("priority_brands") or []:
            if _contains_term(haystack, brand):
                return cat_key, brand, "priority"

    for cat_key, cat in categories.items():
        for keyword in cat.get("signal_keywords") or []:
            if _contains_term(haystack, keyword):
                return cat_key, None, "normal"

    return None, None, "none"


def make_job_id(source, url, title, company):
    basis = url or f"{source}:{title}:{company}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_job(*, source, title, company, url, city_raw=None, description="",
              posted_date=None, salary_raw=None, contract_type_hint=None):
    """Normaliza una oferta cruda de cualquier fuente. Devuelve None si hay
    que descartarla (marca excluida, fuera de zona, o no encaja con ninguna
    categoría configurada).
    """
    title = (title or "").strip()
    company = (company or "").strip()
    if not title or not url:
        return None

    texts = [title, company, city_raw or "", description or ""]

    category, brand_name, brand_tier = detect_category(*texts)
    if brand_tier == "excluded" or category is None:
        return None

    city, city_match = detect_city(*texts)
    if city is None:
        return None

    contract_type = contract_type_hint or detect_contract_type(*texts)
    timestamp = now_iso()
    cfg = load_config()
    category_label = cfg["categories"].get(category, {}).get("label", category)

    return {
        "id": make_job_id(source, url, title, company),
        "title": title,
        "company": company or brand_name or "Empresa sin especificar",
        "brand_name": brand_name,
        "brand_tier": brand_tier,
        "category": category,
        "category_label": category_label,
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
