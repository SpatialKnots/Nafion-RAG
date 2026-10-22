# Query qualifier guard development protocol v0.1

22 October 2026, stage30, `query_qualifiers_v0.1`.

Implement a separate necessary-mention guard after the stage29 observations.
Keep the old production adequacy implementation, thresholds, scoring, selection,
prompt formatting and frozen artifacts unchanged. The guard can be explicitly
injected as an AnswerProvider wrapper; it is not the runtime default. It can only
reject an existing allowance, never upgrade a baseline rejection. No new model
call, corpus edit, database write or scientific record admission is authorized by
this experiment. API/full-page guards of stage29 remain separate and unchanged.

Freeze implementation, tests, this protocol, a versioned constructed reference
fixture, all four prior stage29 contexts, and inherited source/code/PDF/index
bindings before running the real offline comparison. The constructed fixture's
questions and expected necessary-mention decisions are development references
written by the developer, not independent scientific gold or held-out accuracy.
The four inherited questions are exposed regression observations. No questions,
rules, aliases or references may be tuned after comparison.

Finite scope:

- Explicit article surname/year forms: `For NAME YEAR`, `By NAME YEAR`,
  `In the work of NAME YEAR`, `В работе NAME YEAR`, optionally `et al`.
  Check surname/year together in source-bound article metadata, never body text,
  bibliography, filename or inferred title. Missing metadata is unknown and blocks
  that requirement. This snapshot has no author/year metadata captured in stage29;
  do not invent it or silently retrieve changing metadata during offline export.
- Literal material phrases after `containing`, `doped with`, `содержащ…`,
  `с добавкой`, ending at newline or punctuation. Treat the whole captured phrase
  as necessary, without translation, stemming, entity inference or forced category.
  Empty explicit markers remain unresolved. Complex clause tails may over-reject.
- A finite mention catalogue: conductivity, DSC, TGA, EIS and declared RU/EN aliases.
  These are necessary lexical cues, not scientific property equivalence or full
  ontology. Do not hardcode observed author names, years or missing materials.
- Match within raw evidence using token boundaries, token-local NFKC/casefold and
  whitespace/hyphen separators. Preserve exact raw start/end/text. Never join a
  phrase across chunks or sentences. Punctuation is not whitespace normalization.
- Require all recognized mentions within one selected article. No pooling the
  requested author's metadata with another article's method or material. Several
  chunks from the same article may supply mentions; this is not relation proof.
- With no recognized qualifier, preserve the baseline allowance and explicitly
  mark outside finite scope. Unparsed constraints remain unvalidated. Negated,
  hypothetical or cited-work mentions are not established experiments; the guard
  measures mention coverage only and is never sufficient to authorize inference.

Report every case including missing/unknown and baseline refusals. Preserve all
baseline Evidence fields and exact source paths/layers/pages through inherited traces.
Do not regenerate or alter previous packet bytes/scope diagnostics. Do not trim irrelevant evidence or
claim compression, new answers, scientific precision/recall or token savings.

Run constructed tests for positive aliases, article isolation, missing metadata,
references-only matches, word boundaries, split phrases, negation transparency,
input immutability, missing/empty markers, legacy refusal preservation, wrapper
delegation/abstention, frozen drift and deterministic exclusive escaped HTML.
Run full regression, Ruff/mypy, two real offline exports, exact span checks,
source/input hash verification and source/dependency snapshot. HTML includes all
four observed questions and every constructed reference, with search and no
writable forms. Browser acceptance requires actual rendering; static checks alone
do not establish it. Independent quality annotation is separate from Terms use.
