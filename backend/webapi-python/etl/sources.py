"""Leitura do SIH/SUS (RD) via PySUS. PySUS e pandas só são importados aqui, sob demanda.

Cada arquivo UF×ano×mês vira um agregado pequeno em cache (JSON). O arquivo bruto não
precisa ser mantido; o cache de agregados é o que torna a atualização incremental.
"""
import json
import logging
import time
from collections import Counter
from pathlib import Path

from .transform import DIAG_FIELDS, REQUIRED_FIELDS, UF_BY_CODE, aggregate

log = logging.getLogger(__name__)

GROUP = "RD"
REFRESH_MONTHS = 6  # meses mais recentes são rebaixados na atualização (o SIH reprocessa)
UFS = sorted(UF_BY_CODE.values())
FILE_FIELDS = REQUIRED_FIELDS + ("COD_IDADE",) + DIAG_FIELDS


def expected_files(years):
    return [(uf, year, month) for year in years for month in range(1, 13) for uf in UFS]


def agg_path(cache_dir, uf, year, month):
    return Path(cache_dir) / "agg" / f"RD{uf}{year % 100:02d}{month:02d}.json"


class Records(list):
    """Registros relevantes de um arquivo, com o total de linhas lidas (`total_rows`)."""
    total_rows = None


def read_month(uf, year, month, cache_dir):
    """Baixa um arquivo RD e devolve os registros relevantes (pré-filtrados em pandas)."""
    import pysus  # noqa: PLC0415

    pysus.set_cache(Path(cache_dir) / "raw")
    started = time.time()
    frame = pysus.sih(state=uf, year=year, month=month, group=GROUP, as_dataframe=True)
    if frame is None or len(frame) == 0:
        # Um arquivo RD de UF×mês nunca é vazio de verdade: tratar como zero envenenaria o cache.
        raise RuntimeError(f"Arquivo RD{uf}{year % 100:02d}{month:02d} veio vazio ou ausente do PySUS "
                           "(não foi gravado no cache; tente novamente).")
    total_rows = len(frame)
    columns = [c for c in FILE_FIELDS if c in frame.columns]
    frame = frame[columns].astype(str)
    mask = None
    for field in DIAG_FIELDS:
        if field in frame.columns:
            hit = frame[field].str.strip().str.upper().str.match(r"^W(0\d|1\d)")
            mask = hit if mask is None else mask | hit
    if mask is None:
        raise RuntimeError(f"Arquivo RD{uf}{year}{month:02d} sem campos de diagnóstico.")
    normal = frame["IDENT"].str.strip() == "1"
    principal = (frame["DIAG_PRINC"].str.strip().str.upper().str.match(r"^W(0\d|1\d)")
                 if "DIAG_PRINC" in frame.columns else None)
    log.info("RD%s%02d%02d: linhas=%d | queda em qualquer diagnóstico=%d (só principal=%s) | "
             "destas IDENT=1=%d, IDENT!=1=%d | colunas ausentes=%s | %.1fs",
             uf, year % 100, month, total_rows, int(mask.sum()),
             "n/d" if principal is None else int(principal.sum()),
             int((mask & normal).sum()), int((mask & ~normal).sum()),
             sorted(set(FILE_FIELDS) - set(columns)), time.time() - started)
    records = Records(frame[mask & normal].to_dict("records"))
    records.total_rows = total_rows
    return records


def load_month(uf, year, month, cache_dir, refresh=False, fetch=read_month):
    """Agregado do arquivo, do cache ou baixado. Retorna (cells, excluded, baixou)."""
    path = agg_path(cache_dir, uf, year, month)
    if path.exists() and not refresh:
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved["cells"] or saved.get("rows"):
            return decode(saved), saved["excluded"], False
        # Agregado vazio sem contagem de linhas: gravado por versão antiga que tratava arquivo vazio
        # como zero. Baixa de novo em vez de confiar no zero.
        log.warning("RD%s%02d%02d: agregado vazio suspeito no cache; baixando novamente", uf, year % 100, month)
    records = fetch(uf, year, month, cache_dir)
    cells, excluded = aggregate(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(encode(cells, excluded, getattr(records, "total_rows", None)),
                                ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return cells, {str(k): dict(v) for k, v in excluded.items()}, True


def encode(cells, excluded, rows=None):
    return {"rows": rows, "cells": [[*key, dict(value)] for key, value in cells.items()],
            "excluded": {str(k): dict(v) for k, v in excluded.items()}}


def decode(saved):
    return {(y, uf, age, sex): Counter(value) for y, uf, age, sex, value in saved["cells"]}
