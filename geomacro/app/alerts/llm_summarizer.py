"""LLM analyst note (spec section 9). Always optional: failures fall back to the template."""
import json
import logging

import httpx

from ..config import env
from .templates import ACTION

log = logging.getLogger("geomacro.alerts")

PROMPT = """You are an analyst summarizing a geo-macro volatility alert for an Indian NIFTY options seller.
Rules:
- Do not predict market direction.
- Do not recommend automated trading.
- Focus only on volatility/gap risk.
- Use only the supplied evidence.
- Keep it short (max 70 words).
- Mention the suggested action from the provided risk label.
Return: 1 Risk headline, 2 What triggered it, 3 Why it matters for Indian markets, 4 Suggested options action, 5 Confidence score."""


def llm_note(snap):
    provider = env("LLM_PROVIDER", "none").lower()
    if provider in ("", "none"):
        return None
    payload = {"risk_score": snap.score, "risk_label": snap.label, "region": snap.region,
               "active_signals": [{"type": a["type"], "score": a["score"], "evidence": a["evidence"]} for a in snap.active_signals],
               "suggested_action": ACTION[snap.label],
               "confidence": snap.details.get("confidence"),
               "trading_context": "User trades NIFTY weekly iron condors. Alert should focus on volatility and gap risk, not direction."}
    user = json.dumps(payload)
    try:
        if provider == "gemini":
            key = env("GEMINI_API_KEY")
            r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
                           json={"contents": [{"parts": [{"text": PROMPT + "\n\n" + user}]}],
                                 "generationConfig": {"temperature": 0.2}}, timeout=25)
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        if provider == "anthropic":
            r = httpx.post("https://api.anthropic.com/v1/messages",
                           headers={"x-api-key": env("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01"},
                           json={"model": "claude-3-5-haiku-latest", "max_tokens": 300, "temperature": 0.2,
                                 "system": PROMPT, "messages": [{"role": "user", "content": user}]}, timeout=25)
            r.raise_for_status()
            return r.json()["content"][0]["text"].strip()
        base, key, model = {
            "groq": ("https://api.groq.com/openai/v1", env("GROQ_API_KEY"), "llama-3.3-70b-versatile"),
            "openai": ("https://api.openai.com/v1", env("OPENAI_API_KEY"), "gpt-4o-mini"),
        }[provider]
        r = httpx.post(f"{base}/chat/completions", headers={"Authorization": f"Bearer {key}"},
                       json={"model": model, "temperature": 0.2,
                             "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": user}]}, timeout=25)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:  # noqa: BLE001 - template fallback per spec
        log.warning("LLM note failed (%s), using template only", e)
        return None
