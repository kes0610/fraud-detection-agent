"""
The project's full dashboard - one tab per stage, plus the live investigation
agent demo. Run with: streamlit run app.py
"""

import re
import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUTS = PROJECT_ROOT / "outputs"
sys.path.insert(0, str(SCRIPT_DIR))  # so the imports below work regardless of cwd

from agent_tools import gather_all_evidence, gather_all_evidence_for_new_row
from template_baseline import generate_template_note
from ai_agent import generate_ai_note
import scoring

st.set_page_config(page_title="Fraud Detection Project", layout="wide")


def render_markdown_report(path: Path, strip_images: bool = True):
    """Shows a saved stage report as-is - one source of truth, no re-typing
    numbers into the dashboard separately where they could drift out of sync."""
    if not path.exists():
        st.warning(f"Report not found: {path.name}")
        return
    text = path.read_text()
    if strip_images:
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)  # images are shown separately via st.image
    text = text.replace("$", "\\$")  # literal dollar signs, not LaTeX math delimiters
    st.markdown(text)


@st.cache_data
def load_flagged_transactions():
    predictions = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "test_predictions.parquet")
    shap_df = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "shap_top_reasons_flagged.parquet")
    flagged_ids = shap_df["TransactionID"].unique()
    flagged = predictions[predictions["TransactionID"].isin(flagged_ids)].copy()
    return flagged.sort_values("xgb_fraud_probability", ascending=False).reset_index(drop=True)


@st.cache_data
def load_threshold_sweep():
    return pd.read_csv(OUTPUTS / "stage4_threshold_sweep.csv")


@st.cache_data
def build_sample_template() -> bytes:
    import duckdb
    con = duckdb.connect(str(PROJECT_ROOT / "data" / "warehouse.duckdb"), read_only=True)
    cols = scoring.required_columns()
    sample = con.execute(f"SELECT {', '.join(cols)} FROM transactions USING SAMPLE 5").fetchdf()
    return sample.to_csv(index=False).encode("utf-8")


# ------------------------------------------------------------------ Overview
def render_overview():
    st.markdown(
        "This project builds a model that flags likely-fraudulent card transactions on "
        "590,540 real (anonymized) transactions, picks a flagging threshold using real "
        "dollar tradeoffs, and includes an AI \"investigation agent\" that drafts a case "
        "note for a human fraud analyst to review. Every number below comes from a real "
        "run on the real data - nothing here is a placeholder or an estimate."
    )

    st.subheader("Key results")
    c1, c2, c3 = st.columns(3)
    c1.metric("Model quality (PR-AUC)", "0.50", "+0.31 vs. baseline")
    c2.metric("Fraud caught at chosen threshold", "$615,681", "vs. $3.2M legit wrongly declined")
    c3.metric("AI agent note accuracy", "64%", "named the model's real top reason")
    st.caption(
        "PR-AUC, not plain accuracy, is the right scorecard here: fraud is only 3.5% of "
        "transactions, so a model that flags nothing would score 96.5% \"accurate\" while "
        "catching zero fraud. See the Model tab for the full comparison, and the "
        "Investigation Agent tab's Evaluation results for how that 64% was measured."
    )

    st.divider()
    st.subheader("See the investigation agent in action")
    st.caption(
        "One real flagged transaction, with the model's actual reasons (via SHAP) for "
        "flagging it. The full interactive version - pick any transaction, or upload your "
        "own - is in the Investigation Agent tab."
    )
    flagged = load_flagged_transactions()
    example = flagged.iloc[0]
    with st.spinner("Loading example..."):
        evidence = gather_all_evidence(int(example["TransactionID"]))
    e1, e2, e3 = st.columns(3)
    e1.metric("Amount", f"${example['TransactionAmt']:,.2f}")
    e2.metric("Model's fraud score", f"{example['xgb_fraud_probability']:.1%}")
    e3.metric("Actually fraud?", "Yes" if example["isFraud"] else "No")
    shap_display = pd.DataFrame(evidence["shap_reasons"]["reasons"])[["feature", "direction", "shap_value", "meaning"]]
    st.dataframe(shap_display, hide_index=True, width="stretch")

    st.divider()
    with st.expander("Full results detail"):
        render_markdown_report(PROJECT_ROOT / "RESULTS.md")


# ---------------------------------------------------------- Stage 1-2: Data
def render_data_stage():
    st.subheader("Stages 1-2: Data & Quality")
    st.caption("Stage 1: SQL exploration of the raw data. Stage 2: automated data-quality checks.")
    tab_a, tab_b = st.tabs(["Exploration findings", "Data quality report"])
    with tab_a:
        render_markdown_report(OUTPUTS / "stage1_findings.md")
    with tab_b:
        render_markdown_report(OUTPUTS / "stage2_data_quality_report.md")
        st.caption("Full column-by-column data dictionary: see `data_dictionary.md` in the project root.")


# ------------------------------------------------------------- Stage 3: Model
def render_model_stage():
    st.subheader("Stage 3: Model")
    st.caption("Baseline (Logistic Regression) vs. the stronger model (XGBoost).")
    render_markdown_report(OUTPUTS / "stage3_model_results.md")


# ------------------------------------------------------- Stage 4: Threshold
def render_threshold_stage():
    st.subheader("Stage 4: Threshold & Dollars")
    st.caption("Picking a flagging threshold using real dollar amounts.")
    img_path = OUTPUTS / "stage4_threshold_chart.png"
    if img_path.exists():
        st.image(str(img_path))
    render_markdown_report(OUTPUTS / "stage4_threshold_report.md")

    st.divider()
    st.subheader("Try your own cost assumption")
    st.caption(
        "The report above uses 4 illustrative assumptions. Drag the slider to see the "
        "recommended threshold for ANY assumption, computed live from the same real sweep "
        "data (no new numbers invented - this just re-reads outputs/stage4_threshold_sweep.csv)."
    )
    sweep = load_threshold_sweep()
    cost_pct = st.slider(
        "If we wrongly decline a legitimate transaction, what % of its dollar value do we lose?",
        min_value=1, max_value=50, value=5,
    ) / 100
    net_value = sweep["fraud_dollars_caught"] - cost_pct * sweep["legit_dollars_wrongly_declined"]
    best = sweep.loc[net_value.idxmax()]
    c1, c2, c3 = st.columns(3)
    c1.metric("Recommended threshold", f"{best['threshold']:.2f}")
    c2.metric("Fraud $ caught", f"${best['fraud_dollars_caught']:,.0f}")
    c3.metric("Legit $ wrongly declined", f"${best['legit_dollars_wrongly_declined']:,.0f}")


# ------------------------------------------------------- Stage 5: SHAP
def render_shap_stage():
    st.subheader("Stage 5: Explainability (SHAP)")
    st.caption("Explaining individual flagged transactions with SHAP.")
    img_path = OUTPUTS / "stage5_shap_importance.png"
    if img_path.exists():
        st.image(str(img_path))
    render_markdown_report(OUTPUTS / "stage5_shap_findings.md")


# ------------------------------------------------- Stage 6: Investigation agent
def render_note_section(evidence: dict, note_key: str, transaction_id=None):
    shap_reasons = evidence["shap_reasons"]["reasons"]
    st.markdown("**Top SHAP reasons (why the model flagged this):**")
    if shap_reasons:
        shap_df_display = pd.DataFrame(shap_reasons)[["feature", "direction", "shap_value", "meaning"]]
        st.dataframe(shap_df_display, hide_index=True, width="stretch")
    else:
        st.write("No SHAP reasons available.")

    with st.expander("See the raw evidence (what the tools actually found)", expanded=False):
        st.json(evidence)

    st.divider()
    left, right = st.columns(2)
    with left:
        st.markdown("### Template note (no AI, fixed rules)")
        st.text(generate_template_note(evidence))
    with right:
        st.markdown("### AI-generated note")
        if st.button("Generate AI note (takes ~10-20 seconds, runs locally)", key=f"ai_btn_{note_key}"):
            with st.spinner("Asking the local model to write the note..."):
                try:
                    if transaction_id is not None:
                        note = generate_ai_note(int(transaction_id), evidence=evidence)
                    else:
                        from ai_agent import _call_ollama
                        prompt = (
                            f"EVIDENCE JSON for this new (uploaded) transaction:\n\n{evidence}\n\n"
                            f"Write the case note now, following the three-section format and all strict rules."
                        )
                        note = _call_ollama(prompt)
                    st.text(note)
                except Exception as e:
                    st.error(
                        f"Couldn't reach the local AI model. Is Ollama running? "
                        f"(brew services start ollama)\n\nError: {e}"
                    )
        else:
            st.info("Click the button to generate this live.")


def render_existing_browser():
    flagged = load_flagged_transactions()
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_id = st.selectbox(
            "Choose a flagged transaction",
            options=flagged["TransactionID"],
            format_func=lambda tid: (
                f"TransactionID {tid} - "
                f"${flagged.loc[flagged.TransactionID == tid, 'TransactionAmt'].iloc[0]:,.2f} - "
                f"model score {flagged.loc[flagged.TransactionID == tid, 'xgb_fraud_probability'].iloc[0]:.0%}"
            ),
        )
    with col2:
        if st.button("Pick a random one instead"):
            selected_id = int(flagged.sample(1).iloc[0]["TransactionID"])
            st.session_state["selected_id"] = selected_id
        if "selected_id" in st.session_state:
            selected_id = st.session_state["selected_id"]

    row = flagged[flagged["TransactionID"] == selected_id].iloc[0]
    st.subheader(f"TransactionID {selected_id}")
    m1, m2, m3 = st.columns(3)
    m1.metric("Amount", f"${row['TransactionAmt']:,.2f}")
    m2.metric("Model's fraud score", f"{row['xgb_fraud_probability']:.1%}")
    m3.metric("Actually fraud? (ground truth)", "Yes" if row["isFraud"] else "No")

    with st.spinner("Gathering evidence from the 4 tools..."):
        evidence = gather_all_evidence(int(selected_id))
    render_note_section(evidence, note_key=f"existing_{selected_id}", transaction_id=selected_id)


def render_upload_scorer():
    st.caption(
        "Upload a CSV of NEW transactions (same columns as this project's data - not "
        "retrained, just scored with the model already built in Stages 1-5)."
    )
    st.download_button(
        "Download a sample template (5 real rows, right format)",
        data=build_sample_template(),
        file_name="sample_transactions_template.csv",
        mime="text/csv",
    )

    uploaded = st.file_uploader("Upload your CSV", type="csv")
    if uploaded is None:
        st.info("Upload a file to see it scored here.")
        return

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp.write(uploaded.getvalue())
        tmp_path = tmp.name

    raw_df = scoring.load_uploaded_csv(tmp_path)
    scored = scoring.score_transactions(raw_df.copy())

    st.success(f"Scored {len(scored)} transaction(s).")
    display_cols = [c for c in ["TransactionAmt", "ProductCD", "fraud_probability"] if c in scored.columns]
    st.dataframe(
        scored[display_cols].style.format({"fraud_probability": "{:.1%}"}),
        width="stretch",
    )

    st.divider()
    row_choice = st.selectbox(
        "Investigate one of these rows",
        options=scored.index,
        format_func=lambda i: (
            f"Row {i} - ${scored.loc[i, 'TransactionAmt']:,.2f} - "
            f"score {scored.loc[i, 'fraud_probability']:.0%}"
        ),
    )
    raw_row = raw_df.loc[row_choice]
    m1, m2 = st.columns(2)
    m1.metric("Amount", f"${raw_row['TransactionAmt']:,.2f}")
    m2.metric("Model's fraud score", f"{scored.loc[row_choice, 'fraud_probability']:.1%}")

    with st.spinner("Gathering evidence from the 4 tools (computing SHAP live)..."):
        encoded_row = scoring.encode_single_row(raw_row)
        evidence = gather_all_evidence_for_new_row(
            raw_row.to_dict(), encoded_row, scoring.get_explainer(), scoring.get_low_cardinality_columns(),
        )
    render_note_section(evidence, note_key=f"upload_{row_choice}", transaction_id=None)


def render_agent_stage():
    st.subheader("Stage 6: Investigation Agent")
    st.caption(
        "4 tools gather real evidence for a flagged transaction; a template (no AI) and a "
        "local LLM each turn it into a case note."
    )
    st.info(
        "The AI note-writing (below and in 'Upload new transactions') calls a language "
        "model running locally on this machine via Ollama, not a hosted API. If a note "
        "fails to generate, Ollama isn't running — start it with `brew services start "
        "ollama` (see README for full setup)."
    )
    sub_a, sub_b, sub_c = st.tabs(["Browse this project's data", "Upload new transactions", "Evaluation results"])
    with sub_a:
        render_existing_browser()
    with sub_b:
        render_upload_scorer()
    with sub_c:
        render_markdown_report(OUTPUTS / "stage6_evaluation_report.md")


# --------------------------------------------------- Model card & memo
def render_writeups():
    sub_a, sub_b = st.tabs(["Model card", "Memo"])
    with sub_a:
        render_markdown_report(PROJECT_ROOT / "MODEL_CARD.md")
    with sub_b:
        render_markdown_report(PROJECT_ROOT / "MEMO.md")


# ------------------------------------------------------------------- Layout
st.title("Fraud Detection with an Investigation Agent")
st.caption("Click through each tab for that stage's full findings.")

tabs = st.tabs([
    "Overview",
    "Data & Quality",
    "Model",
    "Threshold & Dollars",
    "Explainability (SHAP)",
    "Investigation Agent",
    "Model Card & Memo",
])
with tabs[0]:
    render_overview()
with tabs[1]:
    render_data_stage()
with tabs[2]:
    render_model_stage()
with tabs[3]:
    render_threshold_stage()
with tabs[4]:
    render_shap_stage()
with tabs[5]:
    render_agent_stage()
with tabs[6]:
    render_writeups()
