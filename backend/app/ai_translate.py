from __future__ import annotations

import re
from typing import Iterable, Optional

try:
    from openai import OpenAI as _OpenAI  # type: ignore
except Exception:  # pragma: no cover
    _OpenAI = None


class AITranslator:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 30.0):
        if _OpenAI is None:
            raise RuntimeError("openai package is not installed in backend environment")
        self.client = _OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self.model = model

    def translate(self, text: str, target_lang: str, placeholders: Iterable[str] = (), emoji_prefix: Optional[str] = None) -> str:
        if not text:
            return text
        # Build instructions: preserve curly-brace placeholders exactly, keep emoji prefix
        sys = (
            "You are a precise translator. Translate user text into the target language. "
            "Strict rules: 1) Keep placeholders like {name} exactly unchanged. "
            "2) Preserve any leading emoji prefix if provided. 3) Return only the translated text without quotes."
        )
        pl = ", ".join(sorted(set(placeholders))) if placeholders else ""
        extra = (
            f"Placeholders to preserve: {pl}. " if pl else ""
        ) + (f"Emoji prefix to keep at the very start: {emoji_prefix}. " if emoji_prefix else "")

        prompt = (
            f"Target language: {target_lang}. {extra}Text to translate:\n" 
            f"""{text}"""
        )

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        out = resp.choices[0].message.content or ""
        cleaned = re.sub(r"<think>.*?</think>", "", out, flags=re.DOTALL).strip()
        return cleaned
