-- QUESTION: How big is the dataset, how much of it is fraud, and how much of it
-- actually has identity/device info attached?
--
-- Why this matters: before trusting any other number, we need to know the basic
-- shape of the data we're working with - how many rows, how rare fraud really is,
-- and how much of the data would have NULLs in every identity-related column
-- (since only a minority of transactions have a matching identity record).

SELECT
    COUNT(*) AS total_transactions,
    SUM(isFraud) AS fraud_transactions,
    ROUND(100.0 * SUM(isFraud) / COUNT(*), 2) AS fraud_rate_pct,
    SUM(CASE WHEN id_01 IS NOT NULL THEN 1 ELSE 0 END) AS transactions_with_identity_info,
    ROUND(100.0 * SUM(CASE WHEN id_01 IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_with_identity_info
FROM transactions;
