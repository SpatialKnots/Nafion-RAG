"""Post-hoc, exposed-reference comparison; separate from the immutable technical review."""

import json
import re
from pathlib import Path

from scripts import gigachat_answer_smoke as files
from scripts import run_satoh_fan_qa_20261110 as run


def main():
    closed = json.loads((run.BASE / "scope_closed_v01.json").read_bytes())
    if closed["remaining_allowance"] or (closed["model_attempts"], closed["oauth_attempts"]) != (5, 5):
        raise ValueError("Comparison requires completed closed scope")
    review = run.BASE / "review_v01"
    files.verify_manifest(review)
    report = json.loads((review / "report.json").read_bytes())
    intake_path = run.ROOT / "output/satoh_fan_qa_20261110/intake_v02/report.json"
    intake = json.loads(intake_path.read_bytes())
    anchors = []

    def anchor(label, page, pattern, key):
        source = next(p for p in intake["sources"][label]["pages"] if p["pdf_page"] == page)
        matches = list(re.finditer(pattern, source["text"], re.S))
        if len(matches) != 1:
            raise ValueError("Source comparison anchor missing/ambiguous: " + key)
        m = matches[0]
        a = {"id": key, "article": label, "pdf_page": page, "page_text_sha256": source["page_text_sha256"],
             "start": m.start(), "end": m.end(), "quote": m[0], "meaning": "literal_source_witness_not_scientific_validity"}
        if files.sha(source["text"].encode()) != a["page_text_sha256"]:
            raise ValueError("Frozen PDF text hash mismatch")
        anchors.append(a)

    anchor("Satoh", 10, r"This effect results.*?lower degree of ionic\s+dissociation\.", "S-mechanism")
    anchor("Satoh", 10, r"The conductivity was not merely in inverse proportion to the\s+viscosity in any case\.", "S-noninversion")
    anchor("Satoh", 1, r"TFEMEE\) as a trifluorinated triether\.", "S-identity")
    anchor("Satoh", 8, r"The Ea,η is determined to be 11\.20, 15\.91, 9\.27, and 13\.59.*?respectively\.", "S-activation")
    anchor("Fan", 7, r"XPS confirmed.*?CFx and POxFy species\)", "F-comparison")
    anchor("Fan", 2, r"Among these electrolytes.*?all-fluorinated\s+electrolyte\.", "F-voltammetry")
    notes = {
        "Satoh_04": {"assessment": "core_explanation_differs_from_reference_and_source",
            "note": "Ответ объясняет результат только повышенной вязкостью/размером молекул. "
                    "Пропущен механизм эталона и статьи: снижение донорной способности → сольватации Li → диссоциации. "
                    "PDF9–11 из указателя не входят в selected ranges1–5; ссылки E1–E3 не подтверждают полный причинный вывод.",
            "source_anchors": ["S-mechanism"]},
        "Satoh_09": {"assessment": "partial_with_identity_error",
            "note": "Направления изменения вязкости и проводимости совпадают. Отсутствуют аррениусовская зависимость "
                    "и оговорка об отсутствии простой обратной пропорциональности. TFEMEE ошибочно включён в диэфиры; "
                    "в статье это триэфир. Температурный диапазон проводимости −5…60°C есть в E2.",
            "source_anchors": ["S-noninversion", "S-identity"]},
        "Fan_06": {"assessment": "partial_comparison_missing",
            "note": "Фторированная CEI и толщина5–10нм согласуются с источником. Нет запрошенного сравнения с EC/DMC "
                    "и FEC/DMC: состава CFx/POxFy и F/O10.7 против2.4 и4.0. Основные страницы6–7 не отобраны; "
                    "ответ основан на вводном обобщении E1.", "source_anchors": ["F-comparison"]},
        "Fan_09": {"assessment": "main_comparison_agrees",
            "note": "Сохранены три главных результата эталона: EC/DMC выше4.3В, FEC/DMC около5.0В, "
                    "низкий ток полностью фторированного состава при6.5В. Эти значения и CV на нержавеющей стали "
                    "присутствуют в raw E1/E2. Это локальное совпадение, не экспертное научное принятие.",
            "source_anchors": ["F-voltammetry"]},
        "Satoh_08": {"assessment": "model_abstained",
            "note": "Четыре числа эталона найдены в замороженном PDF8, но эта страница вне selected ranges1–5. "
                    "Модель получила другой контекст и отказалась; это не доказательство отсутствия ответа в статье.",
            "source_anchors": ["S-activation"]},
    }
    rows = []
    for case in report["cases"]:
        row = {"id": case["id"], **notes.get(case["id"], {
            "assessment": "production_gate_rejected", "note": "Ответ не выдан: insufficient_distinctive_term_coverage. "
                "Научная правильность потенциального ответа не оценивалась.", "source_anchors": []})}
        row.update(reference_agreement_score=None, reviewer="implementation_assistant_posthoc_unblinded",
                   independent_accuracy=None, scientific_validity="not_evaluated")
        rows.append(row)
    value = {"cases": rows, "anchors": anchors, "source_text_basis": "prior_frozen_PDF_text_not_fresh_extraction",
             "rubric_applied": False, "score": None, "independent_evaluation": False,
             "bindings": files.bindings([Path(__file__), review / "manifest.json", intake_path,
                                         run.BASE / "scope_closed_v01.json"])}
    out = run.BASE / "assessment_v01"
    out.mkdir(exist_ok=False)
    files.write(out / "assessment.json", value)
    text = ("# ARIADNE: предварительное сравнение Satoh/Fan\n\n"
            "4 ответа /20 вопросов;15 отказов до модели и1 отказ модели.5 model POST+5 OAuth, без повторов; лимиты закрыты.\n\n"
            "Сравнение выполнено агентом после просмотра эталонов. Это development-проверка; независимая точность, "
            "полная научная корректность и шкала0/1/2 не оценивались.\n\n"
            "[Все20 вопросов, исходные ответы и источники](../review_v01/review.html) · "
            "[Точные исходные свидетели](assessment.json)\n\n"
            "|Вопрос|Предварительный вывод|\n|---|---|\n")
    text += "".join("|" + r["id"] + "|" + r["note"] + "|\n" for r in rows)
    text += ("\nУ15/20 вопросов хотя бы одна указанная в эталоне PDF-страница вне диапазонов selected chunks. "
             "Попадание страницы в диапазон ещё не доказывает присутствие конкретного отрывка в запросе модели. "
             "Fan02/07/08 требуют отдельных supplementary; они не загружались.\n\n"
             "Следующий предмет отдельного исправления: выбор релевантных частей указанной статьи и межъязыковая "
             "оценка достаточности, затем проверка причинных объяснений/полноты сравнений. В этом прогоне код продукта не менялся.\n")
    files.save(out / "assessment.md", text.encode())
    files.verify(value["bindings"])
    files.manifest(out)
    print(json.dumps({"cases": len(rows), "literal_anchors": len(anchors), "score": None, "new_model_calls": 0}))


if __name__ == "__main__":
    main()
