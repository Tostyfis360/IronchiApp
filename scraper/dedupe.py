"""Deduplicación aproximada de ofertas vistas en varias fuentes a la vez."""

from collections import defaultdict

from rapidfuzz import fuzz

from normalize import normalize_text

# Orden de preferencia cuando dos fuentes traen "la misma" oferta: nos
# quedamos con la de la fuente más arriba en esta lista (más autorial/fiable).
SOURCE_PRIORITY = ["mango", "infojobs", "jooble", "jobtoday", "indeed"]

SIMILARITY_THRESHOLD = 88


def _priority(job):
    try:
        return SOURCE_PRIORITY.index(job["source"])
    except ValueError:
        return len(SOURCE_PRIORITY)


def _key_text(job):
    return normalize_text(f"{job['title']} {job['company']}")


def dedupe(jobs):
    buckets = defaultdict(list)
    for job in jobs:
        buckets[job["city"]].append(job)

    result = []
    for group in buckets.values():
        kept_jobs = []
        kept_texts = []
        for job in sorted(group, key=_priority):
            text = _key_text(job)
            if any(
                fuzz.token_sort_ratio(text, kept) >= SIMILARITY_THRESHOLD
                for kept in kept_texts
            ):
                continue
            kept_jobs.append(job)
            kept_texts.append(text)
        result.extend(kept_jobs)

    return result
