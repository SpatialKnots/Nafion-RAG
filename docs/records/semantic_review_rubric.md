# Development reference and comparison protocol

This protocol compares saved single-field model outputs with provisional source-bound expectations. It does not certify scientific records or replace independent annotation. Contract versions are `records_development_reference_v0.1` and `records_reference_comparison_v0.1`.

## Reference status and provenance

Every reference is explicitly `needs_independent_review`. Each case contains the complete frozen source-context bundle, its original byte SHA-256, the selected task SHA-256, all ten field expectations and three linkage review dimensions. Source identity includes article, original PDF path/hash, page, text layer, full stored page text and exact fragment offsets. The comparison does not read or alter PDFs/database and does not establish current live-corpus identity.

Each field has one criterion:

- `exact_raw`: a finite list of permitted author-worded raw strings, each anchored to exact source occurrences. Support spans and rationale explain the proposed field assignment. No number/unit conversion, trimming, ligature repair or inferred missing values is allowed.
- `abstain`: no asserted value is supported for the requested measurement in the supplied context. This includes bibliography-only context, missing composition and a present-article method that is not evidenced for a cited result.
- `deferred`: no automatic agreement judgement. The field remains in the report denominator and retains its support/rationale for review.

Source-bound answer variants are explicit. Scientifically defensible alternative wording or occurrences outside that finite list must be reviewed rather than silently normalized into a pass. The current reference was authored after viewing development failures; it is not blinded, independent gold, or a held-out evaluation.

## Separate checks

1. **Wire contract and completion:** parse the actual raw server response using the recorded v0.2/v0.3 contract. Truncation, schema failure and missing responses remain visible.
2. **Literal integrity:** resolve quotes against the frozen source context using the existing strict resolver. A literal bibliographic page identifier can pass this step.
3. **Field agreement:** compare the validated raw proposal with the permitted raw strings, or require an explicit abstention when that is the criterion.
4. **Reference anchor:** for a matching raw answer, its actual evidence must cover a permitted source occurrence. The same unit in an electronic-conductivity clause does not pass an ionic-conductivity anchor.
5. **Abstention:** distinguish correct abstention, false assertion and a missed expected field. Diagnostic-note truth is not automatically assessed.
6. **Sample, condition and origin linkage:** each case retains these three dimensions as `needs_independent_review` or `not_applicable`. Independent field requests do not establish a coherent complete measurement record. Row/specimen identity, header/footnote applicability, general-method-to-point linkage, reference attribution and work grouping remain explicit reviewer decisions.

`reference_agreement` requires valid wire output, literal integrity, declared field agreement and an applicable source-anchor match. It is finite development-reference agreement, not scientific acceptance or model accuracy. Missing/failed outputs are not removed from the denominator. Changed input/task/context/checksums, unknown or duplicate fields and run paths outside their declared batch directory stop comparison. A partial batch produces unavailable rows for every omitted field.

## Initial Li-Nafion cases

- **Sanginov Table 2:** task selects the own-row conductivity cell with footnote d. Expected raw value is `1.1 × 10 −4`; temperature is `20 °C` from footnote d rather than the generic header. Polymer is `Li-Naﬁon-115`; plasticiser is EC/SL; footnote b states `ω(SL) = 0.40`, on an initial-plasticiser mass-fraction basis. The general impedance method is cited, while applying it to the exact point still requires linkage review. Property wording remains `Conductivity`; independent Li-ion confirmation is not implied.
- **Kayumov bibliography:** all ten requested measurement fields require abstention. Sample/property words in the title and identifiers such as `A5253` do not constitute a measurement record.
- **Istomina prior result [26]:** preserve the cited range, author property wording, membrane descriptor, solvent components and prior-work attribution. Do not split a range into inferred scalar pairs. Selected context does not state that sample's composition fraction/basis or its applicable measurement method. Present-article Ni/Z-350M methods must not be transferred to the cited result.

These expectations and their exact evidence are stored privately in `data/experiments/records/development/li_nafion_development_reference_v01.json`; they require independent scientific review. The minimal two-key wire contract has an additional limitation: an isolated unit repeated within one region cannot form a unique answer/evidence span. The five-key format can cite a longer unique passage while preserving the short raw unit. Keep such format limitations visible when interpreting results.

## Reproduce comparison

From the repository root, choose a new output directory:

```powershell
.\.venv\Scripts\python.exe -m app.records.cli compare `
  --reference data/experiments/records/development/li_nafion_development_reference_v01.json `
  --batches data/experiments/records/smoke/single_field_20261009_v02/batch_result.json `
            data/experiments/records/smoke/span_field_20261009_v03/batch_result.json `
  --output-dir data/experiments/records/comparisons/new_reference_comparison
```

Outputs preserve the reference snapshot, a detailed JSON report, a Markdown table, input/run artifact hashes and evaluator code/schema fingerprints. The evaluator parses raw responses rather than accepting recorded integrity statuses as scientific truth. It records source/field failures, settings and runtime identity; it never modifies historical model artifacts or creates accepted records.

For another model, freeze reference before inference, use the same source contexts, tasks, prompt, wire format, seed, output budget and runtime settings, preserve failures, then compare the new batch. Reference answers must never enter inference prompts. Resource measurements and runtime differences accompany the report. Independent annotation and a held-out split are later requirements before making accuracy claims.
