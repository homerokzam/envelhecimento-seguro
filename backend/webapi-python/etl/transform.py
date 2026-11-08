"""Transforma registros do SIH/SUS (RD) em estratos do contrato do painel.

Opera sobre dicionários simples (um por AIH já pré-filtrada ou não) para poder
ser testado só com a biblioteca padrão. A leitura dos arquivos fica em sources.py.
"""
import re
from collections import Counter, defaultdict

from analytics.data import AGES

# Código IBGE da UF (2 primeiros dígitos de MUNIC_RES) -> sigla.
UF_BY_CODE = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}
FALL = re.compile(r"^W(0\d|1\d)")  # CID-10 W00–W19
DIAG_FIELDS = ("DIAG_PRINC", "DIAG_SECUN") + tuple(f"DIAGSEC{i}" for i in range(1, 10))
REQUIRED_FIELDS = ("ANO_CMPT", "IDENT", "IDADE", "SEXO", "MUNIC_RES", "MORTE", "DIAS_PERM", "VAL_TOT")


def is_fall(record):
    """Queda se qualquer campo de diagnóstico tiver W00–W19, não só o principal."""
    return any(FALL.match(str(record.get(f) or "").strip().upper()) for f in DIAG_FIELDS)


def age_in_years(record):
    """Idade em anos ou None. COD_IDADE 4 = anos; 5 = 100 anos ou mais (IDADE = anos - 100)."""
    try:
        value = int(float(record.get("IDADE")))
    except (TypeError, ValueError):
        return None
    unit = str(record.get("COD_IDADE") or "4").strip()
    if unit in ("4", "4.0"):
        return value
    if unit in ("5", "5.0"):
        return 100 + value
    return 0  # horas, dias ou meses: menor de 1 ano


def age_band(years):
    if years is None or years < 60:
        return None
    return AGES[0] if years < 70 else AGES[1] if years < 80 else AGES[2]


def sex_of(record):
    value = str(record.get("SEXO") or "").strip().upper()
    return "M" if value in ("1", "M") else "F" if value in ("3", "F") else "I"


def number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def aggregate(records):
    """Agrega AIHs em {(ano, uf, faixa, sexo): componentes} e conta exclusões por ano."""
    cells = defaultdict(lambda: Counter())
    excluded = defaultdict(Counter)
    for record in records:
        if str(record.get("IDENT") or "").strip() not in ("1", "1.0"):
            continue  # só AIH normal; continuação de longa permanência não é nova internação
        if not is_fall(record):
            continue
        try:
            year = int(float(record.get("ANO_CMPT")))
        except (TypeError, ValueError):
            excluded[0]["ano_invalido"] += 1
            continue
        years = age_in_years(record)
        if years is None:
            excluded[year]["idade_ignorada"] += 1
            continue
        band = age_band(years)
        if band is None:
            continue  # fora da população estudada (menores de 60)
        uf = UF_BY_CODE.get(str(record.get("MUNIC_RES") or "").strip()[:2])
        if uf is None:
            excluded[year]["residencia_invalida_ou_exterior"] += 1
            continue
        cell = cells[(year, uf, band, sex_of(record))]
        cell["admissions"] += 1
        cell["deaths"] += str(record.get("MORTE") or "").strip() in ("1", "1.0")
        cell["stay_days"] += int(number(record.get("DIAS_PERM")))
        cell["stay_count"] += 1
        cell["approved_cents"] += round(number(record.get("VAL_TOT")) * 100)
    return cells, excluded


def merge_cells(parts):
    total = defaultdict(Counter)
    for part in parts:
        for key, counter in part.items():
            total[key].update(counter)
    return total


def to_rows(cells, population, years):
    """Estratos completos (com zero verificado) para os anos completos informados.

    `population[(ano, uf, faixa, sexo)]` vem da projeção do Ministério da Saúde. Estratos
    sem população ficam fora (nunca preenchidos com zero). Sexo ignorado só entra se houver casos.
    """
    rows, missing = [], []
    ufs = sorted(set(UF_BY_CODE.values()))
    for year in sorted(years):
        for uf in ufs:
            for age in AGES:
                for sex in ("F", "M"):
                    pop = population.get((year, uf, age, sex))
                    if not pop:
                        missing.append((year, uf, age, sex))
                        continue
                    c = cells.get((year, uf, age, sex), Counter())
                    rows.append((year, uf, age, sex, c["admissions"], pop, c["deaths"],
                                 c["stay_days"], c["stay_count"], c["approved_cents"]))
                c = cells.get((year, uf, age, "I"))
                if c and c["admissions"]:
                    rows.append((year, uf, age, "I", c["admissions"], 0, c["deaths"],
                                 c["stay_days"], c["stay_count"], c["approved_cents"]))
    return rows, missing
