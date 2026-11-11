-- QUESTION: Which columns are missing data, and how much?
--
-- Why this matters: a model can't use a column that's empty most of the time without
-- some kind of handling, and a column that's ALWAYS missing for fraud (or always
-- missing for non-fraud) could either be a useful signal or a data problem. This is
-- a first look only - the full column-by-column check across all ~434 columns is
-- Stage 2's job (a dedicated data-quality script), not something to eyeball by hand
-- here. This query covers the named (non-anonymized) columns only.

SELECT
    'card2' AS column_name, SUM(CASE WHEN card2 IS NULL THEN 1 ELSE 0 END) AS missing_count,
    ROUND(100.0 * SUM(CASE WHEN card2 IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS missing_pct
FROM transactions
UNION ALL
SELECT 'card4', SUM(CASE WHEN card4 IS NULL THEN 1 ELSE 0 END),
    ROUND(100.0 * SUM(CASE WHEN card4 IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM transactions
UNION ALL
SELECT 'addr1', SUM(CASE WHEN addr1 IS NULL THEN 1 ELSE 0 END),
    ROUND(100.0 * SUM(CASE WHEN addr1 IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM transactions
UNION ALL
SELECT 'dist1', SUM(CASE WHEN dist1 IS NULL THEN 1 ELSE 0 END),
    ROUND(100.0 * SUM(CASE WHEN dist1 IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM transactions
UNION ALL
SELECT 'dist2', SUM(CASE WHEN dist2 IS NULL THEN 1 ELSE 0 END),
    ROUND(100.0 * SUM(CASE WHEN dist2 IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM transactions
UNION ALL
SELECT 'P_emaildomain', SUM(CASE WHEN P_emaildomain IS NULL THEN 1 ELSE 0 END),
    ROUND(100.0 * SUM(CASE WHEN P_emaildomain IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM transactions
UNION ALL
SELECT 'R_emaildomain', SUM(CASE WHEN R_emaildomain IS NULL THEN 1 ELSE 0 END),
    ROUND(100.0 * SUM(CASE WHEN R_emaildomain IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM transactions
UNION ALL
SELECT 'DeviceType', SUM(CASE WHEN DeviceType IS NULL THEN 1 ELSE 0 END),
    ROUND(100.0 * SUM(CASE WHEN DeviceType IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM transactions
UNION ALL
SELECT 'DeviceInfo', SUM(CASE WHEN DeviceInfo IS NULL THEN 1 ELSE 0 END),
    ROUND(100.0 * SUM(CASE WHEN DeviceInfo IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM transactions
ORDER BY missing_pct DESC;
