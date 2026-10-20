# TAC boundary cleanup contract v0.9

Version: `tac_section_proposals_v0.9`. Extends
[v0.8](tac_boundary_cleanup_contract_v0.8.md) after a separately frozen initial
test on eight new documents. The initial v0.8 output and pre-output source
reference are immutable evidence. After observing those results, the eight
documents are development inputs; the repaired result is not held-out validation.

## Explicit rule changes

- Recognize standalone, optionally numbered “Discussion and conclusions” and
  “Обсуждение и выводы/заключение” as combined conclusion sections. Do not
  interpret inline mentions as headings.
- Stop at the bilingual “СПИСОК ЛИТЕРАТУРЫ / REFERENCES” and singular
  “БЛАГОДАРНОСТЬ”, in addition to existing stop headings.
- Keep the first supported explicit abstract in the front matter. Secondary
  abstract headings are diagnostic and not combined with the primary field.
- Exclude bibliographic title candidates identified by year plus volume notation
  or a UDK label. Exclude standalone lines with two parsed initialled names from
  title joining; a terminal uppercase affiliation glyph can be removed only in
  the matching view. Source title slices and original name text are not rewritten.
- For non-title prose joining, allow left-edge movement of at most
  `max(12 points, 2 × font size)` instead of 12 points, accommodating an indented
  first line. Existing font/style/contiguity/vertical-gap requirements remain;
  adjacent columns and distant paragraphs must not be joined by this allowance.
- For a TAC abstract anchor only, when an independently mapped byline is followed
  by an affiliation, allow comparison views that ignore detached lowercase
  correspondence marks and split a hyphen followed by a capital initial. This
  neither fills author metadata nor changes the selected source quote.
- Exclude standalone copyright rows beginning with © and a year from front-matter
  prose. A glyph attached to a scientific sentence is not this rule's trigger.
- A mapped margin must lie wholly in the top 9% of a page, or begin below 90%
  of page height. The earlier absolute top cutoff of 35 points is replaced
  explicitly. Only repeated marginal lines or numeric page-number rows at field
  edges are removed; unsupported/unique text remains diagnostic.
- Clip C before a separately mapped paragraph whose first 200 whitespace-normalized
  characters explicitly state study under a government assignment. This opening
  is a matching view only; the saved source remains unchanged. Ordinary property
  statements without that administrative cue remain.

No article ID, filename or expected reference quotation is a runtime exception.
Unknown bylines, mapping failures and ambiguous boundaries retain diagnostics.
Selected-layer text, original PDF bytes, units, numeric values, chunking, database
schemas, retrieval scoring and historical metrics remain unchanged.

The original 33-document regression requires equality of every T/A/C proposal,
including offsets, methods and source identity, against v0.8. Source metadata
values and PDF hashes must also remain unchanged before updating the automatic
pipeline inputs. The eight new documents stay in an isolated experiment store;
they are not silently added to the production ingestion/retrieval corpus.
