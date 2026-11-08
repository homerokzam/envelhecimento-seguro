"""Piloto: concilia o RD de 2024 (Brasil, DF, SP) com valores do TABNET preenchidos à mão.

Arquivo etl/pilot/tabnet_2024.csv com colunas: escopo,internacoes,obitos,dias_permanencia,valor_aprovado
(escopo = BR, DF ou SP; consulta TABNET: Causas externas → Quedas, por local de residência, 60+, 2024).
Diferença > 1% em internações bloqueia a carga completa.
"""
import csv
import json
from pathlib import Path

TOLERANCE = 0.01
PILOT_YEAR = 2024
TABNET = Path(__file__).parent / "pilot" / "tabnet_2024.csv"


def totals(cells):
    """Totais por escopo (BR, DF, SP) a partir de células {(ano, uf, faixa, sexo): contadores}."""
    result = {scope: {"internacoes": 0, "obitos": 0, "dias_permanencia": 0, "valor_aprovado": 0.0}
              for scope in ("BR", "DF", "SP")}
    for (year, uf, _age, _sex), c in cells.items():
        if year != PILOT_YEAR:
            continue
        for scope in ("BR", uf):
            if scope in result:
                result[scope]["internacoes"] += c["admissions"]
                result[scope]["obitos"] += c["deaths"]
                result[scope]["dias_permanencia"] += c["stay_days"]
                result[scope]["valor_aprovado"] += c["approved_cents"] / 100
    return result


def compare(ours, tabnet_path=TABNET):
    path = Path(tabnet_path)
    if not path.is_file():
        return {"ok": False, "reason": f"Preencha {path} com os valores do TABNET.", "scopes": {}}
    theirs = {}
    with path.open(encoding="utf-8-sig", newline="") as file:
        for r in csv.DictReader(file):
            theirs[r["escopo"].strip().upper()] = {k: float(r[k]) for k in
                                                    ("internacoes", "obitos", "dias_permanencia", "valor_aprovado")}
    scopes, ok = {}, True
    for scope, mine in ours.items():
        ref = theirs.get(scope)
        if ref is None:
            scopes[scope] = {"ok": False, "reason": "sem referência no TABNET"}
            ok = False
            continue
        diff = {k: (mine[k] - ref[k]) / ref[k] if ref[k] else None for k in ref}
        if ref["internacoes"] == 0:
            passed = mine["internacoes"] == 0
        else:
            passed = abs(diff["internacoes"]) <= TOLERANCE
        scopes[scope] = {"ok": passed, "rd": mine, "tabnet": ref, "diferenca_relativa": diff}
        ok = ok and passed
    return {"ok": ok, "tolerancia_internacoes": TOLERANCE, "ano": PILOT_YEAR, "scopes": scopes}


def write_report(report, directory):
    path = Path(directory) / "pilot_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
