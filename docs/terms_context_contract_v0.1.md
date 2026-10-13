# Exact Terms mention/context contract v0.1

Implemented development sidecar: `tac_term_contexts_v0.1`.
Core models/builders: `app/terms/schema.py`, `app/terms/contexts.py`.
Experiment adapter: `scripts/tac_term_contexts.py`.
It consumes existing `tac_term_inventory_v0.1`, frozen corpus and TAC profiles;
it does not change generation, ranking, preview, source sections or scientific
acceptance. Every term use remains `unclassified`.

## Source identity and integrity

SourceFragment stores article scope, original PDF path/hash, 1-based physical
page, recorded selected layer type/ID, layer PDF path/hash, full page-text hash,
zero-based Unicode-codepoint offsets `[start, end)`, exact quote and quote hash.
Source type is `pdf_selected_TAC_text`. Full page text stays in the referenced
frozen corpus; context/mention quotes are exact slices of that text.

Reuse the generic `source_identity` and `text_hash` primitives from
`app.records.schema`, and the read-only streaming file hash from
`app.records.sources`. No Li-Nafion observation/schema/admission rules are reused.
The existing numeric/record contracts are unchanged.

Region identity is SHA-256 of the generic record source-identity payload:
the JSON array of string representations of article ID, original PDF hash,
page number, layer ID/type, layer PDF hash, page-text hash, start and end,
using UTF-8, `ensure_ascii=False`, separators `(',', ':')`.
Paths, extraction date/method/version, preview and machine review labels do not
rename an unchanged physical source slice. Changed page text, selected layer,
PDF content, coordinates or article scope do. Identical visible strings are
insufficient to establish identical source identity.

The builder verifies the page-text hash, exact offsets, source slice, profile
and inventory evidence/layer binding. The CLI also checks physical original
and selected-layer PDF hashes inside the declared `--source-root`; escaping
paths and non-PDF source paths are rejected. Models reject unknown fields,
invalid types, quote length/hash and identity failures. Technical validation
does not verify OCR correctness or scientific meaning.

## Mention, local term and use

For derived IDs, `identity(kind, *parts)` hashes the UTF-8 JSON array
`[kind, *parts]` with `ensure_ascii=False`, separators `(',', ':')`:

- Mention ID: `identity('term_mention', region_id)`. Repeated words at different
  offsets are different mentions. The same physical mention can support two
  uses when upstream T/A/C proposals overlap; mentions are not concepts.
- Local term ID: the existing stage09 article-scoped lexical `candidate_id`,
  preserved with its original label/matching string. It is not a global concept.
- Context ID: `identity('tac_context', region_id, kind)`, where region_id belongs
  to the exact containing section/page fragment.
- Use ID: `identity('term_use', term_id, mention_id, context_id)`. Roles are not
  inferred; a word reused in another context keeps a distinct use.

Article rows contain local terms with use references, de-duplicated mentions,
contexts, uses, section groups, lexical containments and diagnostics. Distinct
uploads/scopes retain separate identities even if selected page texts match.
Physical PDF byte identity and selected text equality are different checks.

## Context scope and page transitions

Initial context is a complete exact frozen TAC fragment on one page. No paragraph
or sentence segmentation is implemented, and word-per-line PDFs are not split
into sentences by newline. Source whitespace, formula case, glyphs and line-end
hyphens are retained. Context method is inherited from the TAC proposal.

Boundary status is inherited from matching inventory evidence. If a context has
no candidate evidence, it is explicitly `unreviewed`; the original field-level
boundary assessment remains in the referenced profile/review table. Contexts
do not promote boundary assessment to scientific acceptance.

Section groups organize contexts by T/A/C and physical page/start/end order.
Transitions record `same_page_disjoint`, `same_page_overlap`, `adjacent_pages`
or `page_gap`. All have `text_continuity='not_asserted'`. Groups are not asserted
single logical sections or reconstructed reading order. No page fragments are
concatenated; missing-page gaps remain explicit. Shorter paragraph/sentence
contexts and verified cross-page semantic continuation are outside v0.1.

## Lexical containment

`lexical_span_contains(outer_use, inner_use)` means proper offset inclusion of
the inner mention in the outer mention, within the same context and physical
source identity (article/PDF/page/layer/page-text). The exact inner quote must
also equal the corresponding slice of the outer quote. Equal spans, different
contexts and unrelated repetitions cannot create such links.

The sidecar stores all proper span containments, including transitively implied
ones; it does not claim a reduced direct graph. These links establish neither
synonymy nor broader/narrower concept hierarchy, property-of, sample membership,
conditions, method linkage or cross-article equivalence.

## Binding and reproducibility

Root manifest records corpus/profiles/inventory byte hashes, schema/state,
adapter and component hashes, timestamp and verified physical PDF hashes.
`validate_contexts` first validates the referenced inventory, then parses the
strict models and reconstructs the expected bindings/containment from frozen
inputs. Missing/fabricated IDs, changed quotes/layers, omitted uses/edges,
duplicates, false containment or scientific accepted states are rejected.
The saved inventory remains unchanged; the context sidecar is optional and
separately versioned. Artifact self-hashes do not substitute for authoritative
frozen inputs and physical source verification.

## HTML review

The existing eight columns remain. Each candidate can expand its mention/use
references, exact containing contexts and lexical inclusions with source offsets.
Context text is stored once per context in shared HTML templates and cloned
on demand; repeated opening must not duplicate it. Search/preview/lazy candidate
groups preserve stage09 behavior. Global expansion exposes all context cards.
No decisions are persisted and no semantic categories are assigned by this UI.
Original PDF links, source diagnostics and existing T/A/C text remain available.
