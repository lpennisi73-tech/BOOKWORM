"""
Préférences de l'utilisateur (config_dir()/settings.json)

    settings.get("compile.distcc_hosts", "")
    settings.update({"compile.distcc": True})

Stockage à plat (clés pointées), relu à chaque appel : le fichier est petit.
Une préférence illisible ou absente ne doit jamais empêcher l'application de tourner.
"""

import json
import logging

from utils import paths

log = logging.getLogger(__name__)


def _file():
    return paths.config_dir() / "settings.json"


def load():
    try:
        data = json.loads(_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get(key, default=None):
    """Valeur enregistrée, ou default si elle est absente ou d'un autre type que default"""
    value = load().get(key, default)
    if default is not None and not isinstance(value, type(default)):
        return default
    return value


def update(values):
    """Enregistre plusieurs préférences (écriture atomique)"""
    data = load()
    data.update(values)
    try:
        path = _file()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
    except OSError as e:
        log.warning(f"Unable to save settings: {e}")
