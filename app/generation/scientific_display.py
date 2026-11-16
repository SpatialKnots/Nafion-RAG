"""Local, escaped scientific-text display. Never rewrites stored/model text."""

from __future__ import annotations

import re
from html import escape


class MathSyntaxError(ValueError):
    pass


SYMBOLS = {
    "times": "×", "cdot": "·", "circ": "°", "degree": "°", "pm": "±", "mp": "∓",
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "Delta": "Δ", "sigma": "σ",
    "omega": "ω", "Omega": "Ω", "mu": "μ", "rho": "ρ", "theta": "θ", "lambda": "λ",
    "approx": "≈", "sim": "∼", "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥",
    "infty": "∞", "rightarrow": "→", "to": "→", "%": "%", "_": "_", "{": "{", "}": "}",
}
MATH = re.compile(r"\$\$(?P<display>[^$\n]+)\$\$|\$(?P<inline>[^$\n]+)\$|"
                  r"\\\((?P<round>.*?)\\\)|\\\[(?P<square>.*?)\\\]", re.S)


class _Math:
    def __init__(self, raw: str) -> None:
        if len(raw) > 2000 or any(ord(c) < 32 for c in raw):
            raise MathSyntaxError("Formula is oversized or contains control characters")
        self.raw, self.position = raw, 0

    def group(self, depth: int) -> str:
        if self.position >= len(self.raw) or self.raw[self.position] != "{":
            raise MathSyntaxError("Expected a braced argument")
        self.position += 1
        return self.parse(depth + 1, grouped=True)

    def parse(self, depth: int = 0, *, grouped: bool = False) -> str:
        if depth > 12:
            raise MathSyntaxError("Formula nesting exceeded")
        parts: list[str] = []
        while self.position < len(self.raw):
            char = self.raw[self.position]
            self.position += 1
            if char == "}":
                if not grouped:
                    raise MathSyntaxError("Unexpected closing brace")
                return "".join(parts)
            if char == "{":
                parts.append(self.parse(depth + 1, grouped=True))
            elif char in "^_":
                if self.position >= len(self.raw):
                    raise MathSyntaxError("Missing script")
                if self.raw[self.position] == "{":
                    value = self.group(depth)
                elif self.raw[self.position].isalnum():
                    value = escape(self.raw[self.position])
                    self.position += 1
                else:
                    raise MathSyntaxError("Unsupported unbraced script")
                tag = "sup" if char == "^" else "sub"
                parts.append(f"<{tag}>{value}</{tag}>")
            elif char == "\\":
                match = re.match(r"[A-Za-z]+|.", self.raw[self.position:])
                if match is None:
                    raise MathSyntaxError("Incomplete command")
                command = match[0]
                self.position += len(command)
                if command in SYMBOLS:
                    parts.append(escape(SYMBOLS[command]))
                elif command in {",", ";", " ", ":", "!"}:
                    parts.append(" " if command != "!" else "")
                elif command in {"mathrm", "text", "operatorname", "mathbf"}:
                    parts.append(self.group(depth))
                elif command == "frac":
                    numerator, denominator = self.group(depth), self.group(depth)
                    parts.append('<span class="math-fraction"><span>' + numerator + '</span><span>'
                                 + denominator + '</span></span>')
                else:
                    raise MathSyntaxError("Unsupported formula command")
            else:
                parts.append(escape(char, quote=True))
        if grouped:
            raise MathSyntaxError("Unclosed formula group")
        return "".join(parts)


def scientific_text(value: object) -> str:
    """Render a bounded LaTeX subset; unknown/malformed formulas remain escaped."""
    text = "" if value is None else str(value)
    parts, cursor = [], 0
    for match in MATH.finditer(text):
        parts.append(escape(text[cursor:match.start()], quote=True))
        raw = next(item for item in match.groups() if item is not None)
        if match.group("inline") is not None and not (
            re.search(r"\\[A-Za-z]|[\^_={}×·°]", raw) or re.fullmatch(r"\s*[-+]?\d+(?:[.,]\d+)?\s*|[A-Za-z0-9]+", raw)
        ):
            parts.append(escape(match[0], quote=True))
            cursor = match.end()
            continue
        try:
            parsed = _Math(raw).parse()
        except MathSyntaxError:
            parts.append('<code class="math-unparsed" title="Нераспознанная разметка; показан исходный текст">'
                         + escape(match[0], quote=True) + '</code>')
        else:
            parts.append('<span class="scientific-math">' + parsed + '</span>')
        cursor = match.end()
    parts.append(escape(text[cursor:], quote=True))
    return "".join(parts)
