# Stage 6 evaluation: AI agent vs. non-AI template baseline

## Method

25 flagged transactions were sampled at random (seed=42) from the 19,057 transactions
flagged at Stage 4's threshold. For each one, the exact same evidence (from the 4 tools)
was turned into a note two ways: the fixed-template baseline, and the AI agent
(Gemini's free tier was tried first but hit a hard 20-requests/day limit during testing,
so this evaluation uses a free LOCAL model instead - `llama3.1:8b` via Ollama, running
entirely on a laptop, no API, no cost, no rate limit - see README for why).

Each pair of notes was checked against the raw evidence JSON on three things, matching the
project plan:
1. **Named the right drivers** - did the note correctly identify the model's actual top
   SHAP reason(s) for the flag?
2. **Unsupported claims** - did the note state anything as fact that the evidence didn't
   actually support? (Checked with both an automated script that compares specific numbers
   in each note against the real numbers, and a manual read of every note.)
3. **Reasonable next step** - was the suggested action sensible given the evidence?

**Honesty note on scope:** every note was read, and every numeric claim that looked
checkable (recall counts, percentages, product-code breakdowns) was spot-checked against
the real data. Long itemized lists some AI notes produced (e.g. specific TransactionIDs)
were not individually re-verified line-by-line - this is a reasonable-effort audit, not an
exhaustive one.

## Results

| | Named the right driver(s) | Unsupported/incorrect claims | Reasonable next step |
|---|---|---|---|
| **Template baseline** | 25/25 (100%) | 0/25 (0%) | 25/25 (100%)* |
| **AI agent (local LLM)** | 10/25 (40%) | 5/25 (20%)** | 25/25 (100%)* |

\* "Reasonable" but **not discriminating** for either version - see Failure patterns below.
\*\* Lower bound - only specific, checkable claims were verified; the true rate may be
slightly higher with a fully exhaustive check.

## Why the template scores 100/100/100

This isn't the template being smart - it's a direct, structural consequence of how it's
built. It literally prints the real SHAP values and real tool-output numbers into fixed
sentences; there's no step where it could introduce an error, because it never generates
new text, only fills in blanks with values pulled straight from the evidence. This is an
important, honest thing to say in the model card later: the template's perfect score is a
reflection of its narrow, rigid design, not of some superior "understanding."

## Failure patterns, described honestly

**1. The AI frequently skipped the SHAP evidence entirely (15 of 25 cases, 60%).** Instead
of saying "the model flagged this because C14 and TransactionAmt pushed the score up," it
often fell back on vague language like "flagged for potential fraud" or "exhibits unusual
characteristics" - true, but uninformative, and the single biggest difference from the
template. An analyst reading these notes would often not learn *why the model specifically
flagged this one*, which is the whole point of pairing an agent with Stage 5's SHAP work.

**2. Confirmed fabrication: conflating two separate evidence sources (Case 11).** The note
claimed "2 of these [10 recent same-card] transactions having been confirmed as fraud" -
but the real number is 0. The "2" actually came from a completely different lookup (similar
past fraud cases), which the model merged into the wrong sentence. This is the clearest,
most serious kind of error: a specific, false fact stated with full confidence.

**3. Miscounted sub-details within an otherwise-accurate note (Cases 2, 18, 20, 25).** The
AI would correctly describe the overall shape of the evidence but get a specific number
wrong - e.g. claiming "6 transactions with product code 'W'" among a card's recent history
when the real count was 9, or "all" of 10 transactions sharing a product code when 1 of the
10 was actually different. These are smaller errors than Case 11's, but still real,
unsupported claims by the project's own rule ("only state facts the tools returned").

**4. Neither version's "suggested next step" actually adapts to the strength of the
evidence.** The template always recommends the same action ("hold the transaction, contact
the cardholder") whenever 2+ similar-fraud matches exist - which, it turns out, was true in
all 25 sampled cases, making this "recommendation" constant and uninformative. The AI
agent's suggestions were almost always some version of "a human analyst should review this"
- safe, never wrong, but equally non-differentiated. **Neither baseline actually earns its
"suggested next step" section** - that's a genuine limitation of both approaches as built,
worth flagging plainly rather than overselling either one.

## What did NOT go wrong

To be fair to the AI agent: it never invented a cardholder name, a merchant, or any detail
that wasn't somewhere in the evidence JSON; it consistently and correctly labeled the "same
card" evidence as an approximate match; and it never claimed to take an action itself
(always phrased as a recommendation for a human). The strict rules in the prompt did hold
for the most serious failure categories they were written to prevent - the errors found
were narrower (numeric/attribution mistakes) than the "inventing a cardholder's name" worst
case the rules were guarding against.

## Bottom line

For this project's specific use case - a short, auditable note that must be scrupulously
accurate for a human analyst to trust - **the simple template baseline is more reliable
than the AI agent**, at zero cost and zero risk of fabrication. The AI agent writes more
naturally and occasionally surfaces good specific detail (e.g. correctly naming V294 or
C14 by name in several cases), but introduces a real error rate that a bank would need to
catch via human review, not eliminate. This is a legitimate, honest finding for a model
card: **AI-drafted notes need a human review step, not blind trust** - which is exactly
what the project's own design already requires (the agent only ever drafts, never acts).
