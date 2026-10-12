# Data citations — London GDP-concentration analysis

Formal citation for the dataset used, identified by the **organization that collected /
published** it. Access date reflects when the data was retrieved for this analysis
(12 October 2026).

---

## Primary source

### United Kingdom — regional GDP by ITL region (London vs UK)
**Office for National Statistics (ONS).** (2026). *Regional economic activity by gross
domestic product, UK: 1998 to 2024* — dataset “Regional gross domestic product (GDP): all
ITL regions.” Newport, Wales: Office for National Statistics. Retrieved 12 October 2026, from
<https://www.ons.gov.uk/economy/grossdomesticproductgdp/datasets/regionalgrossdomesticproductallnutslevelregions>

*Tables used:*
- **Table 5** — Gross domestic product (GDP) at current market prices, £ million, by region.
- **Table 7** — Gross domestic product (GDP) per head at current market prices, £, by region.

*Geography:* London is the ITL1 region (ONS code `TLI`); “United Kingdom” is the workbook’s
national total (`UK`). ITL = International Territorial Levels, the ONS regional classification
that replaced the EU NUTS system.

*Statistical designation:* ONS Accredited Official Statistics.

*Derived measures* (computed in `ons.py`, not published directly by ONS):
- `share_of_uk_gdp_pct` = London GDP ÷ UK GDP × 100 (from Table 5).
- `gdp_per_head_index_uk100` = London GDP per head ÷ UK GDP per head × 100 (from Table 7).
Both are same-year nominal ratios. A common deflator cancels, but regional relative
prices can affect their trends. ONS cautions that GDP per head is affected by commuting;
it is not a measure of residents' incomes or output per worker.

Availability checked 12 October 2026: the 1998–2024 edition was published on
23 September 2026. ONS's geography-conversion notice states that ITL1 countries and
regions, including London, are unaffected by the lower-level suppressions.

*Supports:* `outputs/london/london_share_of_uk_gdp.png`,
`outputs/london/london_gdp_per_head_vs_uk.png`, and `data/london_gdp.csv`.
