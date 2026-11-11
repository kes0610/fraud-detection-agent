# Data quality report


## 1. Missing values

- 0 column(s) are 100% empty (completely unusable as-is).
- 214 column(s) are 50-99% missing (usable, but need a missing-value strategy before modeling).
- Full missing-value percentage for every column is in `outputs/stage2_missingness_by_column.csv`.


## 2. Duplicate records

- TransactionID is supposed to be a unique ID (a "primary key" - one row per transaction). Duplicated TransactionIDs in train_transaction.csv: **0**. In train_identity.csv: **0**.
- Fully duplicate rows (every column identical) in train_transaction.csv: **0**.


## 3. Unrealistic purchase amounts

- Transactions with a purchase amount of $0 or less (not possible for a real purchase): **0**.


## 4. Invalid category values

- `ProductCD`: no values outside the documented valid set. OK.

- `card4`: no values outside the documented valid set. OK.

- `card6`: no values outside the documented valid set. OK.


## 5. Join problems

- Rows in train_identity.csv whose TransactionID has no match in train_transaction.csv (would be silently dropped or cause problems): **0**.
