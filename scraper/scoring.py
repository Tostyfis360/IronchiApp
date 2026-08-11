"""Cálculo del score de relevancia de cada oferta (orden por defecto de la web)."""

from datetime import datetime, timezone

from dateutil import parser as date_parser

from config_loader import load_config


def _days_old(job):
    raw = job.get("posted_date") or job.get("first_seen_at")
    if not raw:
        return None
    try:
        dt = date_parser.parse(raw)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    return max(delta.total_seconds() / 86400, 0)


def compute_score(job):
    cfg = load_config()["scoring"]
    score = 0

    if job.get("brand_tier") == "priority":
        score += cfg["brand_priority"]

    contract = job.get("contract_type")
    if contract == "full":
        score += cfg["full_time"]
    elif contract == "part":
        score += cfg["part_time"]

    if job.get("city_match") == "exact":
        score += cfg["city_exact_match"]
    elif job.get("city_match") == "province":
        score += cfg["province_fallback_match"]

    # Las ofertas ya pasaron el filtro de palabras clave de moda/retail en
    # normalize.build_job, así que aquí sumamos un bonus fijo por relevancia.
    score += cfg["keyword_match"]

    days_old = _days_old(job)
    if days_old is not None:
        window = cfg["recency_days_for_zero_bonus"]
        fraction = max(0.0, 1 - (days_old / window)) if window else 0.0
        score += round(cfg["recency_max_bonus"] * fraction)

    return score


def score_jobs(jobs):
    for job in jobs:
        job["score"] = compute_score(job)
    return jobs
