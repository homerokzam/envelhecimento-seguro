"""Transforma registros do SIH/SUS (RD) em estratos do contrato do painel.

Opera sobre dicionários simples (um por AIH já pré-filtrada ou não) para poder
ser testado só com a biblioteca padrão. A leitura dos arquivos fica em sources.py.
"""
import datetime as dt
import re
from collections import Counter, defaultdict

from analytics.data import AGES
from analytics.profile import INJURY as INJURY_CODES

# Código IBGE da UF (2 primeiros dígitos de MUNIC_RES) -> sigla.
UF_BY_CODE = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}
FALL = re.compile(r"^W(0\d|1\d)")  # CID-10 W00–W19
INJURY = re.compile(r"^[ST]\d")  # CID-10 capítulo XIX (S00–T98): lesões
DIAG_FIELDS = ("DIAG_PRINC", "DIAG_SECUN") + tuple(f"DIAGSEC{i}" for i in range(1, 10))
REQUIRED_FIELDS = ("ANO_CMPT", "IDENT", "IDADE", "SEXO", "MUNIC_RES", "MORTE", "DIAS_PERM", "VAL_TOT")
# Campos do perfil clínico e hospitalar (dimensões extras).
PROFILE_FIELDS = ("DT_INTER", "CAR_INT", "COBRANCA", "RACA_COR", "NAT_JUR", "UTI_MES_TO", "PROC_REA")
# Versão da definição de caso. Muda quando a regra muda; agregados em cache de outra versão são refeitos.
CASE_RULE = "tabnet-v2"  # v2: agregados passam a trazer perfil clínico/hospitalar e município


def _code(record, field):
    return str(record.get(field) or "").strip().upper()


def has_fall_code(record):
    """W00–W19 em algum campo de diagnóstico (pré-filtro; não basta para ser caso)."""
    return any(FALL.match(_code(record, f)) for f in DIAG_FIELDS)


def is_fall(record):
    """Internação por queda, no mesmo critério do TABNET (Morbidade Hospitalar por Causas Externas).

    O diagnóstico principal é uma lesão (capítulo XIX, S00–T98) e a causa externa W00–W19 está em
    algum campo secundário (DIAG_SECUN, DIAGSEC1–9). Internação por outro motivo com a queda só
    registrada como informação adicional não é caso.
    """
    return bool(INJURY.match(_code(record, "DIAG_PRINC"))) and any(
        FALL.match(_code(record, f)) for f in DIAG_FIELDS[1:])


def _int(value, default=-1):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def profile_of(record):
    """Categoria de cada dimensão do perfil (vocabulário em analytics/profile.py)."""
    principal = _code(record, "DIAG_PRINC")[:3]
    injury = principal if principal in INJURY_CODES else f"{principal[:1]}_outras"
    fall = next((_code(record, f)[:3] for f in DIAG_FIELDS[1:] if FALL.match(_code(record, f))), "W19")
    date = str(record.get("DT_INTER") or "").strip()
    try:
        day = dt.date(int(date[:4]), int(date[4:6]), int(date[6:8]))
        month, weekday = f"{day.month:02d}", str(day.weekday())
    except (ValueError, IndexError):
        month = weekday = "ign"
    urgency = {"01": "eletivo", "02": "urgencia"}.get(str(record.get("CAR_INT") or "").strip(), "outros")
    exit_code = _int(record.get("COBRANCA"))
    exit_ = ("alta" if 11 <= exit_code <= 19 else "permanencia" if 21 <= exit_code <= 28 else
             "transferencia" if exit_code in (29, 31, 32) else "obito" if 41 <= exit_code <= 43 else "outros")
    nature = {"1": "publico", "2": "privado", "3": "sem_fins"}.get(str(record.get("NAT_JUR") or "").strip()[:1], "outros")
    race = {1: "branca", 2: "preta", 3: "parda", 4: "amarela", 5: "indigena"}.get(_int(record.get("RACA_COR")), "sem_info")
    procedure = {"03": "clinico", "04": "cirurgico"}.get(str(record.get("PROC_REA") or "").strip()[:2], "outros")
    return {"injury": injury, "fall": fall, "month": month, "weekday": weekday, "urgency": urgency,
            "procedure": procedure, "uti": "com_uti" if _int(record.get("UTI_MES_TO"), 0) > 0 else "sem_uti",
            "exit": exit_, "nature": nature, "race": race}


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


def _add(counter, record):
    counter["admissions"] += 1
    counter["deaths"] += str(record.get("MORTE") or "").strip() in ("1", "1.0")
    counter["stay_days"] += int(number(record.get("DIAS_PERM")))
    counter["stay_count"] += 1
    counter["approved_cents"] += round(number(record.get("VAL_TOT")) * 100)


def aggregate(records):
    """Agrega AIHs em ({(ano, uf, faixa, sexo): componentes}, exclusões por ano, extras).

    `extras` = {"profile": {(ano, uf, faixa, sexo, dimensão, valor): componentes},
    "munic": {(ano, uf, código IBGE de 6 dígitos): componentes}}.
    """
    cells = defaultdict(lambda: Counter())
    excluded = defaultdict(Counter)
    extras = {"profile": defaultdict(Counter), "munic": defaultdict(Counter)}
    for record in records:
        if str(record.get("IDENT") or "").strip() not in ("1", "1.0"):
            continue  # só AIH normal; continuação de longa permanência não é nova internação
        if not has_fall_code(record):
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
        if not is_fall(record):
            excluded[year]["queda_sem_lesao_principal"] += 1  # queda registrada, internação por outro motivo
            continue
        sex = sex_of(record)
        _add(cells[(year, uf, band, sex)], record)
        for dim, value in profile_of(record).items():
            _add(extras["profile"][(year, uf, band, sex, dim, value)], record)
        _add(extras["munic"][(year, uf, str(record.get("MUNIC_RES")).strip()[:6])], record)
    return cells, excluded, extras


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
