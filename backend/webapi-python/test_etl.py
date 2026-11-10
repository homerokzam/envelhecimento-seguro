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
from etl.transform import UF_BY_CODE, age_band, aggregate, is_fall, profile_of, to_rows


def aih(**kw):
    base = {"ANO_CMPT": "2024", "IDENT": "1", "IDADE": "72", "COD_IDADE": "4", "SEXO": "3", "MUNIC_RES": "530010",
            "MORTE": "0", "DIAS_PERM": "5", "VAL_TOT": "1000.50", "DIAG_PRINC": "S720", "DIAG_SECUN": "W19"}
    base.update(kw)
    return base


class TransformTests(unittest.TestCase):
    def test_fall_needs_injury_principal_and_w_code_in_secondary_field(self):
        self.assertTrue(is_fall(aih()))
        self.assertTrue(is_fall(aih(DIAG_SECUN="", DIAGSEC3="W00")))
        self.assertTrue(is_fall(aih(DIAG_PRINC="T07", DIAG_SECUN="", DIAGSEC9="W19")))
        self.assertFalse(is_fall(aih(DIAG_SECUN="V01", DIAG_PRINC="S720")))
        self.assertFalse(is_fall(aih(DIAG_SECUN="W20")))
        # queda só como informação adicional de internação por outro motivo (critério do TABNET)
        self.assertFalse(is_fall(aih(DIAG_PRINC="J189", DIAG_SECUN="", DIAGSEC1="W19")))
        self.assertFalse(is_fall(aih(DIAG_PRINC="W19", DIAG_SECUN="")))

    def test_counts_fall_without_injury_as_exclusion_only_inside_the_study_population(self):
        other = aih(DIAG_PRINC="J189", DIAG_SECUN="W19")
        cells, excluded, _ = aggregate([aih(), other, aih(**{"IDADE": "40", "DIAG_PRINC": "J189"}),
                                     aih(MUNIC_RES="999999", DIAG_PRINC="J189")])
        self.assertEqual(sum(c["admissions"] for c in cells.values()), 1)
        self.assertEqual(excluded[2024]["queda_sem_lesao_principal"], 1)

    def test_age_bands_and_age_codes(self):
        self.assertEqual([age_band(a) for a in (59, 60, 69, 70, 79, 80, 105)],
                         [None, "60–69", "60–69", "70–79", "70–79", "80+", "80+"])
        cells, _, _ = aggregate([aih(COD_IDADE="3", IDADE="8"), aih(COD_IDADE="5", IDADE="3")])
        self.assertEqual(list(cells), [(2024, "DF", "80+", "F")])

    def test_counts_only_ident_1_and_tracks_exclusions(self):
        records = [aih(), aih(IDENT="5"), aih(IDADE=""), aih(MUNIC_RES="999999"), aih(SEXO="0", MORTE="1")]
        cells, excluded, _ = aggregate(records)
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


class ProfileTests(unittest.TestCase):
    def test_profile_of_maps_each_dimension(self):
        got = profile_of(aih(DT_INTER="20240217", CAR_INT="02", COBRANCA="15", RACA_COR="03", NAT_JUR="1023",
                             UTI_MES_TO="2", PROC_REA="0408050632", DIAG_SECUN="W01"))
        self.assertEqual(got, {"injury": "S72", "fall": "W01", "month": "02", "weekday": "5", "urgency": "urgencia",
                               "procedure": "cirurgico", "uti": "com_uti", "exit": "alta", "nature": "publico",
                               "race": "parda"})

    def test_profile_of_handles_missing_and_unknown_values(self):
        got = profile_of(aih(DIAG_PRINC="S999", DIAG_SECUN="", DIAGSEC2="W10", DT_INTER="", COBRANCA="", RACA_COR="99",
                             NAT_JUR="5002", PROC_REA="", CAR_INT="05"))
        self.assertEqual((got["injury"], got["fall"], got["month"], got["weekday"]), ("S_outras", "W10", "ign", "ign"))
        self.assertEqual((got["exit"], got["race"], got["nature"], got["procedure"], got["urgency"], got["uti"]),
                         ("outros", "sem_info", "outros", "outros", "outros", "sem_uti"))

    def test_every_dimension_sums_to_the_main_cell_and_to_the_municipality(self):
        records = [aih(), aih(MORTE="1", DIAG_PRINC="S065", DT_INTER="20240301"), aih(SEXO="0", MUNIC_RES="350010")]
        cells, _, extras = aggregate(records)
        for dim in ("injury", "fall", "month", "exit"):
            total = sum(c["admissions"] for k, c in extras["profile"].items() if k[4] == dim)
            self.assertEqual(total, 3)
        self.assertEqual(sum(c["deaths"] for k, c in extras["profile"].items() if k[4] == "injury"), 1)
        self.assertEqual({k[2]: c["admissions"] for k, c in extras["munic"].items()}, {"530010": 2, "350010": 1})

    def test_load_profile_rejects_a_dimension_that_does_not_close_with_the_base(self):
        from analytics.data import Row
        from analytics.profile import load_profile, PROFILE_FIELDS
        rows = (Row(2024, "DF", "70–79", "F", 2, 100, 0, 10, 2, 100),)
        header = ",".join(PROFILE_FIELDS)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "profile.csv"
            lines = [f"2024,DF,70–79,F,{dim},{value},{n},0,0,0,0" for dim, value, n in
                     [(dim, value, 2) for dim, value in (("injury", "S72"), ("fall", "W19"), ("month", "02"),
                      ("weekday", "0"), ("urgency", "urgencia"), ("procedure", "clinico"), ("uti", "sem_uti"),
                      ("exit", "alta"), ("nature", "publico"), ("race", "parda"))]]
            path.write_text(header + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
            self.assertEqual(len(load_profile(path, rows)), 10)
            path.write_text(header + "\n" + "\n".join(lines[:-1] + [lines[-1].replace(",2,0,0", ",1,0,0", 1)]) + "\n",
                            encoding="utf-8")
            with self.assertRaises(ValueError):
                load_profile(path, rows)


class CacheRuleTests(unittest.TestCase):
    def test_cache_is_reused_only_for_the_current_case_rule(self):
        import json
        import tempfile
        from etl import sources
        from etl.transform import CASE_RULE

        calls = []

        def fetch(*args):
            calls.append(args[:3])
            return [aih()]

        with tempfile.TemporaryDirectory() as d:
            sources.load_month("DF", 2024, 1, d, fetch=fetch)
            sources.load_month("DF", 2024, 1, d, fetch=fetch)
            self.assertEqual(len(calls), 1)  # segunda leitura veio do cache
            path = sources.agg_path(d, "DF", 2024, 1)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["rule"], CASE_RULE)
            saved.pop("rule")
            path.write_text(json.dumps(saved), encoding="utf-8")  # agregado de regra antiga
            sources.load_month("DF", 2024, 1, d, fetch=fetch)
            self.assertEqual(len(calls), 2)


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
    def setUp(self):
        from unittest import mock
        patcher = mock.patch.object(build, "municipality_names", return_value={"530010": "Brasília"})  # sem rede
        patcher.start()
        self.addCleanup(patcher.stop)

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
            from analytics.profile import load_municipalities, load_profile, municipalities_payload, profile_payload
            profile = load_profile(path.with_name("profile.csv"), rows)
            municipalities = load_municipalities(path.with_name("municipios.csv"), rows)
            filters = {"start": 2024, "end": 2024, "uf": "", "age": "", "sex": ""}
            injury = next(d for d in profile_payload(profile, filters)["dims"] if d["key"] == "injury")
            self.assertEqual([(i["key"], i["admissions"]) for i in injury["items"]], [("S72", 2)])
            top = municipalities_payload(municipalities, filters)["top"]
            self.assertEqual((top[0]["name"], top[0]["admissions"]), ("Brasília", 2))


    def test_sample_reads_only_given_ufs_and_never_zeroes_the_others(self):
        from analytics.data import STATES
        from etl.sources import expected_files

        self.assertEqual({uf for uf, _y, _m in expected_files([2024], ["DF"])}, {"DF"})
        self.assertEqual(len(expected_files([2024], ["DF", "GO"])), 24)

        def fetch(uf, year, month, cache):
            return ([aih(MUNIC_RES="530010")] * 2 + [aih(MUNIC_RES="355030")]) if (uf, month) == ("DF", 1) else []

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pop = root / "pop.csv"
            with pop.open("w", encoding="utf-8", newline="") as h:
                w = csv.writer(h)
                w.writerow(["year", "uf", "sex", "age", "population"])
                for uf in STATES:
                    for sex in "FM":
                        for age in (60, 70, 80):
                            w.writerow([2024, uf, sex, age, 1000])
            ref = root / "ref.csv"
            ref.write_text("escopo,internacoes,obitos,dias_permanencia,valor_aprovado\n"
                           "BR,2,0,10,2001\nDF,2,0,10,2001\nSP,0,0,0,0\n", encoding="utf-8")
            old = pilot.compare.__defaults__
            try:
                pilot.compare.__defaults__ = (ref,)
                manifest = build.run(directory=root / "data", population_csv=pop, fetch=fetch, years=[2024],
                                     ufs=["df", "GO"])
                with self.assertRaises(build.PilotBlocked):  # sem UF do piloto, não publica
                    build.run(directory=root / "data2", population_csv=pop, fetch=fetch, years=[2024], ufs=["GO"])
            finally:
                pilot.compare.__defaults__ = old
            self.assertEqual(manifest["sample"], {"ufs": ["DF", "GO"], "years": [2024]})
            self.assertEqual(set(manifest["pilot"]["scopes"]), {"DF"})
            path, _ = store.active(root / "data")
            self.assertEqual({r.uf for r in load(path)}, {"DF", "GO"})

    def _inputs(self, root, years=(2023, 2024)):
        from analytics.data import STATES
        pop = root / "pop.csv"
        with pop.open("w", encoding="utf-8", newline="") as h:
            w = csv.writer(h)
            w.writerow(["year", "uf", "sex", "age", "population"])
            for year in years:
                for uf in STATES:
                    for sex in "FM":
                        for age in (60, 70, 80):
                            w.writerow([year, uf, sex, age, 1000])
        ref = root / "ref.csv"
        ref.write_text("escopo,internacoes,obitos,dias_permanencia,valor_aprovado\n"
                       "BR,2,0,10,2001\nDF,2,0,10,2001\nSP,0,0,0,0\n", encoding="utf-8")
        return pop, ref

    def test_years_load_in_order_publishing_each_year(self):
        calls, published, seen = [], [], []

        def fetch(uf, year, month, cache):
            calls.append((year, uf, month))
            return [aih(MUNIC_RES="530010")] * 2 if (uf, year, month) == ("DF", 2024, 1) else []

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pop, ref = self._inputs(root)
            old = pilot.compare.__defaults__
            try:
                pilot.compare.__defaults__ = (ref,)

                def on_publish():
                    manifest = store.active(root / "data")[1]
                    published.append((manifest["years"], manifest["partialLoad"]))

                manifest = build.run(directory=root / "data", population_csv=pop, fetch=fetch, years=[2023, 2024],
                                     ufs=["DF", "GO"], workers=2, on_publish=on_publish,
                                     progress=lambda done, total, stage, **detail: seen.append(detail.get("year")))
            finally:
                pilot.compare.__defaults__ = old
            self.assertEqual(published, [([2023], True), ([2023, 2024], False)])
            self.assertEqual(manifest["years"], [2023, 2024])
            years_called = [c[0] for c in calls]
            self.assertEqual(years_called, sorted(years_called))  # 2023 inteiro antes de 2024
            self.assertEqual(len(calls), 2 * 12 * 2)
            self.assertIn(2023, seen)
            self.assertEqual(sorted(a for a in seen if a), [a for a in seen if a])  # andamento só avança

    def test_failure_in_current_year_keeps_previous_years_published(self):
        def fetch(uf, year, month, cache):
            if year == 2024 and uf == "GO":
                raise RuntimeError("arquivo indisponível")
            return []

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pop, ref = self._inputs(root)
            old = pilot.compare.__defaults__
            try:
                pilot.compare.__defaults__ = (ref,)
                with self.assertRaises(build.PilotBlocked):  # 2024 (piloto) não concluiu: não publica a carga final
                    build.run(directory=root / "data", population_csv=pop, fetch=fetch, years=[2023, 2024],
                              ufs=["DF", "GO"], workers=2)
            finally:
                pilot.compare.__defaults__ = old
            self.assertEqual(store.active(root / "data")[1]["years"], [2023])  # 2023 já estava no ar

    def test_failure_in_a_past_year_aborts_without_publishing(self):
        def fetch(uf, year, month, cache):
            raise RuntimeError("arquivo indisponível")

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pop, _ref = self._inputs(root)
            with self.assertRaises(RuntimeError):
                build.run(directory=root / "data", population_csv=pop, fetch=fetch, years=[2023, 2024],
                          ufs=["DF", "GO"], workers=2)
            self.assertIsNone(store.active(root / "data"))


if __name__ == "__main__":
    unittest.main()
