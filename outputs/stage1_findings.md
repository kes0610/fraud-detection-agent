# Exploring the data with SQL


## `01_row_counts_and_join_coverage.sql`

QUESTION: How big is the dataset, how much of it is fraud, and how much of it
actually has identity/device info attached?

Why this matters: before trusting any other number, we need to know the basic
shape of the data we're working with - how many rows, how rare fraud really is,
and how much of the data would have NULLs in every identity-related column
(since only a minority of transactions have a matching identity record).

|   total_transactions |   fraud_transactions |   fraud_rate_pct |   transactions_with_identity_info |   pct_with_identity_info |
|---------------------:|---------------------:|-----------------:|----------------------------------:|-------------------------:|
|               590540 |                20663 |              3.5 |                            144233 |                    24.42 |


## `02_purchase_amount_overview.sql`

QUESTION: How big are typical purchases in this dataset?

Why this matters: "TransactionAmt" is the dollar amount of the purchase. Before
we compare fraud vs. non-fraud, we need a sense of normal - what's a typical
purchase, and how spread out are the amounts (a few huge purchases can badly
distort a plain average, which is why we also look at the median and percentiles).

|   min_amt |   p25_amt |   median_amt |   mean_amt |   p75_amt |   p99_amt |   max_amt |
|----------:|----------:|-------------:|-----------:|----------:|----------:|----------:|
|      0.25 |      43.1 |        69.83 |     135.03 |    124.63 |   1118.62 |   31937.4 |

Same thing, but broken out by ProductCD (the product category code for the
transaction - Kaggle doesn't say exactly what each letter means beyond that
it's a product/service category, so we treat these as opaque labels: W, C, R, H, S).

| ProductCD   |   num_transactions |   mean_amt |   median_amt |   fraud_rate_pct |
|:------------|-------------------:|-----------:|-------------:|-----------------:|
| W           |             439670 |     153.16 |        79.67 |             2.04 |
| C           |              68519 |      42.87 |        31.25 |            11.69 |
| R           |              37699 |     168.31 |       125.7  |             3.78 |
| H           |              33024 |      73.17 |        50    |             4.77 |
| S           |              11628 |      60.27 |        35.99 |             5.9  |


## `03_fraud_vs_nonfraud.sql`

QUESTION: How does a fraudulent transaction look different from a normal one?

Why this matters: this is the core question for the whole project - if fraud and
non-fraud transactions looked identical on every measurable column, there'd be
nothing for a model to learn. We're checking a handful of the columns we DO
understand (amount, product, card network, device type) for a visible gap.
We leave the anonymized V/C/D columns out of this query on purpose - their
names don't tell us what they mean, so we can't give a plain-English reading
of a difference in them yet (that's what SHAP, in Stage 5, is for).
Purchase amount: fraud vs. non-fraud

|   isFraud |   num_transactions |   mean_amt |   median_amt |   stddev_amt |
|----------:|-------------------:|-----------:|-------------:|-------------:|
|         0 |             569877 |     134.51 |        69.73 |       239.4  |
|         1 |              20663 |     149.24 |        74.25 |       232.21 |

Card network (card4: visa / mastercard / amex / discover): fraud rate by network

| card_network     |   num_transactions |   fraud_rate_pct |
|:-----------------|-------------------:|-----------------:|
| visa             |             384767 |             3.48 |
| mastercard       |             189217 |             3.43 |
| american express |               8328 |             2.87 |
| discover         |               6651 |             7.73 |
|                  |               1577 |             2.6  |

Device type (desktop vs. mobile, only known for the ~24% with identity info):
fraud rate by device

| DeviceType   |   num_transactions |   fraud_rate_pct |
|:-------------|-------------------:|-----------------:|
|              |             449730 |             2.1  |
| desktop      |              85165 |             6.52 |
| mobile       |              55645 |            10.17 |

Email domain presence: does having a purchaser email on file relate to fraud?

| has_purchaser_email   |   num_transactions |   fraud_rate_pct |
|:----------------------|-------------------:|-----------------:|
| present               |             496084 |             3.6  |
| missing               |              94456 |             2.95 |


## `04_missing_data_overview.sql`

QUESTION: Which columns are missing data, and how much?

Why this matters: a model can't use a column that's empty most of the time without
some kind of handling, and a column that's ALWAYS missing for fraud (or always
missing for non-fraud) could either be a useful signal or a data problem. This is
a first look only - the full column-by-column check across all ~434 columns is
Stage 2's job (a dedicated data-quality script), not something to eyeball by hand
here. This query covers the named (non-anonymized) columns only.

| column_name   |   missing_count |   missing_pct |
|:--------------|----------------:|--------------:|
| dist2         |          552913 |         93.63 |
| DeviceInfo    |          471874 |         79.91 |
| R_emaildomain |          453249 |         76.75 |
| DeviceType    |          449730 |         76.16 |
| dist1         |          352271 |         59.65 |
| P_emaildomain |           94456 |         15.99 |
| addr1         |           65706 |         11.13 |
| card2         |            8933 |          1.51 |
| card4         |            1577 |          0.27 |
