# TAC stage 05: frozen-output boundary audit

Date: 12 October 2026, Asia/Yekaterinburg. Reviewer: assistant development audit.
Independent: false. Human confirmation: pending.

## Changed

Completed the interrupted audit of the unchanged `tac_section_proposals_v0.5` output
from stage 04. All 33 frozen records have explicit T/A/C assessments. Rechecked the
draft assessments against 80 saved, full original-PDF page renders (20 contact
sheets) and the stored proposal beginnings/endings. This is a review of selected
section pages, not a complete reading of all 493 selected pages or independent gold.
The Satoh contamination note now also identifies figure text; the dissertation
note distinguishes indisputable page-number contamination from the debatable
scope of its separately headed recommendations subsection.

Added `scripts/tac_boundary_review.py`: input/profile/PDF/page identity and exact
proposal binding, complete inventory, explicit field states and count summaries.
It rejects stale or inconsistent annotations; it does not generate review judgments
or verify their scientific correctness. The local finalization recipe separately
checks actual original PDF and render hashes before writing the audit sidecar.

The existing HTML exporter accepts an optional `--boundary-review` sidecar.
It retains the eight main columns, full algorithm text, original PDF links,
metadata and diagnostics. Assessments appear next to T/A/C, with explanations and
links to reviewed page renders. A separate button filters rows with boundary errors,
missed evidence or unresolved assessments; it combines with the existing search.
Assessments do not replace or repair algorithm outputs. Existing unaudited input
remains supported. Terms remain unimplemented; metadata was not reassessed here.

Final HTML:
`output/tac_stage05_20261012/ARIADNE_TAC_stage05_boundary_audit_2026-10-12.html`.

| Field | Without observed boundary issues | Boundary error | Missed | Not separately delimited | Raw slots |
| --- | ---: | ---: | ---: | ---: | ---: |
| Title | 32 | 1 | 0 | 0 | 33 |
| Abstract | 30 | 0 | 0 | 3 | 33 |
| Conclusions / labelled summary passages | 22 | 8 | 1 | 2 | 33 |
| Total | 84 | 9 | 1 | 5 | 99 |

No unresolved decisions remain in this assistant review. The five structural
exclusions are A for the Sasaki meeting abstract, Besenhard and the supplement,
and C for the meeting abstract and supplement. They describe the reviewed
structure, not exhaustive absence of useful full-text evidence.

Stage 04 still fills 93/99 TAC cells (93.94%). This audit finds no observed boundary
issues in 84/99 raw slots (84.85%), or 84/94 applicable slots (89.36%) after explicitly
excluding the five structural cases. These are descriptive assistant-review ratios,
not independent parsing accuracy. A summary passage is assessed for its own paragraph
boundaries, not completeness of the article's entire conclusion. The repeated Welch
upload remains a separate frozen record; gold and retrieval denominators are unchanged.

## Confirmed development failure queue

| Source label | Field | Observation / next bounded work |
| --- | --- | --- |
| Peng 2021 | C | `Conﬂicts of interest` and its statement included; heading matching must handle source ligatures without rewriting quotes. |
| Guo 2020 | C | Figure 5 axis text and page numbers included in a two-page section. |
| Чернюк 2023 | C | Unheaded acknowledgments and government funding included. |
| Yu 2022 | C | Fig. 8 text/caption and running header/footer included; scientific continuation must be preserved. |
| Satoh 2013 | C | Figure 10 text, page number and ECS download footer included. |
| Резницких 2021 | C | Late `Таким образом` summary paragraph missed. |
| Диссертация Чернюк | C | Page numbers 138/139 included; page 139 proposal is only whitespace/number. Recommendations scope requires an explicit rule. |
| Lin 2023 | T | Title footnote marker `†` included. |
| Nagasubramanian 2011 | C | Ends at `We believe that these`; rest of the second paragraph missing. |
| Sanginov 2021 | C | `CRediT author statement` and author roles included. |

## Tests run

- Targeted exporter/audit tests: **21 passed in 3.69 s**. Thirteen added cases cover
  stale hashes, duplicate inventory, PDF/layer identity, altered proposal text,
  missing reviewed pages, invalid pass for absent proposal, missing notes/fields,
  prohibited human acceptance claims, explicit denominators and escaped HTML.
- Full pytest: **826 passed, 1 warning in 17.93 s**, fresh basetemp outside sandbox:
  `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp D:/Nafion-RAG/tmp/tac_stage05_full_20261012`.
  Existing warning: Starlette TestClient/httpx deprecation.
- `ruff check app tests scripts`: **All checks passed**.
- `mypy app`: **Success: no issues found in 84 source files**.
- Final headless Edge QA: **33 rows, 8 columns, 33 PDF links, 99 assessment badges,
  10 problem rows**. All T/A/C display texts, all assessment notes and **91 metadata
  values** match their saved JSON; **273 local link targets** exist. Search,
  expansion and combined problem filter work; no page errors. Both screenshots
  visually inspected. The first sandbox Edge launch failed on its temporary profile;
  the successful retry ran outside sandbox. No success is attributed to that first run.
- **33 original PDF hashes and 80 render hashes verified** by the finalization
  recipe. Profiles and snapshot hashes match the render manifest. Application
  source, frozen proposals and metadata remained unchanged during this stage.

## Inputs and reproduction

- Git starting point: `4291239a4de8e2b1ea6b7fde09fbab3ca55c351c`.
- Before source baseline: `output/baselines/20261012_before_tac_stage05/`, 295 files,
  fingerprint `d9f74b60db427e85d92f8ecc954720efd6d671408cf5b03d89dc410d98567b1d`.
- Frozen corpus: `data/experiments/tac/20261012_v01/corpus.json`, SHA-256
  `4189045ddad052b2121e4e809761deaeafa0505f8ff8c4975cdcc2e27d10e73a`.
- Profiles: `data/experiments/tac/20261012_stage04/profiles_final_v02.json`, SHA-256
  `3fe3d152e0ced882e2f68b270a32629316b7350ece30d5cde40fd512e240d0c3`.
- Metadata: stage04 `metadata_final_v02.json`; unchanged.
- Audit: stage05 `boundary_review_final.json`, `boundary_summary_final.json`,
  `source_integrity_final.json`, `render_manifest.json`. These are private artifacts.
- Recipes and copied draft inputs: stage05 `recipes/`; complete artifact identity
  recorded in `artifact_inventory_final.json`. Browser QA and screenshots: final HTML directory.

Re-render the saved audit, using a new destination:

```powershell
.\.venv\Scripts\python.exe -m scripts.tac_review_html --snapshot data/experiments/tac/20261012_v01/corpus.json --profiles data/experiments/tac/20261012_stage04/profiles_final_v02.json --metadata data/experiments/tac/20261012_stage04/metadata_final_v02.json --boundary-review data/experiments/tac/20261012_stage05_audit/boundary_review_final.json --output NEW_AUDIT.html --source-root D:/Nafion-RAG
```

## Limitations

This stage does not fix section extraction, OCR/glyph fidelity or metadata;
does not run models, new live retrieval, performance benchmarks or scientific
record admission; does not create independent labels. Boundary integrity is not
scientific correctness. The 33-record development corpus informed earlier rules;
the current reviewer also authored those rules. Supplement/meeting-abstract
structural exclusions remain review judgments. Local paths and literature text
stay in ignored artifacts. Existing stage outputs are preserved separately.

## Verdict

Stage 05 audit and HTML review are complete. A 95% claim remains unsupported.
The first narrowly scoped repair should address ligature-safe stop headings and
the `CRediT author statement` variant, followed by full-section continuation and
geometry-based exclusion of figure/page furniture. Keep unheaded acknowledgments,
implicit Russian summary detection and title-footnote exclusion separately tested;
do not remove arbitrary words from source quotes to improve a counter.
