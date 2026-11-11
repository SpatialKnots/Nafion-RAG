# Offline claim checks, v0.1

10 November 2026, Asia/Yekaterinburg. Continue the evidence workflow after the
bounded context action. This stage implements an explicit local checker, not an
answer admission policy, model reviewer, new retrieval action, API or product UI.
All previous live budgets remain closed. No model/OAuth/slots, database work,
PDF/index writes, ingestion, deployment or automatic continuation.

Before implementation, freeze current app Python/YAML, this protocol and existing
requirement controls; replay the five current and 76 old full service results and
five unsent native bodies. Preserve all previous work and outputs. Freeze hashes
are evidence of the current dirty working tree, not a clean Git commit.

Input: a canonical evidence packet v0.1, a separately supplied trusted current
requirement-preparation parent, a pinned packet ID, and explicit structured claims.
Reconstruct/validate the full packet first. An embedded parent alone is not an
authenticity check. Context-action capsules and unsupported packet versions fail.
No parsing of arbitrary answer prose or automatic construction of claims. Explicit
claim origin is caller-supplied diagnostic assertion, never a model/human verdict.

Three claim kinds, strict schemas with extra fields forbidden:

- Quotation: an existing exact anchor reference and asserted text. Compare to the
  complete bound raw anchor, without Unicode/whitespace repair or substring search.
  Mismatch means mismatch at that anchor, not absence from the article/literature.
- Fact: an existing fact reference and complete structured tuple: property,
  sample/value/unit/method (text, normalization and numeric interpretation),
  operation, conditions, epistemic status, unknown fields. Compare every field to
  the fact reconstructed by the existing recipe. Report raw-surface presence of
  supplied textual values separately, including normalization differences.
  Report conflicting candidates/uninspected sources and role identity separately;
  matching one tuple never resolves alternative candidates or cross-role ownership.
- Arithmetic: an existing transformation reference and an explicit decimal sum
  (ordered operands, result, unchanged unit). Independently recompute using exact
  rational decimal arithmetic; compare operands/unit and result to the bound
  recipe. No unit conversion, inferred quantities, ratio support or context joins.
  Preserve both raw decimal spelling and exact numeric comparison. Arithmetic is
  system-derived, not literal source prose or semantic/scientific confirmation.

Each result separates literal presence, finite semantic contract status,
arithmetic, and scientific validity. Scientific validity is always not_evaluated.
Quotation semantics remain not_evaluated. Fact tuple equality is explicitly a
finite source-contract comparison, not general entailment/ownership verification.
Differences are not automatically scientific contradictions. No overall approval
or confidence percentage, no deletion of baseline blockers, no admission change.
Keep exact refs, source/page/layer descriptors, unresolved page mapping and unknowns.

Bound work: at most 64 claims, 1024 characters per value, 8000 per quote, 32
conditions/unknowns, 16 decimal sum operands, 80 characters per decimal, and
256000 canonical claim-input bytes. Reject duplicate claim IDs, extra keys,
foreign refs, malformed decimals, unsupported contracts and invalid source graphs.
Empty claims produce an explicit no_claims stop, never a vacuous approval.

Separate canonical report keeps input claims/packet ID/parent hash, declared
checker code bindings, inherited stop/blockers and the parent journal root.
Append deterministic check events and a stop event with sequence/hash links.
Validate by reconstruction from trusted inputs and current code plus pinned report
ID; reject tampering, stale code, reordering and noncanonical JSON. Export local
files exclusively; never overwrite old snapshots or read embedded PDF paths.

Controls: exact/wrong quotes; same numeric text under wrong cell/condition/unit;
lost approximation/unknown fields; unsupported/free prose; foreign/duplicate IDs;
conflicting/uninspected sources; Unicode and dehyphenated raw surfaces; exact
decimal addition and wrong operands/result/unit; schema/budget edges; corrupted
packet/report/event/code/parent/pins; canonical round trip and overwrite refusal;
no retrieval/provider calls. Include saved exposed real raw and constructed cases
separately; neither is independent scientific evaluation. Run affected tests,
Ruff and full app mypy; compare all 81 results/five native bodies after changes.
Generate a local HTML diagnostic review with exact quotes/statuses/refs and reuse
the existing 33-work TAC review without rewriting its outputs. Static HTML/link
checks are not a browser-layout check. Preserve failures and report limitations.
