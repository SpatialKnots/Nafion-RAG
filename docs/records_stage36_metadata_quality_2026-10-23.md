# Stage36: source-based metadata quality audit

23 October 2026. Evaluation `metadata_quality_audit_v0.1`; unchanged extractor
`registered_tac_metadata_v0.1` / `tac_file_metadata_v0.1`.
[Prospective protocol](records/metadata_quality_protocol_v0.1.md),
[preceding integration](records_stage35_bibliography_bridge_2026-10-22.md).

Changed:

- Added a separate evaluation CLI: capture, reference freeze, evaluation, offline
  export and read-only database verification. No runtime extractor, ingestion,
  projection, schema, retrieval scoring or generation change. No proposal applied.
- Declared all **23 documents outside stage35's ten-document scope**, within the
  existing 33-document snapshot, before new predictions. Current article IDs match
  that corpus. No document was dropped after an outcome. Both registered Welch
  documents remain; their inspected text is identical, so they are not independent
  scientific observations. Earlier TAC development had already exposed this corpus.
- Captured registered physical pages 1–2 with exact text/layer IDs and original/
  selected PDF hashes. Assistant source references cover **69 fields**, with **76
  exact spans**, frozen before seeing new outputs. Inspected original first-page
  renderings for all documents and additionally physical page 2 for Cho, Doi and
  Sasaki. No selected text or PDF was repaired.
- Froze protocol, references, printed aliases and evaluation code before the first
  prediction run. Comparison preserves complete ordered bylines, case/whitespace/
  NFC normalization only, integer years and explicit unknown/not-applicable states.
  No rules or aliases changed after outcomes. All candidates/diagnostics retained.
- Produced a searchable read-only HTML review covering every scoped document and
  the agreed eight main columns. **64 complete historical TAC section proposals**
  match current registered sources; their separate historical snapshot is identified.
  Missing sections remain explicit. Terms were not recomputed or confirmed.

## Frozen results

These are bounded agreement counts against assistant source annotations, **not
independent scientific accuracy, general precision/recall or an unseen holdout**.

| Field | Known references | Strict correct proposals | Wrong proposals | Abstentions | Other states |
| --- | ---: | ---: | ---: | ---: | --- |
| Complete ordered authors | 23 | 18 | 1 | 4 | None |
| Publication/issue year | 21 | 21 | 0 | 0 | 2 unknown, unfilled |
| Journal | 21 | 16 | 5 | 0 | 1 unknown unfilled; 1 correct not-applicable |

Correct/known coverage: **18/23 authors, 21/21 year, 16/21 journal**. Among proposals
on known fields: **18/19 authors, 21/21 year, 16/21 journal**. Unknown references
are not successes or errors. The meeting abstract has no printed year and no
applicable journal. The supplement has no supported journal/year on the scoped
pages; metadata was not borrowed from its parent. No reference in this particular
scope required an ambiguous label; constructed tests cover that state.

Interpret the mismatches correctly:

- Four author fields abstain despite visible bylines: Besenhard (`not_found`),
  Nagasubramanian (`not_found`), Sanginov main article (`ambiguous`) and Istomina
  (`not_found`). These expose coverage limitations, not author absence in PDFs.
- Moore's output and selected text have `R. B. Moore, 111`, while the original image
  prints Roman `III`. The existing algorithm preserves the raw anomaly and its
  diagnostic. This is a source-text representation mismatch, not an invented author.
  Besenhard's selected text also corrupts visible `ü`; no repair was performed.
- Five journal mismatches are formatting: `RSC Adv` / `RSC Adv.`, `Adv. Mater` /
  `Adv. Mater.`, two `ACS Macro Lett` / `ACS Macro Lett.`, and
  `JournalofAppliedPolymerScience` / the spaced printed name. They stay wrong under
  the prospective strict rules. These counts **do not demonstrate five wrong journal
  identities**. No post-outcome fuzzy score replaces the frozen result.
- Printed issue years were correct in this run: Kondo 2026 despite 2025 copyright,
  Lin 2024 despite December 2023 online publication, Cho 2015 despite 2014 online
  dates, and Sasaki 2008 despite 2007 received/accepted dates. Doi's 2018 citation
  was distinguished from the 2017 cover thumbnail and 2013 template footer.
  Database labels/filenames supplied no reference years.

Tests run:

- Evaluation, unchanged bridge and legacy extractor regression: **76 passed**, no
  failures/errors/skips, `pytest_target_v04.xml`. Includes a constructed native PDF
  through actual extraction/freeze/scoring/replay, source/code/reference drift,
  complete ordered author lists, aliases, abstentions, unknown/not-applicable,
  scope completeness, exclusive directories, HTML escaping and deterministic export.
- Repository Ruff passed. Mypy passed for **153 app source files**; this does not
  claim strict standalone typing of the new experimental script. Runtime source
  did not change, so the full application suite was not rerun.
- Verified **33 capture**, **72 frozen-reference**, **75 evaluation/review** bindings.
  All 76 reference, 104 prediction-candidate and 64 historical TAC spans match exact
  source text and identities. Bound original/selected PDF hashes verify. Evaluation
  and two separate offline exports match byte-for-byte for JSON, HTML and manifest.
- Real PostgreSQL checks show unchanged metadata for **33 articles** and unchanged
  **ten metadata-history records**. Capture/verification explicitly use
  `REPEATABLE READ, READ ONLY`. No model, retrieval, embedding or external metadata
  requests were made. The saved database verification record contains actual CLI output.
- Isolated headless Chrome rendered actual HTML with `setContent`, without network
  requests or a user profile: 23 rows, eight columns, search counts 1/0/23, expandable
  historical text, no writable review forms and no page errors. Screenshots inspected.
  All **23 original-file links resolve to existing files**; PDF clicks and browser
  file permissions were not tested. Wide table uses horizontal scrolling.
- Initial failures retained: first test run had four basetemp-parent setup errors;
  the next found incomplete constructed fixtures and a JSON roundtrip render-order
  defect. Fixed before reference freeze/predictions; final regression passes.
  Initial database capture was sandbox-denied (10013); approved read-only capture
  succeeded. Playwright's bundled browser was missing; installed Chrome worked.
  Poppler reported Symbol/ArialUnicode display-font and font/shared-object warnings;
  inspected metadata remained legible. No PDF or text repairs were made.

Limitations:

- Assistant references are output-blind for this run, not independent human
  annotations. Scientific acceptance remains open. The small existing corpus,
  duplicate content and prior TAC exposure prevent an independent generalization
  claim. No representative accuracy or confidence interval is established.
- Only physical pages 1–2 feed metadata and references. Unknown does not mean absent
  from every possible source. Historical TAC sections are not newly accepted
  scientific conclusions or a new Terms extraction run.
- Strict agreement measures representation as well as identity. The inventory
  explains the distinction without changing scores or authorizing guessed metadata,
  a new normalization policy, text-layer replacement or correction of `111`.
- Browser QA covers isolated rendering/search/expansion. User-browser PDF opening,
  other-machine restore and clean installation remain unverified. Exact replay
  requires private frozen corpus/output files absent from a source-only clone.

Verdict:

The bounded audit is complete: a frozen metadata baseline, four author abstentions,
one source-text suffix mismatch and five journal-format mismatches. Independent
scientific acceptance is not established. Database, PDFs and extractor are unchanged.
Formatting policy and author recall need separately versioned changes with additional
evaluation cases. The next product task remains source-preserving answer-context
preparation; this metadata audit does not unblock the four earlier blocked packets
or justify a paid answer comparison by itself.

## Artifacts and replay

Local root: `output/records_stage36_20261023/`.

- `capture_v01/`: pre-prediction source/protocol/extractor freeze, pre-audit DB state.
- `source_images_v01/`, `source_notes_v01.py`, `references_draft_v01.json`,
  `references_v01.json`: inspected original images, assistant references, exact
  quotes, explanations and explicitly printed aliases.
- `references_frozen_v01/`: exclusive reference/code/resource freeze before predictions.
- `evaluated_v01/`: first new predictions and all comparisons/candidates.
- `review_v01/review.html`, `review_repeat_v01/`: separate complete review exports.
- `pytest_target_v04.xml`, `browser_qa_v01.cjs`, `browser_qa_v01.json`,
  `review_all_v01.png`, `review_search_v01.png`: software and browser evidence.
- `database_after_v01.json`, `postflight_v01.py`, `postflight_v01.json`:
  actual read-only DB result and offline source/span/replay/HTML/link/binding checks.
- `source_archive_v01/`: final changed source/docs/tests and unchanged extractor
  sources, their hashes and base Git commit; no private corpus or credentials.

Export results without database/model calls, to a fresh directory:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.metadata_quality export --captured output/records_stage36_20261023/evaluated_v01 --output-dir output/records_stage36_new_review
```

Rerun the unchanged extractor against frozen references, to another new directory:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.metadata_quality evaluate --frozen output/records_stage36_20261023/references_frozen_v01 --output-dir output/records_stage36_new_evaluation
```

Fresh read-only database verification:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.metadata_quality verify-database --captured output/records_stage36_20261023/capture_v01
```

Commands fail visibly on changed bound sources/code/references. Exclusive new output
directories are required. Postflight verifies a separately captured DB result;
the last command performs a fresh live check.
