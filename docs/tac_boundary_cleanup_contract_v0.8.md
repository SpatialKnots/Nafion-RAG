# TAC boundary cleanup contract v0.8

The declared development scope is the frozen 33-document corpus with SHA-256
`4189045ddad052b2121e4e809761deaeafa0505f8ff8c4975cdcc2e27d10e73a`.
The extractor version is `tac_section_proposals_v0.8`. This contract explicitly
changes section boundaries; it does not repair, normalize, or rewrite source text.
Original PDFs, selected text layers, page numbering, metadata extraction, chunks,
retrieval scoring and evaluation questions remain unchanged.

## Rules

- Exclude a final title dagger only when a unique mapped lower, smaller footnote
  starts with the same marker. Missing or ambiguous support retains the marker
  with a diagnostic. Original title candidates remain available.
- Clip Conclusions at a standalone administrative paragraph beginning with
  Russian acknowledgments or a statement that the work was performed with
  funding/support or under an assignment. Inline mentions are not boundaries.
- A standalone bold heading “Рекомендации и перспективы дальнейшей разработки
  темы” starts a separate subsection outside C. This preserves all seven numbered
  findings in the dissertation but excludes the following recommendations. It is
  an explicit field-scope choice, not a claim that recommendations lack scientific
  value; their text remains in the original PDF and corpus.
- Remove only edge fragments mapped to page margins and identified as decimal
  page numbers or exact running text repeated on more than one page. Numerical
  scientific rows in the body and unique marginal text remain.
- Exclude a source-order tail that jumps physically above a preceding figure
  caption only when the first tail line also has a panel/numeric label or a short
  text with materially different font size. Matching body prose in a next column
  and unsupported geometry remain. This is a bounded heuristic.
- Add “Таким образом” to the existing paragraph-initial summary markers, in the
  latter half of a document and before bibliography. The existing size bounds
  and exact flow rules remain. Administrative paragraphs end such a proposal.
  These are `summary_passages`, not invented separately headed Conclusions.

Each retained span is exactly `selected_page_text[start:end]`. Changes carry
page/offset/method/source identity and diagnostics. Cleanup requires uniquely
mapped lines; unsupported mappings are retained under existing layout warnings.
No filename, article identifier or known expected text is a runtime exception.

## Development audit and publication

The seven changed T/C fields were checked against original rendered pages.
The 92 unchanged fields inherit prior assessments only after exact proposal
equality, including methods and source identity. Original review files and
earlier artifacts remain separate. A pass is an assistant development finding,
not independent gold or human confirmation. Missing structure is reported
explicitly and remains in the 99-slot denominator.

Only a fully source-validated TAC/metadata/boundary bundle is supplied to the
automatic Terms pipeline. Classification, subsets and bounded relation proposals
are rebuilt; they do not become confirmed scientific facts. Earlier snapshots
remain recoverable. No user decision is required for individual Terms.

The frozen retrieval replay measures the effect of these boundary changes on the
existing development questions, using the same saved candidates. It is neither
a new live-search timing measurement nor an independent scientific evaluation.
