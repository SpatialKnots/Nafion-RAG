# TAC stage18: source-preserving boundary cleanup

Date: 2026-10-14. Scope: the same 33 frozen ARIADNE development documents,
99 T/A/C fields. Extractor: `tac_section_proposals_v0.8`.
Corpus SHA-256: `4189045ddad052b2121e4e809761deaeafa0505f8ff8c4975cdcc2e27d10e73a`.
Profiles SHA-256: `f28ed788f5e283b9391d4348c9692d00c3bf832a0fd07249c70d12006329d568`.

## Changed

Implemented general layout-backed figure-tail and marginal-text exclusions,
Russian administrative paragraph boundaries, a bounded Russian summary marker,
and title footnote-marker handling. Runtime rules contain no article IDs or
filename exceptions. See the [explicit v0.8 contract](tac_boundary_cleanup_contract_v0.8.md).

| Source | Field | Result checked against original PDF |
| --- | --- | --- |
| Guo, uploaded as 2020 | C | Figure 5 labels/axes and next-page number excluded; continuation retained |
| Чернюк, 2023 | C | Unheaded acknowledgments and administrative assignment text excluded |
| Yu, 2022 | C | Figure 8 tail and repeated Articles / Nature Energy headers excluded |
| Satoh, 2013 | C | Figure 10 labels and following publisher text excluded |
| Резницких, 2021 | C | Exact final “Таким образом” paragraph recovered before funding; labelled summary_passages |
| Диссертация Чернюк С.Д. | C | Seven numbered findings retained; marginal numbers and separately bold-headed recommendations excluded |
| Lin, uploaded as 2023 | T | Final dagger excluded using the matching lower, smaller supplementary-information footnote |

Upload names are source identifiers, not corrections to bibliographic years.
All 91 populated Authors/Journal/Year values remain unchanged. The seven changed
fields were visually checked against read-only Poppler renders of original pages.
The 92 other fields inherit earlier assessments only after exact span equality.
No original PDF, selected page text, OCR output, chunk, database schema, retrieval
score or evaluation question was modified. Exact source ligatures and damaged
glyphs remain. MuPDF syntax/color-space warnings are preserved in extraction
stderr and the existing layout diagnostics; they were not silently repaired.

The automatic pipeline now uses the validated stage18 profiles/metadata/audit.
It published snapshot
`da4bbc428e1fada75de0a62beeab1721936281480c82f89c70a76c63170a8301`,
fingerprint `77633139d9d9f53d89090851a84945925a37cced01d184645e85df92d0c78ce8`.
The prior stage17 snapshot and frozen outputs remain available.

## Observed results

| Assistant development audit | Before | After |
| --- | ---: | ---: |
| Pass | 87 | 94 |
| Boundary error | 6 | 0 |
| Missed | 1 | 0 |
| Not separately delimited | 5 | 5 |
| Total fields | 99 | 99 |

These counts are not independent accuracy. T is proposed for 33 documents,
A for 30 and C for 31. Recovered unheaded summaries are not separately headed
Conclusions and do not establish completeness of all scientific findings.

Terms changed from 2,283 / 4,214 uses to **2,154 / 3,976 uses**. Exactly 133
article-local candidate IDs disappear from the narrowed TAC scope and four are
added from the recovered summary. Removed candidates can include scientifically
meaningful recommendations; this is a field-scope change, not deletion from the
corpus or a claim that every removed phrase is noise. All 26 unaffected article
context bundles are exactly equal; there are still 98 selected contexts.

| Automatic axis | Proposed uses | Unclassified uses | Unresolved uses | Unique Terms with proposals |
| --- | ---: | ---: | ---: | ---: |
| Type | 1,310 | 2,658 | 8 | 475 |
| Role | 36 | 3,940 | 0 | 17 |
| Origin | 65 | 3,911 | 0 | 61 |

Relation output remains 9 property-of proposals, 2 measured-by proposals and
36 deferred cases. Proposals and unresolved classifications remain algorithm
outputs, not scientifically confirmed facts. Manual decisions/events remain zero.

Frozen replay of the same 46 questions has **identical aggregate metrics before
and after** for every existing arm: production 46/46, TAC-only 42/46, TAC-deep
44/46, TAC-deep-rescue 45/46. The production MRR is 0.9342105263; TAC-deep-rescue
MRR remains 0.9195906433. Source identities and some TAC candidates/details change;
equality of individual ranking/evidence records is not claimed. This is a saved
candidate replay, not a new live-search or latency benchmark. It does not rerun
or replace the separate Terms retrieval v1/v2 experiments and their frozen code
bindings. No production search integration was introduced.

## Artifacts and operation

- `output/tac_stage18_20261014/ARIADNE_TAC_stage18.html`: all 33 documents, eight
  agreed columns, seven changed-field badges, full expandable TAC/Terms,
  classifications, relation proposals, previous changed text and source diagnostics.
- `output/tac_stage18_20261014/automatic_pipeline/runs/77633139d9d9f53d-94cbecfb`:
  separately frozen input/sidecar/table/Atlas bundle and manifest.
- `output/tac_stage18_20261014/integrity_report.json`, `delivery_verification.json`,
  `live_api_verification.json`, `browser_verification.json`: verification evidence.
- `output/tac_stage18_20261014/source_audit`: original page renders and exact mapped
  geometry. `before` preserves prior bundle, code and pipeline config.
- `output/tac_stage18_20261014/retrieval_replay_before` and `retrieval_replay`:
  separately bound 46-question replays.
- `output/tac_stage18_20261014/preview_summary.png`: actual browser view of recovered C.

The existing loopback Atlas API on port 8766 serves the new current snapshot.
The separate review table is available at
`http://127.0.0.1:8773/ARIADNE_TAC_stage18.html` while the local server runs.
Local file links resolve to the immutable originals on this computer.

The verified stage17 watcher was stopped during changes, then restarted hidden:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.tac_terms_pipeline --config data/terms_pipeline_config.json --output-root output/tac_stage18_20261014/automatic_pipeline --watch 30
```

The initial watch log reports `unchanged` for the published stage18 snapshot;
stderr is empty. Polling remains tied to the host session and JSON corpus inputs;
OS-startup registration and direct database-ingestion-to-snapshot integration are
not implemented. The root review table adds comparison badges; the pipeline's
frozen table/Atlas remains its own separately checksummed output.

## Tests run

- Full pytest: **1,022 passed**, one existing Starlette/httpx deprecation warning,
  96.92 seconds. Command: `.venv\Scripts\python.exe -X utf8 -m pytest -q -p
  no:cacheprovider --basetemp=output/tac_stage18_20261014/pytest_final`.
- 18 new parameterized regression cases cover supported figure tails versus body
  continuation, absent captions, repeated merged headers, body numbers, unique
  marginal text, administrative versus inline statements, separately bold-headed
  recommendations, footnote ambiguity, bounded summary and later-summary retention.
- Ruff passed for `app tests scripts`; mypy passed for 94 app source files;
  Git diff whitespace check passed (existing Windows line-ending notices remain).
- The final HTML's actual embedded script passed bundled Node `--check`.
- Two actual v0.8 extraction runs reproduce identical profile contents. The final
  extraction is bound to final code/component hashes; timestamps and hashes differ
  from the earlier candidate, so byte equality is not asserted.
- Source checks verified all original PDF hashes, exact final TAC/Terms quotes,
  reviewed render hashes, all eight columns/33 rows, seven change badges, 113
  existing local targets, unchanged populated metadata and all pipeline artifacts.
- Actual loopback API: new current snapshot, automatic mode, no manual events or
  problems, original PDF HTTP 200 and `%PDF` signature.
- Actual browser: search Резницких yielded 1/33; recovered C expanded in full;
  all 61 A/C cells and 33 Terms containers opened after asynchronous completion.
  The table was returned to all 33 rows and collapsed cells. An earlier DOM count
  observed partial asynchronous progress; it is retained as an intermediate
  observation, not a successful completed expansion.

Initial targeted pytest reported 84 passes and 13 fixture-setup errors because
the sandbox could not create its temporary directories; that run is not counted
as a pass. The complete rerun used the workspace temporary directory with granted
execution permission. Initial loopback verification hit WinError 10013; an
authorized retry succeeded. Initial Ruff found import order/line length and those
were fixed before the passing checks and final extraction. No failed attempt is
presented as successful verification.

## Limitations

These rules were developed on the known defects in this corpus. There is no new
independent gold set or held-out proof of generalization. Geometric and surface
language rules are bounded; unsupported structure remains diagnostic. The
assistant audit certifies neither scientific meaning nor character fidelity.
Five structurally absent A/C fields remain explicit. Unclassified/unresolved
Terms are retained automatically. Search effectiveness did not increase on the
existing questions. Future scientific evaluation should use independent source
annotations without mandatory per-Term user-resolution forms.

## Verdict

The seven known TAC defects are repaired and traceable under explicit v0.8 rules;
92 other fields and original PDFs remain unchanged. A complete separate HTML
review and automatic Terms snapshot are delivered. General scientific accuracy
and superior retrieval are not claimed.
