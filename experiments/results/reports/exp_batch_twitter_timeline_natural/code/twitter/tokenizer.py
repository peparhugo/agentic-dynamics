from __future__ import annotations

import re

_WORD = re.compile(r"[#@]?\w+")


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for word in _WORD.findall(text.lower()):
        if word not in seen:
            seen.add(word)
            tokens.append(word)
        stripped = word.lstrip("#@")
        if stripped and stripped != word and stripped not in seen:
            seen.add(stripped)
            tokens.append(stripped)
    return tokens
