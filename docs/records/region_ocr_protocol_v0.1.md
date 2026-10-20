# Stage13: local OCR candidates from frozen source regions

Algorithm `source_region_ocr_v0.1`. Separate offline development layer, using
the frozen final stage12 registry and four regions declared before OCR: the
Istomina page 3 raster scheme, Chernyuk page 4 raster plot body, Sanginov page 12
closed table proposal and Kayumov page 3 closed table proposal. The latter two
have native text and are rendered to pixels for an explicit comparison control;
they are not claimed to be previously missing raster tables. The plot body is a
diagnostic control, not a curve digitization task. No extra padding, native text
replacement, adaptive reruns, corpus search, database, generation or API call.

Freeze scope, registry/report/input manifest, code and source PDFs before OCR.
Verify the stage12 input/code hashes and every selected PDF and original PDF.
Rebuild and compare the selected page's complete source-gap registry before
rendering. A raster region must match an existing occurrence rectangle; a table
must match an existing closed-table proposal. Keep repeated/unknown assets in
stage12 unchanged. Use fresh output directories; preserve failed runs.

Render the declared rectangle at 300 dpi, RGB, opaque, from the selected PDF
using the recorded PyMuPDF version. Support only unrotated pages in v0.1;
reject other rotations explicitly. Record requested rectangle, actual pixel-grid
rectangle, pixel dimensions, image hash and pixel origin. Pixel-to-PDF mapping
uses the actual raster origin and scale; it must not assume rounded crop edges
equal requested edges. Keep original PDFs immutable. No image cleanup, image
upscaling beyond this declared render, text repair or reconstructed PDF output.

Run installed local Tesseract with languages eng+rus, OEM 1, PSM 11, 300 dpi,
one OpenMP thread, and a 120-second timeout per region. Freeze executable,
adjacent DLL and traineddata hashes, version stdout/stderr and full argument
vectors. Save native raw UTF-8 TXT, TSV, process stdout/stderr and outcome.
Retain process failures/timeouts explicitly and propagate them; do not quietly
retry or substitute an empty success. Never overwrite existing OCR outputs.

Parse all TSV word rows with exact text, layout IDs, TSV row index, raw confidence,
pixel rectangle and mapped PDF rectangle. Retain empty/low-confidence words;
confidence -1 is unavailable. Reject malformed fields, non-finite/out-of-range
confidence, multi-page output and word rectangles outside the rendered image.
The diagnostic confidence cutoff is 50, not an acceptance threshold or probability
of correctness. Raw TXT and TSV ordering are separate; do not invent alignment
between word offsets and raw TXT offsets.

Preserve complete overlapping registered native lines and their exact page
offsets/rectangles, identifying partially intersecting lines. Compare case-folded
lexical/numeric/symbol token multisets only as a discrepancy diagnostic. Preserve
both exact texts. This comparison is unavailable where native text is absent;
native text is not scientific ground truth. No token match establishes correct
numbers, units, footnote linkage, cell assignment, reading order or scientific
completeness. Unknown cases remain unknown; no automatic promotion into answers.

Generate searchable HTML with all four source crops, exact OCR text, native text,
word coordinates/confidence, discrepancies and source PDF links. Visually inspect
every crop and record observed losses in conditions, numbers, units and notes.
Keep annotations separate from algorithm output. Do not require user resolution
per case. Verify source/input/code/engine hashes after the run. Test failure paths,
exact pixel mapping, parser integrity and unchanged prior mode outputs, then run
the appropriate full regression. Scientific accuracy/acceptance remain unevaluated.
