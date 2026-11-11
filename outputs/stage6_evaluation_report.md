# AI agent vs. non-AI template baseline (v1 vs. v2)

## Method

25 flagged transactions were sampled at random (seed=42, same 25 transactions in both
rounds) from the 19,057 transactions flagged at Stage 4's threshold. For each one, the same
evidence (from the 4 tools) was turned into a note by the fixed-template baseline and by
the AI agent, using a free local model (`llama3.1:8b` via Ollama — Gemini's free tier hit a
hard 20-requests/day limit during testing, nowhere near enough for this evaluation; see
README).

Every note was checked against the raw evidence JSON on: (1) did it name the model's real
top SHAP driver, (2) did it state anything as fact that the evidence didn't support
(checked with an automated script comparing specific numbers/claims against the real data,
plus a full manual read), (3) was its suggested action reasonable.

**v1** is the agent's first version. After reviewing v1's notes, one clear, common failure
stood out: **60% of notes never mentioned the model's actual SHAP reasoning at all**,
defaulting to vague phrases like "flagged for potential fraud." **v2** adds one explicit
rule: always name the single strongest SHAP driver, by its exact feature name, in the "Why
flagged" section. The other 6 rules (don't invent cardholder/merchant details, label the
card match as approximate, don't conflate different tools' evidence, etc.) are unchanged.
The same 25 transactions were then re-run through v2 to measure what actually changed.

## Results: v1 vs. v2

| | Named the real top driver | Unsupported/incorrect claims (confirmed) | Reasonable next step |
|---|---|---|---|
| Template baseline | 25/25 (100%) | 0/25 (0%) | 25/25 (100%)* |
| **AI agent v1** (vague, could omit SHAP) | 10/25 (40%) | 5/25 (20%, lower bound) | 25/25 (100%)* |
| **AI agent v2** (forced to always name a driver) | 16/25 (64%) | **11/25 (44%, lower bound)** | 25/25 (100%)* |

\* Non-differentiated in both versions — see the original findings in
`outputs/stage6_evaluation_report_v1.md`, unchanged by this fix.

## The honest, slightly uncomfortable finding: the fix didn't clearly make things better

This is the real result, and it's worth sitting with rather than smoothing over. Forcing
the model to always name a specific driver **did** raise how often it named the correct one
(40% -> 64%). But it also **created a brand-new failure mode that barely existed in v1**:
confidently naming the *wrong* feature as the top driver, with a specific (sometimes
correct-looking) number attached.

**Example (Case 20):** the real top driver was `TransactionAmt` (SHAP +0.592). v2's note
said: *"The transaction was flagged due to C14 being pushed toward FRAUD (shap_value:
0.592)"* — it used the right NUMBER but the wrong NAME. `C14` wasn't even among this
transaction's top-5 real reasons at all. This happened in a similar way in at least 4 of
the 25 cases (5, 14, 20, 21) — always substituting a specific, plausible-sounding feature
name (`C14` came up suspiciously often — likely because it was the genuinely correct answer
in several other cases in this same batch, suggesting the model may partly be pattern-
matching to a locally common answer rather than reading each transaction's evidence fresh).

**Why this matters more than v1's vagueness:** a vague note ("flagged for potential
activity") is unhelpful but honest about its own uncertainty. A specific, confidently wrong
note ("flagged because of C14") is actively misleading — an analyst reading it would form a
false belief about why the model acted, backed by a real-looking number. **Forcing
specificity without the underlying reasoning to back it up made the AI agent more
confidently wrong, not more reliable.**

The two bugs found in v1 (conflating different tools' evidence; overgeneralizing "all
transactions had product code X" when they didn't) both persisted in v2 at a similar rate
(2/25 and 3/25 respectively) — the targeted fix didn't touch those, as expected, since it
specifically targeted the "why flagged" section.

## What this would mean for a real deployment

This is genuinely good evidence for the model card and memo: **a single, well-intentioned
prompt tweak changed the shape of the agent's errors without clearly improving overall
trustworthiness.** It reinforces, with a concrete before/after measurement rather than just
an assumption, that any version of this AI agent needs mandatory human verification against
the underlying tool evidence before a note is trusted — prompt engineering alone did not
get this local model to a point where its claims can be taken at face value.

## What did NOT change, and still holds

The AI agent still never invented a cardholder or merchant detail, still consistently
labeled "same card" evidence as approximate, and still never claimed to take an action
itself. The strict rules continue to hold for the most serious failure category they were
designed to prevent; the remaining errors are specifically about attribution accuracy
(which feature actually drove the flag), not fabrication of facts about people or merchants.
