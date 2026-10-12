# Stage 3: occurrence diagnostics, 2026-09-14

## Changed

Added `diagnose_numeric_occurrences` alongside the unchanged production candidate
API. Both use the same recognizer, guards, deduplication and capped selection path.
Every recognizer match records its exact half-open character span in chunk text,
line span, decision and first applicable rejection reason. Decisions distinguish
selected candidates, guard rejections, duplicates and cap omissions. Duplicate
links identify the first eligible occurrence by offset, including when that first
occurrence is itself cap-omitted. A rejected range endpoint cannot claim a later
valid identical lexeme.

The read-only `scripts.stage3_numeric_occurrence_audit` exports article/chunk IDs,
chunk text checksum, PDF path and stored checksum, page range, source type and
selected text layer. Multi-page chunks have no inferred occurrence page.
Each occurrence includes its exact source line for interpreting guard decisions.

Production cap remains 12. Candidate fields, order, confidence and selection
remain unchanged. No database facts or original PDFs were written.

## Tests run

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_numeric_occurrences.py tests/unit/test_structured_facts.py tests/unit/test_numeric_cap_audit.py -p no:cacheprovider --basetemp=tmp/occurrence_tests_20260914
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=tmp/occurrence_full_tests_20260914
.\.venv\Scripts\python.exe -m ruff check app tests scripts
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m tmp.compare_occurrences
.\.venv\Scripts\python.exe -m scripts.stage3_numeric_occurrence_audit --output data/exports/stage3_numeric_occurrences_20260914.json
```

- Targeted tests: 101 passed. Full suite: **536 passed**, one existing
  Starlette/httpx deprecation warning. Ruff and mypy passed.
- Compared every candidate dataclass field and list order on **619 live chunks**
  against the pre-patch working-tree snapshot: **2347 candidates, zero changed
  chunks**. Diagnostic and ordinary extraction also matched; all occurrence
  substrings were checked against source text.
- Baseline snapshot: `tmp/stage3_extraction_before_occurrences.py`, SHA256
  `8742647bed82b96ce39e1ce52c0604e495311896daea32cb59e4b6d0cbc015ca`, matching
  the previous reference-fix report. Local comparison script and result:
  `tmp/compare_occurrences.py`,
  `data/exports/stage3_occurrence_equivalence_20260914.json`.
- Current extractor SHA256:
  `319a997533f5d935e19b3057ff3827a39560e5c6b45912a37ff4048f9192d042`.
- Corpus diagnostics: **2347 accepted, 585 rejected, 1029 duplicates,
  383 cap-omitted**. These 383 omissions cover the entire current recognizer;
  they are not the three baseline-displaced candidates in the earlier diff.

## Limitations

Only `NUMERIC_UNIT_PATTERN` matches are diagnosed. Arbitrary unrecognized numbers
are not enumerated. Rejected spans can contain only a partial operand or unit;
the source line supplies context. Accepted means selected by existing rules, not
scientifically verified. Only the first applicable guard reason is recorded.

Chunk provenance is preserved; PDF content and page-layer alignment were not
reverified in this audit. PDF hashes in this export are explicitly stored metadata.
Multi-page occurrence attribution remains unresolved. The comparison snapshot and
generated reports are local artifacts, not independently reviewed gold data.

The existing 981-change scientific review queue remains unapproved. This diagnostic
patch adds no new scientific acceptance, and does not establish general precision
or recall. Earlier hash-bound diff reports must be regenerated before using audit
commands that require the current extractor hash.

## Verdict

Occurrence diagnostics implemented; production selection equivalence confirmed
on the current corpus. Do not bulk-refresh persisted facts. Next use the exact
occurrence decisions to review cap omissions and the existing change queue against
PDF sources before proposing selection or schema changes. Stages 2 and 3 remain open.
