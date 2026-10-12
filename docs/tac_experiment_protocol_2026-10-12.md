# TAC feasibility experiment v0.1

Date: 12 October 2026, Asia/Yekaterinburg. Status: isolated development experiment.

## Scope

Test whether exact-source Title/Abstract/Conclusions proposals can prioritize useful articles in the current Nafion/PFSA corpus. Do not change production ingestion, OCR, chunking, database schema, retrieval scoring, evaluation gold, thresholds or the cross-lingual glossary.

No model-based section classification, new embedding model, scientific-record extraction, automatic dictionary admission or production TAC index is implemented in this experiment. Article selection uses a deterministic lexical TAC profile. Deep-search evaluation is a replay over production full-text candidates, not an implementation of search restricted to a TAC index shortlist.

## Frozen inputs

- Pre-change source baseline: `output/baselines/20261012_before_tac/`, 279 files, fingerprint `eed9331e62aee549eb49f643dd65fd6e49c2f7331053b3dd05c2f371c4283488`.
- Corpus snapshot: `data/experiments/tac/20261012_v01/corpus.json`, 33 Article records, 493 selected pages, 619 chunks. Export performed in a repeatable-read, read-only PostgreSQL transaction. Selected page text must equal its registered text layer; each page/chunk receives a text hash. Original PDF hashes matched Article checksums at export.
- Development questions: unmodified `docs/evaluation_questions_extended.yaml`, 46 questions. The comparison saves its exact input copy and SHA-256.
- Proposals: `profiles_v03.json`, rule `tac_section_proposals_v0.2`; complete source quotes, page offsets, text-layer identity and PDF hashes remain available. Historical `profiles.json` and `profiles_v02.json` remain separate development artifacts.

The corpus snapshot includes private full text and local paths; `data/experiments/` is ignored by Git. This is not a distributable or independent evaluation dataset.

## Extraction rules and limitations

Title: propose the largest eligible first-page text block/font run that resolves uniquely to the selected stored page text. Exclude common metadata/journal labels and overly long blocks. This heuristic may select an institution, formula or partial title. Filename-derived Article titles are metadata only and are not inserted into TAC text.

Abstract: recognize explicit EN/RU headings on the first two physical pages. Prefer exact layout-block endings; otherwise require a supported next heading. An unbounded abstract is excluded with diagnostics rather than extended through the article. A specific Russian publisher pattern after a publication-acceptance line is a separately labelled proposal. Unlabelled abstracts in other layouts remain unsupported. Paragraph fragmentation may truncate a proposal.

Conclusions: recognize explicit headings and stop at supported subsequent sections such as references, methods, acknowledgments and author contributions. Multi-page proposals retain separate page spans. Missing stop variants, document furniture and reading-order errors remain possible.

No source text is normalized or rewritten. Search normalization is derived separately. All boundaries remain `needs_boundary_review`. MuPDF layout diagnostics are retained in profiles and `extract_v03.log`; successful extraction does not establish PDF layout validity.

## Boundary audit

Eight deliberately selected development documents, fourteen original-PDF pages, were rendered with Poppler and visually inspected. Nineteen title/abstract/conclusion boundaries were annotated by the agent after seeing parser proposals. Source identity, exact offsets, proposed spans and assessments are saved in `boundary_audit.json`.

These annotations are not blinded or independent scientific gold. They are never substituted into search profiles. The audit checks section boundaries, not material/value linkage or extraction accuracy. Full absence of sections throughout the supplement was not adjudicated.

## Retrieval comparison

Settings fixed before reviewing retrieval outcomes:

- Production baseline: `hybrid_cross_lingual`, `top_k=10`.
- TAC shortlist: at most five articles, deterministic token coverage on exact-source proposals; use existing glossary query variants, no new synonyms. Equal scores resolve by article UUID.
- Expanded production pool: `hybrid_cross_lingual`, `top_k=20`, separately requested because changing top_k may change fusion/reranking behavior.
- TAC-only: one result per shortlisted article, containing its source-bound section proposals. Article recall is useful here; chunk recall is only textual target coverage, not measurement extraction.
- TAC-deep replay: keep expanded-pool fragments belonging to shortlisted articles, preserving original production order and source objects, then take ten.
- TAC-deep with rescue: when fewer than ten fragments survive, fill remaining slots from the global pool in original order, without consulting expected answers. A full but incomplete list does not trigger rescue.

The expanded-pool top-ten control distinguishes TAC filtering effects from effects of changing production candidate-window size. No scoring improvement is inferred merely from a larger pool.

Use the existing extended evaluator unchanged. Missing expected articles/chunks and unanswerable-control behavior remain visible. Keep all 46 questions in the denominator. Judged hit fraction counts hits matching existing labels; additional unjudged articles are not scientifically established irrelevant results. A TAC result represents an article while full-text results represent chunks, so their hit-fraction denominators differ.

Component timings are recorded for production search, expanded-pool search and TAC lexical ranking. They are sequential, with different cache states, and do not measure a restricted-index TAC-first execution or a general speedup. Evaluator `elapsed_ms=0` for replay variants is a placeholder, not zero-cost retrieval.

## Reproduction

The read-only export recipe is `tmp/export_tac_snapshot_20261012.py`; it writes a new destination and refuses overwrite. To reconstruct a later corpus, use a new destination and preserve the old snapshot. The frozen snapshot is the input for offline extraction:

```powershell
.\.venv\Scripts\python.exe -m scripts.tac_experiment extract `
  --snapshot data/experiments/tac/20261012_v01/corpus.json `
  --output data/experiments/tac/20261012_v01/new_profiles.json
```

Comparison requires the live database and existing index. It rejects changed article inventory, chunks or selected page text and checks original/OCR PDF hashes after execution. Choose a new output directory:

```powershell
.\.venv\Scripts\python.exe -m scripts.tac_experiment compare `
  --snapshot data/experiments/tac/20261012_v01/corpus.json `
  --profiles data/experiments/tac/20261012_v01/profiles_v03.json `
  --questions docs/evaluation_questions_extended.yaml `
  --output data/experiments/tac/20261012_v01/new_comparison `
  --article-k 5 --top-k 10 --pool-k 20
```

Per-question artifacts are written as each query completes. `run_started.json` alone does not establish completion; the final `report.json` must contain all questions. Parse, database, index and validation failures propagate. Historical output is not repaired or overwritten.

## Decision boundary

This experiment may support further development, not production scientific acceptance. Any lost expected source must be diagnosed before TAC is used as a hard article gate. Boundary errors require a separately versioned parser revision and further cases. Do not adjust gold, thresholds, shortlist size or rescue rules to make this development report pass. Independent relevance annotation and measurement-level evaluation remain separate tasks.
