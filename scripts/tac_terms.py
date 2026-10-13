"""Deterministic, source-bound keyword proposals from frozen TAC sections only.

This sidecar populates article review tables. It does not admit terms to the
retrieval glossary, translate them, expand acronyms or classify scientific facts.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from scripts.tac_boundary_review import validate_review
from scripts.tac_experiment import digest, validate_profiles, write_new

VERSION = "tac_term_candidates_v0.3"
INVENTORY_VERSION = "tac_term_inventory_v0.1"
PREVIEW_POLICY = "legacy_greedy_surface_v0.3"
WEIGHTS = {"T": 3, "A": 2, "C": 1}
LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"}
TOKEN = re.compile(r"[^\W_]+(?:[./-][^\W_]+)*\+?", re.UNICODE)
# Generic function words and reporting prose; domain vocabulary is not a stoplist.
STOPWORDS = frozenset("""
a an the and or of in on at to for from by with without as into through than that
this these those it its their our we they is are was were be been being has have
had can could may might will would should also both each all some such which
where when while not no only very more most much about between among during
using used use via based due however further respectively compared including
show shows showed shown found investigated investigate study studies work works
results result obtained demonstrated provide provides present paper effect effects
different various high low higher lower highest lowest good better best new novel
important significant significantly similar almost generally particularly namely because
under after before offers offer suffers suffer arising invoked typically indicates
maintain maintains largely prevents enables enable yield yields regulate regulating
prepared prepare corresponding relative overall mainly past decade wide thin
advanced advances influence origin type kinds types three two one first second
there therefore thus so rather still against less contains containing
exhibited follows forms contain support trigger gave sets describes mitigates known
comprehensive computed enhancing enhanced recent cohesive suitable able probing
и или в во на к ко с со из для от до по при через между что это этой этих этот
как так также однако чем а но же не без был была были быть является являются
его ее её их нами мы они которые который которая которых всех все весь всей
том числе более менее очень достаточно некоторых различных соответствующих
работе работа работы исследованы исследована исследовано исследование исследования
исследований результаты результат показано показали установлено установлены
получены получено получения использованием использование использованы можно
позволяет обеспечивают обеспечивает представляет имеют имеет является
данной данного данные данных образом целом сравнению случае необходимо
значительно существенно проведено выполнены отмечено практически всем свойства
значения значение роль изучение влияния влияние метод методом диапазоне области
системы системах составе зависимости показана течение всей наличие наличием сделан вывод обусловлено
""".split())
EN_NOUNS = frozenset("""
conductivity membrane battery solvent electrolyte ionomer oxide ether carbonate
sulfolane cell interphase transport property morphology toughness gelation
sorption enthalpy entropy dispersion solution temperature structure stability
viscosity capacity performance conduction parameter electrode cathode anode
fluorination energy density plasticiser plasticizer water gas decomposition
polymer interaction kinetics reversibility casting annealing mixture carbon
potential lithium magnesium material technology chargeability dischargeability
efficiency concentration cluster film channel phase transition nanoscale
mobility conformations conformation permeability functionality
""".split())
RU_ANCHORS = (
    "раствор", "мембран", "провод", "электролит", "сольват", "сульфолан", "карбонат", "термодинами",
    "энтальп", "энтроп", "ион", "кислот", "полимер", "сорб", "набух", "морфолог", "структур",
    "стекл", "температур", "вязк", "фаз", "димер", "частиц", "отжиг", "смешен", "литий", "лития", "вод",
)
REPORTING_STEMS = (
    "показ", "объяс", "характериз", "привод", "отмеч", "выраж", "отраж", "состав", "указыва", "обеспеч",
    "исслед", "установ", "достиг", "получ", "использ", "демонстр", "позвол", "осуществ", "представ",
    "подтверж", "предполож", "выяв", "примен", "наблюд", "выполн",
)


def stopword(token: str) -> bool:
    return token in STOPWORDS or token.startswith(REPORTING_STEMS)


def noun_anchor(token: str, raw: str) -> bool:
    # Surface heuristics, not POS tagging or a scientific ontology.
    core = token[:-3] + 'y' if token.endswith('ies') else token[:-1] if token.endswith('s') else token
    return (token in EN_NOUNS or core in EN_NOUNS or token in {'nafion', 'li-nafion', 'pfsa'}
            or any(anchor in token for anchor in RU_ANCHORS)
            or (2 <= len(raw) <= 15 and raw.isupper() and raw.isascii())
            or (any(c.isdigit() for c in raw) and any(c.isupper() for c in raw)))


def excluded_token(token: str, raw: str) -> bool:
    unit_base = re.sub(r"[-+]\d+$", "", token)
    return (stopword(token) or not any(c.isalpha() for c in token)
            or len(token) == 1
            or unit_base in {"ma", "mah", "cm", "dm", "mol", "g", "mg", "mm", "nm", "wt", "vol", "min", "ev"})


def crosses_broken_word(begin: int, end: int, offsets: list[int], broken: list[tuple[int, int]]) -> bool:
    return any(offsets[begin] < right and offsets[end-1] + 1 > left for left, right in broken)


def normalized_view(text: str) -> tuple[str, list[int]]:
    """Matching/display view, with a source-character map; never rewrite quotes.

    Whitespace collapses; known ligatures expand; typography hyphens fold to '-'.
    Broken words are not guessed or joined: 'conduc-\ntivity' stays 'conduc- tivity'.
    """
    chars: list[str] = []
    offsets: list[int] = []
    for index, char in enumerate(text):
        if char.isspace():
            if chars and chars[-1] != " ":
                chars.append(" ")
                offsets.append(index)
            continue
        value = LIGATURES.get(char, "-" if char in "‐‑–−" else char).casefold()
        chars.extend(value)
        offsets.extend([index] * len(value))
    return "".join(chars).strip(), offsets[:len("".join(chars).strip())]


def display_label(text: str) -> str:
    """Preserve case (especially chemical formulae) in the derived display label."""
    return " ".join("".join(LIGATURES.get(c, c) for c in text).split())


def load_seeds(path: Path) -> list[dict[str, str]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("entries"), list):
        raise ValueError("Term seed glossary must contain entries")
    seeds = []
    for entry in raw["entries"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("concept"), str) or not entry["concept"].strip():
            raise ValueError("Term seed glossary concept invalid")
        for language in ("en", "ru"):
            aliases = entry.get(language, [])
            if not isinstance(aliases, list) or any(not isinstance(a, str) or not a.strip() for a in aliases):
                raise ValueError("Term seed glossary aliases invalid")
            seeds.extend({"concept": entry["concept"], "alias": a, "language": language} for a in aliases)
    return seeds


def evidence(section: dict[str, Any], start: int, end: int, status: str) -> dict[str, Any]:
    quote = section["quote"][start:end]
    return {"kind": section["kind"], "page": section["page"],
            "start": section["start"] + start, "end": section["start"] + end, "quote": quote,
            "section_start": section["start"], "section_end": section["end"],
            "layer": section["layer"], "layer_id": section["layer_id"],
            "page_text_sha256": section["page_text_sha256"], "source_type": "pdf_selected_TAC_text",
            "tac_boundary_status": status}


def generate_candidates(profile: dict[str, Any], seeds: list[dict[str, str]],
                        assessments: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Complete ranked lexical output before preview selection; no semantic admission."""
    candidates: dict[str, dict[str, Any]] = {}

    def add(section: dict[str, Any], view: str, offsets: list[int], begin: int, end: int,
            method: str, concept: str | None = None) -> None:
        term = view[begin:end].strip()
        if not term:
            return
        item = candidates.setdefault(term, {"term": term, "status": "proposed", "methods": [], "seed_concepts": [],
                                             "evidence": []})
        if method not in item["methods"]:
            item["methods"].append(method)
        if concept and concept not in item["seed_concepts"]:
            item["seed_concepts"].append(concept)
        source = evidence(section, offsets[begin], offsets[end-1] + 1,
                          assessments[section["kind"]]["status"] if assessments else "unreviewed")
        if source not in item["evidence"]:
            item["evidence"].append(source)
        item["label"] = display_label(item["evidence"][0]["quote"])

    for section in profile["sections"]:
        view, offsets = normalized_view(section["quote"])
        broken = [m.span() for m in re.finditer(r"[^\W\d_]+[-\u00ad]\s*\n\s*[^\W\d_]+", section["quote"])]

        for seed in seeds:
            alias = normalized_view(seed["alias"])[0]
            alias_tokens = list(TOKEN.finditer(alias))
            if len(alias_tokens) > 6 or any(stopword(t.group()) and t.group() not in {'of', 'in', 'and', 'with'} for t in alias_tokens):
                continue
            for match in re.finditer(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", view):
                if not crosses_broken_word(match.start(), match.end(), offsets, broken):
                    add(section, view, offsets, match.start(), match.end(), "existing_glossary_match", seed["concept"])
        tokens = list(TOKEN.finditer(view))
        for i, token in enumerate(tokens):
            token_raw = section["quote"][offsets[token.start()]:offsets[token.end()-1]+1]
            if excluded_token(token.group(), token_raw) or crosses_broken_word(token.start(), token.end(), offsets, broken):
                continue
            for size in range(1, 5):
                group = tokens[i:i+size]
                if len(group) != size or any(
                    excluded_token(t.group(), "") or crosses_broken_word(t.start(), t.end(), offsets, broken) for t in group
                ):
                    break
                if any(view[left.end():right.start()] != " " for left, right in zip(group, group[1:], strict=False)):
                    break
                last_raw = section["quote"][offsets[group[-1].start()]:offsets[group[-1].end()-1]+1]
                if not noun_anchor(group[-1].group(), last_raw):
                    continue
                # Short standalone words need uppercase source evidence (EC, SL, SEI).
                raw = section["quote"][offsets[token.start()]:offsets[token.end()-1]+1]
                if size == 1 and len(token.group()) < 4 and not (len(raw) >= 2 and raw.isupper()):
                    continue
                add(section, view, offsets, group[0].start(), group[-1].end(), "TAC_lexical_phrase")
    ranked = []
    for item in candidates.values():
        counts = Counter(e["kind"] for e in item["evidence"])
        weighted = sum(WEIGHTS[kind] * min(count, 3) for kind, count in counts.items())
        word_count = len(list(TOKEN.finditer(item["term"])))
        item["score"] = weighted * word_count + bool(item["seed_concepts"])
        item["occurrences"] = len(item["evidence"])
        item["language"] = "ru" if re.search(r"[а-яё]", item["term"]) else "en_or_symbol"
        item["methods"].sort()
        item["seed_concepts"].sort()
        ranked.append(item)
    ranked.sort(key=lambda c: (-c["score"], -len(c["term"]), c["term"]))
    return ranked


def select_preview(ranked: list[dict[str, Any]], limit: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
        raise ValueError("Terms preview limit must be between 1 and 50")
    selected = []
    decisions = []
    for item in ranked:
        # Keep one nested surface phrase, not a claim of scientific synonymy.
        against = [s["term"] for s in selected if
                   re.search(r"(?<!\w)" + re.escape(item["term"]) + r"(?!\w)", s["term"]) or
                   re.search(r"(?<!\w)" + re.escape(s["term"]) + r"(?!\w)", item["term"])]
        state = "nested_surface_suppressed" if against else "preview_limit" if len(selected) >= limit else "selected"
        decisions.append({"term": item["term"], "state": state, "against_terms": against})
        if state == "selected":
            selected.append(item)
    return selected, decisions


def propose_article(profile: dict[str, Any], seeds: list[dict[str, str]], max_terms: int,
                    assessments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compatibility path: preserve the v0.3 selected-only article contract."""
    if not 1 <= max_terms <= 50:
        raise ValueError("max_terms must be between 1 and 50")
    ranked = generate_candidates(profile, seeds, assessments)
    selected, decisions = select_preview(ranked, max_terms)
    suppressed = sum(d["state"] == "nested_surface_suppressed" for d in decisions)
    return {"article_id": profile["article_id"], "original_pdf_sha256": profile["original_pdf_sha256"],
            "original_pdf_path": profile["original_pdf_path"], "terms": selected, "candidate_count": len(ranked),
            "nested_candidates_suppressed": suppressed, "status": "proposed" if selected else "not_detected",
            "diagnostics": ["Lexical proposals; no semantic acceptance, translation or acronym expansion.",
                            "TAC source boundaries and glyph damage may affect candidates.",
                            "Broken line-end words and standalone unit tokens excluded; no spelling repair.",
                            f"Display limit {max_terms}; candidate inventory {len(ranked)}."]}


def candidate_id(article_id: str, term: str) -> str:
    """Article-scoped lexical identity, not a global concept or source-mention ID."""
    return digest(json.dumps([article_id, term], ensure_ascii=False, separators=(",", ":")).encode())


def inventory_digest(inventory: list[dict[str, Any]]) -> str:
    return digest(json.dumps(inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def rank_features(term: dict[str, Any]) -> dict[str, Any]:
    counts = Counter(e["kind"] for e in term["evidence"])
    return {"occurrences_by_kind": dict(sorted(counts.items())),
            "weighted_capped_occurrences": sum(WEIGHTS[k] * min(n, 3) for k, n in counts.items()),
            "token_count": len(list(TOKEN.finditer(term["term"]))), "seed_match": bool(term["seed_concepts"])}


def preview_record(ranked: list[dict[str, Any]], limit: int) -> dict[str, Any]:
    selected, decisions = select_preview(ranked, limit)
    identifiers = {t["term"]: t["candidate_id"] for t in ranked}
    return {"limit": limit, "policy": PREVIEW_POLICY, "candidate_ids": [t["candidate_id"] for t in selected],
            "decisions": [{"candidate_id": identifiers[d["term"]], "state": d["state"],
                           "against_candidate_ids": [identifiers[t] for t in d["against_terms"]]} for d in decisions]}


def propose_inventory(profile: dict[str, Any], seeds: list[dict[str, str]], preview_limit: int,
                      assessments: dict[str, Any] | None = None) -> dict[str, Any]:
    ranked = generate_candidates(profile, seeds, assessments)
    for index, term in enumerate(ranked, 1):
        term.update(candidate_id=candidate_id(profile["article_id"], term["term"]),
                    rank=index, rank_features=rank_features(term))
    preview = preview_record(ranked, preview_limit)
    return {"article_id": profile["article_id"], "original_pdf_sha256": profile["original_pdf_sha256"],
            "original_pdf_path": profile["original_pdf_path"], "inventory": ranked,
            "inventory_sha256": inventory_digest(ranked), "candidate_count": len(ranked), "preview": preview,
            "status": "proposed" if ranked else "not_detected",
            "diagnostics": ["Complete output of the current lexical generator, not all scientific concepts in the article.",
                            "TAC source boundaries and glyph damage may affect candidates.",
                            "Broken line-end words and standalone unit tokens excluded; no spelling repair.",
                            "Nested surface candidates retained; preview suppression does not establish semantic relations."]}


def validate_terms(snapshot: dict[str, Any], profiles: dict[str, Any], terms: dict[str, Any], profiles_sha256: str) -> None:
    if terms.get("schema") not in {VERSION, INVENTORY_VERSION} or terms.get("profiles_sha256") != profiles_sha256:
        raise ValueError("Terms schema/profile hash mismatch")
    inventory_mode = terms["schema"] == INVENTORY_VERSION
    validate_profiles(snapshot, profiles, terms.get("snapshot_sha256", ""))
    if terms.get("state") != "proposed_for_article_review":
        raise ValueError("Terms must remain proposals")
    limit = terms.get("settings", {}).get("preview_limit" if inventory_mode else "max_terms")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
        raise ValueError("Terms display limit invalid")
    articles = {a["article_id"]: a for a in snapshot["articles"]}
    predicted = {p["article_id"]: p for p in profiles["profiles"]}
    rows = {r["article_id"]: r for r in terms["articles"]}
    if len(rows) != len(terms["articles"]) or set(rows) != set(articles):
        raise ValueError("Terms inventory mismatch")
    for identifier, row in rows.items():
        article = articles[identifier]
        if row["original_pdf_sha256"] != article["original_pdf_sha256"] or row["original_pdf_path"] != article["original_pdf_path"]:
            raise ValueError("Terms PDF identity mismatch")
        candidates = row.get("inventory" if inventory_mode else "terms")
        if not isinstance(candidates, list) or row.get("status") != ("proposed" if candidates else "not_detected"):
            raise ValueError("Terms row state/limit invalid")
        if not inventory_mode and len(candidates) > limit:
            raise ValueError("Terms row state/limit invalid")
        seen = set()
        for term in candidates:
            if term["status"] != "proposed" or not term["term"] or term["term"] in seen or not term["evidence"]:
                raise ValueError("Term state/duplicate/evidence invalid")
            if not term["methods"] or not set(term["methods"]) <= {"existing_glossary_match", "TAC_lexical_phrase"}:
                raise ValueError("Term proposal method invalid")
            if (term.get("occurrences") != len(term["evidence"]) or not isinstance(term.get("score"), (int, float))
                    or isinstance(term["score"], bool) or not math.isfinite(term["score"]) or term["score"] < 0):
                raise ValueError("Term score/occurrence count invalid")
            seen.add(term["term"])
            if term.get("label") != display_label(term["evidence"][0]["quote"]):
                raise ValueError("Term display label/source mismatch")
            for e in term["evidence"]:
                sources = [s for s in predicted[identifier]["sections"] if s["kind"] == e["kind"] and s["page"] == e["page"]
                           and s["start"] == e["section_start"] and s["end"] == e["section_end"]]
                if len(sources) != 1:
                    raise ValueError("Term evidence outside TAC sections")
                section = sources[0]
                if e.get("source_type") != "pdf_selected_TAC_text" or e.get("tac_boundary_status") not in {
                    "unreviewed", "pass", "boundary_error", "missed", "not_separately_delimited", "unresolved"
                }:
                    raise ValueError("Term source type/review status invalid")
                if not section["start"] <= e["start"] < e["end"] <= section["end"] or any(
                    e[k] != section[k] for k in ("layer", "layer_id", "page_text_sha256")
                ):
                    raise ValueError("Term evidence identity/offset mismatch")
                expected = section["quote"][e["start"]-section["start"]:e["end"]-section["start"]]
                if e["quote"] != expected or normalized_view(expected)[0] != term["term"]:
                    raise ValueError("Term exact quote/display mismatch")
            if inventory_mode:
                features = rank_features(term)
                expected_score = features["weighted_capped_occurrences"] * features["token_count"] + features["seed_match"]
                if (term.get("candidate_id") != candidate_id(identifier, term["term"])
                        or term.get("rank_features") != features or term["score"] != expected_score
                        or len({json.dumps(e, sort_keys=True) for e in term["evidence"]}) != len(term["evidence"])):
                    raise ValueError("Term inventory identity/rank features/evidence duplicates invalid")
        if inventory_mode:
            if (type(row.get("candidate_count")) is not int or row["candidate_count"] != len(candidates)
                    or row.get("inventory_sha256") != inventory_digest(candidates)
                    or [t.get("rank") for t in candidates] != list(range(1, len(candidates) + 1))
                    or candidates != sorted(candidates, key=lambda t: (-t["score"], -len(t["term"]), t["term"]))):
                raise ValueError("Terms complete inventory count/hash/order invalid")
            if terms.get("settings", {}).get("preview_policy") != PREVIEW_POLICY or row.get("preview") != preview_record(candidates, limit):
                raise ValueError("Terms preview references/policy/decisions invalid")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--glossary", type=Path, default=Path("docs/cross_lingual_glossary.yaml"))
    parser.add_argument("--boundary-review", type=Path)
    parser.add_argument("--format", choices=("legacy-v0.3", "inventory"), default="legacy-v0.3",
                        help="Explicit new complete inventory, or backward-compatible selected-only v0.3 (default)")
    limits = parser.add_mutually_exclusive_group()
    limits.add_argument("--max-terms", type=int, help="Legacy stored-list limit; only with --format legacy-v0.3")
    limits.add_argument("--preview-limit", type=int, help="Preview only; requires --format inventory; default 12")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inventory_mode = args.format == "inventory"
    if (inventory_mode and args.max_terms is not None) or (not inventory_mode and args.preview_limit is not None):
        parser.error("Use --preview-limit with --format inventory; --max-terms applies only to legacy-v0.3")
    limit = args.preview_limit if inventory_mode else args.max_terms
    limit = 12 if limit is None else limit
    if not 1 <= limit <= 50:
        parser.error("Terms preview/legacy limit must be between 1 and 50")
    snapshot_raw, profiles_raw, seed_raw = args.snapshot.read_bytes(), args.profiles.read_bytes(), args.glossary.read_bytes()
    snapshot, profiles = json.loads(snapshot_raw), json.loads(profiles_raw)
    validate_profiles(snapshot, profiles, digest(snapshot_raw))
    review_raw = args.boundary_review.read_bytes() if args.boundary_review else None
    reviewed = validate_review(snapshot, profiles, json.loads(review_raw), digest(profiles_raw)) if review_raw else {}
    seeds = load_seeds(args.glossary)
    proposer = propose_inventory if inventory_mode else propose_article
    articles = [proposer(p, seeds, limit, reviewed.get(p["article_id"], {}).get("assessments"))
                for p in profiles["profiles"]]
    result = {"schema": INVENTORY_VERSION if inventory_mode else VERSION,
              "created_at": datetime.now(UTC).isoformat(), "state": "proposed_for_article_review",
              "snapshot_sha256": digest(snapshot_raw), "profiles_sha256": digest(profiles_raw),
              "glossary_sha256": digest(seed_raw), "review_sha256": digest(review_raw) if review_raw else None,
              "code_sha256": digest(Path(__file__).read_bytes()),
              "settings": {"max_phrase_tokens": 4, "section_weights": WEIGHTS,
                           "score": "sum(section_weight * min(occurrences_in_kind, 3)) * token_count + seed_match",
                           "stopwords": sorted(STOPWORDS), "reporting_stems": REPORTING_STEMS,
                           "english_noun_anchors": sorted(EN_NOUNS), "russian_anchors": RU_ANCHORS,
                           }, "articles": articles}
    result["settings"].update({"preview_limit": limit, "preview_policy": PREVIEW_POLICY, "nested_surface_preview_only": True}
                              if inventory_mode else {"max_terms": limit, "nested_surface_suppression": True})
    validate_terms(snapshot, profiles, result, digest(profiles_raw))
    write_new(args.output, result)
    field = "inventory" if inventory_mode else "terms"
    summary = {"documents": len(articles), "with_terms": sum(bool(a[field]) for a in articles),
               "proposed_terms": sum(len(a[field]) for a in articles),
               "methods": dict(Counter(m for a in articles for t in a[field] for m in t["methods"]))}
    if inventory_mode:
        summary.update(schema=result["schema"], preview_terms=sum(len(a["preview"]["candidate_ids"]) for a in articles))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
