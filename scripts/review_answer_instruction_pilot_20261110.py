"""Post-hoc exposed source comparison of the closed five-case provider pilot."""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

from app.generation.answer_instruction_experiment import INSTRUCTION
from app.generation.answer_support import audit
from app.generation.providers import Evidence, GeneratedClaim, _clean_generation_evidence_text
from scripts import gigachat_answer_smoke as f
from scripts.run_answer_instruction_pilot_20261110 import BASE, SELECTED

ASSESSMENTS = {
    "Satoh_07": ("Статус идентификации", "target_defect_corrected",
        "Раньше: идентифицировали возможные продукты. Теперь: не идентифицированы; алкоксиды названы предположением авторов.",
        ["E1", r"Although the\s+organofluorine compounds have not been identified.*?lithium alkoxides\."]),
    "Fan_05": ("Состав и роль SEI/CEI", "target_not_established",
        "Прежний перенос CFx/POxFy и 5–10 нм на SEI исчез. Ответ стал общим: LiF не назван. "
        "Ссылка E2 содержит LiF-rich SEI в рисунке, но явное XPS/high-F предложение и dense layer относятся к CEI. "
        "Причинная цепочка high-F SEI → плотный Li не подтверждена выбранным предложением; вопрос полностью не закрыт.",
        ["E2", r"XPS confirmed.*?reactions between cathode and electrolyte15\."]),
    "Satoh_06": ("Условие EC-смеси", "target_defect_corrected",
        "Теперь около 60% на 30-м цикле явно относятся к EC–TFEME/EC–TFEMEE, а не к чистым эфирам.",
        ["E4", r"We used \(a\).*?There was no\s+consistent correlation"]),
    "Fan_10": ("Основа удельной энергии", "target_defect_persists",
        "Значение >680 Вт·ч/кг и истощение Li после 125 циклов сохранены, но total cathode/anode masses снова опущено.",
        ["E4", r"A high energy density of.*?the reversible capacity began to decay"]),
    "Satoh_03": ("Полнота сравнения плотностей", "target_defect_persists_with_new_terminology_change",
        "Снова приведено только EME: 0.8472×10³ кг/м³; TFEME: 1.1508×10³ кг/м³ из E3 не приведено. "
        "Дополнительно исходное trifluorination передано как «трифторметилирование»; термин изменён.",
        ["E3", r"The mass densities decreased in the following order:.*?Trifluorination of EME and EMEE.*?molecule\."]),
}


def read(path):
    return json.loads(path.read_bytes())


def anchor(source, pattern, prompt):
    matches = list(re.finditer(pattern, source.text, re.S))
    if len(matches) != 1:
        raise ValueError("Ambiguous/missing declared source witness")
    match = matches[0]
    actual = _clean_generation_evidence_text(match[0])
    position = prompt.find(actual)
    if position < 0:
        raise ValueError("Witness absent from actual native prompt")
    return {"citation_id": source.citation_id, "article_id": source.article_id, "chunk_id": source.chunk_id,
        "page_range": [source.page_start, source.page_end], "source_type": source.source_type,
        "raw_text_sha256": f.sha(source.text.encode()), "raw_start": match.start(), "raw_end": match.end(),
        "raw_text": match[0], "actual_prompt_start": position, "actual_prompt_end": position + len(actual),
        "actual_text": actual, "transform": "existing whitespace collapse only"}


def main():
    freeze = BASE / "input_freeze_v01"
    f.verify_manifest(freeze)
    f.verify(read(freeze / "bindings.json"))
    closed = read(BASE / "closed_v01.json")
    if closed["remaining_allowance"] != 0:
        raise ValueError("Live scope must close before comparison")
    output = BASE / "review_v01"
    output.mkdir(exist_ok=False)
    rows, bindings, totals = [], [Path(__file__), freeze / "manifest.json", BASE / "closed_v01.json"], {}
    for dataset, cid in SELECTED:
        prepared, live = freeze / cid, BASE / "live" / cid
        f.verify_manifest(live)
        original = read(prepared / "input.json")
        baseline, new = read(prepared / "historical_baseline.json"), read(live / "provider_result.json")
        raw = (live / "request.json").read_bytes()
        if raw != (prepared / "request.json").read_bytes():
            raise ValueError("Actual request differs from frozen candidate")
        before, after = read(prepared / "baseline_request.json"), json.loads(raw)
        prompt = after["messages"][1]["content"]
        if prompt != INSTRUCTION + "\n" + before["messages"][1]["content"]:
            raise ValueError("Unexpected instruction difference")
        after["messages"][1]["content"] = before["messages"][1]["content"]
        if before != after:
            raise ValueError("Non-instruction native changes")
        native = read(live / "response.bin")
        choice, = native["choices"]
        decoded = json.loads(choice["message"]["content"])
        if decoded != {k: new[k] for k in ("answerable", "claims")} or choice["finish_reason"] != "stop":
            raise ValueError("Parsed answer not identical to complete native content")
        evidence = [Evidence(**e) for e in original["evidence"]]
        claims = [GeneratedClaim(**c) for c in new["claims"]]
        new_audit = audit(original["question"], claims, evidence)
        if new_audit != read(live / "audit.json"):
            raise ValueError("Audit replay differs")
        baseline_audit = audit(original["question"], [GeneratedClaim(**c) for c in baseline["claims"]], evidence)
        goal, outcome, note, witness = ASSESSMENTS[cid]
        source = next(e for e in evidence if e.citation_id == witness[0])
        observations = [anchor(source, witness[1], prompt)]
        if cid == "Fan_05":
            observations.append(anchor(source, r"F-rich CEI\s+LiF-rich SEI", prompt))
        result = read(live / "result.json")
        slot = f.LEDGER / original["request_sha256"]
        if read(slot / "result.json") != result or read(slot / "answer_instruction_pilot_closed_v01.json") != {
                "resend_authorized": False, "allowance_closed": True}:
            raise ValueError("Ledger receipt or closure mismatch")
        if result["model_attempts"] != 1 or result["oauth_attempts"] != 1 or result["network_denials"]:
            raise ValueError("Unexpected call budget/network result")
        for key, value in native["usage"].items():
            totals[key] = totals.get(key, 0) + value
        rows.append({"id": cid, "baseline_dataset": dataset, "question": original["question"], "goal": goal,
            "historical_claims": baseline["claims"], "new_result": new, "target_outcome": outcome, "review_note": note,
            "reviewer": "exposed_implementation_assistant_posthoc_not_independent", "scientific_accuracy": None,
            "baseline_audit": baseline_audit, "new_audit": new_audit, "raw_witnesses": observations,
            "provider_result_status": result["status"], "actual_request_sha256": f.sha(raw),
            "returned_model": native["model"], "usage": native["usage"], "live_folder": str(live)})
        bindings.extend([live / "manifest.json", slot / "result.json", slot / "answer_instruction_pilot_closed_v01.json"])
    report = {"cases": rows, "real_model_calls": 5, "real_oauth_calls": 5, "remaining_allowance": 0,
        "usage_sum": totals, "cost": None, "independent_accuracy": None,
        "design": "historical-baseline exposed five-case provider pilot; no concurrent baseline draw or API test",
        "default_activated": False, "bindings": f.bindings(bindings)}
    f.verify(report["bindings"])
    f.write(output / "report.json", report)

    def esc(value):
        return html.escape(value, quote=True)

    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE: испытание инструкций</title>'
        '<style>body{font:16px system-ui;margin:24px;color:#18333f}table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #abc;padding:10px;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
        '</style><h1>Пять вопросов: общие инструкции генерации</h1><p>5 model POST + 5 OAuth, без повторов. '
        'Все ответы сохранены без исправления; лимит закрыт. Два целевых дефекта исправлены в этом прогоне, '
        'три вопроса не закрыты полностью. Это не научная точность и не независимая оценка.</p>'
        '<p>Baseline исторический, параметры и источники совпадают. Новая случайность/время запуска не контролируются. '
        'Новый прогон выполнен на уровне provider, без повторного поиска/DB/production API.</p>'
        '<table><thead><tr><th>Вопрос</th><th>Было</th><th>Стало</th><th>Сверка</th></tr></thead><tbody>')
    for row in rows:
        body += '<tr><td>' + esc(row["id"]) + '<br>' + esc(row["goal"]) + '</td>'
        for claims in (row["historical_claims"], row["new_result"]["claims"]):
            body += '<td>' + ''.join('<p>' + esc(c["text"]) + ' [' + esc(', '.join(c["citation_ids"])) + ']</p>'
                                     for c in claims) + '</td>'
        body += '<td>' + esc(row["review_note"]) + '<br>Finite audit: ' + esc(row["new_audit"]["decision"]) + '</td></tr>'
    body += '</tbody></table>'
    for row in rows:
        body += '<section><h2>' + esc(row["id"]) + '</h2><p>' + esc(row["question"]) + '</p>'
        for a in row["raw_witnesses"]:
            body += '<p>' + esc(a["citation_id"]) + ' · PDF range ' + esc(str(a["page_range"])) + '</p><pre>'
            body += esc(a["raw_text"]) + '</pre>'
        body += '<details><summary>Все цитированные источники и исходные данные</summary>'
        inp = read(freeze / row["id"] / "input.json")
        used = {cid for c in row["new_result"]["claims"] for cid in c["citation_ids"]}
        for e in inp["evidence"]:
            if e["citation_id"] in used:
                body += '<h3>' + esc(e["citation_id"]) + '</h3><pre>' + esc(e["text"]) + '</pre>'
        for name in ("request.json", "response.bin", "provider_result.json", "audit.json", "result.json"):
            link = (Path(row["live_folder"]) / name).as_uri()
            body += '<p><a href="' + esc(link) + '">' + esc(name) + '</a></p>'
        body += '</details></section>'
    body += '<p>Tokens: ' + esc(str(totals)) + '; стоимость не установлена. Новая модель во всех пяти: '
    body += esc(rows[0]["returned_model"]) + '. Автоматическое включение в проект не выполнено.</p></html>'
    f.save(output / "review.html", body.encode())
    markdown = "# Испытание общей инструкции: пять вопросов\n\n"
    markdown += "5 новых ответов provider/5 OAuth; без повторов. Исторический baseline, те же источники.\n\n"
    markdown += "|Вопрос|Результат сверки целевого дефекта|\n|---|---|\n"
    markdown += ''.join('|' + r["id"] + '|' + r["review_note"] + '|\n' for r in rows)
    markdown += "\nДва дефекта исправлены в этом прогоне; три вопроса не закрыты. Это не показатель научной точности. "
    markdown += "Finite audit не гарантирует полноту: Fan05/Satoh03 остались без veto. "
    markdown += "Нужны отдельные проверки роли/полноты; prompt не заменяет проверку источников.\n"
    f.save(output / "comparison.md", markdown.encode())
    f.manifest(output)
    print(json.dumps({"cases": len(rows), "real_model_calls": 5, "real_oauth_calls": 5, "usage": totals,
                      "source_witnesses": sum(len(r["raw_witnesses"]) for r in rows), "remaining_allowance": 0}))


if __name__ == "__main__":
    policy = f.NetworkPolicy()
    sys.dont_write_bytecode = True
    sys.addaudithook(policy)
    main()
