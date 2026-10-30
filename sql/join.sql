-- Pharma promotion response: build analysis_table in PostgreSQL
-- Run from psql in the project folder:  psql -d yourdb -f sql/join.sql
-- Requires data/part_d_clean.csv and data/open_payments_clean.csv (from prepare_data.py)

DROP TABLE IF EXISTS part_d, open_payments, analysis_table;

CREATE TABLE part_d (
    npi           BIGINT,
    specialty     TEXT,
    state         CHAR(2),
    generic_name  TEXT,
    total_claims  INTEGER
);

CREATE TABLE open_payments (
    npi          BIGINT,
    drug_name_1  TEXT,
    amount_usd   NUMERIC(14,2)
);

\copy part_d FROM 'data/part_d_clean.csv' CSV HEADER
\copy open_payments FROM 'data/open_payments_clean.csv' CSV HEADER

CREATE INDEX ON part_d (npi);
CREATE INDEX ON open_payments (npi);

-- One row per doctor: prescriptions (Part D) LEFT JOIN payments (Open Payments).
-- LEFT JOIN keeps doctors with no payments; COALESCE turns their NULL into 0.
CREATE TABLE analysis_table AS
WITH doctors AS (
    SELECT npi,
           MAX(specialty)     AS specialty,
           MAX(state)         AS state,
           SUM(total_claims)  AS rx_claims
    FROM part_d
    GROUP BY npi
),
payments AS (
    SELECT npi, SUM(amount_usd) AS total_payment
    FROM open_payments
    GROUP BY npi
)
SELECT d.npi, d.specialty, d.state, d.rx_claims,
       COALESCE(p.total_payment, 0) AS total_payment
FROM doctors d
LEFT JOIN payments p USING (npi)
WHERE d.rx_claims > 0;

-- Sanity checks (look at these before trusting any result)
SELECT COUNT(*) AS doctors,
       ROUND(100.0 * AVG((total_payment > 0)::int), 1) AS pct_paid
FROM analysis_table;

-- The headline question in pure SQL: average prescriptions, paid vs unpaid, by specialty
SELECT specialty,
       COUNT(*) AS doctors,
       ROUND(AVG(rx_claims) FILTER (WHERE total_payment = 0), 1) AS avg_rx_unpaid,
       ROUND(AVG(rx_claims) FILTER (WHERE total_payment > 0), 1) AS avg_rx_paid,
       ROUND(100 * (AVG(rx_claims) FILTER (WHERE total_payment > 0)
                  / NULLIF(AVG(rx_claims) FILTER (WHERE total_payment = 0), 0) - 1), 1) AS lift_pct
FROM analysis_table
GROUP BY specialty
HAVING COUNT(*) >= 100
ORDER BY lift_pct DESC;

-- Export for analysis.py
\copy analysis_table TO 'data/analysis_table.csv' CSV HEADER
