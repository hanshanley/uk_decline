"""Compute and report median & average tuition per region (UK vs EU vs US).

Reads ``data/processed/tuition_by_country.csv`` (produced by build_dataset.py), keeps
only primary per-country rows, and computes the median & average annual and four-year
tuition per region, in nominal (market-FX) USD and constant 2022 USD. Writes ``summary.csv`` and
prints a comparison table plus a verdict on the "UK has a higher average" claim.
"""

from __future__ import annotations

import csv

from tuition import config
from tuition.dataset import load_primary
from tuition.stats import aggregate_by_region, round_or_none

REGION_LABELS = config.REGION_LABELS
METRICS = [
    ("annual_tuition_usd", "USD (nominal, market FX)"),
    ("annual_tuition_usd_real2022", "Constant 2022 USD"),
]

VALUE_KEYS = [m[0] for m in METRICS]


def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"${v:,.0f}"


def build_summary(rows: list[dict]) -> list[dict]:
    summary: list[dict] = []
    for value_key, metric_label in METRICS:
        agg = aggregate_by_region(rows, value_key)
        for region in (config.UK, config.EU, config.US):
            stats = agg.get(region)
            if not stats:
                continue
            summary.append({
                "region": REGION_LABELS[region],
                "metric": metric_label,
                "n_countries": stats["n"],
                "mean_annual_usd": round_or_none(stats["mean_annual"]),
                "median_annual_usd": round_or_none(stats["median_annual"]),
                "mean_4yr_usd": round_or_none(stats["mean_4yr"]),
                "median_4yr_usd": round_or_none(stats["median_4yr"]),
            })
    return summary


def print_table(summary: list[dict]) -> None:
    header = f"{'Region':<7} {'Metric':<20} {'n':>3} {'Avg/yr':>9} {'Med/yr':>9} {'Avg 4yr':>10} {'Med 4yr':>10}"
    print("\n" + header)
    print("-" * len(header))
    for row in summary:
        print(
            f"{row['region']:<7} {row['metric']:<20} {row['n_countries']:>3} "
            f"{_fmt(row['mean_annual_usd']):>9} {_fmt(row['median_annual_usd']):>9} "
            f"{_fmt(row['mean_4yr_usd']):>10} {_fmt(row['median_4yr_usd']):>10}"
        )


def print_verdict(summary: list[dict]) -> None:
    nominal = {r["region"]: r for r in summary if r["metric"] == "USD (nominal, market FX)"}
    if not {"UK", "EU-27", "US"} <= nominal.keys():
        return
    uk, eu, us = nominal["UK"], nominal["EU-27"], nominal["US"]
    print("\nVerdict (nominal USD, annual domestic tuition):")
    print(f"  UK avg ${uk['mean_annual_usd']:,.0f}  |  EU-27 avg ${eu['mean_annual_usd']:,.0f}  |  US avg ${us['mean_annual_usd']:,.0f}")
    higher_than_eu = uk["mean_annual_usd"] > eu["mean_annual_usd"]
    higher_than_us = uk["mean_annual_usd"] > us["mean_annual_usd"]
    print(f"  UK vs EU-27: UK is {'HIGHER' if higher_than_eu else 'lower'}.")
    print(f"  UK vs US:    UK is {'HIGHER' if higher_than_us else 'lower'}.")


def main() -> None:
    rows = load_primary(VALUE_KEYS)
    summary = build_summary(rows)
    if not summary:
        print("[analyze] no primary tuition rows found; nothing to summarize.")
        return
    with open(config.SUMMARY_CSV, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)
    print(f"[analyze] wrote summary -> {config.SUMMARY_CSV}")
    print_table(summary)
    print_verdict(summary)


if __name__ == "__main__":
    main()
