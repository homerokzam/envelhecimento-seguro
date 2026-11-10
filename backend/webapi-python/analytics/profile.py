"""Perfil clínico e hospitalar das internações, em dimensões extras sobre os mesmos estratos.

`profile.csv` (formato longo): year,uf,age,sex,dim,value + os cinco componentes aditivos. Para cada estrato
e dimensão, os valores somam exatamente as internações e os óbitos da base principal; isso é validado
ao carregar. `municipios.csv`: totais por município de residência (60+, ambos os sexos), sem taxas,
porque a projeção usada não tem população municipal.
"""
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .data import AGES, FIRST_YEAR, IGNORED_SEX, SEXES, STATES, ratio

COMPONENTS = ("admissions", "deaths", "stay_days", "stay_count", "approved_cents")
PROFILE_FIELDS = ("year", "uf", "age", "sex", "dim", "value") + COMPONENTS
MUNICIPALITY_FIELDS = ("year", "uf", "code", "name") + COMPONENTS

INJURY = {
    "S72": "Fratura do fêmur", "S06": "Traumatismo intracraniano", "S52": "Fratura do antebraço",
    "S42": "Fratura do ombro e do braço", "S32": "Fratura da coluna lombar e da pelve",
    "S22": "Fratura de costelas, esterno e coluna torácica", "S82": "Fratura da perna, incluindo tornozelo",
    "S02": "Fratura de ossos do crânio e da face", "S12": "Fratura do pescoço", "S62": "Fratura do punho e da mão",
    "S92": "Fratura do pé", "S01": "Ferimento da cabeça", "T02": "Fraturas de várias regiões do corpo",
    "T03": "Luxações e entorses de várias regiões",
}
FALL = {
    "W00": "Mesmo nível, gelo ou neve", "W01": "Mesmo nível, escorregão, tropeção ou passo em falso",
    "W02": "Patins, esqui ou skate", "W03": "Mesmo nível, colisão ou empurrão", "W04": "Ao ser carregado ou apoiado",
    "W05": "Cadeira de rodas", "W06": "Cama", "W07": "Cadeira", "W08": "Outro mobiliário",
    "W09": "Equipamento de playground", "W10": "Escadas e degraus", "W11": "Escada de mão",
    "W12": "Andaime", "W13": "Edifício ou estrutura", "W14": "Árvore", "W15": "Penhasco",
    "W16": "Mergulho ou pulo na água", "W17": "Outra queda de um nível a outro",
    "W18": "Outra queda no mesmo nível", "W19": "Queda sem especificação",
}
MONTHS = dict(zip(("%02d" % m for m in range(1, 13)),
                  "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split()))
WEEKDAYS = dict(zip("0123456", "segunda terça quarta quinta sexta sábado domingo".split()))

# dimensão -> (título, ordem natural?, {valor: rótulo})
DIMS = {
    "injury": ("Tipo de lesão (diagnóstico principal)", False,
               {**{c: f"{c} {t}" for c, t in INJURY.items()}, "S_outras": "Outras lesões S (S00–S99)",
                "T_outras": "Outras lesões T (T00–T98)"}),
    "fall": ("Tipo de queda (causa W00–W19)", False, {c: f"{c} {t}" for c, t in FALL.items()}),
    "month": ("Mês da internação", True, {**MONTHS, "ign": "Ignorado"}),
    "weekday": ("Dia da semana da internação", True, {**WEEKDAYS, "ign": "Ignorado"}),
    "urgency": ("Caráter da internação", False, {"urgencia": "Urgência", "eletivo": "Eletiva", "outros": "Outros"}),
    "procedure": ("Tipo de procedimento realizado", False,
                  {"cirurgico": "Cirúrgico", "clinico": "Clínico", "outros": "Outros (diagnóstico, transplante etc.)"}),
    "uti": ("Uso de UTI", False, {"com_uti": "Com UTI", "sem_uti": "Sem UTI"}),
    "exit": ("Motivo de saída", False, {"alta": "Alta", "permanencia": "Continuidade da internação",
                                         "transferencia": "Transferência", "obito": "Óbito", "outros": "Outros"}),
    "nature": ("Natureza jurídica do hospital", False,
               {"publico": "Pública", "sem_fins": "Privada sem fins lucrativos (inclui filantrópicos)",
                "privado": "Privada com fins lucrativos", "outros": "Outra"}),
    "race": ("Raça/cor", False, {"branca": "Branca", "parda": "Parda", "preta": "Preta", "amarela": "Amarela",
                                 "indigena": "Indígena", "sem_info": "Sem informação"}),
}
BY_YEAR_DIMS = ("injury", "fall")  # com série anual por valor


@dataclass(frozen=True)
class ProfileRow:
    year: int
    uf: str
    age: str
    sex: str
    dim: str
    value: str
    admissions: int
    deaths: int
    stay_days: int
    stay_count: int
    approved_cents: int


@dataclass(frozen=True)
class Municipality:
    year: int
    uf: str
    code: str
    name: str
    admissions: int
    deaths: int
    stay_days: int
    stay_count: int
    approved_cents: int


def _read(path, fields):
    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None or tuple(reader.fieldnames) != fields:
            raise ValueError(f"{Path(path).name} deve conter exatamente as colunas documentadas.")
        yield from enumerate(reader, 2)


def _check_components(record, line):
    values = [int(record[name]) for name in COMPONENTS]
    if any(v < 0 for v in values) or values[1] > values[0] or (values[2] and not values[3]):
        raise ValueError(f"Linha {line}: componentes inconsistentes")
    return values


def load_profile(path, rows):
    """Lê o perfil e confere que cada dimensão fecha com a base principal em cada estrato."""
    result, seen = [], set()
    for line, record in _read(path, PROFILE_FIELDS):
        try:
            year, dim, value = int(record["year"]), record["dim"], record["value"]
            if (year < FIRST_YEAR or record["uf"] not in STATES or record["age"] not in AGES
                    or record["sex"] not in SEXES + (IGNORED_SEX,) or dim not in DIMS or value not in DIMS[dim][2]):
                raise ValueError("categoria fora do vocabulário")
            key = (year, record["uf"], record["age"], record["sex"], dim, value)
            if key in seen:
                raise ValueError("categoria duplicada")
            seen.add(key)
            result.append(ProfileRow(year, record["uf"], record["age"], record["sex"], dim, value,
                                     *_check_components(record, line)))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"profile.csv: {exc}") from exc
    sums = defaultdict(lambda: [0, 0])
    for r in result:
        cell = sums[(r.dim, r.year, r.uf, r.age, r.sex)]
        cell[0] += r.admissions
        cell[1] += r.deaths
    main = {(r.year, r.uf, r.age, r.sex): (r.admissions, r.deaths) for r in rows}
    for (dim, year, uf, age, sex), got in sums.items():
        if main.get((year, uf, age, sex)) != tuple(got):
            raise ValueError(f"profile.csv: dimensão {dim} não fecha com a base em {year} {uf} {age} {sex}")
    for stratum, expected in main.items():
        if expected[0] and any(sums.get((dim, *stratum)) != list(expected) for dim in DIMS):
            raise ValueError(f"profile.csv: estrato {stratum} com internações e sem todas as dimensões")
    return tuple(result)


def load_municipalities(path, rows):
    """Lê os totais por município e confere que somam as internações de cada ano da base principal."""
    result = []
    for line, record in _read(path, MUNICIPALITY_FIELDS):
        try:
            year = int(record["year"])
            if year < FIRST_YEAR or record["uf"] not in STATES or len(record["code"]) != 6:
                raise ValueError("município fora do recorte")
            result.append(Municipality(year, record["uf"], record["code"], record["name"],
                                       *_check_components(record, line)))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"municipios.csv: {exc}") from exc
    for year in {r.year for r in rows}:
        if sum(m.admissions for m in result if m.year == year) != sum(r.admissions for r in rows if r.year == year):
            raise ValueError(f"municipios.csv: total de {year} não fecha com a base")
    return tuple(result)


def _stats(items, total):
    n = sum(i.admissions for i in items)
    stay_count = sum(i.stay_count for i in items)
    low = n < 20  # poucos casos: a contagem aparece, mas razões e médias ficam ocultas
    return {
        "admissions": n, "deaths": sum(i.deaths for i in items),
        "mortality": None if low else ratio(sum(i.deaths for i in items), n, 100),
        "meanStay": None if low else ratio(sum(i.stay_days for i in items), stay_count),
        "meanApproved": None if low else ratio(sum(i.approved_cents for i in items) / 100, n),
        "share": ratio(n, total, 100), "lowVolume": low,
    }


def profile_payload(rows, f):
    """Perfil para os filtros ativos. Parcelas, não taxas: não há população por categoria."""
    selected = [r for r in rows if f["start"] <= r.year <= f["end"] and (not f["uf"] or r.uf == f["uf"])
                and (not f["age"] or r.age == f["age"]) and (not f["sex"] or r.sex == f["sex"])]
    dims = []
    for dim, (title, ordered, labels) in DIMS.items():
        mine = defaultdict(list)
        for r in selected:
            if r.dim == dim:
                mine[r.value].append(r)
        total = sum(r.admissions for items in mine.values() for r in items)
        items = []
        for value, label in labels.items():
            found = mine.get(value, [])
            if not found and not ordered:
                continue
            entry = {"key": value, "label": label, **_stats(found, total)}
            if dim in BY_YEAR_DIMS:
                entry["byYear"] = {str(y): sum(r.admissions for r in found if r.year == y)
                                   for y in range(f["start"], f["end"] + 1)}
            items.append(entry)
        if not ordered:
            items.sort(key=lambda i: -i["admissions"])
        dims.append({"key": dim, "title": title, "ordered": ordered, "total": total, "items": items})
    return {"available": True, "dims": dims}


def municipalities_payload(municipalities, f, limit=20):
    """Ranking de municípios de residência (só período e UF; idade e sexo não se aplicam)."""
    totals = defaultdict(list)
    for m in municipalities:
        if f["start"] <= m.year <= f["end"] and (not f["uf"] or m.uf == f["uf"]):
            totals[(m.code, m.uf, m.name)].append(m)
    grand = sum(m.admissions for items in totals.values() for m in items)
    ranked = sorted(((key, _stats(items, grand)) for key, items in totals.items()), key=lambda e: -e[1]["admissions"])
    return {"available": True, "withCases": len(totals), "total": grand,
            "top": [{"code": code, "uf": uf, "name": name or code, **stats} for (code, uf, name), stats in ranked[:limit]]}
