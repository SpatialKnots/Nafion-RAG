# Phase 4 Evidence-Grounded Answers

Date: 2026-08-31

## Implemented Contract

`POST /answer` retrieves source-linked chunks and returns:

- `status`: `answered` or `insufficient_evidence`;
- rendered answer text;
- structured claims;
- citation IDs attached to every claim;
- article, DOI, chunk, page range, source type, and exact returned excerpt;
- retrieval, evidence selection, evidence deduplication, adequacy, and generation metadata.

Unknown citations, uncited claims, empty answerable output, and malformed provider output are rejected rather than returned to the caller.

## Provider

OpenAI is the supported answer provider:

```text
RAG_PROVIDER=openai
RAG_OPENAI_BASE_URL=https://api.openai.com/v1
RAG_OPENAI_API_KEY=<operator-provided-key>
RAG_OPENAI_MODEL=gpt-4.1-mini
RAG_OPENAI_MAX_TOKENS=1200
RAG_TIMEOUT_SECONDS=120
```

Retrieved text is supplied as untrusted evidence. The provider must return structured claims with known evidence IDs. The application validates the returned structure and citation IDs before rendering.

## Evidence Deduplication

Before adequacy assessment and generation, the answer layer removes duplicate or near-duplicate evidence chunks from the same article/title and renumbers citation IDs. This avoids sending repeated neighboring chunks such as overlapping SAXS passages from the same paper as separate evidence items.

## Evaluation

Run structural and gold-target answer evaluation with:

```powershell
python -m app.evaluation.cli answers docs/evaluation_questions.yaml --top-k 5 --method hybrid
```

This evaluation checks target articles, expected keywords, citation coverage, refusals, and provider output structure. It does not independently prove scientific entailment of generated prose.

## Limitations

- OpenAI API availability and key validity are runtime dependencies.
- Citation structure is validated, but semantic entailment of generated prose still requires separate evaluation.
- No external metadata lookup is performed.

## Verdict

The answer API is OpenAI-backed, evidence-grounded, citation-validated, and deduplicates near-identical evidence before generation.
