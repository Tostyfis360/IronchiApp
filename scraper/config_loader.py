import functools
import pathlib

import yaml

CONFIG_PATH = pathlib.Path(__file__).parent / "config.yaml"


@functools.lru_cache(maxsize=1)
def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)
