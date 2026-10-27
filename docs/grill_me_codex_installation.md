# Project-local grill-me-codex installation

Installed on 2026-10-27 for ARIADNE only.

## Source and local change

- Repository: https://github.com/ivanbilotic/grill-me-codex
- Revision: `fe37a7083e93e61d46e84cb8ccdd901fa8aa90fc`
- Upstream directory: `skills/grill-me-codex`
- Installation: `.agents/skills/grill-me-codex`
- Installed using the bundled `skill-installer` helper with `--method git` and the pinned revision; no project API or external inference calls were made.
- The upstream `description` contains 1161 characters, exceeding the bundled skill validator's 1024-character limit. Only this frontmatter value was shortened for Codex compatibility. The skill body is unchanged.
- The upstream MIT license and `THIRD-PARTY-NOTICES.md` are included in the installed directory. Other skills from the repository were not installed.

## Invocation

Use `$grill-me-codex`, `/grill-me-codex`, or explicitly request grilling with a topic, for example: `Прогрилль план следующей стадии ARIADNE`.

The skill interviews the user one question at a time, recommends an answer, and investigates locally answerable questions in the repository. Installation itself does not start the interview. Discovery is expected on the next turn; `AGENTS.md` also records the explicit project-local path.

## Compatibility and limits

The upstream skill targets Claude Code coordinating a separate Codex CLI reviewer. This project runs in Codex. Act 1 can be conducted here, but that alone does not constitute cross-model review. The current user instruction prohibits API calls, so Act 2 and delegated builds must not run. No external review, CLI authentication, or build phase was tested during installation.

Project evidence rules, automatic Terms classification, and existing user authorization remain in force. Do not replace unrelated `PLAN.md` or review logs; choose task-specific paths where necessary. A later request for external review requires checking the active API restriction and actual runtime capabilities, without inventing support or outcomes.

## Installation verification

- Bundled `quick_validate.py`: `Skill is valid!` after shortening the description to 527 characters.
- Byte comparison against the pinned source: only the description line differs; all other skill bytes are preserved.
- Both license files match the pinned source byte for byte.
- `git diff --check` passed. Runtime skill discovery and interactive interview behavior have not been exercised during installation.
