"""Orquestra download, agregação, conciliação e publicação de uma nova versão da base."""
import csv
import datetime as dt
import hashlib
import json
import logging
import os
from collections import Counter
from pathlib import Path

from analytics import store
from analytics.data import FIELDS, load

log = logging.getLogger(__name__)

from . import pilot, population, sources
from .transform import merge_cells, to_rows

FIRST_YEAR = 2015
CID = ("Diagnóstico principal com lesão (CID-10 S00–T98) e causa externa W00–W19 em campo secundário "
       "(DIAG_SECUN, DIAGSEC1–9), como na tabela de causas externas do TABNET; AIH tipo 1")


class PilotBlocked(RuntimeError):
    pass


def candidate_years(today=None):
    return list(range(FIRST_YEAR, (today or dt.date.today()).year))


def pysus_version():
    try:
        from importlib.metadata import version  # noqa: PLC0415
        return version("pysus")
    except Exception:  # noqa: BLE001
        return "desconhecida"


def run(progress=None, refresh=False, directory=None, population_csv=None, fetch=sources.read_month, years=None):
    """Constrói e ativa uma nova versão. `progress(done, total, stage)` informa o andamento."""
    directory = Path(directory or store.data_dir())
    cache = directory / "cache"
    directory.mkdir(parents=True, exist_ok=True)
    notify = progress or (lambda *_: None)
    years = years or candidate_years()
    manual = population_csv or os.environ.get("POPULATION_CSV")
    notify(0, 1, "Obtendo população (TABNET, projeção 2024)")
    pop = population.load_population(manual) if manual else population.fetch_tabnet(years, cache)
    files = sources.expected_files(years)
    total = len(files)
    latest = max(years)
    cutoff = latest * 12 + 12 - sources.REFRESH_MONTHS  # meses recentes são rebaixados na atualização
    parts, excluded, downloaded, failed_years = [], {}, 0, {}
    cached_files, pilot_files = 0, {}
    log.info("Iniciando carga: anos %s-%s, %d arquivos, refresh=%s, cache=%s",
             min(years), latest, total, refresh, cache)
    for done, (uf, year, month) in enumerate(files, 1):
        if year in failed_years:
            continue
        notify(done, total, f"Arquivo RD{uf}{year % 100:02d}{month:02d}")
        recent = refresh and year * 12 + month > cutoff
        try:
            cells, exc, fresh = sources.load_month(uf, year, month, cache, refresh=recent, fetch=fetch)
        except Exception as error:  # noqa: BLE001
            if year < latest:
                raise
            log.warning("Falha em RD%s%02d%02d (ano %s ainda em curso): %s", uf, year % 100, month, year, error)
            failed_years[year] = f"{uf} {month:02d}: {error}"  # ano em curso/ainda incompleto
            continue
        downloaded += fresh
        cached_files += not fresh
        if year == pilot.PILOT_YEAR:
            pilot_files[(uf, month)] = (sum(c["admissions"] for c in cells.values()), "baixado" if fresh else "cache")
        parts.append(cells)
        if done % 100 == 0:
            log.info("Progresso: %d/%d arquivos (baixados=%d, cache=%d)", done, total, downloaded, cached_files)
        for y, counters in exc.items():
            excluded.setdefault(int(y), Counter()).update(counters)
    complete = [y for y in years if y not in failed_years]
    cells = merge_cells(parts)

    log.info("Arquivos: baixados=%d, do cache=%d, ignorados=%d", downloaded, cached_files, total - len(parts))
    by_year = Counter()
    for (year, _uf, _age, _sex), c in cells.items():
        by_year[year] += c["admissions"]
    log.info("Internações por ano (Brasil): %s", dict(sorted(by_year.items())))
    log.info("Exclusões por ano: %s", {y: dict(c) for y, c in sorted(excluded.items())})
    by_month, by_uf = Counter(), Counter()
    for (uf, month), (count, _origin) in pilot_files.items():
        by_month[month] += count
        by_uf[uf] += count
    log.info("Piloto %d por mês (soma das UFs): %s", pilot.PILOT_YEAR, dict(sorted(by_month.items())))
    log.info("Piloto %d por UF de residência dos arquivos lidos: %s", pilot.PILOT_YEAR, dict(sorted(by_uf.items())))
    empty = sorted(k for k, (count, _o) in pilot_files.items() if count == 0)
    if empty:
        log.warning("Arquivos de %d sem nenhuma queda 60+: %d (primeiros 20: %s)", pilot.PILOT_YEAR, len(empty), empty[:20])
    sex_i = sum(c["admissions"] for (y, _u, _a, sx), c in cells.items() if y == pilot.PILOT_YEAR and sx == "I")
    log.info("Piloto %d: internações com sexo ignorado=%d (entram no total, mas não em M/F)", pilot.PILOT_YEAR, sex_i)
    totals_2024 = pilot.totals(cells)
    log.info("Células agregadas: %d | arquivos ignorados por ano com falha: %s | totais 2024: %s",
             len(cells), sorted(failed_years), json.dumps(totals_2024, ensure_ascii=False))
    notify(total, total, "Conciliando piloto com o TABNET")
    report = pilot.compare(pilot.totals(cells))
    pilot.write_report(report, directory)
    if not report["ok"]:
        raise PilotBlocked(report.get("reason") or "Piloto divergente do TABNET; veja pilot_report.json.")

    notify(total, total, "Gerando base")
    rows, missing = to_rows(cells, pop, complete)
    if not rows:
        raise RuntimeError("Nenhum estrato com população disponível.")
    version = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = directory / "versions" / version
    folder.mkdir(parents=True)
    with (folder / "dataset.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(FIELDS)
        writer.writerows(rows)
    load(folder / "dataset.csv")  # valida antes de publicar
    ignored_sex = {}
    for (y, _u, _a, sex), c in cells.items():
        if sex == "I" and y in complete:
            ignored_sex[y] = ignored_sex.get(y, 0) + c["admissions"]
    manifest = {
        "version": version,
        "createdAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": "SIH/SUS (RD) via PySUS",
        "pysusVersion": pysus_version(),
        "populationEdition": population.EDITION,
        "caseDefinition": CID,
        "years": complete,
        "incompleteYears": failed_years,
        "unit": "internações (eventos, não pessoas) por ano de processamento, UF de residência",
        "exclusions": {str(y): dict(c) for y, c in sorted(excluded.items()) if y in complete or y == 0},
        "ignoredSexAdmissions": {str(y): n for y, n in sorted(ignored_sex.items())},
        "strataWithoutPopulation": len(missing),
        "pilot": report,
        "sha256": hashlib.sha256((folder / "dataset.csv").read_bytes()).hexdigest(),
        "filesProcessed": total,
        "filesDownloaded": downloaded,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    store.activate(directory, version)
    notify(total, total, "Concluído")
    return manifest
