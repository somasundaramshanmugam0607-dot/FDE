"""Optional LLM-written explanations.

Off by default. The deterministic, evidence-based explanation is always
computed first; ``--explain llm`` replaces it with a one-sentence version via
the OpenAI Chat Completions API. No key means no network call and no failure.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .analysis import AccountAssessment

DEFAULT_MODEL = "gpt-4o-mini"
ENDPOINT = "https://api.openai.com/v1/chat/completions"
TIMEOUT_SECONDS = 15


def llm_explanation(assessment: AccountAssessment) -> str:
    """Return a short CSM-facing explanation, falling back to the template."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return assessment.reason

    model = os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": 120,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You write one-sentence alerts for a customer-success team. "
                    "Use only the supplied facts. Do not invent events, causes, "
                    "or numbers. At most 25 words. Plain text, no markdown."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Account: {assessment.label} ({assessment.plan_tier})\n"
                    f"Risk tier: {assessment.tier.value}\n"
                    f"Evidence: {assessment.reason}\n"
                    "Write one sentence explaining why this account was flagged."
                ),
            },
        ],
    }
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = json.load(response)
        text = body["choices"][0]["message"]["content"].strip()
        return " ".join(text.split()) or assessment.reason
    except (urllib.error.URLError, KeyError, IndexError, ValueError, TypeError) as exc:
        return f"{assessment.reason} [LLM unavailable: {type(exc).__name__}]"
