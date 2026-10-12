"""Local textual cues for review, never scientific roles or selection rules."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class NumericContextCue:
    kind: str
    start: int
    end: int
    text: str


# Anchored to the immediately preceding text on the same line. No propagation
# through lists, sentences, page boundaries or figure panels is attempted.
PREFIX_CUES = (
    ("scale_bar_cue", re.compile(
        r"(?P<cue>\bscale[ -]bars?|\bмасштабн(?:ая|ые)\s+линейк(?:а|и))\s*[:,=]?\s*$", re.IGNORECASE,
    )),
    ("approximation_cue", re.compile(
        r"(?P<cue>[~≈∼]|\b(?:approximately|approx\.?|roughly|around|about|ca\.|circa|около|примерно|приблизительно))\s*$",
        re.IGNORECASE,
    )),
    ("inequality_cue", re.compile(
        r"(?P<cue><=|>=|[≤≥<>]|\b(?:at\s+most|at\s+least|less\s+than|more\s+than|no\s+more\s+than|"
        r"no\s+less\s+than|не\s+более|не\s+менее|менее|более))\s*$", re.IGNORECASE,
    )),
)


def numeric_context_cues(text: str, *, start: int, end: int, line_start: int, line_end: int) -> list[NumericContextCue]:
    """Return exact cue spans in chunk text. An empty list does not mean exact.

    A cue is lexical evidence only, including in negated or quoted statements.
    It does not assign a material, operator, experiment or figure role.
    """
    cues = []
    prefix = text[line_start:start]
    for kind, pattern in PREFIX_CUES:
        match = pattern.search(prefix)
        if match:
            left, right = match.span("cue")
            cues.append(NumericContextCue(kind, line_start + left, line_start + right, match.group("cue")))
    if not prefix.strip() and not text[end:line_end].strip():
        cues.append(NumericContextCue("isolated_numeric_line", start, end, text[start:end]))
    return cues
