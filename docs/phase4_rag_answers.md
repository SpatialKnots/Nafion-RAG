# Phase 4 Evidence-Grounded Answers

Date: 2026-08-04

## Implemented Contract

`POST /answer` retrieves source-linked chunks and returns:

- `status`: `answered` or `insufficient_evidence`;
- rendered answer text;
- structured claims;
- citation IDs attached to every claim;
- article, DOI, chunk, page range, source type, and exact returned excerpt;
- retrieval and generation metadata.

Unknown citations, uncited claims, empty answerable output, and malformed provider output are rejected rather than returned to the caller.

## Providers

`extractive` is the verified default. It copies retrieved snippets into claims, so each claim is exactly present in its cited evidence. It is an evidence presentation mode, not synthesized scientific prose.

`ollama` is implemented as an optional structured-output provider. No Ollama executable, running model service, or configured model was found in the local environment during this gate. Therefore Ollama generation is not reported as runtime-verified.

## Evaluation

Configuration:

- retrieval: `hybrid_rrf`;
- `top_k`: 5;
- provider: `extractive`;
- questions: 24.

Result from `data/exports/answer_eval_20260804T053433Z.json`:

| Metric | Result |
| --- | ---: |
| Gold-target PASS | 22/24 |
| Answered | 24/24 |
| Refused | 0/24 |
| Claims | 120 |
| Citation coverage | 1.0 |
| Claims exactly equal to cited excerpts | 120/120 |

Failures:

- `q19_chernyuk_2024_enthalpy_solutions`: the target article/checksum and expected alcohol term were absent from the first five answer citations;
- `q23_welch_broad_sans_morphology_2012`: `morphology` was absent from the first five answer excerpts.

These are evidence-selection failures at `top_k=5`, not missing or invalid citations.

## Limitations

- Citation structure is validated, but semantic entailment of future generated prose is not yet independently verified.
- The current refusal rule is structural: no retrieved evidence or provider-declared insufficiency. Semantic retrieval normally returns candidates, so refusal behavior needs a dedicated evidence-adequacy policy before generated prose is promoted.
- No local generative runtime was available for an end-to-end Ollama evaluation.
- This phase does not add conversational history or external metadata.

## Verdict

The answer API and fully traceable extractive mode are operational. Optional Ollama integration is implemented but remains unverified in this environment. Generated scientific prose must not be described as validated until a model is installed and a separate entailment/refusal evaluation is completed.
