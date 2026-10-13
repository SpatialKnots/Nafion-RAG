# TAC stage 07: article keyword proposals in HTML

Artifact date: 12 October 2026, Asia/Yekaterinburg. Stage closure: 13 October 2026.
Scope: the frozen 33-document corpus, including the duplicate Welch upload.

## Changed

Added `scripts/tac_terms.py`, an isolated deterministic keyword proposer with
algorithm version `tac_term_candidates_v0.3`. Added optional `--terms` input to
the existing HTML exporter and 16 unit test cases. The Terms column now contains
ranked per-article candidates, expandable exact quotations, section kind, page,
selected text-layer identity and inherited TAC boundary assessment. Search and
the shared expansion control include Terms. All eight agreed columns remain.

Final review: `output/tac_stage07_terms_20261012/ARIADNE_TAC_terms_2026-10-12.html`.
Final sidecar: `data/experiments/tac/20261012_stage07_terms/terms_final.json`.
The table includes all 33 documents, full expandable TAC text, source diagnostics
and local links to the original PDFs. Terms are explicitly proposals, not accepted
index terms or independently confirmed scientific metadata.

The extractor reads only the existing frozen T/A/C section quotations. It does
not read filenames, article body text, Keywords sections or external metadata to
infer keywords. Exact occurrences of eligible aliases from the existing glossary
provide seeds. Additional contiguous one-to-four-token phrases use explicit
English noun anchors, Russian substring anchors and source acronyms/formulae.
This is a surface heuristic, not POS tagging or semantic extraction. Seed aliases
may contain up to six tokens; reporting prose is filtered in both paths.

A derived matching view folds case, known ligatures, whitespace and typography
hyphens while preserving a map to original Unicode character offsets. Display
labels preserve source case, including chemical formulae; exact quotations retain
original glyphs and whitespace. Detected broken line-end words are excluded
instead of guessed or rejoined. Discovered unit tokens are filtered. Decimal
indices in formulae remain intact.

Ranking uses `sum(section_weight * min(occurrences_in_kind, 3)) * token_count +
seed_match`, with weights T=3, A=2, C=1. This score is not a confidence probability.
Stable sorting and greedy suppression of nested surface phrases produce at most
12 terms per article by default. Suppression does not establish synonymy.
Settings, algorithm code, glossary, corpus, profiles and review hashes are saved.
The validator checks input identity, article inventory, proposal state, limits,
PDF provenance and every exact evidence span within its containing TAC section.

## Results

| Measure | Final output |
| --- | ---: |
| Documents with proposals | 33/33 |
| Proposed article-term entries | 377 |
| Terms per document | 3–12 |
| Exact evidence occurrences | 1,087 |
| Candidates with an existing glossary seed match | 47 |
| Candidates discovered without a seed match | 330 |

These are output counts, not precision or recall. Identical Welch content produces
identical term labels, ranks and quoted spans; separate uploads retain their own
PDF and layer identities. Earlier development sidecars `terms_v01.json`,
`terms_v02.json` and `terms_v03.json` remain separately saved. Only `terms_final.json`
is used in the final HTML.

## Tests run

- Targeted Terms/HTML/boundary tests: **37 passed in 2.39 s**.
- Full pytest: **851 passed, 1 warning in 26.91 s**. Log: stage07
  `pytest_full.log`. Warning: existing Starlette TestClient/httpx deprecation.
- `ruff check app tests scripts`: **All checks passed**.
- `mypy app`: **Success: no issues found in 84 source files**.
- Final headless Edge QA: **33 rows, 8 columns, 377 terms, 1,087 exact evidence
  quotations**, unchanged TAC text and **91 metadata values**. All **1,360 local
  link targets** exist; search and Terms expansion work; no page errors.
  Both final screenshots were visually inspected. QA JSON and screenshots are
  stored beside the final HTML.
- Source integrity: physical hashes of **33 original PDFs** verified; **88 app
  files** and five existing TAC extractor/metadata/glossary files match the before
  baseline. Exact profile and Terms source validation passed. No production
  extraction, OCR, chunking, database, retrieval scoring or glossary change.

Synthetic tests verify source fidelity, formulas, filtering, determinism, rejection
of stale/mutated evidence and optional HTML integration. They are not an independent
scientific keyword benchmark. No new retrieval or latency benchmark was needed
or run for this presentation-only sidecar.

## Inputs and reproduction

- Before baseline: `output/baselines/20261012_before_tac_stage07_terms/`, 299 files,
  fingerprint `2853916d248d84971601912dace6aa739ffcb338619bcd816ee5d6a2376042e1`.
- Corpus: `data/experiments/tac/20261012_v01/corpus.json`, SHA-256
  `4189045ddad052b2121e4e809761deaeafa0505f8ff8c4975cdcc2e27d10e73a`.
- Profiles: `data/experiments/tac/20261012_stage06/profiles_final.json`, SHA-256
  `4a50f223f0f51499e00d5ae28e05515e3f66e1f036edc905c4dc895f807ab20a`.
- Metadata and boundary review: stage06 `metadata_final.json` and
  `boundary_review_final.json`, reused without changes.
- Final Terms SHA-256:
  `841f40d027097ca923b48da3b3b6edcc2c63d0c44c41919fbd606a1bfe090707`.
- Recipes and artifact hashes: stage07 `recipes/` and
  `artifact_inventory_final.json`. Private literature text and local paths remain
  in ignored local artifacts.

Reproduce with new output destinations; existing artifacts are not overwritten:

```powershell
.\.venv\Scripts\python.exe -m scripts.tac_terms --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles data/experiments/tac/20261012_stage06/profiles_final.json --boundary-review data/experiments/tac/20261012_stage06/boundary_review_final.json --output NEW_TERMS.json
.\.venv\Scripts\python.exe -m scripts.tac_review_html --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles data/experiments/tac/20261012_stage06/profiles_final.json --metadata data/experiments/tac/20261012_stage06/metadata_final.json --boundary-review data/experiments/tac/20261012_stage06/boundary_review_final.json --terms NEW_TERMS.json --output NEW_REVIEW.html --source-root D:/Nafion-RAG
```

Generated timestamps differ between runs; candidate selection is deterministic
for the same source, code, glossary, review and settings.

## Limitations

No independent precision/recall or human acceptance is established. Existing TAC
boundary errors and damaged source glyphs can contaminate or omit candidates;
the evidence retains the corresponding review status. Finite language/domain
anchors and the stoplist bias coverage. Morphological variants and overlapping
concepts can survive as separate terms; the display cap can omit useful terms.
Broken-word exclusion favors source fidelity over recall. There is no translation,
acronym expansion, ontology mapping, model inference or production indexing.

## Verdict

The requested automatic per-article Terms list is implemented and available in
the local HTML for all 33 documents, with exact source evidence and reproducible
inputs. It is ready for user review as a candidate list. Scientific acceptance
and production glossary integration remain outside this stage.
