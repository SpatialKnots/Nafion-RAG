# Stage 2: required substance coverage

Date: 2026-09-08. Base application revision: `3727bb0`; changes are uncommitted.

## Changed

`app/generation/required_concepts.py` introduces a versioned identity catalogue:
polybenzimidazole/PBI, phosphoric acid/H3PO4, DMF, DMSO, ethylene carbonate,
sulfolane and diglyme. Explicitly named catalogue identities must all occur in
the selected evidence. A missing identity overrides both the lexical and the
topical concept-coverage acceptance branches in `assess_evidence_adequacy`.

Aliases include English/Russian names and a limited set of Russian inflections.
Matching uses Unicode normalization, word boundaries and normalized spacing/dashes.
Each identity phrase must occur within one fragment; phrase halves across separate
chunks do not count. EC and SL are independent substances, not interchangeable
members of a broad solvent concept. Supported aliases also count toward existing
query-term coverage, allowing bilingual identity matches without lowering thresholds.

The response and extended-evaluation `evidence_adequacy` metadata gain an additive
`required_concepts` field containing `required`, `matched`, `missing`, per-identity
`query_aliases`/`evidence_aliases`, and `catalogue_version=1`.
The new refusal reason is `missing_required_concepts`. Empty-evidence diagnostics
keep `no_evidence` and still list required identities. The UI displays missing
required substances. Existing citation/source fields are preserved.

Retrieval scoring, query expansion, grouping defaults, extraction, database schema
and numerical adequacy thresholds are unchanged. The retrieval glossary is not
used as an identity dictionary: several existing entries deliberately group
related but scientifically different concepts.

## Evidence and regression replay

The live PBI audit now returns `status=insufficient_evidence` instead of `answered`.
Coverage remains 4/6 overall and 3/6 for the first fragment; missing required
identities are `polybenzimidazole` and `phosphoric_acid`. No external provider is
called. The test provider fails immediately if generation is attempted after this
gate, and that integration test passes. The evaluator reports the same diagnostics.

`scripts/stage2_adequacy_replay.py` compares a frozen set of 348 query/method
windows: 46 extended questions, 10 user regression questions and 31 cross-lingual
questions, each with four methods. Each window is assessed twice: original
snippets and selected full chunk text with the existing cross-lingual concepts.
This is 696 gate assessments, not 696 independent scientific questions.
The replay does not rerun retrieval or call generation; source snapshot hashes
are checked before comparison. Selected-full replay excludes the later answer
service's derived-evidence augmentation and deduplication.

Observed verdict changes:

| View | Change | Count |
| --- | --- | --- |
| Snippets | PBI negative control: accept → refuse | 1 |
| Selected full text | PBI negative control: accept → refuse | 4 |
| Snippets | Answerable gold: accept → refuse | 5 |
| Selected full text | Answerable gold: accept → refuse | 7 |
| Snippets | Answerable gold: refuse → accept through aliases | 1 |

The seven additional full-text refusals must not be hidden by retrieval Recall:

- `qext035_chernyuk_dissertation_solvent_table_ru`, exact/semantic/hybrid:
  selected evidence lacks diglyme. The
  [follow-up retention audit](stage2_evidence_retention_2026-09-08.md) establishes
  that the original candidate on dissertation pages 109–111 was removed by
  selection for exact/hybrid; it is absent from semantic's top-10. Those are
  separate selection and candidate-coverage gaps.
- `xling_en_ru_kayumov_li_conducting_membranes`, exact: retrieved text includes
  EC/SL but no recognised diglyme identity.
- `xling_ru_en_sanginov_ec_sl_conductivity`, semantic: no recognised EC/SL
  identities in the selected text.
- `xling_ru_en_istomina_swelling_temperature`, semantic/hybrid: no recognised
  EC/SL identities in selected text.

These are conservative refusals for incomplete selected coverage; they are not
proof that the questions are unanswerable in the corpus. No answerable selected-full
verdict changed to refusal for `hybrid_cross_lingual` across these sets. All user
regression verdicts remained unchanged. Alias support changes the cross-lingual
snippet verdict for the Istomina question from refusal to acceptance.

Local comparison artifacts:

- `tmp/stage2_adequacy_before.json`
- `tmp/stage2_adequacy_after.json` (includes all 18 changed verdicts)
- `tmp/stage2_pbi_source_audit.json` (latest, corrected live answer gate)

Input snapshot SHA-256:

| Snapshot | SHA-256 |
| --- | --- |
| stage2_grouping_audit.json | d78358adcf7bfb0b75b84cd4d91e0bff0c7e330f91c9c62b0e78ffbd00ffdc22 |
| stage2_grouping_user.json | 737abc3f29c067db5074fcf0bc5a6591bc0f03037591535e27bb3be2cbc221ca |
| stage2_grouping_cross_lingual.json | b6ed942253f1c15f50490248c5e0fb3bca85d0d76e2bba733961e2ec52480fce |

## Tests run

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp tmp/required_concepts_full_tests
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m scripts.stage2_pbi_audit
.\.venv\Scripts\python.exe -m scripts.stage2_adequacy_replay tmp/stage2_adequacy_after.json tmp/stage2_grouping_audit.json tmp/stage2_grouping_user.json tmp/stage2_grouping_cross_lingual.json --baseline tmp/stage2_adequacy_before.json
.\.venv\Scripts\python.exe -m app.ingestion.cli corpus-manifest --check data/exports/corpus_manifest_stage1_20260907.json
```

- Full pytest: 381 passed, one pre-existing Starlette/httpx deprecation warning.
- Final targeted check after removing unrelated formatting changes:
  `pytest tests/unit/test_required_concepts.py tests/unit/test_generation.py tests/unit/test_evaluation.py tests/unit/test_ui_routes.py -q -p no:cacheprovider --basetemp tmp/required_concepts_final_tests`:
  105 passed, the same deprecation warning.
- Ruff on application/tests/scripts: PASS; mypy: PASS, 69 source files.
- Corpus manifest: match; live PBI audit: all 33 original PDF hashes match.
- Full `ruff check .` is not clean: 19 errors in pre-existing temporary audit
  scripts under `tmp/`, plus access-denied warnings for old pytest directories.
  Those unrelated artifacts were not changed. Unrelated formatter changes to
  existing application files were removed to retain a minimal patch.
- Positive identity fixtures are synthetic software tests, not measured facts.
  They cover both languages, formula subscripts, partial support, topical fallback
  bypass, substring collisions, split-fragment phrases and independent EC/SL checks.

## Limitations

The catalogue is deliberately finite. Unknown substances, unlisted aliases and
unlisted inflections are not generally recognised. Every named catalogue substance
is treated as required; alternatives, negation, hypothetical comparisons and
question syntax are not interpreted. These can cause conservative refusals.
Abbreviations remain context-dependent. A mention in references or a negated
statement may pass identity coverage; coverage does not prove the experimental
relationship, numeric correctness, or support for each generated claim.

There was no external generation, complete fresh retrieval benchmark, or visual
PDF/browser audit in this implementation. Frozen replay preserves rankings by
construction and is not a new ranking-performance claim.

## Verdict

Required-substance gating is implemented and the PBI failure is corrected. Stage 2
remains open. Next: preserve relevant required-substance evidence during selection,
starting with the diglyme table case, and extend manually reviewed alias/negative
coverage without weakening the refusal rule. Global cap=2 is still not accepted.
