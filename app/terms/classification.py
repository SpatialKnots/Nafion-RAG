"""Draft policy classifications of exact term uses; no scientific acceptance."""
from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import Field, model_validator

from app.records.schema import text_hash
from app.terms.contexts import identity
from app.terms.schema import ArticleContexts, NonEmpty, Sha256, TermModel

Axis = Literal["type", "role", "origin"]
Sort = Literal["rank", "alphabetical", "source"]
VERSION = "tac_term_classification_v0.1"
AUTOMATIC_VERSION = "tac_term_classification_v0.2"
CONTEXT_VERSION = "tac_term_classification_v0.3"
PHRASE_VERSION = "tac_term_classification_v0.4"
MANUAL_VERSION = "tac_manual_classification_proposals_v0.1"


class Rule(TermModel):
    rule_id: NonEmpty
    axis: Axis
    category: NonEmpty
    match: Literal["exact_phrase", "preceding_cue", "context_phrase", "anchored_context", "surface_pattern"]
    phrases: list[NonEmpty]
    pattern: str
    require_type: list[NonEmpty]
    rationale: NonEmpty
    priority: int = Field(default=0, ge=0)


class Taxonomy(TermModel):
    schema_version: Literal[
        "tac_terms_taxonomy_v0.1", "tac_terms_taxonomy_v0.2", "tac_terms_taxonomy_v0.3", "tac_terms_taxonomy_v0.4"
    ] = Field(alias="schema")
    state: Literal["draft_requires_domain_review", "automatic_context_policy"]
    categories: dict[Axis, dict[str, str]]
    rules: list[Rule]

    @model_validator(mode="after")
    def check_policy(self) -> Taxonomy:
        automatic = self.schema_version != "tac_terms_taxonomy_v0.1"
        if automatic != (self.state == "automatic_context_policy"):
            raise ValueError("Classification taxonomy version/state mismatch")
        if set(self.categories) != {"type", "role", "origin"}:
            raise ValueError("Classification axes incomplete")
        if any("unclassified" not in categories or "unresolved" not in categories for categories in self.categories.values()):
            raise ValueError("Classification unknown/conflict categories missing")
        if len({r.rule_id for r in self.rules}) != len(self.rules):
            raise ValueError("Classification rule identities duplicated")
        for rule in self.rules:
            if rule.category not in self.categories[rule.axis] or rule.category in {"unclassified", "unresolved"}:
                raise ValueError("Classification rule category invalid")
            if rule.match == "surface_pattern":
                if (self.schema_version != 'tac_terms_taxonomy_v0.4' or rule.axis != 'type'
                        or rule.phrases or rule.require_type or rule.priority or not rule.pattern):
                    raise ValueError('Classification surface-pattern rule invalid')
                re.compile(rule.pattern)
            elif rule.match == "anchored_context":
                if (self.schema_version not in {"tac_terms_taxonomy_v0.3", "tac_terms_taxonomy_v0.4"} or rule.axis == "type" or rule.phrases
                        or rule.priority or rule.pattern.count("__TERM__") != 1
                        or any(c not in self.categories["type"] for c in rule.require_type)):
                    raise ValueError("Classification anchored-context rule invalid")
                compiled = re.compile(rule.pattern.replace("__TERM__", "(?P<term>x)"))
                if set(compiled.groupindex) != {"term"}:
                    raise ValueError("Classification anchored context requires only the generated term capture")
            elif rule.match == "context_phrase":
                if not automatic or rule.axis != "type" or rule.phrases or rule.require_type:
                    raise ValueError("Classification context-phrase rule invalid")
                compiled = re.compile(rule.pattern)
                if "term" not in compiled.groupindex:
                    raise ValueError("Classification context rule requires an exact named term span")
            elif rule.priority:
                raise ValueError("Classification priority is only supported for context-phrase rules")
            elif rule.match == "exact_phrase":
                if rule.axis != "type" or not rule.phrases or rule.pattern or rule.require_type:
                    raise ValueError("Classification exact-phrase rule invalid")
                if any(p != normalize(p) for p in rule.phrases):
                    raise ValueError("Classification policy phrases must be normalized")
            elif (rule.axis == "type" or rule.phrases or not rule.pattern.endswith("$")
                  or any(c not in self.categories["type"] for c in rule.require_type)):
                raise ValueError("Classification context cue rule invalid")
            else:
                re.compile(rule.pattern)
        return self


class Basis(TermModel):
    rule_id: NonEmpty
    source_region_id: Sha256
    start: int
    end: int
    quote: NonEmpty
    quote_sha256: Sha256
    rationale: NonEmpty

    @model_validator(mode="after")
    def check_quote(self) -> Basis:
        if not 0 <= self.start < self.end or self.end - self.start != len(self.quote) or text_hash(self.quote) != self.quote_sha256:
            raise ValueError("Classification basis quote/offset/hash mismatch")
        return self


class Proposal(TermModel):
    category: NonEmpty
    basis: list[Basis]
    producer: Literal["policy", "manual_proposal"]
    declared_reviewer: str = ""


class Assignment(TermModel):
    assignment_id: Sha256
    use_id: Sha256
    term_id: Sha256
    mention_id: Sha256
    context_id: Sha256
    axis: Axis
    state: Literal["proposed", "unclassified", "unresolved"]
    proposals: list[Proposal]
    diagnostics: list[NonEmpty]


class ManualProposal(TermModel):
    use_id: Sha256
    axis: Axis
    category: NonEmpty
    reason: NonEmpty
    declared_reviewer: NonEmpty
    declared_reviewer_kind: Literal["assistant", "human"]


class ManualInput(TermModel):
    schema_version: Literal["tac_manual_classification_proposals_v0.1"] = Field(alias="schema")
    contexts_sha256: Sha256
    taxonomy_sha256: Sha256
    proposals: list[ManualProposal]


def normalize(value: str) -> str:
    """Matching only; never mutate source text or stored labels."""
    return " ".join(value.casefold().split())


def clause_end(text: str, end: int) -> int:
    """Extend evidence to the next sentence/semicolon boundary, preserving exact text."""
    return end + len(re.split(r"[.!?;]", text[end:], maxsplit=1)[0])


def unsupported_clause(quote: str) -> bool:
    return bool(re.search(r"(?i)\b(?:not|never|no|will|would|planned|expected)\b|n['’]t|\[\s*\d", quote))


def category_members(assignment: dict[str, Any]) -> set[str]:
    categories = {p["category"] for p in assignment["proposals"]}
    if assignment["state"] != "proposed":
        categories.add(assignment["state"])
    return categories


def classify_article(row: dict[str, Any], taxonomy: Taxonomy, taxonomy_hash: str,
                     manual: list[ManualProposal] | None = None) -> dict[str, Any]:
    automatic = taxonomy.schema_version != "tac_terms_taxonomy_v0.1"
    if automatic and manual:
        raise ValueError("Automatic Terms classification does not accept manual proposals")
    article = ArticleContexts.model_validate(row)
    contexts = {c.context_id: c for c in article.contexts}
    mentions = {m.mention_id: m for m in article.mentions}
    use_ids = {u.use_id for u in article.uses}
    decisions = []
    manual_map: dict[tuple[str, str], list[ManualProposal]] = {}
    for proposal in manual or []:
        if proposal.use_id not in use_ids or proposal.category not in taxonomy.categories[proposal.axis]:
            raise ValueError("Manual classification target/category invalid")
        if proposal.category in {"unclassified", "unresolved"}:
            raise ValueError("Manual proposals require a substantive category")
        key = (proposal.use_id, proposal.axis)
        if any(p.category == proposal.category for p in manual_map.get(key, [])):
            raise ValueError("Duplicate manual classification proposal")
        manual_map.setdefault(key, []).append(proposal)
    for use in article.uses:
        source = mentions[use.mention_id].source
        context = contexts[use.context_id]
        prefix = context.source.quote[:source.start - context.source.start]
        contextual: list[tuple[Rule, re.Match[str]]] = []
        for rule in taxonomy.rules:
            if rule.match != "context_phrase":
                continue
            for context_match in re.finditer(rule.pattern, context.source.quote):
                lo, hi = context_match.span("term")
                if (context.source.start + lo, context.source.start + hi) == (source.start, source.end):
                    contextual.append((rule, context_match))
        if contextual:
            priority = max(rule.priority for rule, _ in contextual)
            contextual = [(rule, match) for rule, match in contextual if rule.priority == priority]
        type_candidates = {r.category for r in taxonomy.rules if r.axis == "type" and (
            normalize(source.quote) in r.phrases or (r.match == 'surface_pattern' and re.fullmatch(r.pattern, normalize(source.quote))))}
        if contextual:
            type_candidates = {rule.category for rule, _ in contextual}
        type_candidates.update(p.category for p in manual_map.get((use.use_id, "type"), []))
        for axis in ("type", "role", "origin"):
            proposals = []
            for rule in taxonomy.rules:
                if rule.axis != axis:
                    continue
                if rule.match == "context_phrase" or (axis == "type" and contextual):
                    continue
                if rule.match == "anchored_context":
                    # One exact existing mention, never an invented/nested endpoint.
                    if rule.require_type and not (len(type_candidates) == 1 and type_candidates <= set(rule.require_type)):
                        continue
                    pattern = rule.pattern.replace("__TERM__", "(?P<term>" + re.escape(source.quote) + ")")
                    candidates = [m for m in re.finditer(pattern, context.source.quote)
                                  if (context.source.start + m.start("term"), context.source.start + m.end("term"))
                                  == (source.start, source.end)]
                    for cue in candidates:
                        end = clause_end(context.source.quote, cue.end())
                        quote = context.source.quote[cue.start():end]
                        if unsupported_clause(quote):
                            continue
                        basis = Basis(rule_id=rule.rule_id, source_region_id=context.source.region_id,
                                      start=context.source.start + cue.start(), end=context.source.start + end,
                                      quote=quote, quote_sha256=text_hash(quote), rationale=rule.rationale)
                        proposals.append(Proposal(category=rule.category, basis=[basis], producer="policy"))
                    continue
                if rule.match in {"exact_phrase", "surface_pattern"}:
                    if (normalize(source.quote) not in rule.phrases
                            and not (rule.match == 'surface_pattern' and re.fullmatch(rule.pattern, normalize(source.quote)))):
                        continue
                    region, start, end, quote = source.region_id, source.start, source.end, source.quote
                else:
                    if rule.require_type and not (type_candidates & set(rule.require_type)):
                        continue
                    if (taxonomy.schema_version in {"tac_terms_taxonomy_v0.3", "tac_terms_taxonomy_v0.4"} and rule.require_type
                            and not (len(type_candidates) == 1 and type_candidates <= set(rule.require_type))):
                        continue
                    match = re.search(rule.pattern, prefix)
                    if match is None:
                        continue
                    region, start, end = context.source.region_id, context.source.start + match.start(), source.end
                    if taxonomy.schema_version in {"tac_terms_taxonomy_v0.3", "tac_terms_taxonomy_v0.4"}:
                        end = context.source.start + clause_end(context.source.quote, end - context.source.start)
                        if unsupported_clause(context.source.quote[match.start():end - context.source.start]):
                            continue
                    quote = context.source.quote[match.start():end - context.source.start]
                basis = Basis(rule_id=rule.rule_id, source_region_id=region, start=start, end=end, quote=quote,
                              quote_sha256=text_hash(quote), rationale=rule.rationale)
                proposals.append(Proposal(category=rule.category, basis=[basis], producer="policy"))
            if axis == "type":
                for rule, context_match in contextual:
                    quote = context_match.group()
                    basis = Basis(rule_id=rule.rule_id, source_region_id=context.source.region_id,
                                  start=context.source.start + context_match.start(), end=context.source.start + context_match.end(),
                                  quote=quote, quote_sha256=text_hash(quote), rationale=rule.rationale)
                    proposals.append(Proposal(category=rule.category, basis=[basis], producer="policy"))
            for p in manual_map.get((use.use_id, axis), []):
                basis = Basis(rule_id="manual_source_context", source_region_id=context.source.region_id,
                              start=context.source.start, end=context.source.end, quote=context.source.quote,
                              quote_sha256=context.source.quote_sha256, rationale=p.reason)
                proposals.append(Proposal(category=p.category, basis=[basis], producer="manual_proposal",
                                          declared_reviewer=f"{p.declared_reviewer_kind}:{p.declared_reviewer}"))
            proposals.sort(key=lambda p: (p.category, p.producer, p.basis[0].rule_id, p.declared_reviewer))
            count = len({p.category for p in proposals})
            state: Literal["proposed", "unclassified", "unresolved"] = (
                "unclassified" if count == 0 else "proposed" if count == 1 else "unresolved")
            diagnostics = ["No supported policy cue or manual proposal; unknown retained."] if count == 0 else [
                "Conflicting candidate categories retained; review required." if count > 1 else
                "Policy/manual proposal only; scientific acceptance not performed."]
            if automatic:
                diagnostics = ["No supported automatic rule; unknown retained."] if count == 0 else [
                    "Automatic rules remain ambiguous; alternatives retained without a user resolution task." if count > 1 else
                    "Automatic source-bound classification; no human confirmation is implied."]
                if contextual:
                    diagnostics.append("Explicit type context rules take precedence over generic exact-name rules.")
            if context.boundary_status != "pass":
                diagnostics.append(f"Source TAC boundary status: {context.boundary_status}; classification does not repair it.")
            payload = json.dumps([p.model_dump(mode="json") for p in proposals], sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            decisions.append(Assignment(assignment_id=identity("classification", use.use_id, axis, taxonomy_hash, payload),
                                        use_id=use.use_id, term_id=use.term_id, mention_id=use.mention_id,
                                        context_id=use.context_id, axis=axis, state=state, proposals=proposals,
                                        diagnostics=diagnostics).model_dump(mode="json"))
    assignments = sorted(decisions, key=lambda d: (d["use_id"], d["axis"]))
    result: dict[str, Any] = {"article_id": article.article_id, "assignments": assignments}
    result["groups"] = {axis: [subset(row, assignments, {axis: category}, "rank") | {"category": category,
                            "label": label, "axis": axis} for category, label in categories.items()]
                        for axis, categories in taxonomy.categories.items()}
    return result


def subset(row: dict[str, Any], assignments: list[dict[str, Any]], filters: dict[str, str], sort: Sort) -> dict[str, Any]:
    """AND filters on the same use, then distinct article-local terms. Never join roles across uses."""
    if not filters or not set(filters) <= {"type", "role", "origin"} or sort not in {"rank", "alphabetical", "source"}:
        raise ValueError("Terms subset filter/sort invalid")
    by_use: dict[str, dict[str, set[str]]] = {}
    for assignment in assignments:
        by_use.setdefault(assignment["use_id"], {})[assignment["axis"]] = category_members(assignment)
    uses = [u for u in row["uses"] if all(category in by_use.get(u["use_id"], {}).get(axis, set()) for axis, category in filters.items())]
    members = {u["term_id"] for u in uses}
    terms = [t for t in row["terms"] if t["term_id"] in members]
    if sort == "alphabetical":
        terms.sort(key=lambda t: (normalize(t["label"]), t["term_id"]))
    elif sort == "source":
        mentions = {m["mention_id"]: m["source"] for m in row["mentions"]}
        first = {t["term_id"]: min((mentions[u["mention_id"]]["page_number"], mentions[u["mention_id"]]["start"], u["use_id"])
                                  for u in uses if u["term_id"] == t["term_id"]) for t in terms}
        terms.sort(key=lambda t: (first[t["term_id"]], t["term_id"]))
    return {"filters": filters, "sort": sort, "term_ids": [t["term_id"] for t in terms],
            "use_ids": sorted(u["use_id"] for u in uses), "count": len(terms)}
