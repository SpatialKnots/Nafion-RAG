# TAC stage09: complete candidate inventory and independent preview

Date: 13 October 2026, Asia/Yekaterinburg. Scope: all 33 frozen documents,
including the duplicate Welch upload. Implements stage 1 of the
[Terms plan](terms_implementation_plan_2026-10-13.md), as an isolated sidecar and
HTML review change. Scientific keyword acceptance remains open.

## Changed

Added the explicit `tac_term_inventory_v0.1` format and
[inventory contract](terms_inventory_contract_v0.1.md). The existing
`tac_term_candidates_v0.3` selected-only format remains the default CLI behavior;
its stored-list limit and saved artifacts retain their original meaning.
`--format inventory --preview-limit 12` selects complete storage. Ambiguous
mixing of the new preview option and old `--max-terms` is rejected explicitly.

Separated candidate generation/ranking from preview selection. New rows retain
every produced lexical candidate and all its exact evidence, including nested
surface phrases and candidates beyond the display limit. Article-scoped lexical
IDs, complete-inventory ranks/fingerprints and rank components are recorded.
These IDs are not global concepts or immutable source-mention IDs. A separate
preview references inventory entries and records selection, nested surface
suppression and display-limit reasons. The existing greedy preview policy and
generation/ranking rules are unchanged.

The HTML retains all eight agreed columns and all 33 documents. Terms cells show
the complete count and preview count; the remaining candidates expand in groups
of 50 with full source quotes and explanatory preview diagnostics. HTML templates
defer creation of remaining live cards until expansion; the search index contains
all candidate labels before expansion. Repeated expansion does not duplicate
cards. Global expansion exposes every candidate, and collapse preserves the data.
The table remains a read-only review artifact.

Final table:
`output/tac_stage09_20261013/ARIADNE_TAC_stage09_inventory_2026-10-13.html`.
Final inventory: `data/experiments/tac/20261013_stage09/terms_final.json`.
T/A/C proposals, metadata and boundary review are reused unchanged from stage08.
Earlier stages are preserved separately.

## Results

| Measure | Saved output |
| --- | ---: |
| Documents | 33 |
| Full lexical candidate entries | 2,266 |
| Candidates per document | 6–217 |
| Preview entries | 377 |
| Entries outside preview: nested surface suppression | 905 |
| Entries outside preview: display limit | 984 |
| Exact evidence occurrences across full inventory | 4,195 |
| Filled Authors/Journal/Year values, unchanged | 91 |

The three preview-decision counts sum to the full inventory. These are output
counts, not scientific precision/recall; candidate evidence spans can overlap.
Complete storage means the full output of the existing limited lexical generator,
not every useful scientific concept in the article.

For every document, regenerated legacy v0.3 article output is exactly equal to
the saved stage08 row, including original preview text, ranking, occurrences and
diagnostics. The new preview maps to exactly those same candidate objects after
excluding the three new inventory-only fields. Full inventories and fingerprints
are identical with preview limits 1 and 12. Candidate counts match the original
pre-selection counts. No new taxonomy, term-use roles, scientific relations,
synonym merging, translation or production indexing are introduced.

## Tests run

- Targeted Terms/inventory/HTML/boundary tests: **64 passed in 1.60 s**.
  Twenty-seven new synthetic cases cover inventory independence, source fidelity,
  legacy preview compatibility, more than 50 stored candidates, empty scope,
  article-local identity, hidden-candidate corruption, preview decisions and
  rejection of ambiguous CLI parameter semantics. These are regression fixtures,
  not independent scientific labels.
- Full pytest: **892 passed, 1 warning in 11.77 s**. Log: stage09
  `pytest_full.log`. Warning: existing Starlette TestClient/httpx deprecation.
  The full run used a fresh basetemp outside sandbox because earlier full sandbox
  runs in this session stalled. No success is attributed to those earlier runs.
- `ruff check app tests scripts`: **All checks passed**.
- `mypy app`: **Success: no issues found in 84 source files**.
- Final headless Edge QA: **33 rows, 8 columns, 377 initially materialized preview
  cards, 2,266 cards after full expansion, 4,195 exact evidence quotations**, exact
  T/A/C and assessment text, and **91 metadata values**. All **4,710 local link
  targets** exist. A candidate absent from every initial preview and visible DOM
  text (`future anode material`) was found through the full-inventory search index,
  its hidden card and quotes expanded, and repeated expansion did not duplicate
  cards. Expand/collapse and the problem filter work; no page errors. Both final
  screenshots were visually inspected. Browser QA ran outside sandbox using the
  previously verified local Edge setup.
- Source integrity audit: **33 original PDF hashes**, **88 app files** and six
  extractor/front-matter/section-flow/metadata/boundary/glossary files match the
  before-stage baseline. All candidates, including those outside preview, pass
  exact source validation. The source-bound audit reproduces inventories from
  frozen inputs and checks legacy equality and preview-limit independence.
- No model inference, database mutation, new live retrieval or latency benchmark
  ran. Retrieval and upstream evidence did not change; no new retrieval success
  or performance advantage is claimed.

## Inputs and reproduction

- Before-stage snapshot: `output/baselines/20261013_before_tac_stage09/`, 305 files,
  fingerprint `b7825e6a9911a63ad57efdaec5b8da5cdde7ff94e2f33b4446dc68818ded6b45`.
  This includes the previous uncommitted stage08 and planning files.
- Corpus: `data/experiments/tac/20261012_v01/corpus.json`, SHA-256
  `4189045ddad052b2121e4e809761deaeafa0505f8ff8c4975cdcc2e27d10e73a`.
- Profiles: stage08 `profiles_final_v02.json`, SHA-256
  `1523a30e45197d664a906c450eacac01b6e8c94b581f05082d430800951e0885`.
- Metadata/review: unchanged stage08 `metadata_final_v02.json` and
  `boundary_review_final_v02.json`. Original glossary unchanged.
- New Terms SHA-256:
  `a7d3504a7741a0dffce02d58ff469c596193f4d3ea6611421012dcc7bafeddee`.
- Audit recipe and results: stage09 `recipes/audit_stage09.py`,
  `source_integrity_final.json`, `inventory_comparison_final.json`.
- Browser recipe/QA/screenshots: stage09 `recipes/verify_stage09.cjs` and final
  HTML directory. Private literature text and local paths remain ignored by Git.

Reproduce into new destinations:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.tac_terms --format inventory --preview-limit 12 --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles data/experiments/tac/20261013_stage08/profiles_final_v02.json --boundary-review data/experiments/tac/20261013_stage08/boundary_review_final_v02.json --output NEW_INVENTORY.json
.\.venv\Scripts\python.exe -X utf8 -m scripts.tac_review_html --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles data/experiments/tac/20261013_stage08/profiles_final_v02.json --metadata data/experiments/tac/20261013_stage08/metadata_final_v02.json --boundary-review data/experiments/tac/20261013_stage08/boundary_review_final_v02.json --terms NEW_INVENTORY.json --output NEW_REVIEW.html --source-root D:/Nafion-RAG
```

Use `--format legacy-v0.3 --max-terms 12` for the explicit previous selected-only
contract. The CLI default still produces that legacy format. Created timestamps
change; candidate selection and inventory fingerprints are deterministic for
identical inputs/code/glossary/settings.

## Limitations

Existing TAC boundary errors, damaged glyphs, finite anchors/stopwords and broken
word exclusions remain. Full storage exposes more generic or questionable lexical
phrases; it does not improve their scientific relevance by itself. Preview selection
still has the prior nested-phrase policy, while all candidates remain accessible.
Lazy card creation reduces initial live DOM contents, but no timing/scaling benefit
has been measured. The final HTML is about 3 MB for this input, not a validated
large-corpus performance target.

Article-local candidate IDs do not replace the planned source mention/context
contract. Classification, persistent Terms review, scientific relations,
cross-article comparison and production integration remain later stages. All 33
documents are development inputs; independent evaluation and user scientific
acceptance are not established by these tests.

## Verdict

Stage 1 of the Terms implementation plan is complete as TAC stage09. The existing
generator's complete candidate inventory is preserved, preview is independently
limited, legacy outputs remain compatible and the full review table is available.
Next bounded work: stage 2, exact mention/context identity and lexical structure.
