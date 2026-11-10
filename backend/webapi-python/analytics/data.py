"""Dados em memória e cálculos do estudo, sem banco de dados."""
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

STATES = dict(zip(
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(),
    "Acre|Alagoas|Amapá|Amazonas|Bahia|Ceará|Distrito Federal|Espírito Santo|Goiás|Maranhão|Mato Grosso|Mato Grosso do Sul|Minas Gerais|Pará|Paraíba|Paraná|Pernambuco|Piauí|Rio de Janeiro|Rio Grande do Norte|Rio Grande do Sul|Rondônia|Roraima|Santa Catarina|São Paulo|Sergipe|Tocantins".split("|"),
    strict=True,
))
AGES = ("60–69", "70–79", "80+")
SEXES = ("F", "M")
IGNORED_SEX = "I"  # só contagens; sem população, entra apenas em "Ambos"
FIRST_YEAR, DEFAULT_LAST_YEAR = 2015, 2024
# Amostra real e pequena (~72 arquivos), só para uso local; inclui o DF porque é escopo do piloto
SAMPLE_YEARS = [2023, 2024]
SAMPLE_UFS = ["DF", "GO", "AP"]

SOURCE = ("Ministério da Saúde/DATASUS, Sistema de Informações Hospitalares (SIH/SUS, arquivos RD); "
          "população: projeção MS/SEIDIGI/DEMAS (IBGE), TABNET; acesso via PySUS")
FIELDS = ("year", "uf", "age", "sex", "admissions", "population", "deaths", "stay_days", "stay_count", "approved_cents")


@dataclass(frozen=True)
class Row:
    year: int
    uf: str
    age: str
    sex: str
    admissions: int
    population: int
    deaths: int
    stay_days: int
    stay_count: int
    approved_cents: int


def load(path):
    if not path:
        raise ValueError("Nenhuma base carregada.")
    rows, seen = [], set()
    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None or set(reader.fieldnames) != set(FIELDS) or len(reader.fieldnames) != len(FIELDS):
            raise ValueError("CSV deve conter exatamente as colunas documentadas.")
        for line, record in enumerate(reader, 2):
            try:
                if None in record:
                    raise ValueError("colunas excedentes")
                row = Row(int(record["year"]), record["uf"], record["age"], record["sex"],
                          *(int(record[name]) for name in FIELDS[4:]))
                key = (row.year, row.uf, row.age, row.sex)
                if (row.year < FIRST_YEAR or row.uf not in STATES or row.age not in AGES
                        or row.sex not in SEXES + (IGNORED_SEX,)):
                    raise ValueError("estrato fora do recorte")
                if key in seen or any(getattr(row, name) < 0 for name in FIELDS[4:]):
                    raise ValueError("estrato duplicado ou número negativo")
                if (not row.population and row.sex != IGNORED_SEX) or row.deaths > row.admissions \
                        or (row.stay_days and not row.stay_count):
                    raise ValueError("componentes inconsistentes")
                seen.add(key)
                rows.append(row)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Linha {line}: {exc}") from exc
    if not rows:
        raise ValueError("CSV sem registros.")
    return tuple(rows)


def grouped(rows, key):
    result = defaultdict(list)
    for row in rows:
        result[key(row)].append(row)
    return result


def ratio(numerator, denominator, scale=1):
    return round(numerator / denominator * scale, 2) if denominator else None


def metrics(rows):
    if not rows:
        return None
    sums = {name: sum(getattr(row, name) for row in rows) for name in FIELDS[4:]}
    n = sums["admissions"]
    return {
        **sums,
        "rate": ratio(n, sums["population"], 100000),
        "mortality": ratio(sums["deaths"], n, 100),
        "meanStay": ratio(sums["stay_days"], sums["stay_count"]),
        "approved": sums["approved_cents"] / 100,
        "lowVolume": n < 20,
    }


def years_of(rows):
    return tuple(sorted({r.year for r in rows}))


def parse_filters(query, years=tuple(range(FIRST_YEAR, DEFAULT_LAST_YEAR + 1))):
    allowed = {"start", "end", "uf", "age", "sex"}
    if set(query) - allowed or any(len(values) != 1 for values in query.values()):
        raise ValueError("Filtros desconhecidos ou duplicados.")
    values = {key: value[0] for key, value in query.items()}
    default_start = FIRST_YEAR if FIRST_YEAR in years else years[0]
    default_end = DEFAULT_LAST_YEAR if DEFAULT_LAST_YEAR in years else years[-1]
    start, end = int(values.get("start", default_start)), int(values.get("end", default_end))
    uf, age, sex = (values.get(key, "") for key in ("uf", "age", "sex"))
    if start not in years or end not in years or start > end:
        raise ValueError(f"Use um intervalo válido entre {years[0]} e {years[-1]}, com ano inicial menor ou igual ao final.")
    if (uf and uf not in STATES) or (age and age not in AGES) or (sex and sex not in SEXES):
        raise ValueError("UF, faixa etária ou sexo inválido.")
    return {"start": start, "end": end, "uf": uf, "age": age, "sex": sex}


def dashboard(rows, filters, metadata, weights):
    f = filters
    selected = [r for r in rows if f["start"] <= r.year <= f["end"]
                and (not f["uf"] or r.uf == f["uf"])
                and (not f["age"] or r.age == f["age"])
                and (not f["sex"] or r.sex == f["sex"])]
    sexes = (f["sex"],) if f["sex"] else SEXES
    ages = (f["age"],) if f["age"] else AGES
    years = range(f["start"], f["end"] + 1)

    def summarize(items, expected):
        result = metrics(items)
        if result is None:
            return None
        result["partial"] = sum(r.sex != IGNORED_SEX for r in items) != expected
        by_age = grouped(items, lambda r: r.age)
        result["standardRate"] = None
        if not f["age"] and weights and not result["partial"] and len(by_age) == len(AGES):
            result["standardRate"] = round(sum(
                weights[age] * sum(r.admissions for r in by_age[age]) /
                sum(r.population for r in by_age[age]) * 100000
                for age in AGES
            ), 2)
        if result["partial"]:
            # Contagens parciais podem ser exibidas; taxas comparáveis não.
            result["rate"] = None
        return result

    ufs = (f["uf"],) if f["uf"] else tuple(STATES)
    by_uf, by_year = grouped(selected, lambda r: r.uf), grouped(selected, lambda r: r.year)
    by_age, by_sex = grouped(selected, lambda r: r.age), grouped(selected, lambda r: r.sex)
    return {
        "metadata": metadata,
        "filters": f,
        "options": {"years": years_of(rows), "states": STATES, "ages": AGES, "sexes": SEXES},
        "notes": {"ignoredSexAdmissions": 0 if f["sex"] else
                  sum(r.admissions for r in selected if r.sex == IGNORED_SEX)},
        "summary": summarize(selected, len(ufs) * len(years) * len(ages) * len(sexes)),
        "territories": [{"key": uf, "label": STATES[uf],
                         "metrics": summarize(by_uf[uf], len(years) * len(ages) * len(sexes))}
                        for uf in ufs],
        "series": [{"key": str(year), "label": str(year),
                    "metrics": summarize(by_year[year], len(ufs) * len(ages) * len(sexes))}
                   for year in years],
        "ages": [{"key": age, "label": age, "metrics": summarize(by_age[age], len(ufs) * len(years) * len(sexes))}
                 for age in ages],
        "sexes": [{"key": sex, "label": {"F": "Feminino", "M": "Masculino"}[sex],
                   "metrics": summarize(by_sex[sex], len(ufs) * len(years) * len(ages))}
                  for sex in sexes],
    }


def reference_weights(rows):
    reference = [r for r in rows if r.year == 2024 and r.sex != IGNORED_SEX]
    if len(reference) != len(STATES) * len(AGES) * len(SEXES):
        return None
    total = sum(r.population for r in reference)
    return {age: sum(r.population for r in reference if r.age == age) / total for age in AGES}
