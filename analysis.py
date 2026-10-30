#!/usr/bin/env python3
"""
Pharma Promotion Response Analysis
----------------------------------
Question: do doctors who receive pharma payments prescribe more diabetes drugs
than similar doctors who do not?

Input : analysis_table.csv with columns
        npi, specialty, state, rx_claims, total_payment
        (build it with prepare_data.py or sql/join.sql)
Output: charts (PNG), an Excel workbook of summary tables, findings.txt

Usage:
    python analysis.py --input analysis_table.csv --out outputs
    python analysis.py --demo --out demo_outputs     # SIMULATED data, for testing only
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

TIER_LABELS = ["No payment", "Up to $100", "$100 to $1,000", "Over $1,000"]
TEAL, AMBER, GREY = "#0f766e", "#d97706", "#94a3b8"


# ---------------------------------------------------------------- data
def demo_data(n=6000, seed=42):
    """Simulated data so the pipeline can be tested without the CMS files."""
    rng = np.random.default_rng(seed)
    specs = {"Endocrinology": (420, .20, .08), "Internal Medicine": (310, .12, .30),
             "Family Practice": (290, .10, .30), "Nurse Practitioner": (180, .07, .14),
             "Cardiology": (260, .15, .18)}
    names = list(specs)
    spec = rng.choice(names, size=n, p=[specs[k][2] for k in names])
    pay = np.where(rng.random(n) < .55, np.exp(3 + 1.8 * rng.standard_normal(n)), 0)
    base = np.array([specs[s][0] for s in spec])
    lift = np.array([specs[s][1] for s in spec])
    rx = np.round(base * (1 + .5 * lift * np.log10(1 + pay))
                  * np.exp(.35 * rng.standard_normal(n))).astype(int)
    return pd.DataFrame({"npi": 1_000_000_000 + np.arange(n), "specialty": spec,
                         "state": rng.choice(["TX", "CA", "FL", "NY", "OH"], size=n),
                         "rx_claims": rx, "total_payment": pay.round(2)})


def load_and_clean(path):
    df = pd.read_csv(path)
    need = {"npi", "specialty", "state", "rx_claims", "total_payment"}
    if not need.issubset(df.columns):
        raise SystemExit(f"Missing columns: {sorted(need - set(df.columns))}")
    n0 = len(df)
    df["total_payment"] = df["total_payment"].fillna(0).clip(lower=0)
    df = df.dropna(subset=["npi", "specialty", "state", "rx_claims"])
    df = df[df["rx_claims"] > 0].drop_duplicates("npi")
    keep = df["specialty"].value_counts()
    df = df[df["specialty"].isin(keep[keep >= 30].index)]
    print(f"Cleaning: {n0:,} rows -> {len(df):,} doctors kept")
    return df.reset_index(drop=True)


def add_tiers(df):
    df = df.copy()
    df["tier"] = pd.cut(df["total_payment"], [-0.01, 0, 100, 1000, np.inf],
                        labels=TIER_LABELS)
    df["paid"] = df["total_payment"] > 0
    return df


# ---------------------------------------------------------------- analysis
def group_summary(df, by):
    rows = []
    for key, g in df.groupby(by, observed=True):
        p, u = g[g.paid]["rx_claims"], g[~g.paid]["rx_claims"]
        if len(p) < 10 or len(u) < 10:
            continue
        pval = stats.ttest_ind(p, u, equal_var=False).pvalue
        rows.append({by: key, "doctors": len(g), "pct_paid": round(100 * g.paid.mean(), 1),
                     "avg_rx_unpaid": round(u.mean(), 1), "avg_rx_paid": round(p.mean(), 1),
                     "lift_pct": round((p.mean() / u.mean() - 1) * 100, 1),
                     "p_value": float(f"{pval:.3g}"),
                     "avg_payment_paid": round(g.loc[g.paid, "total_payment"].mean(), 2)})
    return pd.DataFrame(rows).sort_values("lift_pct", ascending=False)


def tier_summary(df):
    t = df.groupby("tier", observed=True).agg(doctors=("npi", "count"),
                                              avg_rx=("rx_claims", "mean"),
                                              median_rx=("rx_claims", "median")).round(1)
    return t.reset_index()


def regression(df):
    """log(rx) on log(1+payment), controlling for specialty and state."""
    m = smf.ols("np.log(rx_claims) ~ np.log1p(total_payment) + C(specialty) + C(state)",
                df).fit(cov_type="HC1")
    k = "np.log1p(total_payment)"
    b, (lo, hi), p = m.params[k], m.conf_int().loc[k], m.pvalues[k]
    eff = lambda x: (np.exp(b * np.log1p(x)) - 1) * 100
    table = pd.DataFrame({"term": [k, "R-squared", "Doctors"],
                          "value": [round(b, 4), round(m.rsquared, 3), int(m.nobs)],
                          "ci_low": [round(lo, 4), None, None],
                          "ci_high": [round(hi, 4), None, None],
                          "p_value": [float(f"{p:.3g}"), None, None]})
    return table, b, p, eff(100), eff(1000)


# ---------------------------------------------------------------- charts
def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", alpha=.25)
    ax.set_axisbelow(True)


def make_charts(df, tiers, spec, out, tag):
    # 1. tiers
    fig, ax = plt.subplots(figsize=(7, 4.2))
    cols = [GREY] + [TEAL] * 3
    bars = ax.bar([str(t).replace("$", r"\$") for t in tiers["tier"]], tiers["avg_rx"], color=cols)
    ax.bar_label(bars, fmt="%.0f", padding=3)
    ax.set_ylabel("Avg prescriptions per doctor")
    ax.set_title("Average prescriptions by payment tier" + tag, loc="left", fontweight="bold")
    style(ax)
    fig.tight_layout()
    fig.savefig(f"{out}/chart1_payment_tiers.png", dpi=180)
    plt.close(fig)

    # 2. lift by specialty
    s = spec.sort_values("lift_pct")
    fig, ax = plt.subplots(figsize=(7, 4.2))
    bars = ax.barh(s["specialty"], s["lift_pct"], color=TEAL)
    ax.bar_label(bars, fmt="+%.1f%%", padding=3)
    ax.set_xlabel("Paid vs. unpaid prescribing lift (%)")
    ax.set_title("Lift by specialty" + tag, loc="left", fontweight="bold")
    ax.grid(axis="x", alpha=.25)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig(f"{out}/chart2_lift_by_specialty.png", dpi=180)
    plt.close(fig)

    # 3. scatter with trend
    p = df[df.paid]
    x = np.log10(1 + p["total_payment"])
    samp = p.sample(min(2500, len(p)), random_state=1)
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.scatter(np.log10(1 + samp["total_payment"]), samp["rx_claims"], s=8,
               alpha=.3, color=TEAL)
    m, c = np.polyfit(x, p["rx_claims"], 1)
    xs = np.linspace(x.min(), x.max(), 50)
    ax.plot(xs, m * xs + c, color=AMBER, lw=2.5)
    ax.set_xticks([0, 1, 2, 3, 4])
    ax.set_xticklabels(["$0", "$10", "$100", "$1k", "$10k"])
    ax.set_xlabel("Total payments received (log scale)")
    ax.set_ylabel("Prescriptions")
    ax.set_title("Payments vs. prescriptions (paid doctors)" + tag, loc="left",
                 fontweight="bold")
    style(ax)
    fig.tight_layout()
    fig.savefig(f"{out}/chart3_payments_vs_rx.png", dpi=180)
    plt.close(fig)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="analysis_table.csv")
    ap.add_argument("--demo", action="store_true", help="use SIMULATED data")
    ap.add_argument("--out", default="outputs")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    if a.demo:
        df, tag = demo_data(), "  [SIMULATED DEMO DATA]"
        print("*** DEMO MODE: data is simulated, not real findings ***")
    elif a.input:
        df, tag = load_and_clean(a.input), ""
    else:
        raise SystemExit("Give --input analysis_table.csv or --demo")

    df = add_tiers(df)
    spec = group_summary(df, "specialty")
    state = group_summary(df, "state")
    tiers = tier_summary(df)
    reg, b, p, e100, e1000 = regression(df)
    overall = df[df.paid]["rx_claims"].mean() / df[~df.paid]["rx_claims"].mean() - 1

    make_charts(df, tiers, spec, a.out, tag)

    with pd.ExcelWriter(f"{a.out}/summary_tables.xlsx", engine="openpyxl") as xw:
        for name, t in [("Specialty summary", spec), ("State summary", state),
                        ("Payment tiers", tiers), ("Regression", reg),
                        ("Data sample", df.head(1000))]:
            t.to_excel(xw, sheet_name=name, index=False)
            ws = xw.sheets[name]
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = max(
                    12, min(30, max(len(str(c.value or "")) for c in col) + 2))

    top = spec.iloc[0]
    text = f"""FINDINGS{tag}
Doctors analysed: {len(df):,} ({df.paid.mean():.0%} received payments)
Overall: paid doctors' average prescriptions differ from unpaid doctors' by {overall:+.1%}.
Largest lift: {top['specialty']} ({top['lift_pct']:+.1f}%).
After controlling for specialty and state (regression): going from $0 to $100 in
payments is associated with a {e100:+.1f}% change in prescriptions, and $0 to $1,000
with a {e1000:+.1f}% change (coefficient {b:.4f}, p={p:.3g}).

CAVEAT: this is association, not causation. Companies may pay doctors who already
prescribe heavily. A matched-region pilot or before/after design would be needed
to estimate the true promotion effect.
"""
    open(f"{a.out}/findings.txt", "w").write(text)
    print(text)
    print(f"Saved charts, summary_tables.xlsx and findings.txt in {a.out}/")


if __name__ == "__main__":
    main()
