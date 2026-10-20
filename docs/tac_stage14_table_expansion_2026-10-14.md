# TAC stage14: responsive visible-row text expansion

Date: 2026-10-14. Scope: all 33 documents, unchanged stage13 scientific inputs.

Changed: the mass-expansion control now opens the full Abstract/Conclusions and
Terms container of visible rows, processing one row per event-loop turn. It does
not clone all candidate pages and repeated full context evidence or open every
nested diagnostic. The control names its visible-row scope and displays progress.
All source content and the complete inventory remain separately expandable.
Search hides rows without materializing their nested Terms evidence.

Prepared snapshot:
`b3c07e157311d24dd3cb4fc574f26761ca29cf2b811f6fc32c8a128b86c78478`.
Classification remains the unchanged stage13 v0.2 sidecar. The stage13 snapshot,
table and prior timeout evidence remain intact.

Artifacts: `output/tac_stage14_20261014/ARIADNE_TAC_stage14.html`, Atlas export,
`browser_verification.json`, `table_preview.png` and `integrity_report.json`.

Tests run: eight HTML unit tests passed after correcting a missing test-output
parent directory (the first attempt had seven setup errors, not test passes).
Actual browser expansion completed for 33 Terms containers and 60 A/C texts;
collapse and search for `Istomina 2021` then expanded only its one visible row.
DOM node count stayed 30,349 and no full context was materialized by this control.
Static verification preserved all eight columns/33 rows, exact TAC/91 metadata
values, 2,266 Terms, 12,585 assignments, recomputed subsets, 113 existing local
targets and 120 source/input file hashes. Manual ledger events remained zero.
The final combined stages passed the full checks reported in stage16.

Limitations: these observations establish successful interaction, not a timing
benchmark or proof of the previous timeout's precise cause. Opening thousands
of nested sources individually can still create a large document. The button
deliberately describes text/list expansion; evidence remains available by drilldown.

Verdict: the observed mass-expansion timeout is resolved for the declared corpus
and tested interactions. Scientific outputs and original PDFs are unchanged.
