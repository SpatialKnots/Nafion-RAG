# Front-matter author guard amendment, before v0.2 measurement

v0.1's retrieval matched the first author/year; a constructed adverse control
showed quotation admission could ignore a different explicitly named coauthor.
Preserve adverse_author_guard_v01.json and review_v01/source_snapshot unchanged.
This is a constructed software defect, not a measured scientific error rate.

v0.2 adds a necessary source identity guard to the bounded quotation contract:
every explicitly named Latin surname in the question's citation must appear as
a whole token in retrieved first-page front matter, before Abstract/Introduction/
Dissolution procedures/table sections. The question's year must also occur on
that original first page. Body-only references or registered metadata alone do
not establish this guard. Et al./и соавторы does not invent unknown names.
Require the resolved work, not a different article or a later-page bibliography.

Bump the quotation contract version; no scoring/threshold/quote text/units/query
change. Freeze positive/negative front-matter controls before measuring v0.2.
Compare unsent native request bytes with v0.1 if quotations are unchanged.
All previous v0.1 limitations and no-live-call scope remain in force.
