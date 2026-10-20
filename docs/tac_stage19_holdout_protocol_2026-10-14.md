# TAC stage19: pre-output source audit protocol

Scope: eight newly downloaded documents, four Russian and four English, absent
from the prior 33-document corpus by exact PDF hash, supplied DOI and full selected
text hash. Selection uses subject relevance, language, layout and public download
availability before TAC outputs. It is an availability sample, not random sampling.
Two arXiv manuscripts, bilingual front matter and several journal layouts are
included. All acquisition failures and replacements remain recorded.

The initial extractor is the unchanged `tac_section_proposals_v0.8`, whose files
are copied and hashed before outputs. Original responses/PDFs remain immutable;
two nonstandard 65/67-byte prefixes remain intact and diagnostic. Selected text
uses the existing original-PDF extractor. No OCR, normalization, ingestion,
chunking, database mutation or live retrieval is part of this experiment.

## Reference policy

Before the first TAC run, an assistant inspects original rendered target pages
and freezes exact reference spans. The assistant does not inspect TAC proposals
while doing this. The reference is an assistant source audit, not independent
human/scientific gold. It evaluates field boundaries, not scientific truth or
character fidelity.

- T: the complete primary article title, excluding author and affiliation marks.
- A: a complete abstract paragraph, excluding its label, keywords, copyright,
  citation instructions, author details and body text. In the bilingual article,
  either complete Russian or complete English abstract is acceptable. Both
  alternatives are frozen before output; the primary Russian variant comes first.
- C: complete scientific text of the explicitly headed Conclusions/Выводы/
  Заключение or the combined Discussion and conclusions section. Supporting
  Information, funding, acknowledgments, bibliography, running text and numbers
  are excluded. Explicit summaries may be reference targets where no heading
  exists. This sample does not estimate behavior on truly absent A/C fields.
- Exact selected-layer characters remain untouched. Reference spans can split
  across pages to exclude running material; surrounding whitespace is ignored
  only by the evaluation, not rewritten in either saved source or algorithm output.

## Evaluation

Compare sets of `(PDF page, character offset)` for non-whitespace characters.
Intersection gives retained target characters; predicted-only characters are
contamination; reference-only characters are omissions. Report counts and
character precision/recall per field, macro averages and micro totals. Zero
predictions with a present reference are `missed`; nonempty unequal sets are
`boundary_error`; identical sets are `pass`. No zero-denominator precision is
silently set to a successful score. For bilingual A, choose the pre-frozen
alternative with largest F1, breaking ties in listed order, and disclose the choice.
These metrics are newly defined for this separate experiment; historical retrieval
or boundary-audit metrics are not changed or compared as the same metric.

The first report must preserve all 24 fields, including failures. A subsequent
repair run, if made, gets separate versioned outputs and is explicitly a development
result on this now-observed sample, not continued held-out validation. Recheck the
original 33 documents for regressions. Do not erase the initial report, edit
algorithm outputs or convert unreviewed Terms proposals into confirmed facts.

Generate a separate HTML review with all eight agreed columns and all eight
documents, exact expandable text, proposed Terms, source links and diagnostics.
Keep its automatic Terms store private to the experiment; the user's existing
33-document active snapshot and watcher remain on their validated inputs.
