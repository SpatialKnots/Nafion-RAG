# Stage12: graphics missing from text-only evidence

20 October 2026. Development algorithm `source_visual_gaps_v0.1`.
[Frozen protocol](records/source_gaps_protocol_v0.1.md).

## Changed

Added `app/evaluation/source_gaps.py` and explicit `--source-gaps` in the offline
context comparison CLI. The new mode composes the unchanged stage11 v0.2
selector and adds a separate source/citation diagnostic registry. Production
retrieval, generation, extraction, OCR, scoring, schemas and gates are unchanged.

Every displayed raster occurrence and vector drawing entry in each selected PDF
page is retained, including repeated occurrences, inline xref-zero images, tiny
pieces and degenerate vector paths. Records retain original/selected PDF hashes,
article/page/layer identity, occurrence/drawing indices, image object metadata,
dimensions, pixel digest, transforms and source rectangles. Rotation, crop/media
boxes and the displayed rectangle are recorded separately. Source coordinates
are unrotated PyMuPDF points; original PDFs are never edited.

Native dictionary spans use the same text flags as the existing block registry.
All line text, order, block numbers, offsets and block rectangles must align
exactly before line overlap is reported. A partial overlay counterexample caught
the difference between image-preserving dictionary block numbering and the
text-only registry; the diagnostic reader was corrected without changing ingestion.
Unproven geometry retains assets with unknown overlap and an explicit diagnostic.
Missing files, PDF errors, wrong identities and hash mismatches fail explicitly.

Exact selected source slices bind to lines by offsets and hashes. Proposed
layout/table bounding-box intersections and selected caption citations are
recorded separately. These intersections do not establish figure ownership.
Neither text overlap nor its absence measures OCR completeness or scientific
information loss. Pixels and vector paths are not serialized into these text-only
candidate messages. No new scientific interpretation or acceptance is inferred.

## Frozen replay

The same four development questions, source packets and corpus snapshot as stage07:
`18c9df4032897aaf576ad0e07beb4045fc39561ebf340c72e1abff4bca15b1ac`.
No new retrieval, database snapshot or held-out questions were used.

| Case | Page registrations | Raster occurrences | Rasters without overlapping registered lines | Vector entries |
| --- | ---: | ---: | ---: | ---: |
| Sanginov EC/SL conductivity | 9 | 10 | 10 | 172 |
| Istomina mixing temperature/swelling | 8 | 10 | 10 | 69 |
| Chernyuk water thermodynamics | 8 | 49 | 37 | 68 |
| Absent regolith negative | 10 | 14 | 14 | 133 |
| Total per-case registrations | 35 | 83 | 71 | 442 |

These are occurrence counts, not independent figures or missing scientific facts.
They include repeated pages across questions: **32 unique article/page/layer
pages, 11 selected PDFs**. All 35 registrations have exactly aligned line geometry.
No tiny asset or repeated occurrence was silently discarded.

Every stage12 result, exact selected context, adequacy outcome and candidate
request matches stage11. All four request files are byte-identical. Context sizes
remain 33750 / 27630 / 24329 / 61210 characters. The complete-page guard still
blocks all four requests with 5 / 5 / 6 / 9 full pages respectively. Zero API
calls, no new answers, no new token/cost or scientific accuracy measurement.
Reports from modes stages08, 09, 10 and 11 were replayed and match their previous
final reports byte-for-byte.

## Review and verification

The separate searchable HTML covers all 35 page registrations and links to each
original PDF page. Full source lines, asset registries, exact selected slices,
proposed groups and diagnostics remain expandable. The original four-question
context review remains available. No XLSX or manual per-case resolution workflow.

Four read-only Poppler page renders and diagnostic overlays were inspected:
raster scheme body with separate native caption, vector formula paths with native
character labels, repeated publisher/header/footer raster objects, and a plot
with small image pieces mixed with native text and vector rules. Rectangles
aligned visibly on those four pages; this is not a corpus-wide scientific review.
HTML rows, source links and image existence were checked statically. Browser
visual/click verification was not run.

- New unit cases: **27 passed** (including text/geometry/hash failures, partial
  overlays, repeated/tiny assets, vector-only and scan-like pages, source binding,
  and four rotations with crop coordinates).
- Full regression: **1301 passed**, one existing Starlette/httpx deprecation
  warning, 114.20 seconds. The later source change only clarified an intersection
  docstring; the final frozen replay uses those exact final source bytes.
- Three additional saved executable counterexamples passed: inline xref-zero
  image retained; fully constructed native text overlay retained without claiming
  OCR completeness; inverted asset rectangle retained with unknown overlap.
- Ruff passed for `app tests scripts`; mypy passed for 107 application files.
- Frozen input/code/PDF, per-case registry and rendered PNG hashes checked.
  Candidate request bytes and earlier-mode compatibility checked as above.
- Exact configured API key scan found no matches in the 35 initial replay JSON/HTML
  artifacts. Credentials were not printed or copied into reports.

Initial pytest attempts could not create/access the system temporary directory,
including outside the sandbox. A fresh temporary directory and cache under the
project output resolved the fixture setup issue. No passing test result is
inferred from those failed setup attempts.

Final private outputs: `output/records_stage12_20261020/replay_v02/`:

- `source_gap_review.html`: searchable complete page/citation registry;
- `source_gap_visual_review.html`: four representative source overlays;
- `review.html`: full four-question context/gate review;
- `report.json`, `input_manifest.json`, per-case `source_gap_registry.json`;
- `postflight.json`, `final_qa.json`, `diagnostics/render_manifest.json` and
  `diagnostics/visual_qa.json`.

The initial `replay_v01` remains separate. The final replay follows a docstring
clarification of the already declared inclusive rectangle intersection; no
algorithm or selection rule changed. Rendering and postflight helpers remain
beside the private outputs, with hashes in their manifests.

Reproduce into a fresh directory from the repository root:

```powershell
.\.venv\Scripts\python.exe -m scripts.compare_answer_context --source-gaps --baseline data/experiments/records/pilot/stage07_20261020 --output output/records_stage12_new
```

## Limitations and verdict

Implemented: reproducible source graphics inventory and exact selected-context
diagnostics. This is not figure OCR, cell reconstruction, plot digitization,
semantic completeness detection or a scientific relevance classifier. The
selected PDF layer is inventoried; this stage does not compare original versus
OCR PDF renderings. Rectangles do not reproduce pixels, clipping, transparency,
path shapes or figure relationships. Unknown content stays unknown.

Next bounded work: a separately versioned, source-preserving route for image/table
text candidates, tested first against these diagnostics and independent cases.
Preserve original text and images; compare extraction results before changing
generation inputs or gates. Scientific acceptance and page continuations remain open.
