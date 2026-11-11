# Query rewriting v0.2: independently usable translation and verified title

User requested «Выполняй» after the prioritized recommendation to implement
steps1+2 first. Scope: improve rewriting/parser reliability and verified-title
disambiguation; keep v0.1 ranking/English adequacy/answer behavior unchanged to
measure this step. Full retrieval fusion/completeness enforcement remain separate.
No default app rollout, DB/index/PDF changes, new ingestion or deployment.

First replay all20 existing native rewrite responses offline. Only English
question is mandatory. Auxiliary keyword fields are independent: empty entries,
duplicates, invalid types/lengths, invented numbers/identifiers or title-conflicting
chemical classes are ignored with explicit diagnostics. Preserve original raw
responses, perform no semantic replacement or answer repair. The old requirements
field is retained as archival diagnostic during offline replay, not executed.
Missing/incorrect translation, changed locked identifiers/numbers and detected
chemical/operation contradictions still reject. This is a new parser policy,
never a retroactive change to the v0.1 result.

Bind each article's actual scientific title to a unique exact first-page span in
the previously frozen original-PDF text, page-text hash and original PDF hash.
DB titles Satoh2013/Fan2018 are insufficient. Send only verified title, article
identity, original question and locked identifiers to rewriter. No abstract/body,
reference answer, expected value, target page hints or previous model answers.
Global terminology instructions distinguish simple ethers from esters and
post-charge holding/resting from immersion/soaking. Title context disambiguates
only; it may not add findings, entities, conditions or values to the question.

New wire schema: english_question required, keywords optional with at most six
entries requested; no generated requirements. Runtime canonical plan supplies
empty requirements as explicit system metadata, so v0.1 retrieval/admission
adapter remains identical except validated English/keywords. Original source
question stays unchanged for final generation; original required-concept/relation
vetoes, thresholds/top5/filters/source hashes/answer validators remain.

Separate new scope: at most20 rewrite POST+20 answer POST and40 OAuth attempts,
one per stage/case, GigaChat-2-Max/1200 output tokens/120s HTTP. No retry/fallback/
continuation. Freeze all20 requests/code/tests/title contexts before new sends.
All20 cases stay in denominator. Exposed-agent semantic review before answer
preparation; no requirement for per-case user action. Preserve invalid outcomes.
Prepare valid cases read-only/rollback in fresh processes; freeze exact native,
trace/source/article bindings before dispatch. Actual ASGI under explicit adapter
must reproduce bytes. Byte-identical previously attempted native requests reuse
their existing result only after scope closes; no new POST and no old slot write.
Known provider failures remain results; internal/unknown failure stops remaining
dispatch. Close all unused allowances and every new slot after stages finish.

Evaluate v0.2 against original4/20 and v0.1's11/20 saved outcomes, distinguishing
new model samples, identical-input reuse, schema/meaning rejection, model refusal
and technical error. Record exact exported source coverage, preliminary exposed
reference agreement, all token use/latency and cost unknown. Not independent
scientific accuracy; no promise of additional answered/correct cases. Other
source-selection/completeness defects are not silently fixed. Progress remains75%.
