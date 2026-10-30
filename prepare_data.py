#!/usr/bin/env python3
"""
Build the analysis table from the two raw CMS files (reads them in chunks, so
the big files do not need to fit in memory).

Inputs (download from data.cms.gov):
  1. Medicare Part D Prescribers - by Provider and Drug   (one year)
  2. Open Payments - General Payment Data                 (same year)

Outputs (in --out):
  part_d_clean.csv        npi, specialty, state, generic_name, total_claims
  open_payments_clean.csv npi, amount_usd, drug_name_1
  analysis_table.csv      npi, specialty, state, rx_claims, total_payment

Usage:
  python prepare_data.py --partd PartD_by_provider_drug.csv \
                         --payments OP_DTL_GNRL_PGYR2023.csv --out data

Column names below are the ones CMS has used; open each file's header once and
adjust PARTD_COLS / the payment columns if a newer release renamed anything.
"""
import argparse
import os
import re

import pandas as pd

# Diabetes drug class: generic names (Part D) and brand/generic names (Open Payments)
DRUGS = ["metformin", "glipizide", "glimepiride", "glyburide", "pioglitazone",
         "sitagliptin", "linagliptin", "saxagliptin", "empagliflozin",
         "dapagliflozin", "canagliflozin", "semaglutide", "liraglutide",
         "dulaglutide", "tirzepatide", "insulin glargine", "insulin lispro",
         "insulin aspart", "insulin degludec",
         "januvia", "jardiance", "farxiga", "invokana", "tradjenta", "ozempic",
         "victoza", "trulicity", "mounjaro", "lantus", "toujeo", "basaglar",
         "tresiba", "novolog", "humalog", "rybelsus", "janumet", "synjardy"]
PATTERN = "|".join(re.escape(d) for d in DRUGS)

PARTD_COLS = {"Prscrbr_NPI": "npi", "Prscrbr_Type": "specialty",
              "Prscrbr_State_Abrvtn": "state", "Gnrc_Name": "generic_name",
              "Tot_Clms": "total_claims"}
PAY_NPI, PAY_AMT = "Covered_Recipient_NPI", "Total_Amount_of_Payment_USDollar"
CHUNK = 500_000


def drug_col(columns):
    """Find 'Name_of_Drug_or_Biological...Associated_1' whatever the year's exact name."""
    hits = [c for c in columns if c.startswith("Name_of_Drug_or_Biological") and c.endswith("_1")]
    if not hits:
        raise SystemExit("Could not find the associated-drug column in the payments file.")
    return hits[0]


def read_partd(path):
    parts = []
    for ch in pd.read_csv(path, usecols=list(PARTD_COLS), chunksize=CHUNK,
                          dtype={"Prscrbr_NPI": "int64"}):
        ch = ch.rename(columns=PARTD_COLS)
        parts.append(ch[ch["generic_name"].str.contains(PATTERN, case=False, na=False)])
    df = pd.concat(parts, ignore_index=True)
    print(f"Part D: {len(df):,} provider-drug rows for the diabetes class")
    return df


def read_payments(path):
    cols = pd.read_csv(path, nrows=0).columns
    dcol = drug_col(cols)
    parts = []
    for ch in pd.read_csv(path, usecols=[PAY_NPI, PAY_AMT, dcol], chunksize=CHUNK,
                          dtype={PAY_NPI: "float64"}):
        ch = ch.dropna(subset=[PAY_NPI])
        ch = ch[ch[dcol].str.contains(PATTERN, case=False, na=False)]
        ch = ch.rename(columns={PAY_NPI: "npi", PAY_AMT: "amount_usd", dcol: "drug_name_1"})
        ch["npi"] = ch["npi"].astype("int64")
        parts.append(ch.groupby(["npi", "drug_name_1"], as_index=False)["amount_usd"].sum())
    df = pd.concat(parts, ignore_index=True)
    df = df.groupby(["npi", "drug_name_1"], as_index=False)["amount_usd"].sum()
    print(f"Open Payments: {len(df):,} doctor-drug payment rows linked to the diabetes class")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--partd", required=True)
    ap.add_argument("--payments", required=True)
    ap.add_argument("--out", default="data")
    ap.add_argument("--states", default="", help="optional, e.g. TX,CA,FL to keep files small")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    pd_ = read_partd(a.partd)
    if a.states:
        pd_ = pd_[pd_["state"].isin(a.states.split(","))]
    pay = read_payments(a.payments)
    pd_.to_csv(f"{a.out}/part_d_clean.csv", index=False)
    pay.to_csv(f"{a.out}/open_payments_clean.csv", index=False)

    docs = (pd_.groupby("npi")
            .agg(specialty=("specialty", "first"), state=("state", "first"),
                 rx_claims=("total_claims", "sum")).reset_index())
    tot = pay.groupby("npi", as_index=False)["amount_usd"].sum().rename(
        columns={"amount_usd": "total_payment"})
    out = docs.merge(tot, on="npi", how="left")
    out["total_payment"] = out["total_payment"].fillna(0)
    out.to_csv(f"{a.out}/analysis_table.csv", index=False)
    print(f"analysis_table.csv: {len(out):,} doctors, "
          f"{(out.total_payment > 0).mean():.0%} received payments")


if __name__ == "__main__":
    main()
