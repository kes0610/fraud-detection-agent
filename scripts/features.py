"""
Stage 3: shared feature engineering, used by every model-training script so
the baseline and the stronger model see exactly the same features.

What this does, in order:
  1. Loads the joined transactions table out of DuckDB into pandas.
  2. Splits it into "train" (older transactions) and "test" (newer transactions)
     by TransactionDT, BEFORE touching any encoding - this matters, see below.
  3. Turns text/category columns into numbers two different ways depending on
     how many distinct values they have:
       - Low-cardinality (<=15 values, e.g. ProductCD, card4, M1-M9): one-hot
         encoded - one new True/False column per category.
       - High-cardinality (e.g. DeviceInfo, email domains): frequency-encoded -
         each category is replaced by how often it appeared IN THE TRAINING SET.
         Rare or brand-new categories just get a low/zero number, which is a
         reasonable way to say "unusual."
  4. Leaves missing numeric values as NaN (empty) rather than filling them in -
     that decision is left to each model script, since different models want
     different handling (XGBoost handles NaN natively; logistic regression
     needs it filled in, so that script fills it in itself).

Why fit the encoders on the TRAINING set only: if we calculated "how often does
this email domain appear" using the whole dataset (train + test together), the
encoding for a training row would secretly depend on data from the future
(the test period). That's called data leakage - it makes a model look better
in testing than it will actually be once deployed, because test information
quietly leaked backwards into training. Fitting only on train and then
applying that same mapping to test avoids it.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOW_CARDINALITY_MAX = 15

# Columns that are IDs/labels/time, not predictive features in their raw form.
NON_FEATURE_COLUMNS = ["TransactionID", "isFraud", "TransactionDT"]


def load_raw_dataframe() -> pd.DataFrame:
    con = duckdb.connect(str(PROJECT_ROOT / "data" / "warehouse.duckdb"), read_only=True)
    con.execute("SET enable_progress_bar = false")
    df = con.execute("SELECT * FROM transactions").fetchdf()
    # Downcast to float32 to cut memory roughly in half; we don't need float64
    # precision for any of these features.
    float_cols = df.select_dtypes(include="float64").columns
    df[float_cols] = df[float_cols].astype("float32")
    return df


def time_based_split(df: pd.DataFrame, train_fraction: float = 0.75):
    """Sort by TransactionDT (chronological order) and take the earliest
    `train_fraction` of rows as train, the rest as test. This simulates
    deploying the model on transactions that happen AFTER the ones it was
    trained on - the real situation a fraud model faces in production -
    instead of a random split, which would let the model implicitly "see the
    future" (e.g. the same card appearing in both train and test)."""
    df_sorted = df.sort_values("TransactionDT").reset_index(drop=True)
    cutoff_index = int(len(df_sorted) * train_fraction)
    train_df = df_sorted.iloc[:cutoff_index]
    test_df = df_sorted.iloc[cutoff_index:]
    return train_df, test_df


def encode_features(train_df: pd.DataFrame, test_df: pd.DataFrame):
    """Fits categorical encoders on train_df only, applies to both. Returns
    (X_train, X_test, y_train, y_test, feature_names)."""
    y_train = train_df["isFraud"].astype(int)
    y_test = test_df["isFraud"].astype(int)

    feature_cols = [c for c in train_df.columns if c not in NON_FEATURE_COLUMNS]
    train_X = train_df[feature_cols].copy()
    test_X = test_df[feature_cols].copy()

    # Includes "boolean": DuckDB reads some True/False-style columns (e.g. M1-M9,
    # which are "T"/"F" match flags) in as native booleans, not text - those need
    # the same one-hot treatment as the text categorical columns, not to be left
    # as a numeric column where quantile/scaling math would try to run on them.
    categorical_cols = train_X.select_dtypes(include=["object", "boolean", "bool"]).columns.tolist()
    numeric_cols = [c for c in feature_cols if c not in categorical_cols]

    low_card, high_card = [], []
    for col in categorical_cols:
        if train_X[col].nunique(dropna=True) <= LOW_CARDINALITY_MAX:
            low_card.append(col)
        else:
            high_card.append(col)

    # High-cardinality columns: frequency-encode using TRAIN counts only.
    # The frequency maps are saved (not just used in-memory) so brand-new
    # transactions can later be encoded the exact same way without refitting -
    # see encode_new_rows() below.
    frequency_maps = {}
    for col in high_card:
        freq_map = train_X[col].value_counts()  # fit on train only
        frequency_maps[col] = freq_map.to_dict()
        train_X[col] = train_X[col].map(freq_map).astype("float32")
        test_X[col] = test_X[col].map(freq_map).astype("float32")  # unseen -> NaN

    # Low-cardinality columns: one-hot encode, aligning test's columns to train's
    # (a category missing from test, or appearing only in test, is handled by
    # reindexing so both matrices end up with identical columns).
    one_hot_columns = []
    if low_card:
        train_dummies = pd.get_dummies(train_X[low_card], dummy_na=True).astype("float32")
        test_dummies = pd.get_dummies(test_X[low_card], dummy_na=True).astype("float32")
        test_dummies = test_dummies.reindex(columns=train_dummies.columns, fill_value=0)
        train_X = pd.concat([train_X.drop(columns=low_card), train_dummies], axis=1)
        test_X = pd.concat([test_X.drop(columns=low_card), test_dummies], axis=1)
        one_hot_columns = train_dummies.columns.tolist()

    feature_names = train_X.columns.tolist()
    return train_X, test_X, y_train, y_test, feature_names, {
        "low_cardinality_one_hot": low_card,
        "high_cardinality_frequency": high_card,
        "numeric_passthrough": numeric_cols,
        "frequency_maps": frequency_maps,
        "one_hot_columns": one_hot_columns,
    }


def encode_new_rows(new_df: pd.DataFrame, encoding_info: dict, feature_names: list) -> pd.DataFrame:
    """Encodes brand-new, never-before-seen transaction rows (e.g. an uploaded
    file) into the exact same feature space the model was trained on, reusing
    the SAVED encoders from training - never refitting on the new data. Any
    category a new row has that training never saw is treated as "unseen"
    (NaN for a frequency column, all-zero for one-hot columns), the same way
    an unseen category in the original test set was handled."""
    df = new_df.copy()
    low_card = encoding_info["low_cardinality_one_hot"]
    high_card = encoding_info["high_cardinality_frequency"]
    numeric_cols = encoding_info["numeric_passthrough"]

    for col in high_card:
        freq_map = encoding_info["frequency_maps"][col]
        df[col] = df[col].map(freq_map).astype("float32")

    if low_card:
        dummies = pd.get_dummies(df[low_card], dummy_na=True).astype("float32")
        dummies = dummies.reindex(columns=encoding_info["one_hot_columns"], fill_value=0)
        df = pd.concat([df.drop(columns=low_card), dummies], axis=1)

    # Final reindex: guarantees identical columns/order to what the model expects,
    # even if the uploaded file is missing a column entirely (becomes NaN).
    return df.reindex(columns=feature_names)


def get_train_test_features(train_fraction: float = 0.75):
    df = load_raw_dataframe()
    train_df, test_df = time_based_split(df, train_fraction)
    X_train, X_test, y_train, y_test, feature_names, encoding_info = encode_features(train_df, test_df)
    test_meta = test_df[["TransactionID", "TransactionDT", "TransactionAmt"]].reset_index(drop=True)
    return X_train, X_test, y_train, y_test, feature_names, encoding_info, test_meta
