# Приоритет 8: расширенная evaluation поиска

## Статус документа

Это подробный технический план для согласования. Описанные schema расширения,
метрики, gold data и regression gates ещё не считаются реализованными.

Этап завершает backend roadmap как quality gate для exact/semantic/hybrid
retrieval. Он не должен менять retrieval scoring сам по себе, кроме случаев,
когда отдельный эксперимент явно согласован.

## 1. Цель

Измерять способность системы находить правильные источники для реальных
научных вопросов, а не только подтверждать, что API возвращает непустой список.

После этапа evaluation должна:

- покрывать русские и английские запросы;
- поддерживать вопросы без ответа;
- оценивать article-level и chunk-level relevance;
- считать Recall@k, Precision@k, MRR, nDCG, latency;
- сравнивать exact/semantic/hybrid на одном corpus snapshot;
- фиксировать manifest/vector generation/config;
- блокировать регрессии качества и трассировки.

## 2. Текущее основание

Сейчас evaluation уже умеет запускать retrieval questions YAML и считать
базовые summary metrics. Корпус имеет tracked manifest, retrieval reports
пишутся в `data/exports`. После приоритета 3 semantic/hybrid зависят от ready
v3 vector generation.

Ограничения текущей evaluation:

- gold set всё ещё мал для строгого качества;
- часть проверок article-level, но chunk-level relevance ограничена;
- вопросы без ответа не являются полноценным first-class case;
- нет nDCG/Precision@k;
- latency не является обязательной метрикой;
- нет regression threshold policy.

## 3. Границы этапа

### Входит

- новая YAML schema evaluation questions;
- backward compatibility со старой schema;
- article-level relevance;
- chunk-level relevance where known;
- unanswerable questions;
- multilingual/paraphrase/numeric/table/caption questions;
- metrics: Recall@k, Precision@k, MRR, nDCG, top-1, empty results, latency;
- comparison report exact vs semantic vs hybrid;
- regression gates;
- docs for gold data rules.

### Не входит

- изменение search scoring;
- LLM judging;
- автоматическая генерация gold labels;
- внешние corpora;
- cloud evaluation;
- ручная полная разметка всех chunks.

## 4. Evaluation schema

Proposed YAML:

```yaml
- id: nafion_solvent_dispersion
  query: "Nafion dilute solvent dispersion"
  language: en
  expected:
    articles:
      - doi: "10.xxxx/example"
        relevance: 3
      - title_contains: "Nafion in Dilute Solvent Systems"
        relevance: 3
    chunks:
      - article_doi: "10.xxxx/example"
        text_contains:
          - "dilute solvent"
          - "dispersion"
        relevance: 3
  filters:
    source_type: null
  answerable: true
  notes: "Evidence exists in indexed chunks."
```

Unanswerable:

```yaml
- id: absent_topic
  query: "Nafion membrane tested on Mars regolith electrolyte"
  answerable: false
  expected:
    articles: []
    chunks: []
```

Rules:

- every answerable question must cite why expected evidence is in corpus;
- DOI preferred when available;
- title/checksum/article id allowed for DOI-less articles;
- chunk expectations use stable text fragments, not local DB UUID only;
- no expected item should depend on generated export paths.

## 5. Metrics

### 5.1. Article-level

- Recall@k: any expected relevant article appears in top-k;
- Precision@k: relevant articles / returned articles up to k;
- MRR: reciprocal rank of first relevant article;
- nDCG@k: graded relevance if labels provide `relevance`;
- top_1_passed;
- missing expected articles.

### 5.2. Chunk-level

- chunk hit if result chunk matches expected chunk id or contains expected text
  fragment in expected article;
- chunk Recall@k;
- evidence trace completeness: article id, chunk id, page range, source type,
  text layer, snippet/PDF links present.

### 5.3. Unanswerable

Unanswerable question success requires:

- zero high-confidence relevant result according to gold labels, or
- explicit report that returned results are non-relevant.

Because retrieval systems always return nearest results, unanswerable metrics
must be reported separately. They should not be counted as ordinary Recall@k.

### 5.4. Latency

Capture:

```text
method
query_id
top_k
elapsed_ms
result_count
vector_generation_id
manifest_sha256
```

## 6. Report format

Output:

```text
data/exports/retrieval_eval_extended_<method>_<timestamp>.json
```

Summary:

```json
{
  "total": 40,
  "answerable": 34,
  "unanswerable": 6,
  "article_recall_at_k": 0.94,
  "article_precision_at_k": 0.42,
  "mrr": 0.71,
  "ndcg_at_k": 0.81,
  "top_1_passed": 24,
  "empty_result_queries": 0,
  "p50_latency_ms": 0,
  "p95_latency_ms": 0
}
```

Include environment:

- corpus manifest checksum;
- vector generation id;
- manifest sha256;
- git commit if available;
- settings relevant to retrieval;
- method;
- top_k;
- filters/grouping mode.

## 7. Regression gates

Define local gate file:

```text
docs/evaluation_thresholds.yaml
```

Example:

```yaml
hybrid:
  min_article_recall_at_10: 0.90
  min_mrr: 0.60
  max_empty_result_queries: 0
semantic:
  min_article_recall_at_10: 0.85
exact:
  min_article_recall_at_10: 0.75
```

Command:

```powershell
python -m app.evaluation.cli retrieval-extended docs/evaluation_questions_extended.yaml --method hybrid --check-thresholds
```

Threshold failures return non-zero and report exact failing metric.

## 8. Gold data expansion

Target minimum:

- 40-60 questions total;
- at least 15 Russian queries;
- at least 10 paraphrases;
- at least 8 method/table/caption/numeric questions;
- at least 5 DOI-less article questions;
- at least 5 unanswerable questions;
- at least 5 broad ambiguity questions.

Categories:

- solution casting and recast Nafion;
- solvent systems: DMF, DMSO, NMP, DMAc, ethanol, water/alcohol;
- conductivity measurement methods;
- Li-Nafion and solvent interactions;
- membrane morphology/toughness;
- Russian theses/articles;
- tables/captions/formulas after priority 6.

## 9. Tests

Required:

- YAML schema validation tests;
- backward compatibility tests with old questions;
- DOI/title/checksum matching tests;
- graded relevance metric tests;
- nDCG/MRR/Precision tests with small fixtures;
- unanswerable question tests;
- threshold pass/fail tests;
- report serialization tests;
- CLI exit code tests.

## 10. Acceptance criteria

Этап готов, если:

- extended evaluation runs for exact, semantic and hybrid;
- report includes corpus/index/config provenance;
- metrics have unit-tested definitions;
- unanswerable questions are reported separately;
- thresholds can fail the command with clear diagnostics;
- gold set is evidence-backed and documented;
- tests, Ruff, mypy pass;
- local smoke comparison produces saved reports for all three methods.

## 11. Rollback

Rollback does not affect corpus or vector indexes. Remove extended evaluation
commands/schema/threshold checks and keep old evaluation CLI. Generated reports
remain local artifacts.
