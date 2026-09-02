# ARIADNE Project Context And Cross-Lingual Query Problem

Date: 2026-08-27

This brief is intended for consultation with another LLM. It summarizes the
project, the current implementation state, and the remaining problem around
understanding Russian, English, and mixed scientific queries.

## 1. Project Summary

ARIADNE is a local-first scientific literature ingestion, retrieval, and
answering system for Nafion/PFSA and related battery literature.

The system ingests PDF files, extracts text/OCR layers, chunks source text,
stores source-preserving evidence, retrieves relevant chunks, and generates
evidence-grounded answers with citations.

Core project constraints:

- Original PDFs must remain immutable.
- Original extracted chunks remain the source of truth.
- Every answer claim must be grounded in retrieved evidence.
- Citations must preserve article, PDF/page, chunk, source type, text layer,
  and original excerpt.
- Do not silently rewrite scientific queries in a way that changes meaning.
- Do not claim semantic search, multilingual retrieval, or answer generation
  behavior unless it is verified in source code and tests.

Current repository path:

```text
D:\Nafion-RAG
```

## 2. Current Pipeline

Current high-level flow:

```text
PDF corpus
  -> ingestion and immutable PDF storage
  -> text extraction / OCR layer selection
  -> deterministic chunking with page ranges
  -> database storage
  -> retrieval: exact, semantic, hybrid, hybrid_cross_lingual
  -> answer evidence selection
  -> evidence adequacy gate
  -> answer provider
  -> citations with source traceability
```

Important files:

```text
app/retrieval/search.py
app/retrieval/cross_lingual.py
app/generation/service.py
app/generation/evidence_selection.py
app/generation/evidence_adequacy.py
app/evaluation/retrieval.py
docs/evaluation_questions_cross_lingual.yaml
tests/unit/test_cross_lingual_retrieval.py
tests/unit/test_generation.py
```

## 3. Corpus Facts Relevant To The Problem

The corpus contains both Russian and English scientific sources.

Known relevant Russian sources:

- `Диссертация Чернюк С.Д.`
- `Чернюк 2023`
- `Чернюк 2024`
- other Russian Nafion/PFSA papers

Known relevant English sources:

- Sanginov 2021, DOI `10.1016/j.electacta.2021.137914`
- Istomina 2021, DOI `10.3390/polym13071150`
- Ma 2009
- Welch
- Kim
- Dai

The motivating failure was:

- Russian diagnostic queries could retrieve `Диссертация Чернюк С.Д.`.
- Broad English mini-review questions about Li-Nafion thermodynamics, swelling,
  solvent parameters, and transport did not cite the Russian dissertation.

This showed a practical language barrier:

- English queries missed Russian evidence.
- Russian queries could miss English evidence.
- Mixed Russian/English scientific queries were brittle.

## 4. Current Cross-Lingual Implementation

A first cross-lingual retrieval increment has been implemented but is not yet
committed.

Implemented method:

```text
hybrid_cross_lingual
```

Concrete retrieval method name:

```text
hybrid_cross_lingual_rrf
```

It works by:

1. Detecting query language deterministically:
   - `ru`
   - `en`
   - `mixed`
   - `unknown`
2. Matching curated scientific concepts from a local bilingual glossary.
3. Building visible query variants from the original query plus controlled
   bilingual glossary terms.
4. Running hybrid retrieval for the original query.
5. Running exact retrieval for glossary variants.
6. Merging candidates with reciprocal rank fusion.
7. Reranking/diversifying results at article level.
8. Exposing diagnostics in retrieval metadata.

Example metadata shape:

```json
{
  "cross_lingual": {
    "enabled": true,
    "query_language": "en",
    "matched_concepts": ["thermodynamic_interaction", "lithium_form"],
    "variants": [
      {
        "text": "How do lithium ions affect thermodynamic properties of Nafion?",
        "language": "en",
        "source": "original"
      },
      {
        "text": "термодинамическое взаимодействие ионы лития литиевая форма",
        "language": "ru",
        "source": "glossary"
      }
    ],
    "variant_hits": [
      {"variant_index": 0, "result_count": 20},
      {"variant_index": 1, "result_count": 20}
    ]
  }
}
```

Current glossary concepts include:

- swelling
- thermodynamic_interaction
- mixing_thermodynamics
- lithium_form
- solvent_parameters
- ion_pairing
- transport
- morphology_dynamics
- plasticizers

This is controlled query expansion, not full translation and not LLM rewriting.

## 5. Current Test Evidence

Full unit test suite:

```text
.\.venv\Scripts\python.exe -m pytest -q
234 passed
```

Targeted lint on changed Python files:

```text
.\.venv\Scripts\python.exe -m ruff check <changed files>
All checks passed
```

Cross-lingual retrieval evaluation:

```text
.\.venv\Scripts\python.exe -m app.evaluation.cli retrieval docs\evaluation_questions_cross_lingual.yaml --top-k 10 --method hybrid_cross_lingual
```

Latest summary:

```json
{
  "total": 6,
  "passed": 6,
  "top_1_passed": 2,
  "failed": 0,
  "recall_at_k": 1.0,
  "mean_rank": 3.0,
  "empty_result_queries": 0
}
```

Report path:

```text
data\exports\retrieval_eval_hybrid_cross_lingual_20260827T040852Z.json
```

Interpretation:

- The first increment can find expected Russian/English sources within top 10.
- It does not yet reliably rank expected cross-lingual sources at top 1.
- This is useful but not a complete solution to query understanding.

## 6. The Current Problem

The remaining problem is not just "translation". It is scientific query
understanding across Russian and English.

Examples:

English query:

```text
How do lithium ions affect thermodynamic and relaxation properties of Nafion membranes?
```

Relevant Russian evidence may use terms like:

```text
ионы лития
термодинамическое взаимодействие
релаксационные свойства
набухание
энергия Гиббса смешения
```

Russian query:

```text
Как смесь этиленкарбоната и сульфолана влияет на ионную проводимость Li-Nafion?
```

Relevant English evidence may use terms like:

```text
ethylene carbonate
sulfolane
EC/SL
ionic conductivity
Li-Nafion
single-ion lithium conductivity
```

Mixed query:

```text
Какие donor number dielectric constant вязкость molar volume контролируют swelling Li-Nafion?
```

Relevant evidence can contain a mixture of Russian and English terminology,
abbreviations, transliterations, and morphology-dependent variants.

The hard parts:

- Russian inflection: `ионная проводимость` vs `ионную проводимость`.
- Scientific synonyms: `Li-Nafion`, `lithium form`, `lithiated Nafion`,
  `замещение H+ на Li+`.
- Abbreviations: `ethylene carbonate` vs `EC`, `sulfolane` vs `SL`.
- Corpus-specific vocabulary: the same concept may be expressed differently
  across dissertation text, Russian papers, and English articles.
- Retrieval ranking: relevant cross-language evidence may be found but ranked
  below same-language or lexically easier chunks.
- Answer evidence selection: even when retrieval finds the right article, the
  answer provider can miss it if only the first few chunks are passed forward.
- Evidence adequacy: term coverage must not become too permissive and allow
  unsupported answers.

## 7. Why A Naive LLM Rewrite Is Risky

The project intentionally avoids silent broad LLM query rewriting.

Reason:

- In scientific retrieval, a rewrite may alter the user's intended compound,
  mechanism, solvent, ion form, temperature condition, or experimental scope.
- If a generated synonym is wrong, retrieval may become confidently misleading.
- The system must show query expansion diagnostics so the user can audit what
  terms were added.

Acceptable derived aids:

- curated bilingual glossary entries;
- explicit query variants in metadata;
- optional user-visible query suggestions;
- future translated citation summaries clearly marked as derived.

Not acceptable without safeguards:

- hidden LLM rewriting of user queries;
- replacing original source excerpts with translations as evidence;
- claiming a source supports a statement only because a translation paraphrase
  appears to match.

## 8. What Needs Advice

Please advise on a robust design for Russian/English scientific query
understanding in this evidence-grounded RAG system.

Specific questions:

1. How should the system represent scientific concepts so that English,
   Russian, mixed-language, abbreviations, and inflected Russian forms map to
   the same concept without overmatching?
2. Should the glossary stay in Python source, move to YAML, or become a small
   versioned ontology with concept IDs, terms, languages, aliases, and evidence
   notes?
3. What is the safest way to handle Russian morphology: curated variants,
   stemming/lemmatization, character n-grams, PostgreSQL full-text configs, or
   a multilingual embedding model?
4. How should retrieval combine:
   - exact lexical search,
   - current semantic search,
   - curated glossary variants,
   - future multilingual embeddings?
5. How should article-level reranking score source relevance so that a Russian
   dissertation or paper is not buried by English snippets, while weak Russian
   evidence is not forced into answers?
6. What diagnostics should be exposed to the user to make cross-lingual query
   expansion scientifically auditable?
7. Should answer generation receive original excerpts only, original plus
   translated summaries, or concept-labeled evidence bundles?
8. How should evidence adequacy be made concept-aware while avoiding false
   positives from overly broad synonyms?
9. What evaluation set and metrics would best prove that the language barrier
   is actually reduced?
10. What rollback/fallback strategy should exist if multilingual embeddings or
    translation make precision worse?

## 9. Current Recommended Direction

The current safest direction is:

1. Keep `hybrid_cross_lingual` explicit and separate from default `hybrid`.
2. Move the glossary toward a versioned, reviewable data file or ontology.
3. Add concept IDs and diagnostics for matched concepts and missing concepts.
4. Improve Russian morphology carefully, with tests for each added behavior.
5. Add multilingual embedding evaluation as a separate method/index, not as a
   silent replacement for the current vector index.
6. Add article-level/source-diverse reranking before answer generation.
7. Add optional translated citation summaries only as derived readability aids.
8. Keep original excerpts as the primary cited evidence.

## 10. Current Worktree State

As of this brief, the cross-lingual implementation is present in the working
tree but not committed.

Relevant uncommitted files:

```text
M  app/evaluation/retrieval.py
M  app/generation/evidence_adequacy.py
M  app/generation/service.py
M  app/retrieval/search.py
M  tests/unit/test_generation.py
?? app/generation/evidence_selection.py
?? app/retrieval/cross_lingual.py
?? docs/cross_lingual_retrieval_answer_plan.md
?? docs/evaluation_questions_cross_lingual.yaml
?? tests/unit/test_cross_lingual_retrieval.py
```

Local service logs are also untracked and should normally not be committed:

```text
?? server.err.log
?? server.out.log
```
