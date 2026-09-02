# ARIADNE Transition Instruction

## Purpose

This document captures the agreed direction for completing the transition to ARIADNE.
It is a practical implementation instruction, not a visual brandbook.

ARIADNE should become a verifiable scientific literature workspace. Nafion remains
the first domain profile and proof-of-work collection, while the platform should be
designed so other scientific domains can be added later.

## Product Positioning

ARIADNE is not a generic AI chat interface. It is a local-first scientific assistant
that helps a researcher move from a question to a supported claim and then to the
source fragment, page, table, figure, or original PDF.

The core product pattern is:

```text
Question -> Claim -> Evidence -> Source fragment -> Original PDF
```

Every substantial conclusion should expose provenance. If evidence is insufficient,
the system should say so explicitly instead of filling gaps with unsupported wording.

## Brand Direction

The ARIADNE design direction is suitable for the project because it matches the
scientific retrieval architecture:

- The thread metaphor maps naturally to provenance and source traceability.
- The product voice is restrained, specific, and evidence-bound.
- The UI direction is a research workspace, not a consumer AI chat.
- The palette is calm and technical rather than decorative.
- The `Claim -> Evidence` pattern should become a real interaction model, not only
  a visual motif.

Use the brand as product architecture reinforcement. Do not let it become a purely
decorative layer.

## Design Principles

1. The evidence thread must represent real data relationships.
   Use it only for actual links between question, claim, citation, fragment, table,
   page, and PDF.

2. Keep the interface dense enough for scientific work.
   The application should prioritize scanning, comparing, verifying, filtering, and
   opening sources. Avoid landing-page composition inside the main product.

3. Treat low evidence as a first-class state.
   Insufficient evidence is not a failure of presentation. It is a valid scientific
   result and should be visible in the answer UI.

4. Preserve source traceability.
   UI and backend changes must preserve article identity, PDF path, page reference,
   source type, table/figure identity when available, and exact text fragment.

5. Separate platform core from domain knowledge.
   ARIADNE should contain generic ingestion, retrieval, evidence, table/fact, and
   citation mechanics. Nafion-specific terms, properties, units, and comparison
   rules belong in a domain profile.

## Priority Breakdown

### P0: Required Before Full Transition

These items define the product and must not be compromised.

1. Preserve the main product idea.
   ARIADNE is a verifiable scientific workspace, not a chatbot skin.

2. Preserve traceability.
   Every answer path should be inspectable from claim to evidence to original source.

3. Keep Nafion as the first domain profile.
   Do not discard existing Nafion-focused behavior. Use it as the first demonstrable
   domain while preparing the system for more domains.

4. Build the product UI first.
   The first screen should be a usable research interface with query, collection,
   answer, claims, evidence, source panel, tables/facts, and document access.

### P1: Needed For A Good First ARIADNE Release

1. Create production logo assets.
   Convert the current logo concept into SVG/PDF master files and create a simplified
   micro-icon for favicon, sidebar, and 16/24 px usage.

2. Implement design tokens.
   Capture colors, type, radii, borders, and states in code.

   Suggested tokens:

   ```text
   Graphite: #2B3843
   Slate: #5D7285
   Ariadne Aqua: #91DEDB
   Endpoint Coral: #E5664A
   Paper: #FDFEFF
   Border / keyline: #DCE3E8
   Typeface: Inter
   Base radius: 12 px
   ```

3. Build the ARIADNE application shell.
   Minimum sections:

   ```text
   Library
   Search
   Answer
   Evidence
   Tables / Facts
   Documents
   Settings
   ```

4. Redesign the answer view.
   Replace plain answer rendering with structured blocks:

   ```text
   Claim card
   Evidence status
   Citation chips
   Source fragment
   Open original PDF action
   Numeric/table fact references where available
   ```

### P2: Important After The Shell Exists

1. Add a structured facts layer.
   Numeric values, tables, table rows, figure-derived values, units, and comparison
   relations should become explicit evidence objects where possible.

2. Generalize scientific domain profiles.
   A domain profile should contain:

   ```text
   glossary
   aliases
   property names
   units
   table schemas
   comparison rules
   retrieval boosts
   evaluation questions
   ```

3. Add strong low-evidence states.
   The UI should distinguish:

   ```text
   answered
   partially supported
   insufficient direct evidence
   numeric evidence unavailable
   source conflict
   extraction/OCR limitation
   ```

4. Make the research layout more operational.
   The real application should be denser than the brandbook mockup. Prioritize
   filters, source cards, fragments, page references, table previews, and comparison
   tools.

### P3: Polish And Public Packaging

1. Add subtle provenance animations only when they clarify evidence flow.
2. Prepare public-facing materials after the product UI is functional.
3. Build a Figma component kit after code tokens and core UI states are stable.
4. Add demo screenshots based on real Nafion workflows.

## Numeric Evidence And Tables

The swelling-degree comparison issue showed that text chunks alone are not enough.
The system needs structured extraction for numeric scientific evidence.

Target behavior:

1. During ingestion or post-processing, detect tables and store them as structured
   rows where possible.
2. Preserve table provenance: article, PDF, page, caption/title, row label, column
   label, unit, and original cell text.
3. For numeric comparison questions, retrieve both text chunks and structured facts.
4. Let deterministic code perform exact numeric comparisons when the query asks for
   greater/less/equal relations.
5. Give the model the resulting evidence and require it to explain the comparison,
   not invent or silently recalculate hidden values.

The model may compare numbers when the selected evidence is clear, but critical
numeric comparisons should be represented as explicit derived evidence from code.

## Platform Generalization

The project can be used beyond Nafion if domain knowledge is isolated cleanly.

Keep in platform core:

```text
PDF ingestion
OCR and text extraction
chunking
table extraction
structured facts
retrieval
answer generation
citations
source inspection
evaluation harness
```

Keep in domain profiles:

```text
Nafion / PFSA terminology
material aliases
property aliases
domain-specific units
known table forms
query expansion terms
comparison rules
domain evaluation cases
```

Do not hard-code Nafion-specific assumptions into generic retrieval, ingestion, or
answer rendering.

## UI Guidance

The main ARIADNE UI should feel like a scientific workbench:

- restrained color usage;
- no decorative AI gradients;
- no oversized marketing hero in the app;
- clear source panel;
- visible citations;
- PDF access close to each claim;
- compact metadata;
- explicit answer status;
- table/fact evidence shown separately from prose evidence;
- coral used sparingly for endpoint or important semantic emphasis;
- aqua used for active provenance paths and selected evidence.

Coral should not be used for small body text on white backgrounds because contrast is
weak. Use it for accents, endpoint dots, rare highlights, or larger labels.

## Recommended Implementation Order

1. Add ARIADNE application shell on top of the current app.
2. Redesign answer/evidence rendering around claims and source fragments.
3. Introduce design tokens and base components.
4. Add structured table/fact extraction and retrieval.
5. Extract Nafion-specific logic into a domain profile.
6. Create production SVG logo and micro-icon.
7. Polish public packaging only after the product workflow works.

## Non-Goals

- Do not build a landing page as the main product screen.
- Do not make the thread motif decorative.
- Do not hide weak evidence behind confident wording.
- Do not remove source diagnostics to make the UI cleaner.
- Do not rename the project in a way that loses the existing Nafion evidence base.
- Do not claim domain-general capability until at least one non-Nafion profile is
  implemented and evaluated.

## Verdict

Proceed with ARIADNE as the product direction, with Nafion/PFSA as the first domain
profile. The design direction is strong because it reinforces the required scientific
behavior: traceable claims, source-first answers, and visible uncertainty.
