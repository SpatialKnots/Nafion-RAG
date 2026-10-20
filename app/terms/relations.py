"""Experimental, source-bound relations from two explicit local grammatical templates.

No co-occurrence inference, new endpoints, cross-context links or numeric records.
Every output is an algorithm proposal or deferred diagnostic, never confirmation.
"""
from __future__ import annotations

import html
import json
import re
from typing import Any

from app.records.schema import source_identity, text_hash
from app.terms.classification import Taxonomy, classify_article
from app.terms.contexts import identity
from app.terms.schema import ArticleContexts, SourceFragment, TermUse

VERSION = "tac_term_relations_pilot_v0.1"
POLICY: dict[str, Any] = {
    "version": VERSION,
    "property-of": r"\s+of\s+(?:the\s+)?",
    "measured-by": r"\s+(?:(?:was|were|is|are)\s+)?measured\s+(?:by|using)\s+(?:the\s+)?",
    "scope": "same selected A/C context and sentence; existing disjoint TermUse endpoints only",
    "types": {"subject": ["property"], "property-of": ["material_substance", "object"], "measured-by": ["method"]},
    "guards": "boundary pass, unambiguous maximal endpoint, no negation/future/citation/hypothesis/list/comparison/model cue",
}


def content_hash(data: Any) -> str:
    return text_hash(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def build_relations(contexts: dict[str, Any], classification: dict[str, Any], bindings: dict[str, str]) -> dict[str, Any]:
    """Reproduce source classifications and retain every recognized template, including abstentions."""
    if classification["manual_input"] is not None or classification["contexts_sha256"] != bindings["contexts"]:
        raise ValueError("Relation pilot requires matching automatic classification without manual input")
    taxonomy = Taxonomy.model_validate(classification["taxonomy"])
    if taxonomy.schema_version == "tac_terms_taxonomy_v0.1":
        raise ValueError("Relation pilot requires automatic taxonomy")
    classes = {a["article_id"]: a for a in classification["articles"]}
    if len(classes) != len(classification["articles"]) or set(classes) != {a["article_id"] for a in contexts["articles"]}:
        raise ValueError("Relation classification article scope mismatch")
    articles: list[dict[str, Any]] = []
    for raw in contexts["articles"]:
        article = ArticleContexts.model_validate(raw)
        expected = classify_article(raw, taxonomy, classification["taxonomy_sha256"])
        if classes[article.article_id] != expected:
            raise ValueError("Relation endpoint classification does not reproduce source/policy")
        types = {a["use_id"]: a for a in expected["assignments"] if a["axis"] == "type"}
        origins = {a["use_id"]: {p["category"] for p in a["proposals"]}
                   for a in expected["assignments"] if a["axis"] == "origin"}
        mentions = {m.mention_id: m.source for m in article.mentions}
        records: list[dict[str, Any]] = []
        for context in article.contexts:
            uses = [u for u in article.uses if u.context_id == context.context_id]
            def source(use: TermUse, lookup: dict[str, SourceFragment] = mentions) -> SourceFragment:
                return lookup[use.mention_id]
            def category(use: TermUse, lookup: dict[str, Any] = types) -> str | None:
                a = lookup[use.use_id]
                return a["proposals"][0]["category"] if a["state"] == "proposed" else None
            subjects = [u for u in uses if category(u) == "property"]
            # Prefer the maximal typed property at the same ending offset (e.g. ionic conductivity).
            subjects = [u for u in subjects if not any(source(v).end == source(u).end and source(v).start < source(u).start
                                                       for v in subjects)]
            for subject in subjects:
                s = source(subject)
                relative_end = s.end - context.source.start
                for predicate in ("property-of", "measured-by"):
                    cue = re.match(POLICY[predicate], context.source.quote[relative_end:], re.I)
                    if cue is None:
                        continue
                    target_start = s.end + cue.end()
                    targets = [u for u in uses if source(u).start == target_start and source(u).end > s.end]
                    # A known short word cannot silently stand in for a longer unknown compound.
                    if targets:
                        longest = max(source(u).end for u in targets)
                        targets = [u for u in targets if source(u).end == longest]
                    target = targets[0] if len(targets) == 1 else None
                    left = context.source.quote[:s.start - context.source.start]
                    begin = max((m.end() for m in re.finditer(r"[.!?;]", left)), default=0)
                    rest = context.source.quote[relative_end:]
                    finish = relative_end + len(re.split(r"[.!?;]", rest, maxsplit=1)[0])
                    quote = context.source.quote[begin:finish]
                    evidence = context.source.model_dump(mode="json")
                    evidence.update(start=context.source.start + begin, end=context.source.start + finish,
                                    quote=quote, quote_sha256=text_hash(quote))
                    evidence["region_id"] = source_identity(evidence)
                    SourceFragment.model_validate(evidence)
                    reasons = []
                    if context.kind == "T":
                        reasons.append("title_only_not_supported")
                    if context.boundary_status != "pass":
                        reasons.append("TAC_boundary_not_pass:" + context.boundary_status)
                    if origins[subject.use_id] & {"cited_work", "hypothesis"}:
                        reasons.append("subject_attributed_to_cited_work_or_hypothesis")
                    if re.search(r"(?i)\b(?:not|never|no|will|would|may|could|planned|expected|"
                                 r"hypothesi\w*|assum\w*|previous|earlier)\b|n['’]t", quote):
                        reasons.append("negated_future_hypothetical_or_previous_work_clause")
                    if re.search(r"(?i)\bet\s+al\b|\[\s*\d|\b(?:model\w*|derived|calculated|compared|than|versus)\b", quote):
                        reasons.append("citation_model_or_comparison_not_supported")
                    if target is None:
                        reasons.append("missing_or_ambiguous_existing_endpoint")
                    else:
                        if source(target).end > context.source.start + finish:
                            reasons.append("endpoint_crosses_sentence_boundary")
                        if category(target) not in POLICY["types"][predicate]:
                            reasons.append("endpoint_type_unknown_ambiguous_or_incompatible")
                        after = context.source.quote[source(target).end - context.source.start:finish]
                        # A typed root cannot replace an unrepresented qualified compound (lithium metal,
                        # Nafion-115 membrane, Nafion water dispersion). Require an explicit object ending.
                        if not re.match(r"\s*(?:$|[(),]|\b(?:is|are|was|were|has|have|can|"
                                        r"in|at|with|prepared|plasticised|plasticized|increased|increases|"
                                        r"decreased|decreases|obey|obeys|show|shows)\b)", after, re.I):
                            reasons.append("endpoint_does_not_end_explicit_object_phrase")
                        if re.match(r"\s*(?:,|/|\band\b|\bor\b)", after, re.I):
                            reasons.append("multiple_objects_or_procedures_not_supported")
                    payload: dict[str, Any] = {"predicate": predicate, "subject_use_id": subject.use_id,
                               "object_use_id": target.use_id if target else None, "context_id": context.context_id,
                               "evidence": evidence, "state": "deferred" if reasons else "proposed",
                               "subject_label": s.quote, "object_label": source(target).quote if target else None,
                               "diagnostics": reasons or ["Explicit grammatical template; scientific acceptance not performed."],
                               "producer": "automatic_policy", "human_confirmation": False,
                               "rationale": "Explicit property-of object or measured-by method; "
                                            "existing source endpoints required; no sample identity is inferred."}
                    payload["relation_id"] = identity(VERSION, article.article_id, content_hash(payload), content_hash(bindings))
                    records.append(payload)
        articles.append({"article_id": article.article_id, "relations": sorted(records, key=lambda r: r["relation_id"]),
                         "diagnostics": [] if records else ["No supported explicit relation template; co-occurrence is insufficient."]})
    return {"schema": VERSION, "state": "experimental_proposals_not_scientifically_accepted", "input_sha256": bindings,
            "contexts_content_sha256": content_hash(contexts), "classification_content_sha256": content_hash(classification),
            "policy": POLICY, "policy_sha256": content_hash(POLICY), "articles": articles}


def validate_relations(contexts: dict[str, Any], classification: dict[str, Any], data: dict[str, Any],
                       bindings: dict[str, str]) -> None:
    if data != build_relations(contexts, classification, bindings):
        raise ValueError("Relation source/endpoint/direction/policy/input mismatch")


def relation_table(table: str, data: dict[str, Any]) -> str:
    """Add read-only relation diagnostics inside Terms, preserving the eight columns."""
    rows = {a["article_id"]: a for a in data["articles"]}
    def insert(match: re.Match[str]) -> str:
        aid = html.unescape(match.group(2))
        row = rows.pop(aid)
        cards = []
        for r in row["relations"]:
            evidence = r["evidence"]
            href = re.search(r'<a class="original" href="([^"]+)"', match.group(3))
            if href is None:
                raise ValueError("Relation table original PDF link missing")
            source_link = href.group(1) + "#page=" + str(evidence["page_number"])
            cards.append('<details class="scientific-relation" data-relation-id="' + r["relation_id"] + '"><summary>'
                         + html.escape(r["predicate"] + ': ' + r["state"] + ' · ' + r['subject_label']
                                       + ' → ' + (r['object_label'] or 'отсутствующий endpoint')) + '</summary><p>'
                         + html.escape(r["subject_use_id"] + ' → ' + str(r["object_use_id"])) + '</p><pre>'
                         + html.escape(evidence["quote"]) + '</pre><p>' + html.escape('; '.join(r["diagnostics"]))
                         + '</p><a href="' + source_link + '">Исходная страница</a><p>'
                         + html.escape(f"{evidence['text_layer_id']}; offsets [{evidence['start']}, {evidence['end']}); "
                                       f"quote SHA-256 {evidence['quote_sha256']}")
                         + '</p></details>')
        block = ('<details class="relation-pilot"><summary>Пилот связей: ' + str(len(cards))
                 + '</summary><p>Автоматические предложения / abstain; научное подтверждение не выполнено.</p>'
                 + ''.join(cards) + '<p>' + html.escape('; '.join(row['diagnostics'])) + '</p></details>')
        cells = match.group(3).split('</td>')
        if len(cells) != 9:
            raise ValueError("Relation table requires eight columns")
        cells[6] += block
        return match.group(1) + '</td>'.join(cells) + '</tr>'
    result = re.sub(r'(<tr data-id="([^"]+)"[^>]*>)(.*?)</tr>', insert, table, flags=re.S)
    if rows:
        raise ValueError("Relation table scope missing articles")
    summary = (f'<p class="identity">Relation pilot {VERSION}; policy {data["policy_sha256"]}; '
               f'inputs {html.escape(json.dumps(data["input_sha256"], sort_keys=True))}. '
               'Только property-of / measured-by в одном контексте. Отсутствие предложения не означает отсутствие связи.</p>')
    return result.replace('<div class="toolbar">', summary + '<div class="toolbar">', 1)
