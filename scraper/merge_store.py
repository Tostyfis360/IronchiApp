"""Fusiona el resultado de una ejecución con el dataset persistido en
docs/data/jobs.json: conserva first_seen_at, marca ofertas nuevas, y retira
las que llevan demasiadas ejecuciones seguidas sin aparecer.
"""

import json
import pathlib

DATA_PATH = pathlib.Path(__file__).parent.parent / "docs" / "data" / "jobs.json"


def load_previous():
    if not DATA_PATH.exists():
        return []
    try:
        with open(DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def merge(current_jobs, max_missed_runs=3):
    previous_by_id = {job["id"]: job for job in load_previous()}
    current_ids = {job["id"] for job in current_jobs}

    merged = []
    for job in current_jobs:
        prev = previous_by_id.get(job["id"])
        if prev:
            job["first_seen_at"] = prev.get("first_seen_at", job["first_seen_at"])
            job["is_new"] = False
        else:
            job["is_new"] = True
        job["missed_runs"] = 0
        merged.append(job)

    for job_id, prev_job in previous_by_id.items():
        if job_id in current_ids:
            continue
        missed_runs = prev_job.get("missed_runs", 0) + 1
        if missed_runs > max_missed_runs:
            continue
        prev_job["missed_runs"] = missed_runs
        prev_job["is_new"] = False
        merged.append(prev_job)

    return merged


def save(jobs):
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
