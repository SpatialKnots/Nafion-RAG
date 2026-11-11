# One-action integration amendment, v0.2

The v0.1 protocol/freeze/results are unchanged. probe_v01:58 new tests passed;
tests_v01:1206 affected tests passed. The first actual preparation→packet→action
probe (pipeline_probe_v01), with synthetic DB/source seams and valid UUIDs,
stopped before lookup: blockers included baseline_insufficient_evidence,
query_qualifier_check_failed and source_registry_unproven. Generation calls0.

Inspection of the preserved actual qualifier output showed qualifiers=[] and
parse_warnings=[], with reason=baseline_rejection_preserved. Existing preparation
always adds query_qualifier_check_failed when baseline_allowed=false, even when
no qualifier was parsed. Thus the original broad blocker guard prevents the
intended bounded diagnostic step as wired through real preparation. Standalone
synthetic packet controls alone did not demonstrate that integration.

The separate final action version is bounded_coulombic_context_action_v0.2.
Only for that inherited case may the diagnostic lookup proceed: baseline_allowed
must be false; the saved complete query_qualifiers report must equal a fresh
assessment on selected raw sources/recorded article metadata with baseline=false;
its qualifier list and parse warnings must both be empty. A real missing/unknown
qualifier, any warning, changed report or other blocker still stops before I/O.
Source/query/author/label/cell/registry/filter/budget preconditions remain intact.

Original preparation status, query_qualifier_check_failed and every original
blocker remain unchanged in the input and diagnostic adapter. No inference veto
or query qualifier logic changes. The selected scope explicitly records that
the inherited empty-catalogue rejection was preserved. Include query_qualifiers.py
in the fixed action code bindings. This is permission for one diagnostic read,
not permission to generate or scientific admission.

Pre-v0.2 app/tests/probe are saved in pre_v02_snapshot. The original pipeline
result, original JUnit and first81-case comparison remain separate. Final checks
must repeat the affected scope and actual pipeline probe, including negative
changed-report/real-qualifier controls and preserved blockers. First Ruff unused
imports/line length and four event-list typing diagnostics were also corrected;
they did not change scientific rules or source values.
