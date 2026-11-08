"""Versões congeladas da base: data/versions/<versão>/{dataset.csv,manifest.json} e ponteiro current.json."""
import json
import os
from pathlib import Path
import shutil

KEEP = 2  # versão ativa + anterior


def data_dir():
    return Path(os.environ.get("DATA_DIR") or Path(__file__).resolve().parent.parent / "data")


def read_pointer(directory):
    try:
        return json.loads((Path(directory) / "current.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def active(directory):
    """(caminho do CSV, manifesto) da versão ativa, ou None se não houver base."""
    pointer = read_pointer(directory)
    if not pointer:
        return None
    folder = Path(directory) / "versions" / pointer["version"]
    try:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return folder / "dataset.csv", manifest


def activate(directory, version):
    """Troca atômica do ponteiro e poda das versões antigas."""
    directory = Path(directory)
    old = read_pointer(directory)
    pointer = {"version": version, "previous": old["version"] if old else None}
    tmp = directory / "current.json.tmp"
    tmp.write_text(json.dumps(pointer), encoding="utf-8")
    os.replace(tmp, directory / "current.json")
    keep = {version, pointer["previous"]}
    for folder in (directory / "versions").iterdir():
        if folder.is_dir() and folder.name not in keep:
            shutil.rmtree(folder, ignore_errors=True)
