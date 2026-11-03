# Corrected offline article-label accounting, v0.2

The first capture counter in `scripts/retrieval_ablation.py` recognized top-level
fixture DOI/title/checksum fields and nested DOI fields. It omitted nested
checksum/title/article-identity fields, incorrectly excluding nine positive
extended fixtures from its article-hit denominator (53 instead of 62).

Retrieval candidates, queries, SQL results, windows, traces and raw capture files
are unchanged. Do not edit the capture or rerun retrieval to conceal this defect.
`scripts/retrieval_ablation_labels.py` recomputes final metrics from the saved
retrieval rows, using the existing repository `_load_extended_expected_articles`
and `_result_matches_extended_article` functions and recorded PDF checksums.
All original capture counters remain available, with an explicit legacy warning.

Affected extended fixtures: qext019, qext020, qext024, qext025, qext034, qext035,
qext036, qext037, qext038. This correction concerns fixture parsing only; it
creates no labels, scientific assertions or new source evidence. Expected
denominator: 24 baseline + 38 positive extended = 62 case labels, with overlap
between existing queries disclosed. Negative/unlabelled cases have no positive
article-hit score. An inconsistent negative with positive targets is rejected.

Seven added tests cover nested checksum/title/title_contains/article_id,
unsupported targets, unlabelled/negative cases and inconsistent negative input.
Final report must name metric version v0.2 and preserve the first counter's
limitation. No ranking, thresholds, model/provider or public schema changes.
