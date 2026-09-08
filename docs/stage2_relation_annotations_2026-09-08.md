# Stage 2: source-verified relation annotations, 2026-09-08

## Changed

Added `docs/evidence_relation_cases.yaml` and the read-only evaluator
`app/evaluation/evidence_relations.py`, exposed as `evidence-relations`.
Production retrieval, evidence selection and adequacy rules are unchanged by this
step. Wider candidate windows and neighboring context remain disabled.

The dataset contains nine scientific cases (four sufficient, five insufficient),
each in Russian and English. Both lexical and cross-lingual-concept adequacy modes
are assessed: 36 decisions, not 36 independent scientific questions.

Annotations were prepared by the assistant after text inspection and visual review
of original PDF pages: Sanginov 2021, pages 9–10; Istomina 2021, pages 6–7;
Чернюк dissertation, pages 28–29 and 109–111. Original PDF paths, full SHA-256
checksums, DOI, page, text layer, exact Unicode offset, exact quote and quote hash
are recorded in the dataset or verified report. Original PDFs were not edited.

The 11 selected fragments distinguish:

- Conductivity versus EC/SL composition, supported by Sanginov and Istomina.
- Separate-solvent table rows versus a measured mixture composition series.
- Background transport discussion versus measured composition dependence.
- Heating/cooling solvent uptake and hysteresis, supported by Istomina.
- A statement that equilibrium swelling temperature effects are outside scope
  versus actual measurements of those effects (Sanginov).
- Conductivity measured while mixing temperature is fixed versus swelling as
  mixing temperature changes, even within the same Istomina page.
- A diglyme conductivity table row with its units, conditions and abbreviations.

An `insufficient` annotation means that the selected fragment bundle does not
support the requested relation. It does not mean that the entire article or corpus
lacks an answer, nor that the requested relation is scientifically false.

## Reproduction

From the repository root, with the local database available:

```powershell
.\.venv\Scripts\python.exe -m app.evaluation.cli evidence-relations --output data/exports/evidence_relation_eval_20260908.json --check
```

Omitting `--output` creates a timestamped report under the configured data root.
The report is written before an exit status is returned. Missing or changed PDFs,
DOIs, page layers, offsets or quote hashes fail integrity checking. Invalid-source
decisions are excluded from accuracy denominators and reported explicitly.
`--check` additionally exits 1 for disagreement with annotations; ordinary audit
mode records disagreements without failing. Unexpected I/O and database failures
propagate. This command does not invoke retrieval or an external generation provider.

## Tests run

- Full pytest: **403 passed**, one existing Starlette/httpx deprecation warning.
- Scoped Ruff (`app tests scripts`): passed.
- Mypy (`app`): passed, 70 source files.
- Live annotation evaluation: 11 verified fragments, zero integrity errors,
  all 36 decisions evaluated. `--check` returned **1**, as expected for the
  observed disagreements; this is not a successful adequacy acceptance run.

| Mode | True accepts | True refusals | False accepts | False refusals | Agreement |
| --- | ---: | ---: | ---: | ---: | ---: |
| lexical | 3 | 10 | 0 | 5 | 13/18 |
| cross_lingual_concepts | 8 | 2 | 8 | 0 | 10/18 |
| Combined | 11 | 12 | 8 | 5 | 23/36 |

Tests cover annotation references, duplicate YAML keys, invalid labels, offset and
hash drift, missing/modified originals, invalid-source denominators, confusion
metrics, independence of predictions from labels, and CLI report/exit behavior.

## Limitations

Small, deliberately difficult diagnostic set; assistant-reviewed annotations await
independent scientific review. Results describe exact annotated page fragments,
not naturally retrieved chunk bundles, generated answers, or corpus-wide quality.
Containing chunk identifiers are traceability aids; empty lists are possible when
a selected quote spans chunk boundaries. Metrics across modes/languages are
correlated. No production relation-validation rule has been introduced.

## Verdict

The reproducible evaluation is implemented. Scientific adequacy acceptance fails:
cross-lingual concept coverage admits evidence about the wrong relation, while
lexical matching rejects some sufficient evidence. The next implementation must
address relation support and measure both false accepts and false refusals against
reviewed examples; expanding candidate windows alone is not justified.
