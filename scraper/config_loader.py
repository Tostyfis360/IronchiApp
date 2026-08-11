import functools
import pathlib

import yaml

CONFIG_PATH = pathlib.Path(__file__).parent / "config.yaml"


@functools.lru_cache(maxsize=1)
def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def all_search_keywords(cfg=None):
    """Términos de búsqueda de todas las categorías combinados, para las
    fuentes que consultan por palabra clave sin distinguir categoría
    (InfoJobs, Job Today, Indeed). La categorización real de cada oferta
    ocurre después, en normalize.build_job."""
    cfg = cfg or load_config()
    keywords = []
    for cat in cfg["categories"].values():
        keywords.extend(cat.get("search_keywords") or [])
    return keywords
