"""Bounded source-quote selection for Nafion lithiation-method overviews.

The finite parsers establish textual candidates only. Model output may select
exact attributed quotations; it cannot turn them into unverified free claims.
All numeric/chemical ownership states remain unverified and no values propagate.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Any

from app.generation.providers import Evidence, GeneratedClaim, GenerationOutputError

VERSION = "nafion_lithiation_quote_selection_v0.1"
SOURCE_TYPE = "procedure_derived"
CONTRACT_TYPES = {SOURCE_TYPE: VERSION, "comparison_derived": "nafion_swelling_transition_v0.1"}
METHOD = re.compile(r"ионным\s+обменом|ионного\s+обмена|ion[ -]+exchange|нейтрализаци\w*|neutrali[sz]ation", re.I)
OVERVIEW = re.compile(r"\b(?:метод\w*|методик\w*|способ\w*|methods|ways|procedures)\b", re.I)
LITHIATION = re.compile(r"\b(?:литировани\w*|lithiation|lithiate)\b", re.I)
ALLOWED = set((
    "какие существуют методики методы способы литирования литирование нафион nafion li h мембран мембраны "
    "мембрана дисперсии дисперсий для получения описаны описано известны есть применяют используются "
    "получения литированной формы литиевая литиевой какие найдены literature the what which are methods "
    "ways procedures of for to used available reported known nafion lithiation lithiate membranes membrane "
    "dispersion dispersions li h"
).split())


@dataclass(frozen=True)
class Overview:
    eligible: bool
    reason: str
    records: list[dict[str, Any]]
    evidence: list[Evidence]
    diagnostics: list[dict[str, Any]]

    def metadata(self) -> dict[str, Any]:
        return {"version": VERSION, "eligible": self.eligible, "reason": self.reason,
                "records": self.records, "diagnostics": self.diagnostics,
                "scope": "found_source_descriptions_not_complete_method_catalogue",
                "scientific_acceptance": "not_established", "values_propagated": False,
                "output_policy": "exact_source_quote_selection_only"}


def prepare(question: str, evidence: list[Evidence], *, answer_language: str = "auto") -> Overview | None:
    normalized = unicodedata.normalize("NFKC", question)
    if not (OVERVIEW.search(normalized) and LITHIATION.search(normalized) and re.search(r"\b(?:Nafion|нафион)\b", normalized, re.I)):
        return None
    # The frozen diagnostic readers also inspect historical GigaChat JSON.
    # Import them only after provider modules have finished initialization.
    from scripts import lithiation_subject_context_audit as context
    tokens = re.findall(r"[a-zа-яё0-9]+", normalized.casefold())
    unsupported = sorted(set(tokens) - ALLOWED)
    if unsupported:
        return Overview(False, "unsupported_lithiation_overview_constraint", [], [], [{"unsupported_terms": unsupported}])
    english = answer_language == "en" or (answer_language == "auto" and not re.search(r"[а-яё]", question, re.I))
    records, selected, diagnostics = [], [], []
    for source in evidence:
        result = context.audit(source.text)
        source_records = []
        for attempt in result["attempts"]:
            row = result["baseline"]["operations"][attempt["operation_index"]]
            if attempt["state"] not in {"context_subject_candidate_unverified", "local_target_already_present"}:
                continue
            if context._material_conflicts(row["region"]["text"]) or context._operation_object_conflicts(row["region"]["text"]):
                continue
            # A local candidate still needs an affirmative unambiguous operation,
            # a literally named method, and LiOH in that very operation region.
            if row["status"] != "affirmative_action_cue_unverified":
                continue
            method = METHOD.search(row["region"]["text"])
            reagents = [field for field in row["fields"] if field["field"] == "reagent"]
            if method is None or not reagents:
                continue
            links = [link for link in attempt["links"] if link["state"] == "context_subject_candidate_unverified"]
            if links:
                link = next((link for link in links if link["kind"] == "explicit_figure_subpanel_reference"), links[0])
                material_context = (link["caption"]["span"] if link["kind"] == "explicit_figure_subpanel_reference"
                                    else link["subject_heading"]["span"])
                binding_kind = link["kind"]
                forms = (link["subpanel"]["form_cues"] if binding_kind == "explicit_figure_subpanel_reference"
                         else link["subject_heading"]["form_cues"])
            else:
                material_context = row["target_links"][0]
                binding_kind = "explicit_local_template"
                forms = [item["form_cue"] for item in row["target_links"]]
            span = row["region"]
            method_span = {"start": span["start"] + method.start(), "end": span["start"] + method.end(), "text": method.group()}
            fields = {}
            for name in ("reagent", "concentration", "duration", "temperature"):
                candidates = [field["span"] for field in row["fields"] if field["field"] == name]
                fields[name] = {"state": "single_literal_in_operation_unverified" if len(candidates) == 1 else
                               "not_found_in_operation" if not candidates else "multiple_literals_unresolved",
                               "spans": candidates, "owner_established": False}
            incomplete = not source.text.rstrip().endswith((".", "!", "?", ";"))
            if english:
                claim = (f'Found description: “{method.group()}”. Material context: “{material_context["text"].strip()}”. '
                         f'Operation: “{span["text"].strip()}”. The selected excerpts do not establish a complete catalogue of methods.')
                if incomplete:
                    claim += " The selected source excerpt ends mid-protocol; this is not a complete protocol."
            else:
                claim = (f'Найденное описание: «{method.group()}». Контекст материала: «{material_context["text"].strip()}». '
                         f'Операция: «{span["text"].strip()}». Полный перечень методик по выбранным фрагментам не установлен.')
                if incomplete:
                    claim += " Выбранный фрагмент обрывается; это не полный протокол."
            record = {"citation_id": source.citation_id, "article_id": source.article_id, "chunk_id": source.chunk_id,
                      "pages": [source.page_start, source.page_end], "material_context": material_context,
                      "binding_kind": binding_kind, "operation": span, "method": method_span, "fields": fields,
                      "material": {"family_cue": "Nafion", "form_cue": forms[0] if len(set(forms)) == 1 else "not_established",
                                   "grade": "not_established", "state": "textual_candidate_unverified"},
                      "source_excerpt_incomplete": incomplete, "allowed_claim": claim,
                      "material_owner_established": False, "performed_established": False}
            records.append(record)
            source_records.append(record)
        diagnostics.append({"citation_id": source.citation_id, "subject_context": result,
                            "record_count": len(source_records)})
        if source_records:
            payload = {"version": VERSION, "records": source_records,
                       "policy": "Select exact allowed_claim strings only. No paraphrases or additional conditions. "
                                 "These are attributed source descriptions, not scientific confirmations."}
            selected.append(replace(source, source_type=SOURCE_TYPE, text=json.dumps(payload, ensure_ascii=False)))
    return Overview(bool(records), "bounded_source_quote_candidates" if records else "no_bounded_lithiation_description",
                    records, selected, diagnostics)


def allowed_claims(evidence: list[Evidence]) -> dict[str, list[str]]:
    selected = [item for item in evidence if item.source_type in CONTRACT_TYPES]
    if not selected:
        return {}
    if len(selected) != len(evidence):
        raise GenerationOutputError("Procedure quote evidence must not mix with unrestricted evidence")
    result = {}
    for item in selected:
        try:
            payload = json.loads(item.text)
        except (ValueError, UnicodeError) as exc:
            raise GenerationOutputError("Invalid procedure quote contract") from exc
        if not isinstance(payload, dict) or payload.get("version") != CONTRACT_TYPES[item.source_type]:
            raise GenerationOutputError("Unsupported procedure quote contract")
        records = payload.get("records")
        if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
            raise GenerationOutputError("Invalid procedure records")
        claims = [record.get("allowed_claim") for record in records]
        if not claims or not all(isinstance(claim, str) and claim.strip() for claim in claims):
            raise GenerationOutputError("Empty procedure quote selection")
        result[item.citation_id] = [str(claim) for claim in claims]
    return result


def validate_claims(claims: list[GeneratedClaim], allowed: dict[str, list[str]]) -> None:
    if not allowed:
        return
    seen = set()
    for claim in claims:
        if (len(claim.citation_ids) != 1 or claim.text not in allowed.get(claim.citation_ids[0], [])
                or claim.text in seen):
            raise GenerationOutputError("Bounded answer must select unique exact source-backed statements")
        seen.add(claim.text)
