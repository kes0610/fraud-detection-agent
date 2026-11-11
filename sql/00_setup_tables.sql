-- STAGE 1 SETUP
--
-- What this does: loads the two raw CSV files into DuckDB as real tables (not just
-- reading the CSV fresh every time), then creates one combined view called
-- `transactions` that joins them together. Every later query in this project reads
-- from `transactions` instead of the raw files, so we only write the join logic once.
--
-- Why a LEFT JOIN (not a plain JOIN): only about 24% of transactions have a matching
-- row in train_identity.csv (device/identity info). A LEFT JOIN keeps every single
-- transaction, filling in NULL (empty) for the identity columns when there's no match.
-- A plain JOIN would silently throw away the other 76% of transactions, which would
-- badly skew anything we calculate.

CREATE TABLE IF NOT EXISTS raw_train_transaction AS
    SELECT * FROM read_csv_auto('data/raw/train_transaction.csv');

CREATE TABLE IF NOT EXISTS raw_train_identity AS
    SELECT * FROM read_csv_auto('data/raw/train_identity.csv');

CREATE OR REPLACE VIEW transactions AS
    SELECT
        t.*,
        i.* EXCLUDE (TransactionID)  -- drop identity's copy of TransactionID, we already have it from t
    FROM raw_train_transaction t
    LEFT JOIN raw_train_identity i USING (TransactionID);
