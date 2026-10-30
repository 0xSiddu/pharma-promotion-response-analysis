# Pharma Promotion Response Analysis

> **Note:** everything in `demo_outputs/` is generated from SIMULATED data to test the pipeline. It is not a real finding. Real results will be added after running on the CMS data.

> **Note:** everything in `demo_outputs/` is generated from SIMULATED data to test the pipeline. It is not a real finding. Real results will be added after running on the CMS data.

**Question:** Do doctors who receive pharma payments prescribe more diabetes drugs than similar doctors who do not?

**Data (free, US government):** Medicare Part D Prescribers by Provider and Drug, and Open Payments General Payments, both from data.cms.gov, same year.

## Run it

```bash
pip install pandas scipy statsmodels matplotlib openpyxl

# 0. Test the pipeline on SIMULATED data (not real findings)
python analysis.py --demo --out demo_outputs

# 1. Build the analysis table from the real CMS files
python prepare_data.py --partd PartD_by_provider_drug.csv --payments OP_DTL_GNRL_PGYR2023.csv --out data --states TX,CA,FL

# 2a. (optional) Do the join in PostgreSQL to show off SQL
psql -d yourdb -f sql/join.sql

# 3. Analyse the real data
python analysis.py --input data/analysis_table.csv --out outputs
```

Outputs: three charts (PNG), `summary_tables.xlsx` (specialty, state, payment tiers, regression), and `findings.txt`.

Open each CMS file's header once. If a column name differs from the one in `prepare_data.py`, change it at the top of that file.

## Then build in Power BI / Excel / slides
- Load `summary_tables.xlsx` into Power BI for the dashboard; use the Excel sheets for pivot tables.
- 3 to 4 slides: the question, the method, the key chart, the recommendation and caveat.

## How to explain it in the interview
1. **Business question:** does promotion influence prescribing, and where should a sales team focus?
2. **What I did:** joined two public datasets on doctor ID (SQL), filtered to the diabetes drug class, compared paid and unpaid doctors, and ran a regression controlling for specialty and state.
3. **Result:** quote your real numbers from `findings.txt`.
4. **Limits (say this yourself):** it is association, not causation. Companies may pay doctors who already prescribe heavily. Recommend a matched-region pilot.

Never present the `--demo` numbers as real findings.
