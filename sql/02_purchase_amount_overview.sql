-- QUESTION: How big are typical purchases in this dataset?
--
-- Why this matters: "TransactionAmt" is the dollar amount of the purchase. Before
-- we compare fraud vs. non-fraud, we need a sense of normal - what's a typical
-- purchase, and how spread out are the amounts (a few huge purchases can badly
-- distort a plain average, which is why we also look at the median and percentiles).

SELECT
    ROUND(MIN(TransactionAmt), 2) AS min_amt,
    ROUND(approx_quantile(TransactionAmt, 0.25), 2) AS p25_amt,
    ROUND(approx_quantile(TransactionAmt, 0.50), 2) AS median_amt,
    ROUND(AVG(TransactionAmt), 2) AS mean_amt,
    ROUND(approx_quantile(TransactionAmt, 0.75), 2) AS p75_amt,
    ROUND(approx_quantile(TransactionAmt, 0.99), 2) AS p99_amt,
    ROUND(MAX(TransactionAmt), 2) AS max_amt
FROM transactions;

-- Same thing, but broken out by ProductCD (the product category code for the
-- transaction - Kaggle doesn't say exactly what each letter means beyond that
-- it's a product/service category, so we treat these as opaque labels: W, C, R, H, S).
SELECT
    ProductCD,
    COUNT(*) AS num_transactions,
    ROUND(AVG(TransactionAmt), 2) AS mean_amt,
    ROUND(approx_quantile(TransactionAmt, 0.50), 2) AS median_amt,
    ROUND(100.0 * SUM(isFraud) / COUNT(*), 2) AS fraud_rate_pct
FROM transactions
GROUP BY ProductCD
ORDER BY num_transactions DESC;
