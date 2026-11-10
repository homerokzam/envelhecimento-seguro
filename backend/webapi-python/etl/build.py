"""Orquestra download, agregação, conciliação e publicação de uma nova versão da base."""
import csv
import datetime as dt
import gzip
import hashlib
import json
import logging
import os
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from pathlib import Path

from analytics import store
from analytics.data import FIELDS, SAMPLE_UFS, SAMPLE_YEARS, SOURCE, load  # noqa: F401 - reexportados para o CLI
from analytics.profile import MUNICIPALITY_FIELDS, PROFILE_FIELDS, load_municipalities, load_profile

log = logging.getLogger(__name__)

from . import pilot, population, sources
from .transform import merge_cells, to_rows

FIRST_YEAR = 2015
LAST_YEAR = 2024  # o estudo cobre 2015–2024; anos posteriores só entram com --years explícito
IBGE_MUNICIPALITIES = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
CID = ("Diagnóstico principal com lesão (CID-10 S00–T98) e causa externa W00–W19 em campo secundário "
       "(DIAG_SECUN, DIAGSEC1–9), como na tabela de causas externas do TABNET; AIH tipo 1")


class PilotBlocked(RuntimeError):
    pass


def candidate_years(today=None):
    return list(range(FIRST_YEAR, min((today or dt.date.today()).year, LAST_YEAR + 1)))


def pysus_version():
    try:
        from importlib.metadata import version  # noqa: PLC0415
        return version("pysus")
    except Exception:  # noqa: BLE001
        return "desconhecida"


def municipality_names(cache):
    """Nomes dos municípios (IBGE, código de 6 dígitos). Sem rede, os nomes ficam vazios e o painel mostra o código."""
    path = Path(cache) / "ibge_municipios.json"
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        with urllib.request.urlopen(IBGE_MUNICIPALITIES, timeout=60) as response:
            body = response.read()
        if body[:2] == b"\x1f\x8b":  # a API do IBGE responde compactada mesmo sem pedir
            body = gzip.decompress(body)
        names = {str(m["id"])[:6]: m["nome"] for m in json.loads(body)}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(names, ensure_ascii=False), encoding="utf-8")
        return names
    except Exception as error:  # noqa: BLE001
        log.warning("Nomes de municípios indisponíveis (%s); o painel mostrará só o código IBGE.", error)
        return {}


def write_profile(folder, profile_cells, munic_cells, complete, main_rows, cache):
    """Grava profile.csv e municipios.csv só para estratos e anos da base principal, já validados."""
    present = {(r.year, r.uf, r.age, r.sex) for r in main_rows}
    sampled_ufs = {r.uf for r in main_rows}  # em amostra, residentes de outras UFs ficam fora da base
    components = ("admissions", "deaths", "stay_days", "stay_count", "approved_cents")
    with (folder / "profile.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(PROFILE_FIELDS)
        for key, c in sorted(profile_cells.items()):
            if key[:4] in present:
                writer.writerow([*key, *(c[name] for name in components)])
    names = municipality_names(cache)
    with (folder / "municipios.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(MUNICIPALITY_FIELDS)
        for (year, uf, code), c in sorted(munic_cells.items()):
            if year in complete and uf in sampled_ufs:
                writer.writerow([year, uf, code, names.get(code, ""), *(c[name] for name in components)])
    load_profile(folder / "profile.csv", main_rows)  # confere que fecha com a base antes de publicar
    load_municipalities(folder / "municipios.csv", main_rows)


WORKERS = int(os.environ.get("ETL_WORKERS", "6"))  # UFs lidas ao mesmo tempo (uma thread por UF)


def read_uf_year(uf, year, cache, refresh, cutoff, fetch, tick):
    """Uma thread: os 12 meses de uma UF num ano. `tick(uf, month)` informa o andamento."""
    months = []
    for month in range(1, 13):
        recent = refresh and year * 12 + month > cutoff
        months.append(sources.load_month(uf, year, month, cache, refresh=recent, fetch=fetch))
        tick(uf, month)
    return months


def publish(directory, cache, pop, years_done, ufs, cells, profile_cells, munic_cells, excluded, failed_years,
            stats, final, scopes):
    """Valida, grava e ativa uma versão com os anos concluídos até agora (UFs lidas, ou todas)."""
    if pilot.PILOT_YEAR in years_done and scopes:
        report = pilot.compare(pilot.totals(cells, scopes))
        pilot.write_report(report, directory)
        if not report["ok"]:
            raise PilotBlocked(report.get("reason") or "Piloto divergente do TABNET; veja pilot_report.json.")
    elif final:
        report = {"ok": False, "reason": f"A carga precisa incluir {pilot.PILOT_YEAR} e ao menos uma UF do piloto "
                  f"({', '.join(s for s in pilot.SCOPES if s != 'BR')}).", "scopes": {}}
        raise PilotBlocked(report["reason"])
    else:  # ano anterior ao piloto: dados completos por ano, conciliação com o TABNET só quando 2024 chegar
        report = {"ok": False, "reason": f"Conciliação com o TABNET pendente até concluir {pilot.PILOT_YEAR}.", "scopes": {}}
    rows, missing = to_rows(cells, pop, years_done, ufs)
    if not rows:
        raise RuntimeError("Nenhum estrato com população disponível.")
    while True:  # duas publicações no mesmo segundo não podem colidir
        version = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        folder = directory / "versions" / version
        try:
            folder.mkdir(parents=True)
            break
        except FileExistsError:
            time.sleep(0.3)
    with (folder / "dataset.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(FIELDS)
        writer.writerows(rows)
    main_rows = load(folder / "dataset.csv")  # valida antes de publicar
    write_profile(folder, profile_cells, munic_cells, years_done, main_rows, cache=directory / "cache")
    ignored_sex = {}
    for (y, _u, _a, sex), c in cells.items():
        if sex == "I" and y in years_done:
            ignored_sex[y] = ignored_sex.get(y, 0) + c["admissions"]
    manifest = {
        "version": version,
        "createdAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": SOURCE,
        "pysusVersion": pysus_version(),
        "populationEdition": population.EDITION,
        "caseDefinition": CID,
        "years": sorted(years_done),
        "incompleteYears": failed_years,
        "unit": "internações (eventos, não pessoas) por ano de processamento, UF de residência",
        "exclusions": {str(y): dict(c) for y, c in sorted(excluded.items()) if y in years_done or y == 0},
        "ignoredSexAdmissions": {str(y): n for y, n in sorted(ignored_sex.items())},
        "strataWithoutPopulation": len(missing),
        "pilot": report,
        "sha256": hashlib.sha256((folder / "dataset.csv").read_bytes()).hexdigest(),
        "filesProcessed": stats["total"],
        "filesDownloaded": stats["downloaded"],
        "partialLoad": not final,
    }
    if ufs:
        manifest["sample"] = {"ufs": ufs, "years": sorted(years_done)}
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    store.activate(directory, version)
    return manifest


def run(progress=None, refresh=False, directory=None, population_csv=None, fetch=sources.read_month, years=None,
        ufs=None, workers=None, on_publish=None):
    """Constrói e ativa uma nova versão, ano a ano (crescente), com uma thread por UF dentro de cada ano.

    `progress(done, total, stage, **detalhe)` informa o andamento (ano, UFs em leitura e concluídas).
    Ao concluir cada ano (todas as UFs) uma versão com os anos prontos é ativada e `on_publish()` é
    chamado, para a interface já mostrar os dados. `ufs` gera uma amostra real (uso local): só essas UFs
    são lidas, as demais ficam ausentes (nunca zeradas) e o piloto concilia apenas os escopos cobertos.
    """
    directory = Path(directory or store.data_dir())
    cache = directory / "cache"
    directory.mkdir(parents=True, exist_ok=True)
    notify = progress or (lambda *_, **__: None)
    years = sorted(years or candidate_years())
    manual = population_csv or os.environ.get("POPULATION_CSV")
    notify(0, 1, "Obtendo população (TABNET, projeção 2024)")
    pop = population.load_population(manual) if manual else population.fetch_tabnet(years, cache)
    ufs = sorted({u.upper() for u in ufs}) if ufs else None
    if ufs and set(ufs) - set(sources.UFS):
        raise ValueError(f"UF desconhecida na amostra: {sorted(set(ufs) - set(sources.UFS))}")
    scopes = [s for s in pilot.SCOPES if s in ufs] if ufs else list(pilot.SCOPES)
    load_ufs = ufs or list(sources.UFS)
    workers = max(1, min(workers or WORKERS, len(load_ufs)))
    total = len(years) * 12 * len(load_ufs)
    latest = max(years)
    cutoff = latest * 12 + 12 - sources.REFRESH_MONTHS  # meses recentes são rebaixados na atualização
    log.info("Iniciando carga: anos %s-%s, %d arquivos, refresh=%s, cache=%s, amostra=%s, threads=%d",
             min(years), latest, total, refresh, cache, ufs or "não", workers)

    lock = threading.Lock()
    stats = {"done": 0, "downloaded": 0, "cached": 0, "total": total}
    year_cells, year_profile, year_munic, excluded = {}, {}, {}, {}
    failed_years, years_done, manifest = {}, [], None
    pilot_files = {}

    for position, year in enumerate(years):
        running, finished = {}, []

        def tick(uf, month, year=year, running=running, finished=finished):
            with lock:
                stats["done"] += 1
                running[uf] = month
                snapshot = dict(done=stats["done"], total=total, year=year, running=sorted(running),
                                finished=list(finished), yearsDone=list(years_done))
            notify(snapshot["done"], total, f"{year} · {', '.join(snapshot['running'])}",
                   **{k: v for k, v in snapshot.items() if k not in ("done", "total")})

        results, failure = {}, None
        pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix=f"etl-{year}")
        try:
            futures = {pool.submit(read_uf_year, uf, year, cache, refresh, cutoff, fetch, tick): uf for uf in load_ufs}
            for future in as_completed(futures):
                uf = futures[future]
                try:
                    results[uf] = future.result()
                except Exception as error:  # noqa: BLE001
                    failure = (uf, error)
                    break
                with lock:
                    running.pop(uf, None)
                    finished.append(uf)
        finally:
            pool.shutdown(wait=True, cancel_futures=True)
        if failure:
            uf, error = failure
            if year < latest:
                raise error
            log.warning("Falha em RD%s %s (ano %s ainda em curso): %s", uf, year, year, error)
            failed_years[year] = f"{uf}: {error}"  # ano em curso/ainda incompleto
        else:
            parts, profile_parts, munic_parts = [], [], []
            for uf in load_ufs:
                for month, (cells, exc, extras, fresh) in enumerate(results[uf], 1):
                    stats["downloaded"] += fresh
                    stats["cached"] += not fresh
                    if year == pilot.PILOT_YEAR:
                        pilot_files[(uf, month)] = (sum(c["admissions"] for c in cells.values()),
                                                    "baixado" if fresh else "cache")
                    parts.append(cells)
                    profile_parts.append(extras["profile"])
                    munic_parts.append(extras["munic"])
                    for y, counters in exc.items():
                        excluded.setdefault(int(y), Counter()).update(counters)
            year_cells[year], year_profile[year], year_munic[year] = (
                merge_cells(parts), merge_cells(profile_parts), merge_cells(munic_parts))
            years_done.append(year)
            log.info("Ano %s concluído (%d UFs); anos prontos: %s", year, len(load_ufs), years_done)
        if not years_done:
            continue
        last = position == len(years) - 1
        notify(stats["done"], total, f"Publicando {', '.join(map(str, years_done))}" if not last else "Conferindo e publicando",
               year=year, running=[], finished=list(load_ufs) if not failure else [], yearsDone=list(years_done))
        cells = merge_cells([year_cells[y] for y in years_done])
        profile_cells = merge_cells([year_profile[y] for y in years_done])
        munic_cells = merge_cells([year_munic[y] for y in years_done])
        if year == pilot.PILOT_YEAR or last:
            by_year = Counter()
            for (y, _uf, _age, _sex), c in cells.items():
                by_year[y] += c["admissions"]
            log.info("Internações por ano (Brasil): %s", dict(sorted(by_year.items())))
            log.info("Exclusões por ano: %s", {y: dict(c) for y, c in sorted(excluded.items())})
        if year == pilot.PILOT_YEAR:
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
        manifest = publish(directory, cache, pop, years_done, ufs, cells, profile_cells, munic_cells, excluded,
                           failed_years, stats, last, scopes)
        log.info("Versão %s ativa com os anos %s%s", manifest["version"], years_done, "" if last else " (carga em andamento)")
        if on_publish:
            on_publish()
    log.info("Arquivos: baixados=%d, do cache=%d, ignorados=%d", stats["downloaded"], stats["cached"],
             total - stats["done"])
    if manifest is None:
        raise RuntimeError("Nenhum ano concluído.")
    notify(total, total, "Concluído", year=latest, running=[], finished=[], yearsDone=list(years_done))
    return manifest
