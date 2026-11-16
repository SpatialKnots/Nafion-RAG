# ARIADNE: scientific answer display and source context

2026-11-16, Asia/Yekaterinburg. User supplied a screenshot of the current web
pipeline answering `Li-Nafion conductivity in EC`, then requested the three
proposed display/context fixes. No new live model calls were authorized or made.

Changed:

- Added a local, escaped, bounded scientific-text renderer. It supports ordinary
  inline/display LaTeX delimiters, multiplication, numeric powers, subscripts,
  common Greek symbols, upright units and simple fractions. No external script,
  CDN, model or rendering service. Unknown commands, malformed groups, excessive
  nesting and control characters remain visibly escaped as unparsed markup.
  It never guesses a missing backslash, changes a value or converts a unit.
- Both answer text and claim text use this renderer; citation links remain
  readable. A separate disclosure preserves the exact answer before formatting.
  Native model results, API data and generation/scientific logic are unchanged.
- Source cards select an exact contiguous slice of the request-local text using
  literal number/term matches for the first cited claim. Common display words
  are excluded, sentence ends limit the quote, and one preceding sentence is
  retained when it fits the 1100-character display budget. This keeps nearby
  composition/conditions without claiming to establish their owner or meaning.
  This display-only budget does not change retrieval/context/model budgets.
- Each card retains its full exact context and provenance. Claim disclosures
  link to that context instead of duplicating it. Wrong-request source identity
  never supplies the preview or composition notice. No outside source is fetched
  at rendering time or inserted into the original evidence.
- A finite composition notice appears when a question names one catalogued
  component but both the answer and cited model context explicitly mention a
  recognised solvent pair with a mixture cue. In this case: EC versus EC/SL.
  It warns that mixture data do not establish pure-EC properties. It is not a
  general chemical identity/purity/scope checker and does not change delivery.
- The answer card explicitly distinguishes an obtained answer from scientific
  correctness/completeness. The generation prompt, parser, schemas, thresholds,
  numerical data, PDF extraction, corpus, index and DB remain unchanged.

Tests run:

- `tmp/answer_display_v04.xml`: **105 passed**, no failures/errors/skips, one
  existing Starlette/httpx deprecation warning. Includes **26 new controls**
  plus existing presentation, UI and full current-pipeline controls. Covers
  local math/XSS/unknown markup, exact slices past the old prefix, raw-data
  preservation, EC/SL notice boundaries, unavailable/wrong source identity,
  linked citations, source deduplication and the actual Sanginov page text.
- Ruff app/new tests passed; mypy **233 app files** passed; `git diff --check`
  passed with Windows line-ending notices. No fresh full-suite run claimed.
- Original Sanginov main PDF checksum verified against its registered SHA;
  physical pages 12–13 freshly extracted in the preceding screenshot diagnosis.
  Conclusion on PDF12 contains 6.3×10^-6 to 6.9×10^-4 S/cm at -40…+80°C for
  EC/SL containing 40 wt.% sulfolane, and ~10^-9 S/cm electronic contribution.
  Exact extracted witness and page/PDF hashes remain in
  `output/current_answer_screenshot_20261116/`.
- Browser verification of the constructed local HTML via computer-use: powers,
  units, readable links, EC/SL notice and original-answer disclosure displayed.
  Final v03 DOM confirmed a compact exact quote beginning with the best-sample
  conditions, including EC/SL, 40 wt.% and both conductivity values. The final
  refinement was inspected in DOM; earlier v02 formula/notice screenshots were
  viewed. Desktop viewport was not overridden. No visual-scientific acceptance.
- Server restarted on 127.0.0.1:8000. GET current page **HTTP200** with updated
  math/scope styles. No live question POST, real model/OAuth **0/0**.

Review artifact:

- `output/answer_display_20261116/review_v03/review.html`, also served locally at
  `http://127.0.0.1:8789/review_v03/review.html`.
- It is explicitly a **constructed display control**, transcribed from the
  screenshot with explicit LaTeX commands and the separately re-extracted PDF
  text. It is not the original native response, not an exact replay and not a
  new model answer. The actual request's raw response/chunk ID were unavailable;
  the control has no fabricated chunk-context links. Existing article/PDF links
  use the registered article. Input/HTML/source/code hashes are recorded.

Diagnostics retained:

- Initial run: 100pass/5fail. New controls exposed a math-input classification
  edge, overly long context/number-boundary issues, and two existing tests caught
  duplicate source disclosures. Fixed without changing scientific rules.
- Intermediate refinement: 104pass/1fail. An actual-page control caught a short
  quote beginning with `Its conductivity` and losing the adjacent 40 wt.% sample
  condition. Added preceding-sentence retention; final 105 passed.
- One terminal probe could not print a multiplication glyph under cp1251;
  repeated as escaped JSON, without altering extracted text. A stale preview tab
  was replaced in the same browser. Previous controls v01/v02 remain separate.

Limitations:

- This is a display and finite scope-notice fix, not a new scientific validator.
  Matching numbers/terms does not establish value ownership, semantic support,
  completeness or purity; unrelated materials can share values. Derived summaries
  and unavailable trace context retain their existing explicit provenance.
- It is not a complete LaTeX engine. Corrupted/unsupported markup stays raw and
  marked; it is never silently reconstructed from the screenshot or PDF.
- The source preview targets the first cited claim; remaining claims require
  inspection of the full context. Exact page within a multi-page chunk is not
  invented: existing page-range links are retained.
- A previously rendered browser response cannot be retroactively restyled by
  this server-side patch. New responses use the new display. The review control
  demonstrates it without a paid repeat. No scientific answer-quality gain or
  independent accuracy is claimed; the deferred scientific queue remains open.

Verdict:

The three display fixes are implemented, locally verified and running. Source
values and native results are preserved. Overall project-plan estimate remains
75%; independent scientific acceptance is unchanged.
