import json
import tempfile
import unittest
from pathlib import Path

from grocery_prices import Config, GroceryPricePipeline

from .synthetic import QUARTERLY_INFLATION, make_dataset


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        make_dataset(root / "data")
        cls.config = Config(data_dir=root / "data", output_dir=root / "out", big_manufacturer_min_items=20)
        cls.pipeline = GroceryPricePipeline(cls.config)
        cls.df = cls.pipeline.build_dataset()
        cls.results = cls.pipeline.analyse(cls.df)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    # --- cleaning ---------------------------------------------------------
    def test_price_outliers_removed(self):
        self.assertTrue(self.df["price"].between(0.2, 200, inclusive="neither").all())

    def test_every_store_joined(self):
        self.assertEqual(self.df["sub_chain_id"].isna().sum(), 0)
        self.assertTrue(self.df["store_code"].astype(str).str.startswith("ram").any())

    def test_rami_levy_has_two_sub_chains(self):
        rami = self.df[self.df["chain"] == "ramiLevi"]
        self.assertEqual(set(rami["sub_chain_id"].dropna().astype(int)), {1, 2})

    def test_ambiguous_manufacturers_become_missing(self):
        self.assertNotIn("[]", set(self.df["manufacturer"].dropna().astype(str)))

    # --- analysis ---------------------------------------------------------
    def test_matched_index_recovers_known_inflation(self):
        """The fake data has exactly 2% inflation per quarter over 6 quarters."""
        expected = ((1 + QUARTERLY_INFLATION) ** 6 - 1) * 100
        change = self.results["price_index"].summary["matched_index_total_change_pct"]
        for chain, pct in change.items():
            self.assertAlmostEqual(pct, expected, delta=3, msg=chain)

    def test_prices_vary_more_between_chains_than_within(self):
        s = self.results["price_dispersion"].summary
        self.assertGreater(s["median_cv_between_chains_pct"], s["median_cv_within_chain_pct"])

    def test_all_analyzers_succeed_and_outputs_are_written(self):
        self.assertEqual(len(self.results), 6)
        self.pipeline.export(self.results)
        out = self.config.output_dir
        self.assertGreaterEqual(len(list((out / "figures").glob("*.png"))), 7)
        json.loads((out / "summary.json").read_text())


class ReuseTests(unittest.TestCase):
    """The pipeline must work with any builder that returns the standard table."""

    def test_custom_builder_runs_with_unchanged_analyzers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_dataset(root / "data")
            config = Config(data_dir=root / "data", output_dir=root / "out", big_manufacturer_min_items=20)
            frame = GroceryPricePipeline(config).build_dataset()

            class StubBuilder:  # stands in for "another country's loader + cleaner"
                def build(self):
                    return frame.copy()

            results = GroceryPricePipeline(config, dataset_builder=StubBuilder()).analyse(frame)
            self.assertEqual(len(results), 6)

    def test_wrong_schema_is_rejected_with_clear_message(self):
        class BadBuilder:
            def build(self):
                import pandas as pd
                return pd.DataFrame({"price": [1.0]})

        with self.assertRaisesRegex(ValueError, "missing standard columns"):
            GroceryPricePipeline(Config(), dataset_builder=BadBuilder()).build_dataset()


if __name__ == "__main__":
    unittest.main()
