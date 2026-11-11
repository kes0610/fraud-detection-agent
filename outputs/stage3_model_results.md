# Baseline vs. stronger model

## Baseline model: Logistic Regression

Logistic regression draws a straight-line (linear) boundary between fraud and non-fraud based on a weighted sum of the features. It's simple, fast, and easy to explain - a reasonable floor to measure the stronger model against.

Fraud is rare (3.5%), so a model can get 96.5% 'accuracy' by predicting 'not fraud' for everything and never catching a single fraud case - which is useless. That's why accuracy is never reported here: PR-AUC, precision and recall all specifically account for how rare the positive class (fraud) is.

We compare two ways of handling that imbalance:

- **Class weighting** - tell the model to treat each fraud example as more important than a non-fraud example when learning, roughly in proportion to how rare fraud is. No new rows are created.
- **Random oversampling** - literally duplicate fraud examples in the training set (only the training set - never the test set) until the two classes are equally represented.

### Logistic Regression + class weighting

- **PR-AUC: 0.1944** (threshold-independent; closer to 1.0 is better, a model that only guesses the 3.5% fraud rate at random scores about 0.035)
- At a provisional 0.5 cutoff - precision: 0.060, recall: 0.807
- Confusion matrix at 0.5 cutoff: TP=4115, FP=64338, FN=985, TN=78197

### Logistic Regression + random oversampling

- **PR-AUC: 0.1910** (threshold-independent; closer to 1.0 is better, a model that only guesses the 3.5% fraud rate at random scores about 0.035)
- At a provisional 0.5 cutoff - precision: 0.060, recall: 0.809
- Confusion matrix at 0.5 cutoff: TP=4126, FP=64488, FN=974, TN=78047

**Winner: class weighting** (higher PR-AUC) - this is the version we call "the baseline" from here on.

## Stronger model: XGBoost

XGBoost builds hundreds of small decision trees one after another, where each new tree focuses on correcting the previous trees' mistakes. We chose it over LightGBM (the other option in the plan) simply because it needed no extra system setup beyond a standard pip install, and it has native support for missing values and for weighting the rare class, both of which this dataset needs.

For imbalance, XGBoost uses class weighting too (`scale_pos_weight` = 27.5, i.e. treat one fraud example as worth about 27 non-fraud examples) - the same style of fix that won the baseline comparison above, now applied to a model built to use it well.

### XGBoost

- **PR-AUC: 0.4999** (threshold-independent; closer to 1.0 is better, a model that only guesses the 3.5% fraud rate at random scores about 0.035)
- At a provisional 0.5 cutoff - precision: 0.229, recall: 0.711
- Confusion matrix at 0.5 cutoff: TP=3628, FP=12197, FN=1472, TN=130338

## Comparison

XGBoost's PR-AUC (0.4999) vs. the baseline's (0.1944): a difference of +0.3055.
