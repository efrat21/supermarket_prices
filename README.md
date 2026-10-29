# Competition and Centralization in Israeli Supermarket Prices

An analysis of ~13M grocery price observations from six Israeli supermarket chains (Shufersal, Rami Levy, Victory, Yochananof, Yeinot Bitan, Osher Ad), built as a small, tested Python package.

**Question:** how competitive and concentrated is the Israeli food market, and where do price differences come from: chains, manufacturers, time, or geography?

**Data:** price-transparency data published by the non-profit *Lobby 99* on Kaggle (store-level prices, a manufacturer lookup, and a store directory).

## Quick start

```bash
pip install -r requirements.txt
# put the four input files in ./data (names are configurable in grocery_prices/config.py)
python -m grocery_prices --data-dir data --output-dir outputs
python -m grocery_prices --sample-frac 0.1      # fast dev run on 10% of rows
python -m unittest discover -s tests -t .       # tests run on synthetic data, no download needed
```

For a 2-minute walkthrough open `demo.ipynb`. It shows each result next to the key code behind it (printed live from the package source). Run it from the project root.

Outputs: `outputs/summary.json` (headline numbers), `outputs/tables/*.csv`, `outputs/figures/*.png`.

## Design

```
grocery_prices/
  config.py        Config dataclass: all paths and thresholds
  constants.py     Chain names, banner labels, district map, manufacturer translations
  data.py          IsraelPricesBuilder (DataLoader -> StoreCatalog -> PriceCleaner); DatasetBuilder interface
  analyzers.py     Analyzer (ABC) + 6 concrete analyses, each returns an AnalysisResult
  plotting.py      Plotter: result tables -> figures (no analysis logic)
  pipeline.py      GroceryPricePipeline: load -> clean -> analyse -> export
tests/             synthetic dataset generator + end-to-end tests
```

Each analysis is an `Analyzer` subclass with a single `run(df) -> AnalysisResult` method. Analyzers never plot or write files, the plotter never computes, and the pipeline only orchestrates. Adding an analysis means one new class and one line in `DEFAULT_ANALYZERS`. Analysing a different dataset means writing one new builder (anything with `build() -> DataFrame` in the standard column layout) and passing it to `GroceryPricePipeline(config, dataset_builder=...)`.

| Analyzer | Answers |
|---|---|
| `PriceDispersionAnalyzer` | How much does the price of the same item vary within a chain vs. between chains? |
| `PriceDriverAnalyzer` | What explains price: item, manufacturer, chain, city, time? |
| `SubChainComparator` | Which banners of one chain (e.g. Shufersal Deal vs. Express) are cheapest on identical items? |
| `PriceIndexAnalyzer` | How did each chain's price level change over time? |
| `ManufacturerConcentrationAnalyzer` | How concentrated is the product range (top-k share, HHI)? |
| `RegionalPriceAnalyzer` | Which districts are cheapest/most expensive, adjusted for product mix? |

## Methodology fixes over my first version

This project began as a Kaggle notebook. On revisiting it I found several problems that affect its conclusions, and fixed them:

1. **Time axis.** The notebook plotted prices by `PriceUpdateDate`, the date a price last *changed*, not the date it was observed. An item unchanged since 2013 shows up as a 2013 observation, so early periods contain only items whose prices barely moved. The default time axis is now `upload_date` (scrape date), configurable via `Config.time_column`. Consequently, the original "prices rose 100-150% over 10 years" claim is **not** reproduced by default and should be re-checked.
2. **Basket composition.** Averaging all prices per quarter changes whenever the product mix changes. `PriceIndexAnalyzer` builds a chained Jevons (matched-item) index and also returns the naive mean for comparison. On synthetic data with a known 2% quarterly inflation, the matched index recovers it while the naive mean does not.
3. **Regional comparison.** Mean price per district mixes geography with product and chain mix. Prices are now divided by the same item's average that year before aggregating.
4. **Feature importance.** The old approach ran mutual information with `discrete_features=True` on continuous data (several features got an identical meaningless score), treated `ItemCode` as a number, and used PCA without the target to claim what "drives price". It is replaced by cross-fitted target encoding with proper MI/F-test/correlation, plus a within-item variance decomposition that answers the real question: once you know the item, how much do chain, city and time add?
5. **Missing geography.** Dropping every row with any missing value removed all stores without a zip code (~20% of stores) from *every* analysis. Rows are now kept; only the regional analysis excludes them.
6. **Safer joins.** Positional assignment of geocoded zip codes is now verified against store keys; duplicate keys in lookup tables are removed before joining so rows cannot silently multiply.
7. **Manufacturer matching.** Ambiguous matches (certainty 0, where the lookup returned several candidates) are treated as unknown instead of becoming pseudo-manufacturers.
8. **Bug fixes / hygiene.** Removed a district dictionary that was defined but never used; replaced `pyearth` (unmaintained, fails to install on modern Python) with the explicit index; vectorised the row-by-row `store_code` loop; replaced deprecated APIs (`np.product`, `np.NaN`, chained assignment); renamed "SE" to what it actually is (coefficient of variation).

## Results

After running on the full dataset, `outputs/summary.json` holds the headline numbers. Add your findings here, with the figures from `outputs/figures/`.

## Known limitations

- Item codes are assumed to identify the same product across chains. Some chains use internal codes for non-barcoded goods, so cross-chain comparisons may mix different products. A GTIN-validity filter would tighten this.
- Price-transparency files list shelf prices, not promotions actually applied or quantities sold. This is a price-level analysis, not a consumer price index.
- District boundaries are approximated from zip-code prefixes.
- A strong claim about small chains "not reporting all prices" needs a coverage analysis (items per store over time) before it can be supported. The code exposes the pieces for it but the analysis is not included.
