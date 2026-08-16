"""Write a concise, reproducible interpretation of the austerity data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .charts import BASE_YEAR, END_YEAR, indexed_function_series, trough_change

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SUMMARY = ROOT / "outputs" / "austerity" / "austerity_summary.md"


def build_summary(source, output: Path | str = DEFAULT_SUMMARY) -> Path:
    df = source.copy() if hasattr(source, "columns") else pd.read_csv(source)

    function_labels = {
        "housing_community": "Housing and community amenities",
        "recreation_culture": "Recreation, culture and religion",
        "public_order_safety": "Public order and safety",
        "defence": "Defence",
        "health": "Health",
    }
    lines = [
        "# UK austerity: public spending and investment",
        "",
        "The aggregate budget did not collapse uniformly. The deepest real-terms "
        "cuts were concentrated in particular public services and in investment, "
        "while health was protected.",
        "",
        "## Service spending during the austerity decade",
        "",
        "| Function | Deepest fall from 2010–11 | 2019–20 vs 2010–11 |",
        "|---|---:|---:|",
    ]
    for category, label in function_labels.items():
        trough, trough_year = trough_change(df, category)
        series = indexed_function_series(df, category)
        end_change = float(series.iloc[-1]["index"] - 100)
        lines.append(
            f"| {label} | {trough:.1f}% ({trough_year}) | {end_change:+.1f}% |"
        )

    investment = df[
        df["metric"] == "public_sector_net_investment_pct_gdp"
    ].set_index("financial_year")["value"]
    tme = df[df["metric"] == "total_managed_expenditure_real"].set_index(
        "financial_year"
    )["value"]
    inv_start = float(investment.loc[BASE_YEAR])
    inv_low_year = str(investment.loc[BASE_YEAR:END_YEAR].idxmin())
    inv_low = float(investment.loc[inv_low_year])
    tme_change = (float(tme.loc[END_YEAR]) / float(tme.loc[BASE_YEAR]) - 1) * 100

    lines.extend(
        [
            "",
            "## What the totals conceal",
            "",
            f"- **Total Managed Expenditure:** {tme_change:+.1f}% in real terms "
            f"between {BASE_YEAR} and {END_YEAR}. The headline total was broadly "
            "flat because it also includes social protection, debt interest and "
            "other annually managed spending.",
            f"- **Public sector net investment:** fell from **{inv_start:.1f}% of GDP** "
            f"in {BASE_YEAR} to **{inv_low:.1f}%** in {inv_low_year}.",
            "- **Distribution mattered:** housing/community spending fell by about "
            "a third at its trough, while health spending was essentially protected "
            "and then rose.",
            "",
            "The New York Times described the same pattern in 2019, quoting the "
            "Institute for Fiscal Studies: roughly **£40 billion of departmental "
            "spending cuts**, with some individual budgets down **30–40%**. That "
            "figure is contextual rather than reconstructed here; the chart uses "
            "HM Treasury's current, revised official outturn series.",
            "",
            "## Sources and caveats",
            "",
            "- HM Treasury, *Public Spending Statistics: July 2026*, Tables 4.1 and "
            "4.3 (Accredited Official Statistics). Real figures use the GDP deflator "
            "and are expressed in 2025–26 prices.",
            "- New York Times, “Britain’s Austerity Has Officially Ended. Not So Fast.”, "
            "24 February 2019.",
            "- Departmental budgets and broad TME are different concepts; this "
            "analysis does not treat the £40bn quotation as an observation in the "
            "Treasury time series.",
            "- Education is excluded from the comparison chart because Treasury warns "
            "that the removal of the grant-equivalent element of student loans creates "
            "a break between 2010–11 and 2011–12.",
        ]
    )

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n")
    return output
