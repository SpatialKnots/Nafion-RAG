# Cross-Lingual Retrieval And Answer Plan

## Status

This document is a design plan, not an implementation record. The current system
must not be described as having solved Russian/English cross-lingual retrieval
or bilingual answer generation until source code, tests, and evaluation reports
prove it.

The motivating failure is confirmed locally: `Диссертация Чернюк С.Д.` is
indexed and is retrieved by Russian diagnostic queries, but it was absent from
the citations for broad English mini-review questions about Li-Nafion
thermodynamics, swelling, solvent parameters, and transport.

## 1. Goal

Remove the practical barrier between English and Russian at both input and
output layers while preserving scientific traceability.

After implementation, a user should be able to:

- ask an English question and retrieve Russian evidence from the dissertation
  and Russian papers;
- ask a Russian question and retrieve English evidence from Sanginov, Istomina,
  Ma, Welch, Kim, Dai, and related papers;
- ask mixed Russian/English scientific questions;
- receive an answer in the requested or detected language;
- inspect citations that preserve original article, page, source type, text
  layer, and original excerpt;
- see diagnostics showing which query variants and languages contributed.

## 2. Current Evidence And Problem

Known corpus facts:

- `Диссертация Чернюк С.Д.` is indexed.
- The dissertation has no DOI and is tracked by title/checksum.
- The dissertation has 159 pages, 151 chunks, and 318 text layers in the current
  manifest.
- Russian queries about Chernyuk, lithium ions, thermodynamics, relaxation, and
  Nafion retrieve the dissertation at rank 1.
- Broad English mini-review questions did not cite the dissertation.

Likely causes:

- exact lexical retrieval does not cross the English/Russian vocabulary gap;
- current semantic model is `BAAI/bge-small-en-v1.5`, which is not a validated
  multilingual retrieval model for Russian/English scientific text;
- `top_k=5` can exclude Russian evidence before the answer provider sees it;
- answer generation only uses retrieved evidence and cannot cite missing
  sources;
- current evidence adequacy uses English-oriented term handling and a small
  manual synonym map.

## 3. Non-Negotiable Constraints

- Original PDFs remain immutable.
- Stored original chunks remain the source of truth.
- Translation must be treated as derived evidence aid, not as a replacement for
  original source text.
- Every answer claim must remain citation-grounded.
- Citations must continue to include article, chunk, page range, source type,
  text layer, and exact original excerpt.
- Query expansion must be visible in metadata and diagnostics.
- No silent broad LLM query rewriting should change the user's scientific
  meaning.
- Do not hide retrieval, translation, embedding, or generation failures with
  broad `try/except`.

## 4. Scope

### In Scope

- cross-lingual evaluation questions;
- bilingual scientific glossary for Nafion/PFSA/Li-Nafion terms;
- query bundle generation from original query plus controlled bilingual terms;
- retrieval diagnostics for query variants;
- multilingual semantic retrieval experiment;
- article-level grouping/reranking for bilingual evidence;
- answer language policy;
- optional translated citation summaries while preserving original excerpts;
- UI/API metadata showing source language and query expansion.

### Out Of Scope For The First Increment

- translating the entire corpus as a new source of truth;
- external metadata lookup;
- changing OCR or original PDF storage;
- changing chunking globally;
- uncontrolled LLM-generated query rewrites;
- promoting a new default retrieval method without evaluation.

## 5. Proposed Architecture

```text
user query
  -> language detection and scientific term extraction
  -> controlled bilingual query bundle
  -> retrieval over original query and bilingual variants
  -> exact + current semantic + multilingual semantic candidates
  -> article grouping and cross-lingual evidence selection
  -> evidence adequacy over bilingual term coverage
  -> answer generation in requested/detected language
  -> citations with original excerpt and optional translated summary
```

## 6. Input Layer

### 6.1 Language Detection

Add a lightweight deterministic detector:

- `ru` if Cyrillic characters dominate;
- `en` if Latin characters dominate;
- `mixed` if both are substantial;
- `unknown` for short or ambiguous queries.

This detector is diagnostic, not a scientific classifier.

Metadata:

```json
{
  "query_language": "en",
  "language_detection": {
    "cyrillic_chars": 0,
    "latin_chars": 212,
    "decision": "en"
  }
}
```

### 6.2 Scientific Term Extraction

Extract normalized scientific terms and phrases, not only whitespace tokens.

Initial controlled phrase set:

```text
swelling
equilibrium swelling
thermodynamic interaction
mixing enthalpy
mixing entropy
Gibbs free energy of mixing
lithium form
Li-Nafion
lithiated Nafion
PFSA ionomer
polar aprotic solvent
donor number
acceptor number
dielectric constant
Hansen solubility parameter
molar volume
viscosity
contact ion pair
ion-pair dissociation
ionic conductivity
lithium-ion transport
single-ion polymer electrolyte
ionic domain
amorphous phase
crystalline phase
dielectric relaxation
segmental dynamics
thermal behavior
plasticizer
electrochemical stability
```

Russian equivalents must be reviewed against corpus text before being used.

## 7. Bilingual Glossary

Add a versioned local glossary, for example:

```text
app/retrieval/cross_lingual_glossary.py
```

or a data file:

```text
docs/cross_lingual_glossary.yaml
```

Recommended initial entries:

```yaml
- concept: swelling
  en: ["swelling", "equilibrium swelling", "sorption"]
  ru: ["набухание", "равновесное набухание", "сорбция"]

- concept: thermodynamic_interaction
  en: ["thermodynamic interaction", "mixing energetics"]
  ru: ["термодинамическое взаимодействие", "термодинамика взаимодействия"]

- concept: mixing_thermodynamics
  en: ["mixing enthalpy", "mixing entropy", "Gibbs free energy of mixing"]
  ru: ["энтальпия смешения", "энтропия смешения", "энергия Гиббса смешения"]

- concept: lithium_form
  en: ["lithium form", "Li-form", "lithiated Nafion", "Li-Nafion"]
  ru: ["литиевая форма", "Li-форма", "литированный Nafion", "Li-Nafion"]

- concept: solvent_parameters
  en: ["donor number", "acceptor number", "dielectric constant", "Hansen solubility parameter", "viscosity", "molar volume"]
  ru: ["донорное число", "акцепторное число", "диэлектрическая проницаемость", "параметр растворимости Хансена", "вязкость", "молярный объем"]

- concept: ion_pairing
  en: ["contact ion pair", "ion-pair formation", "ion-pair dissociation"]
  ru: ["контактная ионная пара", "образование ионных пар", "диссоциация ионных пар"]

- concept: transport
  en: ["ionic conductivity", "lithium-ion transport", "single-ion conductor"]
  ru: ["ионная проводимость", "литий-ионный транспорт", "одноионный проводник"]

- concept: morphology_dynamics
  en: ["ionic domain", "amorphous phase", "crystalline phase", "dielectric relaxation", "segmental dynamics", "thermal behavior"]
  ru: ["ионные домены", "аморфная фаза", "кристаллическая фаза", "диэлектрическая релаксация", "сегментальная подвижность", "термическое поведение"]
```

Rules:

- glossary entries are curated, not LLM-generated at runtime;
- every new entry should be justified by corpus vocabulary or user-approved
  terminology;
- expansion metadata must list matched concepts and emitted query variants.

## 8. Query Bundle Retrieval

For each user query, build a `QueryBundle`:

```python
QueryBundle(
    original="...",
    language="en",
    variants=[
        QueryVariant(text="original query", language="en", source="original"),
        QueryVariant(text="термодинамика взаимодействия набухание Li-Nafion", language="ru", source="glossary"),
        QueryVariant(text="литиевая форма Nafion энтальпия смешения", language="ru", source="glossary"),
    ],
    concepts=["swelling", "thermodynamic_interaction", "lithium_form"],
)
```

Retrieval should run over variants and merge candidates. Initial safe method:

- run current `search_chunks` for original query;
- run exact search for each glossary variant;
- optionally run semantic search for original query;
- later add multilingual semantic search;
- merge by chunk id with method/variant diagnostics;
- group by article before answer evidence selection.

Diagnostics:

```json
{
  "cross_lingual": {
    "enabled": true,
    "query_language": "en",
    "matched_concepts": ["swelling", "lithium_form"],
    "variants": [
      {"text": "...", "language": "en", "source": "original"},
      {"text": "...", "language": "ru", "source": "glossary"}
    ],
    "variant_hits": [
      {"variant_index": 0, "result_count": 5},
      {"variant_index": 1, "result_count": 7}
    ]
  }
}
```

## 9. Multilingual Semantic Retrieval

Current semantic model should not be assumed adequate for cross-lingual
retrieval. Evaluate a multilingual embedding model behind an explicit method or
index generation.

Candidate models:

- `BAAI/bge-m3`;
- `intfloat/multilingual-e5-base` or a size suitable for local runtime;
- `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`.

Acceptance requirements:

- index manifest records model name, dimension, corpus checksum, and build
  command;
- exact retrieval remains available;
- current English semantic index is not overwritten without a migration plan;
- generated vector indexes remain rebuildable artifacts under ignored data
  paths.

Recommended method names:

```text
semantic_multilingual
hybrid_cross_lingual
```

Do not change the default method until evaluation shows benefit.

## 10. Article Grouping And Selection

Cross-lingual answer quality should rank evidence at article level before
selecting chunks for the provider.

Reason:

- a dissertation may contribute many relevant Russian chunks, but each single
  chunk may rank below English chunks;
- broad English queries need source diversity across dissertation, Russian
  papers, and English papers;
- top-5 chunk-only retrieval can hide the strongest article-level source.

Proposed selection signals:

- number of matched bilingual concepts per article;
- best chunk rank per variant;
- number of variants that found the article;
- source diversity limit, for example max 2 chunks per article before provider;
- exact term hits for high-value scientific phrases;
- semantic score where available.

Metadata should show why an article was selected.

## 11. Evidence Adequacy

Current adequacy checks should become concept-aware.

Instead of only:

```text
distinctive terms matched in text
```

add:

```text
concepts matched by original or translated equivalents
language coverage
article coverage
missing high-value concepts
```

Example:

```json
{
  "concept_coverage": {
    "matched": ["swelling", "lithium_form", "mixing_thermodynamics"],
    "missing": ["segmental_dynamics"]
  },
  "language_coverage": {
    "en_evidence_count": 3,
    "ru_evidence_count": 2
  }
}
```

## 12. Output Layer

### 12.1 Answer Language Policy

Add an explicit parameter eventually:

```text
answer_language=auto|en|ru
```

Initial behavior:

- `auto`: answer in the dominant language of the user question;
- `en`: answer in English even when citing Russian evidence;
- `ru`: answer in Russian even when citing English evidence.

### 12.2 Citations

Keep original evidence excerpt as the primary citation text.

Optional derived fields:

```json
{
  "original_text": "...",
  "original_language": "ru",
  "translated_excerpt": "...",
  "translation_provider": "configured-provider",
  "translation_status": "translated"
}
```

Rules:

- translated excerpt is for readability only;
- claim grounding is still checked against original evidence where possible;
- translation failures should not remove the citation;
- UI should clearly label original vs translated text.

### 12.3 Mini-Review Behavior

For broad questions, mini-review should be grouped by work/article:

```text
Chernyuk dissertation: ...
Chernyuk 2023/2024 papers: ...
Sanginov/Istomina: ...
Ma/Welch/Kim/Dai: ...
```

This prevents English articles from occupying all answer space when Russian
sources are highly relevant.

## 13. Evaluation Plan

Create a dedicated cross-lingual evaluation file:

```text
docs/evaluation_questions_cross_lingual.yaml
```

Required categories:

1. English query must find Russian dissertation.
2. Russian query must find English article.
3. Mixed Russian/English query must find both.
4. English query about thermodynamics must find `Диссертация Чернюк С.Д.` and
   `Чернюк 2023`.
5. English query about Li-Nafion solvent parameters must find Sanginov and
   dissertation if relevant evidence exists.
6. Russian query about EC/SL Li-Nafion conductivity must find Sanginov/Istomina.
7. Broad mini-review query must include at least one Russian and one English
   source when both are relevant.

Example gold items:

```yaml
- id: xling_en_dissertation_lithium_thermodynamics
  query: "How do lithium ions affect thermodynamic and relaxation properties of Nafion membranes?"
  expected_article_titles:
    - "Диссертация Чернюк С.Д."
  expected_keywords:
    - "Li"
    - "термодинами"
    - "релакса"

- id: xling_ru_sanginov_ec_sl_conductivity
  query: "Как смесь этиленкарбоната и сульфолана влияет на проводимость Li-Nafion?"
  expected_article_dois:
    - "10.1016/j.electacta.2021.137914"
  expected_keywords:
    - "EC"
    - "SL"
    - "conductivity"
```

Metrics:

- top-k pass;
- top-1 pass;
- MRR for expected article;
- cross-language recall@k;
- source-language diversity;
- missing expected Russian sources;
- missing expected English sources;
- answer citation coverage;
- answer-language correctness.

## 14. Implementation Phases

### Phase A: Baseline And Evaluation

Deliverables:

- `docs/evaluation_questions_cross_lingual.yaml`;
- current baseline reports for `exact`, `semantic`, `hybrid`;
- answer eval report for the five broad mini-review questions.

Acceptance:

- failures are documented;
- dissertation omission is reproduced by automated evaluation.

### Phase B: Glossary-Based Query Bundle

Deliverables:

- curated bilingual glossary;
- query language detector;
- query bundle builder;
- retrieval method or option that searches glossary variants;
- diagnostics in metadata.

Acceptance:

- English queries can retrieve `Диссертация Чернюк С.Д.` without requiring the
  user to type Russian;
- Russian queries can retrieve English papers without requiring English terms;
- exact/current retrieval remains unchanged when cross-lingual mode is off.

### Phase C: Article-Level Cross-Lingual Selection

Deliverables:

- article grouping/reranking for cross-lingual candidates;
- per-article concept coverage diagnostics;
- source diversity controls for answer evidence.

Acceptance:

- broad mini-review evidence includes relevant Russian and English articles;
- no article is selected without source-traceable matched evidence.

### Phase D: Multilingual Embedding Experiment

Deliverables:

- selected multilingual model;
- rebuilt multilingual index;
- method-specific evaluation reports;
- comparison against glossary-only mode.

Acceptance:

- measurable improvement in cross-language recall/MRR;
- no unacceptable regression against existing English/Russian exact baselines;
- model and index manifest are reproducible.

### Phase E: Bilingual Answer Output

Deliverables:

- `answer_language` policy;
- citation language metadata;
- optional translated excerpt/summary fields;
- UI/API rendering for original and translated citation text.

Acceptance:

- answer language follows user request or auto-detection;
- original evidence remains visible;
- generated claims cite original source ids.

## 15. Tests

Required tests:

- language detector for English, Russian, mixed, and ambiguous inputs;
- glossary concept matching;
- query bundle construction;
- no duplicate query variants;
- cross-lingual retrieval metadata serialization;
- article grouping preserves best page/source diagnostics;
- answer evidence selection includes Russian dissertation for English gold
  queries;
- Russian answer can cite English evidence;
- translated excerpt failures do not remove citations;
- existing exact/hybrid tests remain unchanged unless explicitly extended.

## 16. Operational Checks

Before accepting implementation:

```powershell
.\.venv\Scripts\python.exe -m app.ingestion.cli corpus-manifest --check docs\corpus_manifest.json
.\.venv\Scripts\python.exe -m app.evaluation.cli retrieval docs\evaluation_questions.yaml --top-k 10 --method hybrid
.\.venv\Scripts\python.exe -m app.evaluation.cli retrieval-extended docs\evaluation_questions_cross_lingual.yaml --top-k 10 --method hybrid_cross_lingual
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy app
```

If an external provider is used for translation or answer generation, record:

- provider;
- model;
- temperature/settings;
- whether network execution was required;
- failures and retries.

## 17. Risks

- curated glossary may overfit to current corpus;
- translation can blur scientific terms or units;
- multilingual embeddings may improve recall but reduce precision;
- broad English questions may retrieve Russian text that is topically related
  but not directly answer-bearing;
- source diversity limits can force weak evidence into an answer if not guarded
  by adequacy checks;
- evaluation keywords can fail due to ligatures or translation variants.

Mitigations:

- keep original exact and hybrid methods selectable;
- report query variants and matched concepts;
- evaluate article-level targets, not only answer text keywords;
- require original excerpts in citations;
- add failure examples to eval rather than hiding them.

## 18. Rollback

Rollback must not require re-ingestion.

Required rollback paths:

- disable cross-lingual query expansion by method/setting;
- fall back to current `hybrid`;
- delete generated multilingual indexes under `data/processed/vector_indexes`;
- keep glossary as documentation if it is not harmful;
- keep cross-lingual eval reports as diagnostic artifacts.

## Verdict

The next safe implementation step is Phase A plus Phase B: add a cross-lingual
evaluation file, then implement glossary-based query bundles behind an explicit
mode. Multilingual embeddings and translated citation output should follow only
after the glossary baseline proves the dissertation and Russian papers can be
retrieved reliably from English questions without weakening source
traceability.
