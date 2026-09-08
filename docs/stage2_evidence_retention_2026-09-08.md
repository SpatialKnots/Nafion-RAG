# Stage 2: retain required-substance evidence during selection

Date: 2026-09-08. Uncommitted follow-up to the required-substance gate on base
application revision `3727bb0`.

## Changed

`select_answer_evidence` now checks identity coverage after its existing ranking,
article diversification and conductivity-specific filter. When an explicitly named
substance has been lost, it appends an original retrieved candidate that supplies
that identity. Candidates are considered in existing evidence-ranking order.

- Existing selected objects and their order remain intact.
- Only full text, or the same snippet fallback used by the answer gate, counts.
  Article titles and translated query expansions are not source evidence.
- Every appended chunk covers at least one still-missing identity; duplicates and
  candidates that add no missing identity are skipped. Additions are bounded by
  the number of initially missing catalogue identities.
- The original query defines requirements. Query-expansion terms do not silently
  introduce additional mandatory substances.
- No candidate is fetched outside the retrieved window. Remaining gaps still
  cause the existing adequacy gate to refuse the answer.

`answer_evidence_selection.required_concept_retention` is an additive diagnostic
with identity coverage `before` and `after`, and `restored` entries containing
chunk ID, article ID and supplied concepts. The existing
`filtered_to_conductivity_plasticizer_evidence` flag still records that the initial
filter ran; retention diagnostics explicitly disclose exceptions restored afterward.

No database, extraction, original PDF, retrieval-score, alias-catalogue, grouping
default or numerical adequacy-threshold changes were made. Restored SearchResult
objects keep their source fields; the existing citation schema is unchanged.

## Corpus evidence

For `qext035_chernyuk_dissertation_solvent_table_ru`, exact and hybrid previously
selected only chunk `6ee652c1-0d8f-48a3-801a-b37786e203ad`, pages 107–109.
They now retain the additional dissertation table-continuation chunk
`d7cb5ab1-5d10-4e02-a5ef-e1d7e1c7b779`, pages 109–111, which names diglyme.
Both belong to article `6f6fca14-92e8-446d-b1cd-ec08ca811962`.

Live calls through `answer_question` with an explicitly injected local
`ExtractiveAnswerProvider(max_claims=10)` returned:

| Query | Method | Result |
| --- | --- | --- |
| Diglyme table | exact | answered; both source chunks cited |
| Diglyme table | hybrid | answered; both source chunks cited |
| Diglyme table | semantic | insufficient_evidence; no candidate restored |
| PBI/phosphoric-acid negative control | hybrid_cross_lingual | insufficient_evidence; no candidate restored |

Semantic's diglyme failure is a candidate-coverage gap in its top-10, not a chunk
removed by this filter. This narrows the earlier combined description of the
exact/semantic/hybrid failures: restoration is possible for exact and hybrid only.
No OpenAI call was made. These local excerpt answers test plumbing and citations,
not scientific correctness of a generated comparison.

## Frozen regression comparison

The same three snapshot files used by the previous gate audit were replayed before
and after the change: 348 query/method windows, each assessed as snippets and
selected full text. The replay records selected chunk IDs and selection metadata;
input hashes must match the baseline before comparison.

- Two selected-chunk lists changed: the exact and hybrid diglyme cases above.
- Their selected-full-text gate verdicts changed from refusal to acceptance.
- The other 346 selected-chunk lists and verdicts are unchanged.
- All snippet assessments are unchanged.
- No previously refused negative control became accepted.
- All user-regression and cross-lingual-set selections remained unchanged.

This is a frozen-window selection regression check, not a fresh retrieval-quality
or latency benchmark. Full-service live probes supplement it because frozen replay
does not include downstream derived-evidence augmentation and deduplication.

Artifacts:

- `tmp/stage2_retention_before.json`
- `tmp/stage2_retention_after.json` (`changes` and `selection_changes`)
- `tmp/stage2_retention_live.json`

## Tests run

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp tmp/evidence_retention_full_tests
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m scripts.stage2_retention_live
.\.venv\Scripts\python.exe -m scripts.stage2_adequacy_replay tmp/stage2_retention_after.json tmp/stage2_grouping_audit.json tmp/stage2_grouping_user.json tmp/stage2_grouping_cross_lingual.json --baseline tmp/stage2_retention_before.json
.\.venv\Scripts\python.exe -m app.ingestion.cli corpus-manifest --check data/exports/corpus_manifest_stage1_20260907.json
```

Full pytest: 387 passed, one existing Starlette/httpx deprecation warning. Ruff on
app/tests/scripts and mypy: PASS. Format checks passed for the changed selection
module, new tests and audit scripts. Corpus manifest: match. Whole-workspace lint
was not repeated; the previous audit documents unrelated errors under `tmp/`.

Six new tests cover full-text restoration, retained priority/provenance, duplicate
candidates, already-covered identities, misleading titles/snippets, missing
identities, query-expansion isolation, separate EC/SL restoration, and actual
provider input/citation preservation. Fixtures are synthetic.

## Limitations

Retention only covers recognized catalogue identities available in the retrieval
window. It does not retrieve missing sources, interpret table rows or establish
that a mentioned substance participates in the claimed measurement. A mention in
a reference or unrelated passage remains a limitation of lexical coverage.

Appending evidence preserves existing priorities rather than solving an optimal
minimum-context selection problem. External generation, broad scientific answer
review, browser verification and performance benchmarking were not run.

## Verdict

The requested selection repair is implemented: diglyme evidence survives filtering
for exact/hybrid and reaches the answer provider with source citations. The PBI
refusal guard remains effective. Five previously identified incomplete-evidence
cases remain refused; candidate retrieval and broader scientific acceptance are
still open work in stage 2.
