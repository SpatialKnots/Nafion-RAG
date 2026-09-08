# Stage 2: candidate-window and neighboring-context experiments

Date: 2026-09-08. Read-only follow-up to required-substance evidence retention.

## Changed

Added reproducible audit scripts for larger retrieval windows and same-article
neighbors. No automatic candidate expansion, context expansion, search setting,
ranking change or adequacy relaxation was enabled.

## Larger-window experiment

Five remaining query/method cases were searched live at top-k 10, 25 and 50.
The existing selected-full-text gate was assessed alongside expected-article gold.

| Case | Method | First required-identity hit | Expected article | Observation |
| --- | --- | --- | --- | --- |
| Dissertation solvent table | semantic | rank 12 | already at rank 1 | top-25 supplies diglyme and passes the gate |
| Kayumov Russian conductivity paper, English query | exact | diglyme absent at top-25 | rank 42 at top-50 | top-50 passes gold and the gate |
| Sanginov EC/SL conductivity, Russian query | semantic | rank 27 | absent through top-50 | gate accepts at top-50 despite failing gold |
| Istomina mixing-temperature/swelling, Russian query | semantic | rank 30 | absent through top-50 | gate accepts at top-50 despite failing gold |
| Istomina mixing-temperature/swelling, Russian query | hybrid | rank 25 | absent through top-50 | gate accepts at top-25 despite failing gold |

The initial top-10 prefix stayed unchanged in all measured larger windows. That
does not make wider evidence scientifically adequate: identity coverage and
expected-source retrieval are distinct checks. An absent gold article alone is
not proof that every alternative source is irrelevant, so source text was inspected
for the neighboring-context experiment below.

## Same-article +/-2 chunk experiment

The 348 frozen selections were checked for missing required identities. Candidate
neighbors were restricted to the same article and text layer, with chunk-index
distance at most two. Only chunks covering a still-missing identity were considered.
Four query/method cases would gain identity coverage:

- semantic dissertation-table query: chunk `d7cb5ab1-5d10-4e02-a5ef-e1d7e1c7b779`,
  pages 109–111, supplies diglyme; its parent is
  `7ecad17d-a7c1-47d6-af2f-bcca3029d328`, pages 105–107.
- semantic Sanginov EC/SL query: the same dissertation table supplies separate
  ethylene-carbonate and sulfolane identities.
- semantic/hybrid Istomina query: dissertation chunk
  `5cd9b368-442d-474f-a171-35725287c6e7`, pages 28–29, supplies both identities.

All these chunks belong to dissertation article
`6f6fca14-92e8-446d-b1cd-ec08ca811962`, original text layer.

Source inspection establishes a useful distinction:

- Pages 109–111 contain the solvent/conductivity table, individual EC and sulfolane
  rows, the diglyme row and abbreviation definitions. These are relevant to the
  solvent-table query. Separate pure-solvent entries alone do not establish the
  behavior of their binary mixture.
- Pages 28–29 discuss lithium transport and conductivity in EC/SL mixtures and
  broader Nafion phase behavior. This inspected fragment does not establish how
  mixing temperature changes swelling in the question attributed to Istomina.

Consequently, limiting expansion to neighboring chunks does not by itself solve
the scientific adequacy problem. This experiment reports identity coverage only;
it is not a claim that four additional answers are validated.

## Tests run

```powershell
.\.venv\Scripts\python.exe -m scripts.stage2_candidate_coverage_audit
.\.venv\Scripts\python.exe -m scripts.stage2_neighbor_coverage_audit
.\.venv\Scripts\python.exe -m ruff check app tests scripts
```

Both audit scripts completed and saved:

- `tmp/stage2_candidate_coverage_audit.json` — 15 live searches, gate metadata,
  expected-source results, source-linked identity hits and prefix comparisons.
- `tmp/stage2_neighbor_coverage_audit.json` — four possible context additions,
  parent/source IDs, pages, layers and covered identities.

The first candidate-audit run completed searches but failed JSON serialization of
an evaluation dataclass. Explicit dataclass encoding was added and the whole audit
rerun successfully. Ruff app/tests/scripts: PASS. Application logic was not changed
after the retention implementation's 387-test run. No external generation was used.

## Limitations

Five deliberately selected failures are not a representative quality benchmark.
Only the identified stored text fragments were inspected; there was no visual PDF
review or independent scientific annotation of every candidate. Gold targets can
omit other valid sources, and identity matches can occur in references or unrelated
conditions. Full source-context correctness requires more than lexical coverage.

## Verdict

Do not enable automatic top-25/50 or neighboring-context expansion based on these
results. Preserve the validated within-window retention patch. The next evaluation
work is to label evidence for the actual relation in each query: separate solvents
versus a binary mixture, conductivity versus swelling, and the effect of mixing
temperature. Candidate recovery should be accepted against those labels, not merely
because all substance names become present.
