# Li-Nafion: development cases and annotation protocol

Date: 9 October 2026. Status: manually prepared development proposals; no independent gold or scientific acceptance. The selected mandatory conditions are sample identity, temperature, medium composition and method. See the [experimental contract](experimental_record_contract.md) for exact representation and validator boundaries.

## Sources and inspected scope

The source adapter exported all 14 stored pages of Sanginov 2021 and all 14 stored pages of Istomina 2021, plus page 1 of the possible Sanginov supplement. Exports retain separate pages and recorded layers. Original PDF hashes were checked during export. Text inspection focused on methods/results/reference passages; complete relevant pages were rendered with Poppler and visually inspected for Sanginov pp3, 11 and 12 and Istomina pp2 and 4. This is not exhaustive scientific annotation of every page or record.

| Source | Article UUID | Relevant PDF pages | Development use |
|---|---|---|---|
| Sanginov 2021, Electrochimica Acta 373, 137914 | aec95165-f993-4576-9dba-0ec4bb8ecee1 | 3, 8, 11, 12 | Preparation/AC method, composition basis and series context, Table 2 own row, conclusion |
| Sanginov 2021 supplement | 7bc8d131-9060-4484-bf72-9749468b833b | 1 | Same title/authors and explicit Supplementary Materials heading; identity/grouping proposal only |
| Istomina 2021, Polymers 13, 1150 | b6024911-628a-4bd9-9dd1-085c932afade | 2, 4, 14 | Prior-work conductivity passage, own AC method, reference 26 |
| Kayumov 2021 | 1445f31a-0de7-482b-b335-029ebdd552a5 | 9 | Earlier isolated bibliography context; its whole page/article is not a negative label |

Local PDFs are immutable source inputs. Generated source bundles, recipes, images and worksheets remain under ignored `data/experiments/records/` and must not be automatically included in a public release.

## Case A: Table 2 own row, three scalar candidates

The final row of Sanginov Table 2 reports Li-Nafion-115, plasticiser EC/SL with footnote b, and origin `This work`. Footnote b specifies `ω(SL) = 0.40`; the composition basis is separately linked to the page 8 caption's mass fraction of sulfolane. The conclusion on page 12 identifies the best sample as the one saturated with an EC/SL mixture containing 40 wt.% sulfolane. The sample label is a matrix/row descriptor plus composition, not a unique specimen identifier supplied by the paper.

Three manually proposed points were created after visual inspection of the table:

| Raw conductivity lexeme | Raw unit from header | Temperature mapping proposal | Evidence that must be checked |
|---|---|---|---|
| `6.3 × 10 −6` | `S cm −1` | Lower-limit column → raw `-40`, °C from range header | Own row, lower-limit header, temperature-range cell |
| `6.9 × 10 −4` | `S cm −1` | Upper-limit column → raw `+ 80`, °C from range header | Own row, upper-limit header, temperature-range cell |
| `1.1 × 10 −4` | `S cm −1` | Raw `20 °C` from footnote d | Cell marker d overrides the generic 25 °C column header |

The raw endpoint temperature fields do not concatenate an invented `°C` suffix; their evidence includes the unit-bearing header. No numbers or units are normalized or converted. The 20 °C point is not renamed 25 °C. The previous abstract range proposal remains preserved separately; it is not counted as three additional independent measurements.

Property wording is `Conductivity` from the table header. The author's single-ion lithium claim is preserved separately from the conclusion. Independent Li-ion confirmation remains `not_reviewed`; a generic material name or transference-number proximity is not treated as confirmation.

The method proposal cites Sanginov's own page 3 AC conductivity passage: impedance spectroscopy, Ti blocking electrodes, and the reported frequency/amplitude/cooling procedure. The raw general error about 10% is retained as general method error; no point-specific ± uncertainty is calculated from it.

All mandatory observations and linkage proposals are present according to the technical checker. **All three remain `needs_review`**, with scientific admission `not_evaluated`. The exact conditioning history is still `ambiguous`: page 8 discusses a conductivity series saturated at 30 °C, whereas the methods describe swelling Series 1/2 at 30/40 °C. Reviewer must verify which preparation history belongs to this Table 2 row. The composition describes the initial plasticiser mixture, not independently measured in-membrane fractions; selective sorption must not be silently assumed absent.

Artifacts, relative to `data/experiments/records/`:

- `sources/sanginov2021_all_pages_v01.json`
- `development/create_sanginov_table2_cases.py` — manual, source-specific annotation recipe, not an extractor
- `development/sanginov2021_table2_candidates_v01.json`
- `development/sanginov2021_table2_candidates_v01.manifest.json`
- `development/sanginov2021_table2_review_v01.md` — review worksheet with field/linkage evidence and blank decisions
- `development/sanginov_table2-11.png`, `sanginov_methods-03.png`, `sanginov_conclusion-12.png` — page renders

## Case B: prior-work origin and wrong-method transfer

Istomina page 2 explicitly introduces the conductivity range as `In recent work [26]`. Reference 26 on page 14 names the Sanginov article in Electrochimica Acta 373, 137914. This cited range must not become a new independent measurement of Istomina's present study merely because the paper contains its own methods.

Istomina page 4 describes its own through-plane conductivity measurements using Ni blocking electrodes and a Z-350M analyser. Sanginov page 3 describes Ti blocking electrodes and an Elins Z-2000 analyser (the stored text splits its instrument digits). The own-method passages are distinct. An extractor must not attach Istomina's Ni/Z-350M procedure to the prior-work range cited from Sanginov. Preserve the author's original instrument text; do not repair the stored text layer.

This case exports context pages 2, 4 and 14 with **zero record candidates**. Zero records is a context-only artifact, not an automatic negative gold label. Reviewer can separately annotate reference-origin records if the final scope admits them, keeping the original work identity and origin explicit.

Artifacts:

- `sources/istomina2021_all_pages_v01.json`
- `development/create_istomina_reference_context.py`
- `development/istomina2021_prior_work_context_v01.json`
- `development/istomina2021_prior_work_context_v01.manifest.json`
- `development/istomina2021_prior_work_review_v01.md`
- `development/istomina_context-02.png` and `istomina_context-04.png` — visually inspected relevant pages

## Grouping proposal before any dev/test split

Conservative development family proposal: `proposed:ec_sl_2021_related` includes Sanginov main article, its possible supplement and Istomina article. Evidence for the supplement relationship is the matching title/authors and explicit Supplementary Materials heading; no external metadata lookup or curator confirmation was performed. Evidence for the related-work edge to Istomina is its explicit prior-work passage plus reference 26. These relationships differ: a supplement belongs to a work, while a related article may also contain genuinely new experiments.

Keep this family development-only for now. Do not count Istomina's repeated introductory range as independent gold or place it across a train/test boundary from the original. This grouping proposal does not assert that every measurement in both articles is duplicated. Kayumov and the dissertation require separate relationship review; name/year similarity alone is insufficient.

No corpus-wide work-group manifest or split has been finalized. The candidate's work-group field explicitly carries the `proposed:` prefix. It is not an approved cluster or a production database mapping.

## Annotation protocol v0.1

1. Define article, exact inspected regions and supported layout before annotation. Distinguish full article review from a selected paragraph/table case.
2. For independent annotation, give the annotator original source/context without model or these manually proposed answers. This candidate-filled worksheet is appropriate for review/adjudication, not a blinded independent gold pass.
3. Annotate every eligible measurement inside scope, including missed candidates. Preserve unsupported cases and ambiguity; do not remove them from the denominator after observing system failures.
4. For tables, record sample/matrix, row, multi-level column header, temperature cell, units, footnotes and origin. An empty cell is not a repeated value unless the layout or source explicitly establishes that repetition.
5. Mark general methods separately from point-specific conditions. Attach a method only with work/sample/measurement linkage; do not borrow methods across citations or neighboring experiments.
6. Keep initial mixture composition separate from measured composition inside a membrane. Preserve mass/mole/volume basis and author assumptions.
7. Record author property wording and author Li-ion claims; independent confirmation is a separate reviewer decision with evidence. Electronic conductivity and transference number remain different properties.
8. Preserve raw lexemes, signs, approximation, uncertainty and units. Do not normalize room temperature, map range endpoints by ordering alone, or ignore overriding footnotes.
9. Record reviewer ID, elapsed time, field corrections and exact evidence. Do not convert an agent-authored draft into human gold without a human decision.
10. Resolve work grouping and duplicate measurement references before splitting. For a second annotator, independently annotate a declared subset before adjudication; report disagreement counts honestly.

Next decisions: independently review this row's sample/thermal history and the proposal's mandatory fields; confirm supported table/footnote/range scope; establish who performs blinded annotation. Meanwhile, local provider/runtime inspection and S06 smoke preparation can proceed without treating these cases as gold.
