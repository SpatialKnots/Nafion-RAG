# Separate-set acceptance protocol

Status: awaiting the user's separate questions and references. The user explicitly
chose to provide that set. No cases, references, labels or scientific scores have
been invented. No new model budget is opened by creating this protocol.

1. Freeze the completed candidate code, resources, configuration and checks before
   opening the new set for development. Record the candidate version ID and all
   original PDF identities. Do not tune code, prompts or ranking on the new cases
   during this pass. If tuning becomes necessary, close the pass and classify the
   exposed cases as development data; a later independent pass needs another set.
2. Preserve the supplied questions/references verbatim. Record authorship, method,
   LLM assistance, expert verification and preparation time as declarations, with
   unknowns left unknown. Disclose any prior topic/source/prediction exposure. A
   different file name alone does not establish independence.
3. Commit hashes of questions and private references before any new prediction.
   The inference worker receives only the original question and explicitly
   authorized article context. References, answer rubrics and source-page hints
   stay outside its input tree and native prompt. If the implementation assistant
   has already seen them, record that exposure rather than claim blinded review.
4. Prepare the real route with read-only DB/rollback and stop before transport.
   Preserve the unmodified question, exact selected raw evidence, source registry,
   admission/refusal reason and complete native bytes. Do not rewrite a refused
   question or change filters to make it pass. Separate production refusals,
   article-scope stops, missing sources and harness failures.
5. Only after concrete inputs are reviewable, declare a new bounded live scope:
   case IDs, model, attempts, token/time/request-size limits, no automatic retry,
   costs known or unknown, and closure behavior. Obtain authorization for that
   scope; older closed allowances cannot be reused. This protocol has no send mode.
6. Preserve native model output and delivered API output separately. Close all
   allowances, including unsent and unknown reserved attempts, before opening
   references for scoring. Keep transport/schema failures separate from scientific
   assessment. Reproduce delivered API results offline from saved native bytes.
7. Evaluate each requested item against its cited source and the frozen reference:
   object/sample identity, all requested members, numerical value/unit/basis,
   concentration and conditions, chemical names, negation/modal status, experimental
   versus interpreted result, and support for causal/universal statements. Unknown
   information must remain unknown. A source-backed refusal may be appropriate;
   an absent excerpt is not proof of absence in the literature.
8. Report availability and protocol compliance for the full registered denominator.
   Keep scientific judgments per case with source witnesses and reviewer provenance.
   Do not turn HTTP200, exact citation or F-ID compliance into scientific accuracy.
   Numeric scientific aggregation/acceptance thresholds remain unspecified until
   independently agreed and frozen before predictions; no arbitrary score is used.

Reference annotation and independent review are evaluation activities, not a
compulsory per-document or per-Term product workflow. Ordinary users do not have
to resolve algorithmic categories manually. Existing project plan remains75% until
the independent stage's actual evidence justifies a status change.

Templates below are empty intake structures only. The actual incoming format can
be adapted without altering the supplied question/reference text or their hashes.
