# Glossary

Plain-English definitions of every technical term used in this project, in the order they
first came up. If you read a term here and still don't get it, ask — that's what this file
is for.

### Kaggle
A free website where people share datasets and write/run code in the browser for free,
without installing anything. Think of it like a mix of Dropbox (for datasets) and Google
Colab (for running code).

### Dataset vs. Competition (on Kaggle)
Kaggle hosts data two ways: a plain **Dataset** page (click Download, done) and a
**Competition** page (you have to "join" and agree to rules first, and old/closed
competitions sometimes add extra steps like a "late submission" agreement). Same data can
sometimes be found both ways — we're using a Dataset-page copy of this project's data to
skip the competition's extra steps.

### Repo (repository)
One project's folder on GitHub (a free website for storing code online with full history of
every change) — like a Google Drive folder, but for code, and with a record of who changed
what and when.

### git
The tool that tracks every change to the files in a repo on your own computer, before
anything is uploaded to GitHub. "Committing" means saving a labeled snapshot of your changes.

### Virtual environment (venv)
An isolated, project-specific copy of Python and its installed packages, so this project's
tools (like DuckDB) don't clash with tools used by other projects on the same computer. You
"activate" it before running project code.

### CSV
"Comma-Separated Values" — a plain text file that stores a table, like a simplified Excel
spreadsheet: one line per row, commas separating the columns.

### SQL
"Structured Query Language" — the standard language for asking questions of data stored in
tables, e.g. "show me the average purchase amount for fraud vs. non-fraud transactions."

### DuckDB
A free, lightweight tool that lets you run SQL directly on files on your own computer (like
our CSVs) without needing a database server. It's a small-scale stand-in for the kind of
SQL engines (Snowflake, Databricks, etc.) used at a real company.

### TransactionID
The unique ID number that identifies one transaction. It's the column used to join (match
up rows from) the two data files — `train_transaction.csv` and `train_identity.csv`.

### Anonymized column
A column whose real-world meaning has been hidden on purpose (e.g. columns named `V1`,
`V2`, ...) to protect sensitive business or customer information. We never guess what these
mean — we just say "meaning unknown (anonymized)."

### Fraud rate
The share of transactions that are actually fraud. In this dataset it's about 3.5% — meaning
fraud is rare, which turns out to matter a lot for how we build and judge the model (see
"class imbalance," added once we get to Stage 3).

### Data quality check
An automated check that looks for problems in a dataset before you trust it — things like
missing values, duplicate records, or values that don't make sense (a negative purchase
amount, for example). The point is to catch problems early, before they quietly throw off a
model later.

### Primary key
The column (or combination of columns) that's supposed to uniquely identify one row — no two
rows should ever share the same value. Here, `TransactionID` is the primary key: if the same
ID showed up twice, that would mean the same transaction got recorded twice by mistake.

### Duplicate record
Two or more rows that are exact copies of each other (every column matches). Usually a sign
of a data-collection or data-processing mistake, since each transaction should only appear once.

### Categorical column
A column whose values are labels/categories rather than numbers you'd do math on — like
`ProductCD` (W, C, R, H, S) or `card4` (visa, mastercard, etc.). You can count how often each
label appears, but "average ProductCD" wouldn't mean anything.

### Data dictionary
A reference document that lists every column in a dataset along with what it means, what
type of data it holds, and anything important to know about it (like whether it's sensitive).
Think of it as the "legend" for reading the data correctly.

### Model
A program that has learned patterns from past data (training data) well enough to make a
prediction on new data it hasn't seen before — here, predicting whether a new transaction is
likely fraud.

### Time-based split
Splitting data into a training set and a test set by TIME — train on older transactions,
test on newer ones — instead of randomly shuffling and splitting. This mimics how the model
will actually be used in real life (only ever seeing the past, predicting the future), and
avoids accidentally giving the model "hints" from the future during training.

### Data leakage
When information that wouldn't actually be available at prediction time accidentally sneaks
into training — e.g. letting a calculation "see" test-period data while preparing the
training set. It makes a model look better during testing than it will actually perform once
deployed, because it secretly got a peek at the answers.

### Logistic regression
A simple, fast prediction method that draws a straight-line (technically, a smooth S-curve)
boundary between two classes — here, fraud vs. not fraud — based on a weighted combination
of the input columns. It's a common first model to try: simple and explainable, used here as
the baseline to compare everything else against.

### XGBoost
A more powerful prediction method that builds many small decision trees one after another,
where each new tree tries to fix the mistakes of the trees before it. Generally more
accurate than logistic regression on messy, real-world data, at the cost of being harder to
explain directly (that's what SHAP, in Stage 5, is for).

### Class imbalance
When one outcome is much rarer than the other — here, fraud (3.5%) vs. not-fraud (96.5%).
It matters because a model (and a careless evaluation) can get fooled into looking "good" by
just predicting the common class every time, while being useless at the one thing that
matters.

### Class weighting
A way to handle class imbalance: tell the model to treat each example of the rare class
(fraud) as more important when learning, without changing how many rows of data there are.

### Oversampling
A different way to handle class imbalance: duplicate examples of the rare class in the
training data until the two classes are more evenly represented.

### Precision
Of everything the model flagged as fraud, what share was actually fraud? Low precision means
lots of false alarms — legitimate customers getting wrongly flagged.

### Recall
Of everything that was actually fraud, what share did the model catch? Low recall means a
lot of real fraud is slipping through undetected.

### Precision-Recall AUC (PR-AUC)
A single score summarizing how well a model balances precision and recall across every
possible cutoff point, from 0 to 1 (higher is better). It's the preferred scorecard here
instead of plain accuracy, because it isn't fooled by class imbalance the way accuracy is.

### Confusion matrix
A simple 2x2 table comparing what the model predicted against what was actually true: true
positives (correctly flagged fraud), false positives (wrongly flagged a legitimate
transaction), false negatives (missed real fraud), true negatives (correctly left alone).

### LLM
"Large Language Model" — an AI system (like Gemini or Claude) trained on huge amounts of
text, able to read and write natural-language text. Used in Stage 6 to turn structured
evidence into a readable, plain-English case note.

### Agent
An AI system that can decide to use tools (look things up, run calculations) before giving
its final answer, instead of only generating text from what it already "knows." Our
investigation agent calls 4 tools to gather real evidence about a transaction, then writes a
note based on what it found — it never just makes something up.

### Tool (in an AI agent context)
A specific function an agent is allowed to call to get real information — here, SQL lookups
against the actual transaction data. The agent's tools return facts; the agent's only job is
to read those facts and summarize them in plain English, not to invent new ones.

### Hallucination
When an AI states something as fact that isn't actually true or isn't supported by the
evidence it was given — a well-known failure mode of language models. Stage 6's evaluation
specifically checks for this: did the agent's note say anything the tools didn't actually find?

### Template baseline
A non-AI comparison point: fixed sentence templates and simple if/else rules that turn the
same tool evidence into a note, with no language model involved. Used to answer "is the AI
actually adding value here, or could basic string templates do just as well?"

### Model card
A standard one-page document that summarizes what a model is for, what data it was built
and tested on, its real performance numbers, and — just as important — its known
limitations and who needs to review its output. Think of it like a nutrition label for a
model.

### Concept drift
When the real-world patterns a model learned from slowly change over time, making the
model's predictions less accurate even though nothing about the model itself changed. For
fraud specifically: scammers adapt their tactics, so a model trained on last year's fraud
patterns can quietly get worse without ever being "broken."

### Shadow mode
Running a model on real, live data to see how it performs — but without letting it actually
affect any decision yet. A safe way to validate a model's real-world performance before
trusting it to flag or block anything for real.

### Local model
An AI model that runs entirely on your own computer instead of calling a company's server
over the internet. No account, no API key, no rate limit, no cost — the tradeoff is it's
usually less capable than a large cloud model, and needs enough disk space/RAM to run. This
project uses one (via a free tool called Ollama) after hitting Gemini's free-tier daily limit.

### SHAP
A tool that explains one individual prediction by assigning each feature a signed number
for that one case: positive means "this pushed the score toward fraud," negative means "this
pushed it toward not-fraud," and the size shows how much it mattered relative to the other
features for that same transaction. It turns an opaque model score into a readable list of
reasons for one specific case — the technique behind this project's case notes in Stage 6.

### False positive
A case the model flagged as fraud that actually wasn't. In this project, that's a legitimate
transaction wrongly declined — see "false decline."

### Threshold
The cutoff point on the model's fraud probability (0 to 1) above which a transaction actually
gets flagged. A low threshold flags almost everything (catches more fraud, more false
alarms); a high threshold flags almost nothing (fewer false alarms, misses more fraud).
Picking it is a real business tradeoff, not just a modeling detail.

### False decline
A legitimate transaction that gets wrongly flagged/declined because the model scored it as
likely fraud. Has a real cost: lost sales, an annoyed or embarrassed customer, and a risk
they stop using the card altogether.

### Sensitivity analysis
Testing how much an answer (here, the recommended threshold) changes when an assumption you
weren't sure about (here, the cost of a false decline) is varied across a range of plausible
values — instead of quietly picking one guess and hoping it's right.

### Regularization
A setting that discourages a model from relying too heavily on any single feature, which
helps keep its predictions stable and keeps it from "memorizing" quirks of the training data
instead of learning a pattern that generalizes.
