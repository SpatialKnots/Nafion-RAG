"""Finite exact-quotation contracts for explicitly referenced compound questions.

These contracts admit attributed source excerpts, never unverified free claims.
Scientific ownership, independent accuracy and unit interpretation remain unknown.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from typing import Any

from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError
from app.retrieval.source_reference import normalize, reference

VERSION = "explicit_reference_quotes_v0.3"
SOURCE_TYPE = "reference_quote_derived"
COMMON = set("и в с ним были была каков какова какие каким способом из этой при the what which how of and in with for to a an".split())
COMPOSITION_WORDS = (r"состав\w*|разработан\w*|электролит\w*|фторирован\w*|эфир\w*|карбонат\w*|"
                     r"результат\w*|циклирован\w*|получен\w*|ячейк\w*")
PREPARATION_WORDS = (r"получ\w*|не|содержащ\w*|этанол\w*|водн\w*|дисперс\w*|образец|протонн\w*|проводим\w*|"
                     r"мембран\w*|изготовлен\w*|сравнени\w*|коммерческ\w*")
ENGLISH_WORDS = set(("composition developed electrolyte fluorinated ether carbonates cycling results obtained cells "
                     "prepare prepared preparation ethanol free aqueous water dispersion sample proton conductivity membrane "
                     "made comparison compare commercial from containing without was were it its this").split())
STATUS_EXCLUSIONS = re.compile(
    r"\b(?:did|does|do) not (?:obtain|prepare|measure|perform|test|cycle)|"
    r"\b(?:not measured|not performed|not prepared|will|would|proposed|plan to|hypothe[st]|future work)", re.I)


@dataclass(frozen=True)
class Packet:
    eligible: bool
    reason: str
    evidence: list[Evidence]
    display: list[Evidence]
    records: list[dict[str, Any]]
    diagnostics: dict[str, Any]

    def metadata(self) -> dict[str, Any]:
        return {"version": VERSION, "eligible": self.eligible, "reason": self.reason, "records": self.records,
                "diagnostics": self.diagnostics, "output_policy": "all_required_ascii_ids_then_server_quotes_or_abstention",
                "scientific_ownership_verified": False, "units_converted": False}


def _span(raw: str, start: int, end: int) -> dict[str, Any]:
    leading = len(raw[start:end]) - len(raw[start:end].lstrip())
    text = raw[start:end].strip()
    return {"start": start + leading, "end": start + leading + len(text), "text": text}


def _regions(raw: str, start: str, end: str) -> list[dict[str, Any]]:
    result = []
    for match in re.finditer(start, raw, re.I | re.M):
        finish = re.search(end, raw[match.end():], re.I | re.M)
        if finish is not None:
            result.append(_span(raw, match.start(), match.end() + finish.start()))
    return result


def _cell(value: str) -> str:
    return re.sub(r"\s+", "", normalize(value)).replace("‖", "||")


def _label_in(label: str, raw: str) -> bool:
    body = normalize(raw)
    if re.search(r"(?<!\w)" + re.escape(label.casefold()) + r"(?!\w)", body):
        return True
    # A source footnote marker must have its own definition; b1a is otherwise a
    # different label. Do not silently strip arbitrary sample suffixes.
    return any(re.search(r"(?<!\w)" + re.escape(label.casefold() + marker) + r"\)", body)
               for marker in re.findall(r"^([a-z])\)\s", raw, re.M))


def _family(question: str) -> str | None:
    text = normalize(question)
    if (re.search(r"состав|composition", text) and re.search(r"циклирован|cycling", text)
            and re.search(r"фторирован|fluorinated", text) and re.search(r"эфир|ether", text)):
        return "composition_cycling"
    if (re.search(r"nafion", text) and re.search(r"дисперс|dispersion", text)
            and re.search(r"этанол|ethanol", text) and re.search(r"проводим|conductiv", text)):
        return "preparation_conductivity"
    return None


def prepare(question: str, evidence: list[Evidence], metadata: Any, *, answer_language: str = "auto") -> Packet | None:
    citation, family = reference(question), _family(question)
    if citation is None or family is None:
        return None
    diagnostics: dict[str, Any] = {"family": family}

    def blocked(reason: str) -> Packet:
        return Packet(False, reason, [], [], [], diagnostics)

    if not isinstance(metadata, dict) or metadata.get("resolved") is not True:
        return blocked("explicit_reference_not_uniquely_resolved")
    sources = [e for e in evidence if e.article_id == metadata.get("article_id")]
    if not sources or len(sources) != len(evidence):
        return blocked("reference_evidence_not_one_resolved_work")
    named_authors = re.findall(r"[A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)*", question[citation.start:citation.end])
    front_pages = [e for e in sources if e.page_start == 1]
    identity = []
    for source in front_pages:
        heading_end = re.search(r"^\s*(?:abstract\s*:|introduction\s*$|\d+\.\s*introduction|dissolution procedures|tab(?:le|\.))",
                                source.text, re.I | re.M)
        prefix = source.text[:heading_end.start()] if heading_end else ""
        author_words = set(re.findall(r"\w+", normalize(prefix)))
        if all(set(re.findall(r"\w+", normalize(name))) <= author_words for name in named_authors) and re.search(
                r"(?<!\d)" + re.escape(citation.year) + r"(?!\d)", source.text):
            identity.append(source.citation_id)
    diagnostics["front_matter_author_citation_ids"] = identity
    if not identity:
        return blocked("explicit_authors_not_bound_to_source_front_matter")
    remainder = question[:citation.start] + " " + question[citation.end:]
    cells = re.findall(r"Li\s*(?:‖|\|\|)\s*[A-Z][A-Za-z0-9₀-₉]*", remainder)
    product_match = re.search(r"(?:образец|sample)\s+([a-z]\d+)\b", remainder, re.I)
    product = product_match[1] if product_match else ""
    grades = re.findall(r"Nafion[-‐‑ ]\d+", remainder, re.I)
    comparators = re.findall(r"\b[A-Z][A-Z0-9]{2,}\b", remainder)
    for literal in [*cells, *grades, *comparators, product]:
        if literal:
            remainder = remainder.replace(literal, " ")
    words = re.findall(r"[a-zа-яё0-9]+", normalize(remainder))
    pattern = COMPOSITION_WORDS if family == "composition_cycling" else PREPARATION_WORDS
    unsupported = sorted({w for w in words if w not in COMMON | ENGLISH_WORDS and not re.fullmatch(pattern, w)})
    diagnostics["unsupported_query_terms"] = unsupported
    if unsupported:
        return blocked("unsupported_explicit_reference_constraint")
    required = ("abstract",) if family == "composition_cycling" else ("method", "table")
    candidates: dict[str, list[tuple[Evidence, dict[str, Any]]]] = {key: [] for key in required}
    for source in sources:
        if family == "composition_cycling":
            for span in _regions(source.text, r"^\s*abstract\s*:", r"^\s*(?:keywords\s*:|\d+\.\s+introduction)"):
                body = normalize(span["text"])
                if (len(set(map(_cell, cells))) != 2 or len(span["text"]) > 4500 or STATUS_EXCLUSIONS.search(body)
                        or not all(_cell(c) in _cell(span["text"]) for c in cells)
                        or not all(token in body for token in ("electrolyte", "ether", "carbonate"))
                        or not re.search(r"fluoro|fluorinat", body)
                        or not re.search(r"\b\d+(?:\.\d+)?\s*m\b", body)
                        or not re.search(r"\d+\s*:\s*\d+", body) or not re.search(r"by volume|by mass|molar", body)):
                    continue
                # Preserve whole abstract and every condition. These are textual
                # coverage guards, not inferred links between experimental values.
                if all(re.search(r"\d", sentence) and re.search(r"cycles|times", sentence)
                       and "%" in sentence and re.search(r"\bma\b", sentence)
                       for cell in cells for sentence in [_cell_sentence(body, cell)]):
                    candidates["abstract"].append((source, span))
        else:
            if len(grades) != 1 or not product or len(comparators) != 1:
                continue
            for span in _regions(source.text, r"^\s*dissolution procedures\s*$", r"^\s*(?:nafion recast film|characterisation)\s*$"):
                body = normalize(span["text"])
                if (len(span["text"]) <= 4500 and not STATUS_EXCLUSIONS.search(body) and _label_in(product, span["text"])
                        and normalize(grades[0]) in body and re.search(r"ethanol[ -]free", body)
                        and "azeotropic distillation" in body and "water" in body
                        and re.search(r"\d+\s*k\b", body) and re.search(r"(?:\d+|six|one|two) hours?", body)):
                    candidates["method"].append((source, span))
            for span in _regions(source.text, r"^\s*tab(?:le|\.)\s*\d+\.", r"^\s*fig(?:ure|\.)\s*\d+\."):
                body = normalize(span["text"])
                if (len(span["text"]) <= 4500 and not STATUS_EXCLUSIONS.search(body) and "conductivity" in body
                        and "water content" in body and _label_in(product, span["text"])
                        and _label_in(comparators[0], span["text"])
                        and re.search(r"(?<!\w)s\s*(?:[n·⋅×]\s*)?cm\s*[−–-]\s*1\b", body)
                        and len(re.findall(r"^\s*\d+\.\d+\s*$", span["text"], re.M)) >= 2):
                    candidates["table"].append((source, span))
    diagnostics["missing_roles"] = [role for role, found in candidates.items() if not found]
    if diagnostics["missing_roles"]:
        return blocked("missing_bounded_reference_source_roles")
    records = []
    parents: dict[str, Evidence] = {}
    english = answer_language == "en" or (answer_language == "auto" and not re.search(r"[а-яё]", question, re.I))
    for ordinal, role in enumerate(required, 1):
        # Repeated overlapping chunks may expose the identical quotation; retain
        # a single deterministic parent. Different quotations are ambiguous.
        unique = {span["text"] for _, span in candidates[role]}
        if len(unique) != 1:
            return blocked("ambiguous_bounded_reference_passage")
        source, span = min(candidates[role], key=lambda pair: (len(pair[0].text), pair[0].chunk_id))
        prefix = ("Source quotation" if english else "Цитата источника") + " (" + role + "):\n"
        record = {"role": role, "selection_id": f"S{ordinal}", "citation_id": source.citation_id, "article_id": source.article_id,
                  "chunk_id": source.chunk_id, "raw_span": span,
                  "raw_chunk_sha256": hashlib.sha256(source.text.encode()).hexdigest(),
                  "allowed_claim": prefix + "«" + span["text"] + "»", "scientific_ownership_verified": False}
        records.append(record)
        parents[source.citation_id] = source
    selected = [replace(source, source_type=SOURCE_TYPE, text=json.dumps({"version": VERSION,
                "records": [r for r in records if r["citation_id"] == source.citation_id]}, ensure_ascii=False))
                for source in parents.values()]
    return Packet(True, "complete_bounded_reference_quotations", selected, list(parents.values()), records, diagnostics)


def _cell_sentence(body: str, cell: str) -> str:
    normalized_cell = _cell(cell)
    for sentence in re.split(r"(?<=[.!?])\s+", body):
        if normalized_cell in _cell(sentence):
            return sentence
    return ""


def validate_complete(claims: list[GeneratedClaim], packet: Packet) -> None:
    if {c.text for c in claims} != {r["allowed_claim"] for r in packet.records}:
        raise GenerationOutputError("Bounded reference answer must select every required source quotation")


def selection_records(evidence: list[Evidence]) -> dict[str, dict[str, Any]]:
    selected = [e for e in evidence if e.source_type == SOURCE_TYPE]
    if not selected:
        return {}
    if len(selected) != len(evidence):
        raise GenerationOutputError("Reference selections must not mix with unrestricted evidence")
    result: dict[str, dict[str, Any]] = {}
    for source in selected:
        try:
            payload = json.loads(source.text)
        except (ValueError, UnicodeError) as exc:
            raise GenerationOutputError("Invalid reference selection contract JSON") from exc
        if not isinstance(payload, dict) or payload.get("version") != VERSION:
            raise GenerationOutputError("Unsupported reference selection contract")
        records = payload.get("records")
        if not isinstance(records, list) or not records:
            raise GenerationOutputError("Empty reference selection records")
        for record in records:
            if not isinstance(record, dict):
                raise GenerationOutputError("Invalid reference selection record")
            selection_id = record.get("selection_id")
            span = record.get("raw_span")
            if (not isinstance(selection_id, str) or not re.fullmatch(r"S[1-9][0-9]*", selection_id, re.ASCII)
                    or selection_id in result or record.get("citation_id") != source.citation_id
                    or record.get("article_id") != source.article_id or record.get("chunk_id") != source.chunk_id
                    or record.get("role") not in {"abstract", "method", "table"} or not isinstance(span, dict)
                    or not isinstance(span.get("text"), str) or not span["text"]
                    or type(span.get("start")) is not int or type(span.get("end")) is not int
                    or span["start"] < 0 or span["end"] - span["start"] != len(span["text"])):
                raise GenerationOutputError("Invalid or duplicate reference selection ID/binding")
            allowed = {prefix + " (" + record["role"] + "):\n«" + span["text"] + "»"
                       for prefix in ("Source quotation", "Цитата источника")}
            if record.get("allowed_claim") not in allowed:
                raise GenerationOutputError("Reference selection is not an exact attributed quotation")
            result[selection_id] = record
    if set(result) != {f"S{i}" for i in range(1, len(result) + 1)}:
        raise GenerationOutputError("Noncanonical reference selection ID set")
    return dict(sorted(result.items(), key=lambda pair: int(pair[0][1:])))


def selection_choices(evidence: list[Evidence]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for selection_id, record in selection_records(evidence).items():
        result.setdefault(record["citation_id"], []).append(selection_id)
    return result


def resolve_selections(claims: list[GeneratedClaim], evidence: list[Evidence]) -> list[GeneratedClaim]:
    records = selection_records(evidence)
    if not records:
        return claims
    seen = set()
    for claim in claims:
        if (claim.text not in records or claim.text in seen
                or claim.citation_ids != [records[claim.text]["citation_id"]]):
            raise GenerationOutputError("Invalid reference selection ID or citation")
        seen.add(claim.text)
    if seen != set(records):
        raise GenerationOutputError("Reference selection must include every required ID")
    # Only server-held text is rendered. Nothing from the model is normalized,
    # repaired, combined with the quote, or used as a source quotation.
    return [GeneratedClaim(record["allowed_claim"], [record["citation_id"]]) for record in records.values()]


def verify_raw_binding(payload_text: str, raw: str, *, article_id: str, chunk_id: str, citation_id: str | None = None) -> None:
    payload = json.loads(payload_text)
    records = payload.get("records")
    if payload.get("version") != VERSION or not isinstance(records, list) or not records:
        raise ValueError("Invalid reference quote binding")
    seen = set()
    for record in records:
        span = record["raw_span"]
        selection_id = record.get("selection_id")
        if (not isinstance(selection_id, str) or not re.fullmatch(r"S[1-9][0-9]*", selection_id, re.ASCII)
                or selection_id in seen or record["article_id"] != article_id or record["chunk_id"] != chunk_id
                or (citation_id is not None and record["citation_id"] != citation_id)
                or record["raw_chunk_sha256"] != hashlib.sha256(raw.encode()).hexdigest()
                or raw[span["start"]:span["end"]] != span["text"]):
            raise ValueError("Reference quote differs from original raw source")
        seen.add(selection_id)
        if record["role"] not in {"abstract", "method", "table"} or record["allowed_claim"] not in {
                prefix + " (" + record["role"] + "):\n«" + span["text"] + "»" for prefix in ("Source quotation", "Цитата источника")}:
            raise ValueError("Reference allowed claim differs from exact attributed quotation")
