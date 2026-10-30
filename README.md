# Pharma Promotion Response Analysis

**Do doctors who receive pharma payments prescribe more diabetes drugs than similar doctors who do not?**

An end-to-end analytics project that joins two large US government datasets (Medicare Part D prescribing and Open Payments), isolates the diabetes drug class, and measures how prescribing volume differs between paid and unpaid physicians, overall, by specialty, by state, and by payment size. The output is a set of charts, an Excel workbook of summary tables, and a plain-English findings file.

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-data%20wrangling-150458?logo=pandas&logoColor=white)
![statsmodels](https://img.shields.io/badge/statsmodels-OLS%20regression-4051b5)
![SQL](https://img.shields.io/badge/PostgreSQL-join%20in%20SQL-336791?logo=postgresql&logoColor=white)

> **Status note:** everything in `demo_outputs/` is generated from **simulated data** to verify the pipeline end to end. It is **not** a real finding. Real results are reported in the [Results](#results) section once the pipeline is run on the CMS files.

---

## Business Question

Pharma companies spend heavily on physician-facing promotion (meals, speaker fees, travel, consulting). A commercial or sales-operations team wants to know:

1. Is promotional spend associated with higher prescribing?
2. Does the relationship differ by specialty or geography?
3. Does more money correlate with more prescribing, or is there a threshold?
4. Where should a sales team focus, and how should they test it properly?

## Data

Both sources are free and public from [data.cms.gov](https://data.cms.gov). Use the **same program year** for both.

| Dataset | What it contains | Used for |
|---|---|---|
| Medicare Part D Prescribers, by Provider and Drug | Claims per prescriber (NPI) per drug, plus specialty and state | Outcome: diabetes prescription claims per doctor |
| Open Payments, General Payments | Payments from manufacturers to physicians, with the associated drug | Exposure: total payments tied to diabetes drugs per doctor |

Doctors are linked on **NPI** (National Provider Identifier). The diabetes class is defined by a curated list of 37 generic and brand names (metformin, sulfonylureas, DPP-4 inhibitors, SGLT2 inhibitors, GLP-1 agonists, insulins, and brands such as Januvia, Jardiance, Ozempic, Mounjaro, Lantus). It lives in `DRUGS` at the top of `prepare_data.py`.

## Approach

```
CMS Part D file ─┐
                 ├─► prepare_data.py ─► analysis_table.csv ─► analysis.py ─► charts + Excel + findings.txt
Open Payments ───┘   (or sql/join.sql)
```

**1. Data preparation (`prepare_data.py`)**
- Streams the very large CMS CSVs in 500k-row chunks, so they do not need to fit in memory.
- Filters both files to the diabetes drug class using a regex over the drug-name list.
- Aggregates to one row per doctor: total diabetes claims, total diabetes-linked payments, specialty, state.
- Left-joins payments onto prescribers, so doctors with no payments get `$0`.
- Optional `--states` flag (e.g. `TX,CA,FL`) to keep the working dataset small.
- Auto-detects the payments drug column, since CMS changes the exact name between years.

**2. SQL alternative (`sql/join.sql`)**
The same join written for PostgreSQL, for people who prefer to do the heavy lifting in the database.

**3. Cleaning (`analysis.py`)**
- Drops rows with missing NPI, specialty, state, or claims.
- Keeps doctors with at least one claim and removes duplicate NPIs.
- Keeps only specialties with **30 or more** doctors, so group comparisons are stable.

**4. Analysis (`analysis.py`)**
- **Paid vs. unpaid comparison:** average claims for each group and the percentage lift.
- **Segment cuts:** the same comparison by specialty and by state, with a **Welch's t-test** per segment (segments need at least 10 paid and 10 unpaid doctors).
- **Payment tiers:** No payment, up to $100, $100 to $1,000, over $1,000, with mean and median claims per tier.
- **Regression:** OLS on `log(claims) ~ log(1 + payment) + specialty + state` with **HC1 heteroskedasticity-robust standard errors**. The log-log form gives an elasticity-style effect and handles the heavy right skew in both variables. Specialty and state fixed effects control for the obvious confounders: endocrinologists simply prescribe more diabetes drugs than other specialties.
- Reports the implied change in prescriptions going from $0 to $100 and from $0 to $1,000 in payments.

## Outputs

| File | Description |
|---|---|
| `chart1_payment_tiers.png` | Average prescriptions per doctor by payment tier |
| `chart2_lift_by_specialty.png` | Paid-vs-unpaid prescribing lift by specialty |
| `chart3_payments_vs_rx.png` | Payments vs. prescriptions for paid doctors, with trend line |
| `summary_tables.xlsx` | Sheets: Specialty summary, State summary, Payment tiers, Regression, Data sample |
| `findings.txt` | Auto-generated plain-English summary with the key numbers and caveat |

The Excel workbook is built to feed straight into Power BI or Excel pivot tables.

## Results

> Replace this section with your real numbers from `outputs/findings.txt` after running on the CMS data. Keep the structure; fill in the blanks.

- **Sample:** `___` doctors analysed, `__%` received at least one diabetes-related payment.
- **Overall:** paid doctors prescribe `__%` more diabetes drug claims on average than unpaid doctors.
- **By specialty:** the largest lift is in `________` (`+__%`); the smallest is in `________`.
- **Dose-response:** after controlling for specialty and state, moving from $0 to $100 in payments is associated with a `__%` change in prescriptions, and $0 to $1,000 with `__%` (coefficient `____`, p = `____`).
- **Recommendation:** `_____________` (for example, prioritise specialties with the highest lift for a controlled pilot).

## Limitations

This is an **observational association, not a causal estimate.**

- **Reverse causality / targeting:** companies likely pay doctors who already prescribe heavily, which would inflate the apparent effect.
- **Unobserved confounders:** practice size, patient mix, and prior prescribing history are not in the data.
- **Scope:** Part D covers Medicare prescriptions only, and payments are limited to those tied to diabetes drugs.

**Next step to measure true promotion effect:** a matched-region pilot or a before/after (difference-in-differences) design using prior-year prescribing as a baseline.

## Quick Start

```bash
git clone https://github.com/0xSiddu/pharma-promotion-response-analysis.git
cd pharma-promotion-response-analysis
pip install -r requirements.txt
```

**Test the pipeline on simulated data (not real findings):**
```bash
python analysis.py --demo --out demo_outputs
```

**Run on real CMS data:**
```bash
# 1. Build the analysis table from the raw CMS files
python prepare_data.py \
  --partd PartD_by_provider_drug.csv \
  --payments OP_DTL_GNRL_PGYR2023.csv \
  --out data \
  --states TX,CA,FL

# 2. (Optional) do the join in PostgreSQL instead
psql -d yourdb -f sql/join.sql

# 3. Analyse
python analysis.py --input data/analysis_table.csv --out outputs
```

If a newer CMS release renames a column, update the column constants at the top of `prepare_data.py` (`PARTD_COLS`, `PAY_NPI`, `PAY_AMT`).

## Project Structure

```
├── prepare_data.py     # Chunked ETL: raw CMS files -> analysis_table.csv
├── analysis.py         # Cleaning, stats, regression, charts, Excel, findings
├── sql/
│   └── join.sql        # PostgreSQL version of the join
├── demo_outputs/       # Outputs from SIMULATED data (pipeline test only)
├── requirements.txt
└── README.md
```

## Skills Demonstrated

Python (pandas, NumPy, SciPy, statsmodels, matplotlib) · SQL (PostgreSQL) · ETL on multi-GB files · hypothesis testing · log-log regression with fixed effects and robust standard errors · data visualisation · Excel / Power BI reporting · translating a statistical result into a business recommendation.

## Author

**Siddu** · [GitHub @0xSiddu](https://github.com/0xSiddu)
