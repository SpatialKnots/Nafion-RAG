# Stage12: source graphics absent from text-only messages

Algorithm `source_visual_gaps_v0.1`. Development diagnostics only. Replay the four
frozen stage07 questions using unchanged stage11 v0.2 selection. No database,
retrieval, inference, OCR, source repair, production activation or new gate.
Freeze protocol, source code, corpus snapshot, source packets and selected PDFs
before replay. Preserve each run separately.

Inventory every image occurrence from `get_image_info(hashes=True, xrefs=True)`
and every `get_drawings()` entry in the selected source PDF. Keep duplicate
occurrences, inline images, tiny pieces and zero-height/width drawing paths.
Do not use a size filter or classify icons, logos, plots, scientific tables or
decorations by appearance or bounding box. This is an occurrence inventory, not
a reconstruction of independent figures, transparency masks or external assets.

Retain article, page, layer, original and selected PDF paths/hashes, occurrence
indices, image object numbers/xrefs, pixel digest, dimensions, transforms,
drawing indices/types/counts and unrotated PyMuPDF source coordinates. Record
page rotation, media/crop boxes and displayed page rectangle separately.
These rectangles locate source objects; they do not reproduce their pixels,
clipping, transparency, rendering order or individual vector path geometry.

Read dictionary spans with `TEXTFLAGS_TEXT`, matching the registered text/block
flags; image-preserving dictionary mode can shift later text block numbers.
Concatenate native dictionary text spans per line plus its newline. Require
exact registered page text, block ordering, offsets and block rectangles before
recording line overlap. Retain exact line text, offsets and SHA-256. On an
alignment failure retain assets with unknown overlap and explicit diagnostics.
File, PDF, identity and hash failures must propagate. Invalid asset geometry
remains recorded with unknown overlap. Rectangular overlap includes touching
edges and degenerate vector paths; it is not pixel coverage or OCR evaluation.

Bind selected source slices by exact identity, offsets and text hash. Record
their overlap with registered lines. Record proposed layout/table group bounding
box intersections and selected caption citations separately, without claiming
figure ownership. Include complete proposed groups and exact caption lines.
An image with no overlapping line has no registered text in its bounding box;
it may contain a logo, photograph, scientific graphic or other unknown content.
Overlapping text, including an OCR layer, never proves complete representation.
Scientific relevance, information loss and text completeness stay unevaluated.
All image pixels/vector paths are absent from these text-only candidate messages.

Validate synthetic image-only, partial/complete text overlay, repeated/tiny/inline
assets, vector-only drawing, wrong hashes/identities, unknown line geometry,
rotation/crop coordinates and exact source binding. Replay all declared pages,
compare stage11 evidence and candidate request bytes unchanged, and verify earlier
mode report compatibility. Generate searchable HTML and representative page PNG
overlays with exact source links. Visual review is limited to the displayed pages;
no corpus-level OCR or scientific accuracy claim follows. Original PDFs immutable.
