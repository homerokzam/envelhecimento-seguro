"""Piloto: concilia o RD de 2024 (Brasil, DF, SP) com valores do TABNET preenchidos à mão.

Arquivo etl/pilot/tabnet_2024.csv com colunas: escopo,internacoes,obitos,dias_permanencia,valor_aprovado
(escopo = BR, DF ou SP; consulta TABNET: Causas externas → Quedas, por local de residência, 60+, 2024).
Diferença > 1% em internações bloqueia a carga completa.
"""
import csv
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

TOLERANCE = 0.01
PILOT_YEAR = 2024
TABNET = Path(__file__).parent / "pilot" / "tabnet_2024.csv"


SCOPES = ("BR", "DF", "SP")


def totals(cells, scopes=SCOPES):
    """Totais por escopo (BR, DF, SP) a partir de células {(ano, uf, faixa, sexo): contadores}.

    Numa amostra de UFs, só os escopos cobertos entram (BR exige as 27 UFs).
    """
    result = {scope: {"internacoes": 0, "obitos": 0, "dias_permanencia": 0, "valor_aprovado": 0.0}
              for scope in scopes}
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
        log.error("Piloto: arquivo de referência ausente: %s", path)
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
        pct = diff["internacoes"]
        log.log(logging.INFO if passed else logging.ERROR,
                "Piloto %s: %s | internações RD=%s TABNET=%s diferença=%s (tolerância %.1f%%) | óbitos RD=%s TABNET=%s",
                scope, "OK" if passed else "DIVERGENTE", mine["internacoes"], ref["internacoes"],
                "n/d" if pct is None else f"{pct:+.2%}", TOLERANCE * 100, mine["obitos"], ref["obitos"])
        ok = ok and passed
    return {"ok": ok, "tolerancia_internacoes": TOLERANCE, "ano": PILOT_YEAR, "scopes": scopes}


def write_report(report, directory):
    path = Path(directory) / "pilot_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
