-- QUESTION: How does a fraudulent transaction look different from a normal one?
--
-- Why this matters: this is the core question for the whole project - if fraud and
-- non-fraud transactions looked identical on every measurable column, there'd be
-- nothing for a model to learn. We're checking a handful of the columns we DO
-- understand (amount, product, card network, device type) for a visible gap.
-- We leave the anonymized V/C/D columns out of this query on purpose - their
-- names don't tell us what they mean, so we can't give a plain-English reading
-- of a difference in them yet (that's what SHAP, in Stage 5, is for).

-- Purchase amount: fraud vs. non-fraud
SELECT
    isFraud,
    COUNT(*) AS num_transactions,
    ROUND(AVG(TransactionAmt), 2) AS mean_amt,
    ROUND(approx_quantile(TransactionAmt, 0.50), 2) AS median_amt,
    ROUND(STDDEV(TransactionAmt), 2) AS stddev_amt
FROM transactions
GROUP BY isFraud;

-- Card network (card4: visa / mastercard / amex / discover): fraud rate by network
SELECT
    card4 AS card_network,
    COUNT(*) AS num_transactions,
    ROUND(100.0 * SUM(isFraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions
GROUP BY card4
ORDER BY num_transactions DESC;

-- Device type (desktop vs. mobile, only known for the ~24% with identity info):
-- fraud rate by device
SELECT
    DeviceType,
    COUNT(*) AS num_transactions,
    ROUND(100.0 * SUM(isFraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions
GROUP BY DeviceType
ORDER BY num_transactions DESC;

-- Email domain presence: does having a purchaser email on file relate to fraud?
SELECT
    CASE WHEN P_emaildomain IS NULL THEN 'missing' ELSE 'present' END AS has_purchaser_email,
    COUNT(*) AS num_transactions,
    ROUND(100.0 * SUM(isFraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions
GROUP BY has_purchaser_email;
