"""Offline review packet for proposals; does not create human decisions or gold."""

from __future__ import annotations

import html
import re
from collections.abc import Iterator

from app.records.readiness import assess_readiness
from app.records.schema import CandidateBundle, EvidenceSpan, QuantityProposal, RecordCandidate, TextObservation


def observations_for_review(record: RecordCandidate) -> Iterator[tuple[str, TextObservation]]:
    for name in RecordCandidate.model_fields:
        value = getattr(record, name)
        if isinstance(value, TextObservation):
            yield name, value
        elif isinstance(value, QuantityProposal):
            for part in QuantityProposal.model_fields:
                observation = getattr(value, part)
                if isinstance(observation, TextObservation):
                    yield f"{name}.{part}", observation


def _cell(value: str | None) -> str:
    if value is None:
        return "—"
    return html.escape(value, quote=False).replace("|", "&#124;").replace("\r", "&#13;").replace("\n", "<br>")


def _literal(value: str) -> str:
    # Keep quoted source bytes as text even when a source contains Markdown fences.
    longest = max((len(match.group()) for match in re.finditer(r"`+", value)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{value}\n{fence}"


def render_review_packet(bundle: CandidateBundle) -> str:
    regions = {region.region_id: region for region in bundle.regions}
    citations: dict[tuple[str, int, int, str], tuple[str, EvidenceSpan]] = {}

    def cite(span: EvidenceSpan) -> str:
        key = (span.region_id, span.start, span.end, span.quote)
        if key not in citations:
            citations[key] = (f"E{len(citations) + 1}", span)
        label = citations[key][0]
        return f"[{label}](#{label.lower()})"

    lines = [
        "# Пакет научного review кандидатов Li-Nafion",
        "",
        "Статус: development proposals, не gold. Все записи — needs_review; Li-ion confirmation — not_reviewed.",
        "Проверка evidence подтверждает точные цитаты и ссылки, но не научную корректность или сравнимость.",
        "Пакет не записывает решения в БД. Заполненные заметки нужно отдельно проверить перед созданием gold/revisions.",
        "",
        f"Run ID: `{bundle.run_id}`. Schema: `{bundle.schema_version}`. Кандидатов: {len(bundle.records)}.",
        "",
        "## Просмотренный context",
        "",
    ]
    for region in bundle.regions:
        lines.extend([
            f"- Article `{region.article_id}`, PDF page {region.page_number}, layer `{region.text_layer}`.",
            f"  Region `{region.region_id}`; page span [{region.start}, {region.end}).",
            "  Original PDF:",
            "", _literal(region.original_pdf_path), "",
            f"  SHA-256: `{region.original_pdf_sha256}`. Selection: `{region.selection_basis}`.",
            "", _literal(region.selection_note), "",
        ])
    if not bundle.records:
        lines.extend([
            "## Задание разметки context", "",
            "Пустой список кандидатов сам по себе не является отрицательной gold-разметкой.",
            "Найдите все records внутри указанного context; отдельно отметьте bibliography/reference и unsupported layout.",
            "Reviewer: ______. Решение/основание: ______. Затраченное время: ______.", "",
        ])
    for index, record in enumerate(bundle.records, start=1):
        readiness = assess_readiness(record)
        lines.extend([
            f"## Кандидат {index}: {record.record_id}", "",
            f"Article: `{record.article_id}`. Work group proposal: {_cell(record.work_group_id)}.",
            f"Value representation proposal: `{record.value.representation}`.",
            "",
            "Отсутствующие обязательные observations: " + (", ".join(readiness.missing_fields) or "нет по status; требуется review") + ".",
            "Отсутствующие linkage proposals: " + (", ".join(readiness.missing_linkage_roles) or "нет; связи ещё не подтверждены") + ".",
            "",
            "| Поле | Status | Raw text | Evidence | Примечание |",
            "|---|---|---|---|---|",
        ])
        for name, observation in observations_for_review(record):
            refs = ", ".join(cite(span) for span in observation.evidence) or "—"
            lines.append(f"| {name} | {observation.status} | {_cell(observation.raw_text)} | {refs} | {_cell(observation.note)} |")
        lines.extend(["", "### Связи, предложенные для проверки", ""])
        for link in record.linkage:
            lines.append(f"- `{link.role}`: {', '.join(cite(span) for span in link.evidence)}. {_cell(link.note)}")
        if not record.linkage:
            lines.append("Связи пока не предложены.")
        lines.extend([
            "", "### Независимое решение reviewer", "",
            "Reviewer: ______. Дата: ______. Затраченное время: ______.",
            "",
            "- [ ] Проверены original PDF, headers, footnotes и sample identity.",
            "- [ ] Проверены value/unit, температура, состав среды, basis и метод.",
            "- [ ] Проверены linkage, primary/reference origin и повторы в связанных работах.",
            "- [ ] Авторский Li-ion claim отделён от независимого подтверждения.",
            "",
            "Решение (подтвердить / исправить / отклонить / оставить неопределённым): ______.",
            "Исправления и точное evidence: ______. Разногласия/ограничения: ______.", "",
        ])
    lines.extend(["## Exact evidence", ""])
    for label, span in citations.values():
        region = regions[span.region_id]
        lines.extend([
            f"### {label}", "",
            f"Article `{region.article_id}`, PDF page {region.page_number}, layer `{region.text_layer}`.",
            f"Region `{span.region_id}`, region span [{span.start}, {span.end}); "
            f"page span [{region.start + span.start}, {region.start + span.end}).",
            "", _literal(span.quote), "",
        ])
    if not citations:
        lines.extend(["Field-level evidence отсутствует; полный просмотренный текст хранится в исходном bundle.", ""])
    return "\n".join(lines)
