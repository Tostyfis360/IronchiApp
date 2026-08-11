"""Orquesta la ejecución completa: llama a cada fuente (aislando errores),
normaliza, puntúa, deduplica, fusiona con lo anterior y escribe
docs/data/jobs.json + docs/data/status.json.
"""

import json
import pathlib
import sys
import traceback
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from config_loader import load_config  # noqa: E402
from dedupe import dedupe  # noqa: E402
from merge_store import merge, save  # noqa: E402
from scoring import score_jobs  # noqa: E402
from sources import indeed, infojobs, jobtoday, jooble, mango_workday  # noqa: E402
from sources.jooble import JoobleNotConfigured  # noqa: E402

STATUS_PATH = pathlib.Path(__file__).parent.parent / "docs" / "data" / "status.json"

SOURCES = {
    "jooble": jooble,
    "infojobs": infojobs,
    "jobtoday": jobtoday,
    "indeed": indeed,
    "mango": mango_workday,
}


def run():
    cfg = load_config()
    all_jobs = []
    status = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": {},
    }

    for name, module in SOURCES.items():
        source_cfg = cfg.get("sources", {}).get(
            name if name != "mango" else "mango_workday", {}
        )
        if not source_cfg.get("enabled", True):
            status["sources"][name] = {"ok": None, "count": 0, "note": "deshabilitada"}
            continue

        try:
            jobs = module.fetch()
            all_jobs.extend(jobs)
            status["sources"][name] = {"ok": True, "count": len(jobs)}
        except JoobleNotConfigured:
            status["sources"][name] = {
                "ok": None,
                "count": 0,
                "note": "JOOBLE_API_KEY no configurada (ver README)",
            }
        except Exception as exc:  # noqa: BLE001 - aislamos cualquier fallo de fuente
            traceback.print_exc()
            status["sources"][name] = {
                "ok": False,
                "count": 0,
                "error": f"{type(exc).__name__}: {exc}",
            }

    scored = score_jobs(all_jobs)
    deduped = dedupe(scored)
    final_jobs = merge(deduped, max_missed_runs=cfg["expiry"]["max_missed_runs"])
    final_jobs.sort(key=lambda j: j["score"], reverse=True)

    save(final_jobs)

    status["total_jobs"] = len(final_jobs)
    status["new_jobs"] = sum(1 for j in final_jobs if j.get("is_new"))
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
