"""População residente: projeção do Ministério da Saúde (SEIDIGI/DEMAS), edição 2024.

O arquivo é exportado do site do Ministério (ou do TABNET) e informado em
POPULATION_CSV. Nenhuma outra fonte é usada como substituta.

CSV UTF-8 com colunas: year,uf,sex,age,population
  uf = sigla; sex = F ou M; age = idade simples em anos (0..90; 90 = 90+); population = inteiro.
"""
import csv
from collections import defaultdict
from pathlib import Path

from analytics.data import AGES, STATES

EDITION = "Projeção MS/SEIDIGI/DEMAS, edição 2024"


TABNET_URL = "http://tabnet.datasus.gov.br/cgi/tabcgi.exe?ibge/cnv/projpop2024uf.def"
TABNET_BANDS = {"60 a 69 anos": AGES[0], "70 a 79 anos": AGES[1], "80 anos e mais": AGES[2]}
TABNET_SEX = {"M": "1", "F": "2"}


def _post(year, sex):
    import urllib.parse  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415

    body = [("Linha", "Unidade_da_Federação"), ("Coluna", "Faixa_Etária_2"), ("Incremento", "População_residente"),
            ("Arquivos", f"projuf{year % 100:02d}.dbf"), ("SSexo", TABNET_SEX[sex]),
            *(("SFaixa_Etária_2", code) for code in ("9", "10", "11")),
            ("SUnidade_da_Federação", "TODAS_AS_CATEGORIAS__"), ("formato", "prn"), ("mostre", "Mostra")]
    request = urllib.request.Request(TABNET_URL, data=urllib.parse.urlencode(body, encoding="latin-1").encode(),
                                     headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(request, timeout=90).read().decode("latin-1")


def parse_tabnet(text, year, sex):
    """Lê a tabela <PRE> do TABNET: linhas 'NN UF';60-69;70-79;80+;Total."""
    import html  # noqa: PLC0415
    import re  # noqa: PLC0415

    pre = re.search(r"<PRE>(.*?)</PRE>", text, re.S | re.I)
    if not pre:
        raise ValueError("Resposta do TABNET sem tabela de população.")
    from .transform import UF_BY_CODE  # noqa: PLC0415

    lines = [html.unescape(line).strip() for line in pre.group(1).splitlines() if line.strip().startswith('"')]
    header = [c.strip('"') for c in lines[0].split(";")]
    columns = {i: TABNET_BANDS[name] for i, name in enumerate(header) if name in TABNET_BANDS}
    if len(columns) != 3:
        raise ValueError("Faixas etárias inesperadas na resposta do TABNET.")
    result = {}
    for line in lines[1:]:
        cells = [c.strip('"') for c in line.split(";")]
        match = re.match(r"^(\d{2}) ", cells[0])
        if not match or match.group(1) not in UF_BY_CODE:
            continue  # linha de total
        for i, age in columns.items():
            result[(year, UF_BY_CODE[match.group(1)], age, sex)] = int(cells[i])
    if len(result) != 27 * 3:
        raise ValueError(f"TABNET devolveu {len(result)} estratos de população para {year}/{sex}; esperado 81.")
    return result


def fetch_tabnet(years, cache_dir, post=_post):
    """Projeção MS/IBGE edição 2024 do TABNET, por ano e sexo, com cache em JSON."""
    import json  # noqa: PLC0415

    path = Path(cache_dir) / "population_tabnet_2024.json"
    saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for year in years:
        for sex in ("F", "M"):
            key = f"{year}/{sex}"
            if key not in saved:
                saved[key] = {"|".join(map(str, k[1:3])): v for k, v in parse_tabnet(post(year, sex), year, sex).items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
    result = {}
    for key, strata in saved.items():
        year, sex = key.split("/")
        for stratum, value in strata.items():
            uf, age = stratum.split("|")
            result[(int(year), uf, age, sex)] = value
    return result


def band(age):
    return AGES[0] if age < 70 else AGES[1] if age < 80 else AGES[2]


def load_population(path):
    if not path or not Path(path).is_file():
        raise FileNotFoundError(
            "Informe POPULATION_CSV com a projeção populacional do Ministério da Saúde "
            "(edição 2024) por UF, sexo e idade simples. Formato: year,uf,sex,age,population.")
    total = defaultdict(int)
    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if set(reader.fieldnames or ()) != {"year", "uf", "sex", "age", "population"}:
            raise ValueError("POPULATION_CSV deve ter exatamente: year,uf,sex,age,population.")
        for line, r in enumerate(reader, 2):
            try:
                year, age, pop = int(r["year"]), int(r["age"]), int(r["population"])
            except ValueError as exc:
                raise ValueError(f"Linha {line}: número inválido.") from exc
            if r["uf"] not in STATES or r["sex"] not in ("F", "M") or pop < 0 or age < 0:
                raise ValueError(f"Linha {line}: UF, sexo ou valor inválido.")
            if age >= 60:
                total[(year, r["uf"], band(age), r["sex"])] += pop
    if not total:
        raise ValueError("POPULATION_CSV sem pessoas de 60 anos ou mais.")
    return dict(total)
