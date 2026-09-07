# Retrieval Error Fixing Policy

## Purpose

This policy defines how retrieval errors should be fixed in ARIADNE.

The project should improve retrieval behavior by fixing general classes of
errors, not by adding hidden one-query or one-article shortcuts.

## Core Rule

Every retrieval fix must state the error class it addresses before code changes
are made.

Acceptable fix shape:

```text
observed failure
  -> error class
  -> corpus-backed evidence
  -> explicit feature or diagnostic
  -> regression question
  -> before/after evaluation
```

Unacceptable fix shape:

```text
if query text equals X, promote article Y
```

Article-specific expectations are allowed in evaluation gold data, but ranking
code should use source-visible features such as terms, phrases, protected tokens,
titles, source type, numeric evidence, and conflict diagnostics.

## Error Classes

Use these classes unless a new class is justified in the implementation report.

### `article_crowding`

One article contributes many medium-quality chunks and pushes a stronger article
out of the inspected window.

Preferred mechanisms:

- article-diverse candidate windows;
- capped chunk-support contribution;
- article-level evidence coverage.

### `property_confusion`

The query asks for one property, but retrieval is dominated by a nearby property.

Examples:

- ionic conductivity vs proton conductivity;
- lithium-ion transport vs electronic conductivity;
- swelling degree vs generic sorption;
- phase diagram vs EC/SL conductivity;
- broad/plural plasticizer conductivity survey evidence vs EC/SL-only binary
  plasticizer conductivity evidence.

Preferred mechanisms:

- protected property terms;
- positive evidence for the requested property;
- narrow conflict penalties when the wrong property appears without the right
  one.

### `compound_intent_ambiguity`

The same compound system appears in multiple scientific contexts.

Examples:

- EC/SL as binary plasticizer;
- EC/SL as phase diagram;
- EC/SL as Li-Nafion swelling medium;
- EC/SL as conductivity modifier.

Preferred mechanisms:

- query-intent diagnostics;
- co-occurrence of compound tokens with property/method terms;
- no broad glossary expansion unless backed by missed evidence.

### `method_title_intent`

The query names a method, article-level title phrase, or experimental setup, but
results are dominated by incidental mentions or references.

Examples:

- solution casting morphology;
- casting solvent and annealing temperature;
- mixing temperature and physicochemical properties.

Preferred mechanisms:

- title phrase match;
- method phrase match in full chunk text;
- best component rank as a tie-breaker for intent-matched chunks.

### `numeric_table_evidence`

The query asks for a comparison or numeric relation, but retrieval returns prose
background instead of table-like evidence.

Preferred mechanisms:

- table/source-type evidence;
- numeric condition coverage;
- unit/column/header terms;
- derived table evidence when implemented and verified.

### `source_type_ambiguity`

Multiple source types are relevant, and the query wording is ambiguous.

Examples:

- standalone paper vs dissertation;
- review/background article vs primary experimental paper;
- article text vs bibliography entry.

Preferred mechanisms:

- explicit evaluation relevance grades;
- ambiguity diagnostics;
- source-visible quality signals such as DOI-bearing main text vs
  reference-like bibliography chunks;
- query wording that distinguishes source type when needed.

Do not force one source through hidden article-specific code when multiple stored
sources genuinely contain relevant evidence.

### `mixed_language_protected_tokens`

The query mixes languages and contains scientific tokens that must survive
normalization.

Examples:

- donor number;
- acceptor number;
- dielectric constant;
- DMF/DMSO/NMP/DMAc;
- EC/SL;
- Li-Nafion/H-Nafion.

Preferred mechanisms:

- protected-token extraction;
- boundary-aware short-token matching;
- phrase preservation across query variants.

## Required Evidence Before A Fix

### Check for `gold_source_mismatch` first

An expected article may not support the compounds, conditions, or method named
in the question. Verify the question against the source before changing retrieval.
An incidental mention or citation of another study is not evidence that the
target article performed the named experiment.

When the gold question is wrong, record the original wording, source checksum,
page/section evidence and corrected wording. Keep user-authored questions intact
unless an explicit relabeling is documented. Report corrected-set metrics as a
new baseline, not a retrieval improvement, and compare unchanged questions
separately. Do not weaken protected-token requirements to satisfy invalid gold.

The Ma solvent-list correction is documented in
`stage2_gold_audit_2026-09-07.md`.

Before changing code, capture:

- the exact query;
- expected article or chunk target;
- observed rank;
- top competing results;
- whether the issue is top-k recall, top-3 ranking, top-1 ranking, or evidence
  adequacy;
- whether the competing result is wrong, partially relevant, or ambiguous.

If the competing result is scientifically plausible, mark the case as ambiguity
rather than treating it as a simple failure.

## Regression Data Requirements

Every new regression question should include:

```yaml
error_class: property_confusion
expected_behavior: "What the system should generally prefer."
regression_guard: "What future changes must not break."
```

Use `category` for topic/domain grouping and `error_class` for engineering
failure mode grouping. They are intentionally separate.

Gold targets may be article-specific because evaluation needs stable expected
evidence. Ranking implementation should still be feature-level.

## Evaluation Requirements

Before a retrieval fix:

```powershell
python -m app.ingestion.cli doctor
python -m app.ingestion.cli corpus-manifest --check docs\corpus_manifest.json
python -m app.evaluation.cli retrieval-extended docs\evaluation_questions_cross_lingual_extended.yaml --top-k 10 --method hybrid_cross_lingual
python -m app.evaluation.cli retrieval-extended docs\evaluation_questions_user_cross_lingual.yaml --top-k 10 --method hybrid_cross_lingual
python -m app.evaluation.cli retrieval-extended docs\evaluation_questions_user_regression_extended.yaml --top-k 10 --method hybrid_cross_lingual
```

After a retrieval fix, rerun the same evaluations and compare:

- article recall@10;
- MRR;
- top-1 count;
- mean rank;
- nDCG@10 where relevance grades exist;
- `summary.by_error_class`;
- failures and rank regressions.

## Acceptance Criteria

A retrieval fix is acceptable only if:

- the targeted error class improves or remains stable;
- core top-k recall does not drop;
- user-style top-k recall does not drop except for an explicitly documented
  ambiguity relabeling;
- evidence trace completeness remains true;
- no silent fallback is introduced;
- focused tests and full project checks pass.

If MRR or top-1 improves but top-k recall drops, reject or narrow the fix unless
the user explicitly accepts the tradeoff.

## Implementation Constraints

Allowed:

- query feature extraction;
- protected-token and phrase matching;
- article-level coverage scoring;
- article-diverse candidate windows;
- narrow intent diagnostics;
- conflict penalties tied to explicit query/property evidence;
- tests and evaluation metadata.

Not allowed without separate approval:

- changing ingestion, OCR, chunking, or stored text;
- changing exact/semantic/hybrid component scoring formulas;
- adding an LLM reranker;
- external metadata lookup;
- hard-coded query-to-article promotion;
- broad glossary expansion without a documented missed-evidence class.

## Reporting Format

Every completed retrieval-fix step should report:

```text
Changed:
- files and behavior changed

Tests run:
- exact commands and observed results

Evaluation:
- before/after report paths and key metrics

Limitations:
- ambiguous cases, unresolved classes, or accepted tradeoffs

Verdict:
- accepted or rejected against this policy
```

## Verdict

Use this policy as the gate for future retrieval ranking work. The project should
be improved through documented, testable error-class fixes rather than hidden
special cases.
