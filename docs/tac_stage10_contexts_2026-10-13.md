# TAC stage10: exact mentions, contexts and lexical containment

Date: 13 October 2026, Asia/Yekaterinburg. Implements stage 2 of the
[Terms plan](terms_implementation_plan_2026-10-13.md) on the same 33-document
development snapshot. Existing TAC profiles, metadata, boundary audit and stage09
inventory are inputs, not rewritten outputs. Scientific classification remains open.

## Changed

Added `app/terms/schema.py` and `contexts.py` with strict source/mention/context/use
models and deterministic builders. The new `scripts/tac_term_contexts.py` adapter
produces a separate `tac_term_contexts_v0.1` sidecar. Generic source identity/text
hash and streaming file hash are reused from the record evidence implementation;
Li-Nafion scientific fields/admission rules are not copied. Contract:
[exact Terms contexts v0.1](terms_context_contract_v0.1.md).

Each physical mention retains exact text, article/PDF/page/layer identities and
offsets. Repeated occurrences have separate IDs. Local term IDs stay those of
stage09; uses link a local term, physical mention and exact containing TAC context.
Source IDs exclude paths, run timestamps and preview limits, while source content,
page/layer identities and bounds remain part of identity. Every use is unclassified.

Initial contexts are full frozen TAC page fragments. No paragraph/sentence
segmentation, newline-based sentence inference or reconstructed reading order is
introduced. Section groups preserve separate contexts and record page adjacency,
overlap or gaps; all text-continuity states remain `not_asserted`. The current run
has no page-gap transitions; synthetic tests separately cover missing pages.

Lexical containment is proper offset inclusion between two uses in the same
physical source/context, checked against exact quotes. All such inclusions are
retained, including transitive ones. They are not synonym, concept-hierarchy,
property/material or experimental-condition relations.

The optional `--term-contexts` HTML input adds expandable mention/use details,
exact context quotations and lexical inclusion endpoints inside Terms. Shared
context templates store each unique context once and clone text when opened;
repeated opening does not duplicate the quote. The eight main columns, stage09
preview, full inventory, source diagnostics and original PDF links are preserved.

Final review:
`output/tac_stage10_20261013/ARIADNE_TAC_stage10_contexts_final_2026-10-13.html`.
Final sidecar: `data/experiments/tac/20261013_stage10/contexts_final.json`.
Earlier stage tables and stage10 candidate artifacts remain separately available.

## Results

| Measure | Saved output |
| --- | ---: |
| Documents | 33 |
| Existing local Terms retained | 2,266 |
| Physical source mentions | 4,195 |
| Context fragments | 98 |
| Context-scoped term uses | 4,195 |
| Proper lexical span containments | 3,635 |
| Filled metadata values, unchanged | 91 |

These are structural counts, not independent scientific accuracy. This input has
one distinct physical mention per inventory occurrence. The contract also allows
shared physical mentions with distinct uses when T/A/C contexts overlap; a
synthetic regression case verifies that distinction. There are 2,926 rendered
term/context cards because repeated uses within one context share its display.

The Welch control pair has identical selected page-text hashes and matching
mention text/coordinate signatures, but **different original PDF byte hashes**.
One upload has the stored title `priority3_e2e_upload`; the other names Welch.
Both article/layer scopes retain disjoint mention IDs. The development audit's
initial assumptions of matching titles, then identical original hashes, failed;
the final control selects the pair by identical frozen page-text signatures.
This does not perform automatic work grouping or cross-article concept merging.

The Nagasubramanian control keeps the restored page-6 C boundary `[207,2175)`
and exact word-per-line source quotes. No source text or glyphs were repaired.

## Tests run

- Targeted context/Terms/inventory/HTML/boundary tests: **85 passed in 1.80 s**.
  Twenty-one new synthetic cases cover exact sources, repeated mentions,
  overlapping contexts, article-scope separation, path-independent IDs,
  changed page/layer identities, missing-page gaps, source/endpoint corruption,
  missing/fabricated uses/containments, scientific-state rejection, physical PDF
  hash failures and root escape rejection. They are not scientific gold.
- Final full pytest: **913 passed, 1 warning in 8.07 s**. Log: stage10
  `pytest_full_final.log`. The warning remains the existing Starlette TestClient/
  httpx deprecation. The run used a fresh basetemp outside sandbox after the
  earlier session's full-suite sandbox stalls. A prior intermediate full run
  also passed; final success refers to the final code.
- `ruff check app tests scripts`: **All checks passed**.
- `mypy app`: **Success: no issues found in 87 source files**, including the new
  three-file Terms package. Existing application modules are unchanged.
- Source/context validation re-derives exact expected records and links from the
  authoritative frozen inputs. Physical original and selected-layer PDF hashes
  are checked. Before-stage checks confirm **88 existing app files** and seven
  extractor/inventory/metadata/review/glossary files unchanged. Three new app
  files are added; the application as a whole is not claimed unchanged.
- Final headless Edge QA: **33 rows, 8 columns, 2,266 Terms, 4,195 mention/use
  nodes, 98 unique contexts, 2,926 context cards, 3,635 unique lexical endpoint
  pairs and 4,195 original term quotations**. All displayed mention/context quotes
  match the sidecar, all T/A/C text and 91 metadata values match the prior inputs.
  All **7,636 local link targets** exist; repeat expansion does not duplicate
  context text, search and the problem filter work, and no page errors occurred.
  Both final screenshots were visually inspected. QA ran outside sandbox using
  the previously verified local headless Edge setup.
- No new model inference, scientific labeling, live retrieval, latency benchmark,
  database migration or ingestion ran. The unchanged inventory remains at its
  stage09 byte hash; retrieval performance is not re-measured by this stage.

## Inputs and reproduction

- Before-stage baseline: `output/baselines/20261013_before_tac_stage10/`, 308 files,
  fingerprint `e2aee60a6d5e9660cfb432bb3f2376b895c212408cc3d2b3db2dfba909a0709e`.
  Earlier uncommitted work is included and retained.
- Frozen corpus SHA-256:
  `4189045ddad052b2121e4e809761deaeafa0505f8ff8c4975cdcc2e27d10e73a`.
- Profiles: stage08 `profiles_final_v02.json`; metadata/review likewise unchanged
  stage08 inputs. Inventory: stage09 `terms_final.json`, SHA-256
  `a7d3504a7741a0dffce02d58ff469c596193f4d3ea6611421012dcc7bafeddee`.
- New contexts SHA-256:
  `98bbc65104c25e00859739d2ef9c05d6481a8c595c7ce803ee15b3a48d1ea517`.
- Final source audit: stage10 `source_integrity_final.json`; recipes in `recipes/`.
  Browser QA/screenshots are beside the final HTML. Private source text and paths
  remain in ignored local artifacts.

Reproduce to new destinations; outputs refuse overwrite:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.tac_term_contexts --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles data/experiments/tac/20261013_stage08/profiles_final_v02.json --inventory data/experiments/tac/20261013_stage09/terms_final.json --output NEW_CONTEXTS.json --source-root D:/Nafion-RAG
.\.venv\Scripts\python.exe -X utf8 -m scripts.tac_review_html --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles data/experiments/tac/20261013_stage08/profiles_final_v02.json --metadata data/experiments/tac/20261013_stage08/metadata_final_v02.json --boundary-review data/experiments/tac/20261013_stage08/boundary_review_final_v02.json --terms data/experiments/tac/20261013_stage09/terms_final.json --term-contexts NEW_CONTEXTS.json --output NEW_REVIEW.html --source-root D:/Nafion-RAG
```

Run timestamps change; source/mention/context/use identities are stable for the
same frozen content and article scopes. Validation against an altered input hash
requires a separately generated sidecar, not silent rebinding of an old artifact.

## Limitations

Context remains coarse TAC scope and may contain inherited boundary/glyph errors.
It is not necessarily a paragraph or a scientific claim. Contexts without term
evidence are explicitly unreviewed; existing field-level audit notes remain in
the table. Page adjacency does not prove text continuity. Source-exact containment
does not establish concept hierarchy, semantic roles, sample identity or scientific
comparability. Full original-PDF read-through and independent annotation were not
performed in this stage.

The sidecar is about 8.9 MB and final HTML about 8.1 MB for this input; these are
observed file sizes, not scaling/performance acceptance. Persistent review,
classifications, scientific relations and production indexing remain future work.
The strict offline checks verify the declared frozen evidence, not whether live
ingestion has subsequently selected another layer. Scientific admission remains
separate from source integrity.

## Verdict

Stage 2 is implemented as TAC stage10. All prior Terms are retained with exact
mentions, context-scoped uses, explicit page-fragment structure and source-bound
lexical inclusions. The complete HTML review is available. Next stage: proposed
classification by type/role/origin and reproducible overlapping subsets, with
unclassified/ambiguous cases preserved until review.
