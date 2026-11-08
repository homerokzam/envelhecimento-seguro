import csv
import tempfile
import unittest
from pathlib import Path

from analytics.data import FIELDS, Row, dashboard, load, metrics, parse_filters, reference_weights
from analytics.fixtures import demo_rows


class AnalyticsTests(unittest.TestCase):
    def test_aggregates_components_instead_of_averaging_rates(self):
        rows = [Row(2024, "DF", "60–69", "F", 10, 1000, 1, 40, 10, 10200),
                Row(2024, "DF", "70–79", "F", 20, 10000, 0, 20, 5, 19800)]
        result = metrics(rows)
        self.assertEqual(result["rate"], 272.73)
        self.assertEqual(result["meanStay"], 4)
        self.assertEqual(result["mortality"], 3.33)
        self.assertEqual(result["approved"], 300)

    def test_fixture_covers_all_territories_and_age_strata(self):
        rows = tuple(demo_rows())
        filters = parse_filters({"start": ["2024"], "end": ["2024"]})
        result = dashboard(rows, filters, {"demo": True}, reference_weights(rows))
        self.assertEqual(len(result["territories"]), 27)
        self.assertIsNotNone(result["summary"]["standardRate"])
        self.assertTrue(all(x["metrics"]["standardRate"] is None for x in result["ages"]))

    def test_distinguishes_zero_partial_and_missing(self):
        rows = [Row(2024, "DF", "60–69", "F", 0, 1000, 0, 0, 0, 0)]
        filters = parse_filters({"start": ["2024"], "end": ["2024"], "age": ["60–69"], "sex": ["F"]})
        result = dashboard(rows, filters, {}, None)
        self.assertTrue(result["summary"]["partial"])
        self.assertIsNone(result["summary"]["rate"])
        self.assertEqual(next(x for x in result["territories"] if x["key"] == "DF")["metrics"]["rate"], 0)
        self.assertIsNone(next(x for x in result["territories"] if x["key"] == "SP")["metrics"])

    def test_rejects_inverted_range_and_duplicate_query_parameter(self):
        for query in ({"start": ["2024"], "end": ["2015"]}, {"uf": ["DF", "SP"]}):
            with self.subTest(query=query), self.assertRaises(ValueError):
                parse_filters(query)

    def test_years_come_from_data_and_load_requires_a_file(self):
        rows = (Row(2025, "DF", "60–69", "F", 1, 1000, 0, 4, 1, 100),)
        self.assertEqual(parse_filters({}, (2024, 2025))["end"], 2024)
        self.assertEqual(parse_filters({}, (2025,))["start"], 2025)
        with self.assertRaises(ValueError):
            parse_filters({"start": ["2025"], "end": ["2024"]}, (2024, 2025))
        with self.assertRaises(ValueError):
            parse_filters({"end": ["2030"]}, (2024, 2025))
        self.assertEqual(dashboard(rows, parse_filters({}, (2025,)), {}, None)["options"]["years"], (2025,))
        with self.assertRaises(ValueError):
            load(None)

    def test_ignored_sex_counts_only_in_both(self):
        rows = [Row(2024, "DF", "60–69", "F", 10, 1000, 0, 0, 10, 0),
                Row(2024, "DF", "60–69", "M", 10, 1000, 0, 0, 10, 0),
                Row(2024, "DF", "60–69", "I", 5, 0, 0, 0, 5, 0)]
        base = {"start": ["2024"], "end": ["2024"], "uf": ["DF"], "age": ["60–69"]}
        both = dashboard(rows, parse_filters(base, (2024,)), {}, None)
        self.assertEqual(both["summary"]["admissions"], 25)
        self.assertFalse(both["summary"]["partial"])
        self.assertEqual(both["notes"]["ignoredSexAdmissions"], 5)
        female = dashboard(rows, parse_filters({**base, "sex": ["F"]}, (2024,)), {}, None)
        self.assertEqual(female["summary"]["admissions"], 10)

    def test_rejects_duplicate_csv_strata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(FIELDS)
                for _ in range(2):
                    writer.writerow([2024, "DF", "60–69", "F", 10, 1000, 1, 40, 10, 10200])
            with self.assertRaisesRegex(ValueError, "duplicado"):
                load(path)


if __name__ == "__main__":
    unittest.main()
