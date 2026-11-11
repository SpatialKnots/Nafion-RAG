# Query rewriting development experiment v0.1

User explicitly requested implementation and testing of the query rewriting
hypothesis on the existing twenty Satoh/Fan questions. This opens a separate
bounded experiment, not a continuation of any closed allowance. Maximum20 rewrite
model POST+20 answer POST, and one fresh OAuth per POST, overall40 each. Exactly
one attempt per stage/case; no retry, fallback, automatic continuation or prompt
tuning after outputs. GigaChat-2-Max/1200 output tokens/120s per HTTP; cost unknown.

Question-only originals are copied from the existing public export before calls.
No references, page hints, old answers or source texts enter the rewriting model.
The original question and article identity remain fixed. Rewriter returns only
English question, search keywords and requested-information requirements, never
answers. Strict JSON, preserved literal chemical identifiers and numeric
constraints, no new numeric values. Save original native responses and validation
failures; reject invalid rewrites without repair. Agent meaning review is exposed
development review, not independent annotation; review all20 before answer sends.

No default application/runtime files change. An explicit experiment-only adapter
uses the frozen English question/keywords to rank raw chunks of the same uniquely
resolved article and to augment existing evidence selection. Existing top_k5,
source filters, source objects, text layers, deduplication, budgets and output
validators stay. Original author/year resolution is unchanged. Retain first raw
chunk as in baseline ranker. Final model still receives the original Russian
question and raw source chunks, with no rewrite text as evidence.

Adequacy experiment computes the existing lexical/concept thresholds on the
English question, while preserving original required-concept and relation vetoes.
Original adequacy is retained diagnostically. This is a declared experimental
admission policy, not a claim of semantic entailment/complete requirement checking.
Free-text requirements are diagnostic only; no fabricated evidence or LLM-based
scientific acceptance. No change to existing source/fact/fidelity policies.

Freeze code/tests/settings, all20 native rewrite requests and question-only data
before rewrite sends. After all20 results, close rewrite allowance and freeze
valid plans/meaning decisions before preparation. Prepare actual production
service in read-only rollback/fresh processes; record full trace/source/PDF/native
and ablations. Invalid rewrite cases stay in denominator with no answer call.
Answer dispatch only for valid-reviewed preparations that reach native boundary;
if a prepared native request is byte-identical to an already attempted baseline
request, record identical-input reuse and issue no new call or slot. Reuse the
baseline response only during the closed-scope comparison, explicitly labelled;
never reopen/write the old attempt slot. This is not a new model sample.
reprepare through actual ASGI /answer under the explicit adapter, require exact
trace/source/article/native equality before POST, append-only global request slots.
Known provider refusals/HTTP errors remain results; internal/unknown failure stops
remaining dispatch. Close all unused allowance. Never modify baseline artifacts.

Offline ablations: saved baseline; rewritten ranking with original adequacy;
baseline evidence with English adequacy; rewritten ranking plus English adequacy.
These adequacy diagnostics are not full answer runs. No extra LLM ablation calls.
Before baseline input verification, snapshot hashes; baseline manifests remain
immutable even if environment/cache drifts are separately reported. No corpus
ingestion, index rewrite, DB writes, PDF edits, supplement downloads or deployment.

Compare all20 cases against saved baseline after dispatch closes. Record response
availability, raw selected page ranges versus declared reference page locations,
exact source witnesses, preliminary exposed-assistant reference agreement,
rewrite and answer token use/latency separately. Page overlap is not support;
technical answers are not scientific accuracy. Missing supplements/Fan07 pointer
ambiguity stay. This dataset is development-exposed, not independent evaluation.
Overall project progress remains75%. No rollout authorized by the experiment.
