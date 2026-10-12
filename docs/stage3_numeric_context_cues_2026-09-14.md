# Stage 3: local numeric context cues, 2026-09-14

## Changed

Added diagnostic-only, same-line cues in `app/facts/context_cues.py`:

- `scale_bar_cue`: explicit immediately preceding scale-bar wording.
- `approximation_cue`: immediately preceding markers such as `~`, `≈`, `roughly`,
  `around`, `примерно` and the other explicitly enumerated forms.
- `inequality_cue`: immediately preceding inequality symbols or listed phrases
  such as `at most` and `не менее`.
- `isolated_numeric_line`: an otherwise empty source line; role remains unknown.

Every cue preserves its exact source text and half-open character offsets in
chunk text. Enrichment runs after production selection, only through
`diagnose_numeric_occurrences`. Flags attach independently to accepted, rejected,
duplicate and cap-omitted occurrences. No rule uses these flags to select facts.

The occurrence audit JSON is explicitly versioned from schema 1 to **schema 2**:
occurrences gain `context_cues` and `duplicate_scientific_equivalence` (the latter
is `not_assessed` for lexical duplicates); summary gains cue counts and a hash of
the cue module. Existing candidate/report/database schemas remain unchanged.

Added a read-only source replay command,
`scripts.stage3_numeric_context_audit`, that verifies the previously reviewed
occurrences against live chunks, page layers and original PDF checksums. It does
not transplant scientific verdicts or claim new PDF review.

## Tests run

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_numeric_context_cues.py tests/unit/test_numeric_occurrences.py tests/unit/test_numeric_occurrence_review.py -p no:cacheprovider --basetemp=tmp/context_cue_tests_20260914
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=tmp/context_cue_full_tests_20260914
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m tmp.compare_context_cues
.\.venv\Scripts\python.exe -m scripts.stage3_numeric_context_audit --output data/exports/stage3_numeric_context_sources_20260914.json
.\.venv\Scripts\python.exe -m scripts.stage3_numeric_occurrence_audit --output data/exports/stage3_numeric_context_cues_20260914.json
.\.venv\Scripts\python.exe -m tmp.check_context_diagnostic_delta
```

- Targeted tests: **56 passed**. Full suite: **579 passed**, one existing
  Starlette/httpx deprecation warning. Ruff and mypy passed.
- All **2347 candidate dataclasses and their order on 619 chunks** matched the
  pre-patch snapshot. Snapshot SHA256:
  `319a997533f5d935e19b3057ff3827a39560e5c6b45912a37ff4048f9192d042`.
- All original diagnostic record fields for **4344 occurrences** matched the
  previous export exactly after removing the two new diagnostic fields.
- Live source replay: **14 targets, 20 occurrences, seven verified originals**.
  Reviewed line text, occurrence spans/decisions, page fragments and source
  checksums matched. Test assertions cover expected cue kinds on all 20 reviewed
  source lines, plus synthetic RU/EN and cross-number isolation cases.
- Corpus counts: **423 approximation cues, 114 inequality cues, 238 isolated
  numeric lines, six scale-bar cues**. These are occurrence counts, including
  duplicates across chunks, not counts of independent facts or scientific errors.
- All six scale-bar cue contexts were inspected as stored text; they explicitly
  contain scale-bar wording. No new visual approval is inferred from that check.

Results are saved in `data/exports/stage3_context_cue_equivalence_20260914.json`,
`stage3_context_diagnostic_equivalence_20260914.json`,
`stage3_numeric_context_sources_20260914.json` and
`stage3_numeric_context_cues_20260914.json`.

Current extractor SHA256:
`4e858bc5d9daf31e5db2c0e9e58b9e57d45926cea5932e4d6644234c5e0a8d9f`.
Cue module SHA256:
`02f3cfd9627d799e0b7cedb952725d29ddf87b63f7587369d41b414fbec6ca4a`.

## Limitations

These are lexical cues, not validated scientific roles, operators or extracted
experimental relationships. Negated/quoted cue wording can still produce a cue.
An empty cue list does not establish exactness or scientific validity. Same-line
prefix matching intentionally misses cross-line context, list propagation,
unlisted phrases, suffix qualifiers and arbitrary mathematical constructions.
It does not reconstruct ranges or uncertainty expressions.

Yu's explicit caption now has a scale-bar cue; Guo's treatment-temperature label
does not acquire one. Fan's isolated `10 nm` lines remain unresolved. Choi's two
`roughly 55%` occurrences retain separate cues and the existing lexical duplicate
decision; their scientific identity is explicitly unassessed. Laporta's later
`around 523 K` has an approximation cue distinct from its water-treatment value.
Guo's cap-omitted `~100 nm` and Sanginov's cap-omitted `≤1.5%` carry the applicable
cues without being restored to selection.

No production selection, deduplication, cap, confidence, PDF or database fact was
changed. The previous 981-change scientific review remains incomplete; its 968
unresolved changes are not automatically approved by this patch. Old hash-bound
diffs/labels remain historical and must not be passed off as current snapshots.

## Verdict and next step

Diagnostic step completed, with corpus-wide selection and diagnostic equivalence
confirmed. Keep cap 12 and do not bulk-refresh facts.

Next use the cue groups to prioritize source review and test a narrowly scoped
selection proposal for explicit scale-bar captions against valid figure conditions.
Any production exclusion must be measured separately for freed-slot effects and
newly exposed candidates. Approximation, bounds and distinct experiments still
need an explicit representation/selection decision before scientific comparison;
adding flags alone does not resolve them.
