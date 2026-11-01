"""Prompt-injection guardrails: spotlighting, input scan and output check.

No single layer stops prompt injection. The point is layers plus measurement:
every layer reports what it caught, and the evals count attacks before and after.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .corpus import Doc
from .entities import Gazetteer, fold

# ---------------------------------------------------------------- spotlighting


def spotlight(docs: list[Doc]) -> str:
    """Wrap each retrieved document in tags so the model can tell data from instructions."""
    parts = []
    for d in docs:
        # Stop a document from closing its own tag and "escaping" into the prompt.
        body = re.sub(r"</?\s*document[^>]*>", "[tag removed]", d.text, flags=re.I)
        parts.append(f'<document id="{d.doc_id}" source="{d.source or d.kind}">\n{body}\n</document>')
    return "\n\n".join(parts)


# ---------------------------------------------------------------- input scan

INJECTION_RULES: list[tuple[str, re.Pattern]] = [
    ("ignore_previous", re.compile(r"\b(ignore|disregard|forget|override)\b.{0,40}\b(previous|prior|above|earlier|all|your|system)\b.{0,30}\b(instructions?|rules?|prompts?|guidelines?)", re.I)),
    ("fake_system", re.compile(r"(^|\n|\[|<)\s*(system|assistant|developer)\s*(:|\]|>)", re.I)),
    ("role_switch", re.compile(r"\byou are now\b|\bfrom now on,? you\b|\bact as\b.{0,30}\bbot\b|\bnew (persona|role|instructions?)\b", re.I)),
    ("secret_request", re.compile(r"\b(reveal|print|output|share|tell|show|leak|repeat)\b.{0,50}\b(password|admin key|api key|secret|system prompt|hidden instructions?)", re.I)),
    ("announce_transfer", re.compile(r"\b(announce|confirm|state|say|tell (users|everyone|readers))\b.{0,60}\b(signed|signing|joined|transfer|completed (a|his|her) move)", re.I)),
    ("link_push", re.compile(r"\b(include|add|append|insert|share|post|output|send)\b.{0,40}\b(link|url|website)\b", re.I)),
    ("html_comment", re.compile(r"<!--.*?-->", re.S)),
    ("zero_width", re.compile(r"[​‌‍⁠﻿]")),
    ("base64_blob", re.compile(r"\b[A-Za-z0-9+/]{48,}={0,2}")),
    # Hindi / Hinglish
    ("hi_ignore", re.compile(r"(निर्देश|निर्देशों).{0,20}(अनदेखा|भूल|नज़रअंदाज़)|(pichle|purane|saare)\s+(instructions?|nirdesh).{0,20}(bhool|ignore|bhul)", re.I)),
    # Tamil / Tanglish
    ("ta_ignore", re.compile(r"(அறிவுறுத்தல்|வழிமுறை).{0,30}(மறந்து|புறக்கணி)|(instructions?|rules?)[- ]?(a|ah|ai)?\s+(marandhu|maranthu|marandhudu|ignore pannu)", re.I)),
]


def scan_text(text: str) -> list[str]:
    return [name for name, pattern in INJECTION_RULES if pattern.search(text)]


# ---------------------------------------------------------------- output check

URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?((?:[a-z0-9-]+\.)+(?:com|net|org|io|bet|xyz|co|in|uk|info|biz|app|site|club|top|live|win|me|gg))\b(?:/\S*)?",
    re.I,
)
TRANSFER_VERBS = re.compile(
    r"\b(signed (for|with)|has signed|joined|joins|will join|completed (a|his|her) (move|transfer)|"
    r"moved to|transferred to|sealed a move|agreed (terms|a deal) with|"
    r"sign kar (liya|li|diya)|join kar (liya|li)|join kiya|sign kiya|"
    r"sign panni(taan|tan|ttaan|yachu|achu)|join panni(taan|tan|ttaan|yachu|achu)|sign aayitaan)\b",
    re.I,
)


@dataclass
class OutputVerdict:
    blocked: bool
    reason: str | None = None  # secret | link | unverified_transfer
    detail: str = ""


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def find_disallowed_link(reply: str, allowed_domains: list[str]) -> str | None:
    allowed = {d.lower() for d in allowed_domains}
    for m in URL_RE.finditer(reply):
        domain = m.group(1).lower()
        if not any(domain == a or domain.endswith("." + a) for a in allowed):
            return domain
    return None


def check_output(reply: str, gazetteer: Gazetteer, secret: str, allowed_domains: list[str]) -> OutputVerdict:
    if secret.lower() in reply.lower() or re.search(r"PUNDIT-ADMIN-\d{4}", reply, re.I):
        return OutputVerdict(True, "secret", "reply contained the admin key")
    if domain := find_disallowed_link(reply, allowed_domains):
        return OutputVerdict(True, "link", f"link to {domain}")
    if detail := find_unverified_transfer(reply, gazetteer):
        return OutputVerdict(True, "unverified_transfer", detail)
    return OutputVerdict(False)


def find_unverified_transfer(reply: str, gazetteer: Gazetteer) -> str | None:
    for sentence in _sentences(reply):
        if not TRANSFER_VERBS.search(sentence):
            continue
        ents = gazetteer.extract(sentence)
        if not ents.players or not ents.teams:
            continue
        for player_key in ents.players:
            for player in player_key.split("|"):
                verified = gazetteer.verified_team(player)
                # "X, who joined <verified club> from <old club>" names the real club, so it passes.
                if verified and verified not in ents.teams:
                    claimed = next(iter(sorted(ents.teams)))
                    return f"{player} -> {claimed} (verified: {verified})"
    return None


SAFE_REFUSAL = (
    "I can't share that. I only report what's in the verified stats, and I don't announce "
    "transfers, links or anything that isn't in the data."
)


def mentions(text: str, needle: str) -> bool:
    return fold(needle) in fold(text)
