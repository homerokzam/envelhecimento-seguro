import csv
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from analytics import store
from analytics.data import FIELDS, load
from etl import build, pilot
from etl.population import fetch_tabnet, parse_tabnet
from etl.transform import UF_BY_CODE, age_band, aggregate, is_fall, to_rows


def aih(**kw):
    base = {"ANO_CMPT": "2024", "IDENT": "1", "IDADE": "72", "COD_IDADE": "4", "SEXO": "3", "MUNIC_RES": "530010",
            "MORTE": "0", "DIAS_PERM": "5", "VAL_TOT": "1000.50", "DIAG_PRINC": "S720", "DIAG_SECUN": "W19"}
    base.update(kw)
    return base


class TransformTests(unittest.TestCase):
    def test_fall_in_any_diagnosis_field_not_only_principal(self):
        self.assertTrue(is_fall(aih()))
        self.assertTrue(is_fall(aih(DIAG_SECUN="", DIAGSEC3="W00")))
        self.assertFalse(is_fall(aih(DIAG_SECUN="V01", DIAG_PRINC="S720")))
        self.assertFalse(is_fall(aih(DIAG_SECUN="W20")))

    def test_age_bands_and_age_codes(self):
        self.assertEqual([age_band(a) for a in (59, 60, 69, 70, 79, 80, 105)],
                         [None, "60–69", "60–69", "70–79", "70–79", "80+", "80+"])
        cells, _ = aggregate([aih(COD_IDADE="3", IDADE="8"), aih(COD_IDADE="5", IDADE="3")])
        self.assertEqual(list(cells), [(2024, "DF", "80+", "F")])

    def test_counts_only_ident_1_and_tracks_exclusions(self):
        records = [aih(), aih(IDENT="5"), aih(IDADE=""), aih(MUNIC_RES="999999"), aih(SEXO="0", MORTE="1")]
        cells, excluded = aggregate(records)
        self.assertEqual(cells[(2024, "DF", "70–79", "F")]["admissions"], 1)
        self.assertEqual(cells[(2024, "DF", "70–79", "I")]["deaths"], 1)
        self.assertEqual(excluded[2024]["idade_ignorada"], 1)
        self.assertEqual(excluded[2024]["residencia_invalida_ou_exterior"], 1)
        self.assertEqual(cells[(2024, "DF", "70–79", "F")]["approved_cents"], 100050)

    def test_missing_population_is_never_filled_with_zero(self):
        rows, missing = to_rows({}, {(2024, "DF", "60–69", "F"): 1000}, [2024])
        self.assertEqual(rows, [(2024, "DF", "60–69", "F", 0, 1000, 0, 0, 0, 0)])
        self.assertEqual(len(missing), 27 * 3 * 2 - 1)


TABNET_SAMPLE = '<PRE>\n"Unidade da Federa&ccedil;&atilde;o";"60 a 69 anos";"70 a 79 anos";"80 anos e mais";"Total"\n' + "".join(
    f'"{code} X";{i + 1}0;{i + 1}1;{i + 1}2;{(i + 1) * 3}\n' for i, code in enumerate(UF_BY_CODE)) + '"Total";1;1;1;3\n&\n</PRE>'


class PopulationTests(unittest.TestCase):
    def test_parses_tabnet_table_by_uf_code_and_band(self):
        got = parse_tabnet(TABNET_SAMPLE, 2024, "F")
        self.assertEqual(len(got), 81)
        self.assertEqual(got[(2024, "RO", "60–69", "F")], 10)
        self.assertEqual(got[(2024, "DF", "80+", "F")], 27 * 10 + 2)

    def test_rejects_incomplete_response(self):
        with self.assertRaises(ValueError):
            parse_tabnet(TABNET_SAMPLE.replace('"53 X";270;271;272;81\n', ""), 2024, "M")

    def test_fetch_caches_and_does_not_repeat_requests(self):
        calls = []
        with tempfile.TemporaryDirectory() as d:
            def post(year, sex):
                calls.append((year, sex))
                return TABNET_SAMPLE
            first = fetch_tabnet([2024], d, post=post)
            fetch_tabnet([2024], d, post=post)
        self.assertEqual(len(first), 162)
        self.assertEqual(sorted(calls), [(2024, "F"), (2024, "M")])


class PilotAndBuildTests(unittest.TestCase):
    def tabnet(self, directory, value):
        path = Path(directory) / "tabnet.csv"
        path.write_text("escopo,internacoes,obitos,dias_permanencia,valor_aprovado\n"
                        f"BR,{value},0,0,0\nDF,{value},0,0,0\nSP,0,0,0,0\n", encoding="utf-8")
        return path

    def test_pilot_gate_uses_one_percent_tolerance(self):
        cells = {(2024, "DF", "60–69", "F"): Counter(admissions=1000)}
        ours = pilot.totals(cells)
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(pilot.compare(ours, self.tabnet(d, 1005))["scopes"]["DF"]["ok"])
            self.assertFalse(pilot.compare(ours, self.tabnet(d, 1200))["scopes"]["DF"]["ok"])
            self.assertFalse(pilot.compare(ours, Path(d) / "inexistente.csv")["ok"])

    def test_build_publishes_atomically_and_blocks_on_divergence(self):
        def fetch(uf, year, month, cache):
            return [aih(MUNIC_RES="530010")] * 2 if (uf, month) == ("DF", 1) else []

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pop = root / "pop.csv"
            with pop.open("w", encoding="utf-8", newline="") as h:
                w = csv.writer(h)
                w.writerow(["year", "uf", "sex", "age", "population"])
                from analytics.data import STATES
                for uf in STATES:
                    for sex in "FM":
                        for age in (60, 70, 80):
                            w.writerow([2024, uf, sex, age, 1000])
            old = pilot.TABNET
            ok_ref = root / "ok.csv"
            ok_ref.write_text("escopo,internacoes,obitos,dias_permanencia,valor_aprovado\n"
                              "BR,2,0,10,2001\nDF,2,0,10,2001\nSP,0,0,0,0\n", encoding="utf-8")
            try:
                pilot.TABNET = root / "falta.csv"
                pilot.compare.__defaults__ = (root / "falta.csv",)
                with self.assertRaises(build.PilotBlocked):
                    build.run(directory=root / "data", population_csv=pop, fetch=fetch, years=[2024])
                self.assertIsNone(store.active(root / "data"))
                pilot.compare.__defaults__ = (ok_ref,)
                manifest = build.run(directory=root / "data", population_csv=pop, fetch=fetch, years=[2024])
            finally:
                pilot.TABNET = old
                pilot.compare.__defaults__ = (old,)
            path, saved = store.active(root / "data")
            self.assertEqual(saved["version"], manifest["version"])
            rows = load(path)
            self.assertEqual(sum(r.admissions for r in rows), 2)
            self.assertEqual(list(csv.reader(path.open()))[0], list(FIELDS))
            self.assertEqual(json.loads((path.parent / "manifest.json").read_text())["years"], [2024])


if __name__ == "__main__":
    unittest.main()
