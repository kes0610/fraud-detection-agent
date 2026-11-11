"""
Scores brand-new transactions (e.g. an uploaded CSV) with the already-trained
model - no retraining involved. Reuses the exact encoders fit during Stage 3's
training, saved to models/encoding_info.json, so new data goes through the
identical transformation the model was trained to expect.

Required input format: a CSV with the same columns as this project's own data
(see data_dictionary.md) - TransactionAmt, ProductCD, card1-card6, etc. A
template with the right columns can be exported from the dashboard.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import duckdb
import pandas as pd
import shap
import xgboost as xgb

from features import encode_new_rows, NON_FEATURE_COLUMNS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"

_model = None
_explainer = None
_feature_names = None
_encoding_info = None


def _load():
    global _model, _explainer, _feature_names, _encoding_info
    if _model is None:
        _model = xgb.Booster()
        _model.load_model(str(MODELS_DIR / "xgboost_model.json"))
        _explainer = shap.TreeExplainer(_model)
        _feature_names = json.loads((MODELS_DIR / "feature_names.json").read_text())
        _encoding_info = json.loads((MODELS_DIR / "encoding_info.json").read_text())
        if "frequency_maps" not in _encoding_info:
            raise RuntimeError(
                "models/encoding_info.json is from before encoders were saved - "
                "re-run train_stage3_models.py once to regenerate it."
            )
    return _model, _explainer, _feature_names, _encoding_info


def required_columns() -> list:
    """The columns an uploaded file must have (everything except the label/ID/time
    columns, which aren't needed to score new data)."""
    _, _, feature_names, encoding_info = _load()
    cols = set(encoding_info["numeric_passthrough"])
    cols |= set(encoding_info["low_cardinality_one_hot"])
    cols |= set(encoding_info["high_cardinality_frequency"])
    return sorted(cols)


def load_uploaded_csv(file_path: str) -> pd.DataFrame:
    """Reads an uploaded CSV through DuckDB's own CSV reader - NOT pandas'
    read_csv - so column types come out identical to how the original
    training data was loaded (critically: columns like M1-M9 are "T"/"F" text
    in the raw file, and DuckDB auto-detects those as real booleans; plain
    pandas would leave them as text, which would silently produce different,
    mismatched one-hot column names from what the model was trained on).

    One more wrinkle this guards against: DuckDB infers each column's type
    from the sample it's given. A small uploaded file (maybe just a handful
    of rows) can easily have a sparse numeric column (many of this dataset's
    anonymized columns are >70% missing) that's ALL empty in that small file -
    DuckDB then infers "text" instead of "number" for it, since there's no
    numeric value to see. Any column this project's training data says is
    numeric gets force-coerced back to numeric here, overriding that guess."""
    _, _, _, encoding_info = _load()
    con = duckdb.connect()
    df = con.execute("SELECT * FROM read_csv_auto(?)", [file_path]).fetchdf()

    numeric_cols = set(encoding_info["numeric_passthrough"]) | set(encoding_info["high_cardinality_frequency"])
    for col in numeric_cols & set(df.columns):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    float_cols = df.select_dtypes(include="float64").columns
    df[float_cols] = df[float_cols].astype("float32")
    return df


def score_transactions(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Takes a raw dataframe (same columns as this project's data) and returns
    it with a `fraud_probability` column added. Rows missing a required column
    get that column filled as missing (NaN), same as a column missing for any
    historical transaction - the model handles missing values natively."""
    model, _, feature_names, encoding_info = _load()
    for col in required_columns():
        if col not in raw_df.columns:
            raw_df[col] = pd.NA

    encoded = encode_new_rows(raw_df, encoding_info, feature_names)
    dmatrix = xgb.DMatrix(encoded, feature_names=feature_names)
    probabilities = model.predict(dmatrix)

    result = raw_df.copy()
    result["fraud_probability"] = probabilities
    return result.sort_values("fraud_probability", ascending=False)


def encode_single_row(raw_row: pd.Series) -> pd.Series:
    """Encodes one raw row into the model's feature space - used to compute
    live SHAP for a single uploaded transaction someone wants to investigate."""
    _, _, feature_names, encoding_info = _load()
    encoded = encode_new_rows(raw_row.to_frame().T, encoding_info, feature_names)
    return encoded.iloc[0]


def get_explainer():
    _, explainer, _, _ = _load()
    return explainer


def get_low_cardinality_columns() -> list:
    _, _, _, encoding_info = _load()
    return encoding_info["low_cardinality_one_hot"]
