"""
Stage 6: the AI investigation agent. For one flagged transaction, it calls all
four tools in agent_tools.py to gather real evidence, then asks a language
model to turn that evidence into a short case note - and ONLY that evidence.

Originally this called Google's Gemini free API. While testing, we hit a real
wall worth documenting honestly: Gemini's free tier currently allows only
20 requests/day on the only available model (gemini-3.8-flash), and testing
alone used up the day's quota - nowhere near enough for a 25-transaction
evaluation in one sitting. So this now runs a small model LOCALLY instead, via
Ollama (a free tool that runs language models on your own computer): no
account, no API key, no rate limit, and no cost - fully in the spirit of the
project's "everything free" rule, and arguably a better fit than a cloud API
for a project about reproducibility.

Setup (one-time): `brew install ollama`, then `ollama pull llama3.2:3b`, with
the Ollama server running in the background (`brew services start ollama`).
"""

from __future__ import annotations

import time

import requests

from agent_tools import gather_all_evidence

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3.1:8b"
REQUEST_DELAY_SECONDS = 0.5  # local model, no real rate limit - just a small courtesy gap
MAX_RETRIES = 3

SYSTEM_INSTRUCTION = """You are a fraud-investigation assistant drafting a short case note \
for a human fraud analyst to review. You do not make decisions and you do not take any \
action on the account - you only draft a note for a person to read.

STRICT RULES:
1. Only state facts that literally appear in the EVIDENCE JSON you are given. Never invent, \
assume, or guess any detail about the cardholder, the merchant, or the transaction that \
isn't in that JSON.
2. If a tool found nothing (e.g. zero similar fraud cases, zero prior history), say that \
plainly - do not paper over it or invent a plausible-sounding substitute.
3. Never claim an exact identity match for "same card" evidence - the evidence is explicitly \
an approximate match (see its match_type field) and your note must reflect that, e.g. say \
"this card (approximate match)" not "this card".
4. Write exactly three short sections: "Why flagged", "Evidence", "Suggested next step". \
Keep the whole note under 150 words.
5. The suggested next step is a RECOMMENDATION for a human analyst, never an action you are \
taking yourself (never say "I have declined/held/flagged the account").
6. The evidence comes from 4 SEPARATE tools/lookups - never combine or imply a connection \
between facts from different tools. In particular, "recent_same_card_transactions" and \
"similar_confirmed_fraud" are two DIFFERENT lists of transactions found by different \
searches - do not say the fraud cases from one list are part of the other list unless a \
TransactionID literally appears in both.
7. The "Why flagged" section MUST explicitly name the single strongest driver from \
shap_reasons (the one with the largest absolute shap_value) by its exact "feature" name - \
e.g. "C14" or "card6 is NOT debit" - not a vague paraphrase like "unusual activity". State \
its direction (toward fraud or not-fraud) too. This is the model's actual reason for the \
flag and must not be omitted or replaced with a generic statement.
"""


def _call_ollama(prompt: str) -> str:
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_NAME,
                    "messages": [
                        {"role": "system", "content": SYSTEM_INSTRUCTION},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                },
                timeout=120,
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
        except requests.exceptions.ConnectionError as e:
            if attempt < MAX_RETRIES - 1:
                print("[ai_agent] Can't reach Ollama - is it running? Retrying in 3s...")
                time.sleep(3)
                continue
            raise RuntimeError(
                "Could not connect to Ollama at localhost:11434. "
                "Start it with: brew services start ollama"
            ) from e


def generate_ai_note(transaction_id: int, evidence: dict | None = None) -> str:
    if evidence is None:
        evidence = gather_all_evidence(transaction_id)
    prompt = (
        f"EVIDENCE JSON for TransactionID {transaction_id}:\n\n{evidence}\n\n"
        f"Write the case note now, following the three-section format and all strict rules."
    )
    note = _call_ollama(prompt)
    time.sleep(REQUEST_DELAY_SECONDS)
    return note


if __name__ == "__main__":
    import sys
    tid = int(sys.argv[1])
    print(generate_ai_note(tid))
