# Stage13: local OCR candidates from frozen source regions

20 October 2026. Algorithm `source_region_ocr_v0.1`.
[Protocol](records/region_ocr_protocol_v0.1.md). Development layer only.

## Changed

Added `app/evaluation/region_ocr.py` and `scripts/audit_region_ocr.py`.
The CLI consumes a separately frozen stage12 source-gap report and a declared
region scope. It resolves exact raster occurrence or closed-table proposal
rectangles, verifies original/selected PDF hashes, and rebuilds the complete
source-gap registry before rendering each region. It refuses changed registries,
unregistered rectangles, unsupported rotations and existing output directories.

Regions are rendered as opaque RGB PNG at 300 dpi, with no padding or cleanup.
The requested PDF rectangle and actual raster-grid rectangle, pixel origin,
dimensions, image hash and source identity are retained. Word coordinates map
through the actual raster origin, including fractional crop boundaries.
No original PDF is edited; no replacement OCR PDF is generated.

Local Tesseract creates exact TXT and TSV in a fresh directory. Raw bytes,
stdout/stderr, arguments, process outcomes and hashes remain preserved. The
executable, adjacent DLLs, eng/rus traineddata and version output are frozen.
The declared settings are OEM 1, PSM 11, 300 dpi, one OpenMP thread and a
120-second timeout per region. There is no adaptive setting selection or retry.
This new module uses the existing tool environment but does not change the
ingestion OCRmyPDF path, extraction, text-layer selection or database schema.

Every TSV word retains exact text, source TSV row, layout IDs, raw confidence,
pixel rectangle and PDF rectangle. Low-confidence/empty words are retained;
confidence -1 means unavailable. Malformed schema/fields, non-finite confidence,
out-of-image rectangles and multi-page output fail explicitly. Process failures
and timeouts save diagnostics and propagate. Raw TXT order and TSV word order
remain separate; no invented character alignment or automatic text repair.

Complete intersecting native lines are retained with exact source offsets and
rectangles, including an explicit flag for partial intersections. Case-folded
token multiset differences are diagnostic, not a scientific score or accepted
numeric extraction. No OCR candidate is added to retrieval or GPT evidence.
Production answer behavior, selection and gates remain unchanged.

## Declared pilot and results

Scope was generated and frozen before corpus region OCR from the final stage12
report. Scope SHA-256:
`c676c161d2541ede994825f048503f8dc3a2eaa154337c9bdf221366aebfde14`.

| Region | Role | Words | Raw TXT characters | Words with confidence below 50 |
| --- | --- | ---: | ---: | ---: |
| Istomina 2021, page 3 scheme | Raster labels/conditions | 56 | 326 | 7 |
| Chernyuk 2023, page 4 plot body | Diagnostic control, no curve digitization | 0 | 0 | 0 |
| Sanginov 2021, page 12 Table 3 | Native-text table rendered to pixels | 323 | 1860 | 6 |
| Kayumov 2021, page 3 Table 1 | Native-text table including notes rendered to pixels | 84 | 464 | 2 |

The two table controls are not claimed to be previously missing raster tables.
Three of four regions produced nonempty text: 463 word rows and 2650 raw TXT
characters in total. These counts do not measure correctness or scientific
completeness. The confidence cutoff 50 only marks diagnostics.

All four original source crops and word-box overlays were inspected. Separate
development observations, without repairing the raw output:

- The scheme retains many temperature/duration labels, but its visible HCl label
  becomes mixed-script `МНС!` with confidence 85.761093. The visible peroxide/water
  concentration line is absent. Water subscripts and diagram textures also cause
  damaged or spurious words, including boxes encompassing vessel shapes.
- The plot-body crop contains curve/markers and produces no text. All 11 native
  line boxes intersecting this region are partial intersections; their complete
  retained texts can include labels outside the crop. Token absence in this
  comparison must not be treated as evidence of missed complete visible labels.
  The crop is not a complete figure/axes enclosure or digitized dataset.
- The dense table contains numerical and chemical notation errors. In one
  visible cell `4.3` becomes `43` with confidence 90.406754; several negative
  superscript exponents collapse into `103`, and some leading factors are lost.
  Units and mixed-script labels are damaged. Cells are not reconstructed.
- The second table retains three visible rows and all four star-prefixed
  temperature notes, but Greek header symbols, units, Latin EC and title Li+
  are damaged. Note text preservation does not prove correct cell-note linkage.

High confidence therefore does not establish scientific correctness. These
observations are from the development examples, not independent gold annotation,
a held-out evaluation or an accuracy estimate. No per-case user resolution form
is introduced.

## Tests run and reproducibility

- New unit cases: **35 passed**, including fractional crop/pixel mapping,
  changed PDF/registry/image/engine inputs, unsupported rotation, malformed TSV,
  low/unavailable confidence, raw CR/LF preservation, process timeout/exit/launch
  failure, missing/malformed output, partial native lines and absent native text.
- Full regression: **1336 passed**, one existing Starlette/httpx deprecation
  warning, 128.81 seconds.
- Ruff passed for `app tests scripts`; mypy passed for 108 application files.
- All four PNG, TXT and TSV files are byte-identical on a second actual local
  OCR run using the same frozen scope/settings. Different output-directory
  arguments/process manifests are not claimed to be byte-identical.
- A fresh stage12 replay report is byte-identical to the previous final report.
  The prior stage12 frozen input/code hashes also remain valid. No evidence,
  candidate request, answer provider or gate was modified in this stage.
- Source, scope, code, registry, runtime, traineddata, PNG and raw output hashes
  checked after the run. Static HTML coverage: four rows, four crop images and
  four existing PDF links. Additional visual-review links/images checked.
- Exact configured API key scan found zero matches in 32 generated JSON, HTML,
  TXT, TSV and process-byte artifacts at postflight. No credentials printed.
- No external API call, fresh retrieval, corpus mutation or scientific answer.

A read-only console inspection initially used a Windows encoding unable to print
a Unicode minus; UTF-8 inspection resolved it without changing saved outputs.
The first private annotation helper failed while hashing its own filename string.
Its partial diagnostics and explicit failure record remain preserved. A corrected
helper wrote separate `diagnostics_v02/` and `visual_review_v02.html`; raw OCR was
not rerun or repaired for that helper correction. `visual_qa.json` records the
subsequent inspection of all four final overlays. Browser visual/click QA was
not run.

## Artifacts and reproduction

Private root: `output/records_stage13_20261020/`.

- `scope_v01.json`: four frozen references and exact rectangles;
- `run_v01/review.html`: searchable source crop, raw OCR, native text and diagnostics;
- `run_v01/visual_review_v02.html`: separate visual observations and word overlays;
- `run_v01/input_manifest.json`, `report.json`, `final_qa.json`;
- each region: immutable `source.png`, exact `ocr.txt`, `ocr.tsv`, process logs,
  `process.json` and `result.json`;
- `run_v01/diagnostics_v02/visual_annotations.json`, `visual_qa.json` and PNGs;
- `repeat_v01/`: second actual local OCR run;
- `stage12_compatibility/`: unchanged previous mode replay;
- private scope/postflight helpers with hashes in scope/QA records.

From the repository root, use a fresh output directory:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.audit_region_ocr --stage12 output/records_stage12_20261020/replay_v02 --scope output/records_stage13_20261020/scope_v01.json --output output/records_stage13_new
```

## Limitations and verdict

Implemented: reproducible local region OCR candidates, exact source/word geometry,
raw failure diagnostics and source-versus-OCR review. Real chemical/numeric errors
remain even at high confidence. Native token comparison does not validate signs,
exponents, units, layout or note linkage; partial native lines can extend outside
the rendered crop. Rotated pages, cell reconstruction, plot digitization,
cross-page stitching and scientific acceptance remain unsupported here.

Next bounded step: a separate version for scientific-notation and geometry
diagnostics, retaining sign/exponent/unit evidence and distinguishing complete
native content from partial intersections. Use independent constructed and real
counterexamples before changing OCR settings or adding candidates to generation.
