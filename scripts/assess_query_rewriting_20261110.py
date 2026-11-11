"""Exposed assistant comparison after all query-rewriting experiment allowances close."""

import json
import re
from pathlib import Path

from scripts import gigachat_answer_smoke as f
from scripts import run_query_rewriting_20261110 as run


def main():
    base = run.BASE
    if json.loads((base / "answers_closed_v01.json").read_bytes())["remaining_allowance"]:
        raise ValueError("Scope must close before assessment")
    f.verify_manifest(base / "review_v01")
    report = json.loads((base / "review_v01/report.json").read_bytes())
    notes = {
        "Satoh_03": "Основные плотности/вещество/температура совпадают. Исходные единицы ×10³кг/м³ сохранены; процент35.8 не вычислялся.",
        "Satoh_04": "Вывод о вязкости остаётся неполным причинным объяснением. В новом контексте нет PDF10–11 "
                    "с donor ability/solvation/dissociation. Переписывание не устранило эту потерю источника.",
        "Satoh_05": "Все4 приблизительных потенциала и привязка к эфиру/отсчёт Li/Li+ совпали с источником и эталоном.",
        "Satoh_06": "Основные60%/30циклов и20%/15циклов совпадают. Ответ пропускает явное условие бинарных смесей EC–эфир; "
                    "не следует переносить результат на чистые растворители.",
        "Satoh_08": "Все4 энергии и единицы совпадают; прежний отказ модели заменён содержательным ответом.",
        "Satoh_09": "Правильные направления изменения, прежней ошибки диэфир/триэфир нет. Оговорка об отсутствии простой "
                    "обратной пропорциональности вязкости/проводимости по-прежнему пропущена.",
        "Satoh_10": "Качественные эффекты TFEME/TFEMEE согласуются с источником; сравнение с EME/EMEE и EC-условия изложены неполно.",
        "Fan_01": "1M/2:6:2 по массе совпадают. Название HFE в ответе отличается от источника; распределение функций компонентов "
                  "не воспроизводит эталон. E2 даёт состав, но его цитирование не обосновывает все приписанные функции. Methods PDF9 не отобран.",
        "Fan_02": "Модель отказалась. В фактическом новом prompt нет5.1 и10.3, а10.7 встречается в другом контексте. "
                  "PDF2 с сравнением проводимостей потерян при переотборе; ответа модель не придумала.",
        "Fan_04": "90%/450циклов и93%/1000циклов с правильными ячейками совпадают с источником и эталоном.",
        "Fan_06": "Сравнение F/O10.7/2.4/4.0 восстановлено. CFx/POxFy и толщина5–10нм из полного эталона не названы.",
        "Fan_09": "Исходный успешный случай в новом прогоне получил HTTP502: provider вернул пустой message.content. "
                  "Native сохранён, повтор не выполнялся; это техническая регрессия доступности, не оценка научной истинности.",
        "Fan_10": "680Wh/kg и125циклов присутствуют, но ключевой знаменатель total cathode/anode masses пропущен, "
                  "хотя есть в цитируемом E4. Ответ нельзя принимать как удельную энергию полной ячейки.",
    }
    patterns = {
        "Satoh_03": r"The mass densities decreased.*?EME \(0\.8472.*?25.*?C\)\.",
        "Satoh_05": r"We found\s+that TFEME.*?that of EMEE was about 5 V vs\. Li \| Li\+\.",
        "Satoh_06": r"The cycling efficiency of the EC.*?30th cycle\.",
        "Satoh_08": r"The Ea,η is determined to be 11\.20, 15\.91, 9\.27, and 13\.59.*?respectively\.",
        "Fan_01": r"a mixture of fluoroethylene carbonate/3,3,.*?2:6:2 by weight\)",
        "Fan_04": r"Unprecedented cycling stabilities.*?1,000th cycle\)\.",
        "Fan_06": r"XPS confirmed.*?CFx and POxFy species\)",
        "Fan_10": r"A high energy density of.*?total cathode/anode masses is achieved\.",
    }
    anchors, rows = [], []
    for c in report["cases"]:
        cid = c["id"]
        if cid in patterns:
            cited = {i for claim in c["answer"].get("claims", []) for i in claim["citation_ids"]}
            found = False
            for e in c["selected_raw_evidence"]:
                if e["citation_id"] not in cited:
                    continue
                match = re.search(patterns[cid], e["text"], re.S)
                if not match:
                    continue
                native = json.loads((base / "answers" / cid / "live/request.json").read_bytes())
                quote = match[0]
                anchors.append({"id": cid, "citation_id": e["citation_id"], "article_id": e["article_id"],
                    "chunk_id": e["chunk_id"], "page_range": [e["page_start"], e["page_end"]],
                    "source_text_sha256": f.sha(e["text"].encode()), "start": match.start(), "end": match.end(),
                    "quote": quote, "literal_quote_in_actual_prompt": quote in native["messages"][1]["content"],
                    "meaning": "literal source witness; not independent scientific validation"})
                found = True
                break
            if not found:
                raise ValueError("Declared cited-source comparison witness missing: " + cid)
        note = notes.get(cid, "Переписывание отклонено до ответа: " + c["rewrite"]["decision"]["note"])
        rows.append({"id": cid, "note": note, "reviewer": "implementation_assistant_unblinded_posthoc",
                     "score": None, "scientific_validity": "not_evaluated"})
    accepted = [c for c in report["cases"] if c["rewrite"]["accepted"]]
    gained = [c["id"] for c in report["cases"] if c["baseline_answer"]["status"] != "answered"
              and c["answer"].get("status") == "answered"]
    lost = [c["id"] for c in report["cases"] if c["baseline_answer"]["status"] == "answered"
            and c["answer"].get("status") != "answered"]
    summary = {"newly_answered": gained, "previously_answered_now_unavailable": lost,
        "accepted_cases": len(accepted), "baseline_reference_range_gaps_on_accepted": sum(
            bool(c["baseline_declared_pages_outside_ranges"]) for c in accepted),
        "new_reference_range_gaps_on_accepted": sum(bool(c["new_declared_pages_outside_ranges"]) for c in accepted),
        "literal_source_witnesses": len(anchors), "score": None, "independent_accuracy": None,
        "hypothesis_scope": "combined translation/keyword ranking/English lexical admission with per-plan agent review",
        "conclusion": "availability improved in exposed20-case development set; autonomous rewrite reliability/scientific accuracy not established"}
    out = base / "assessment_v01"
    out.mkdir(exist_ok=False)
    value = {"summary": summary, "cases": rows, "anchors": anchors,
             "bindings": f.bindings([Path(__file__), base / "review_v01/manifest.json", base / "answers_closed_v01.json"])}
    f.write(out / "assessment.json", value)
    text = ("# Query rewriting: предварительный результат\n\n"
            "Выданных ответов4→11 из20.8 новых ответов, один прежний успешный случай Fan09 получил пустой ответ провайдера/HTTP502. "
            "Ровно20 rewrite+13 answer POST, столько же OAuth, без повторов; лимиты закрыты.\n\n"
            "В обработку прошли13 переводов после смыслового review агентом.7 отклонены:3 формат/пустые keywords, "
            "3 ether→ester и1 неоднозначное hold→soak. Это experiment с ручной смысловой проверкой, не автономный deployment.\n\n"
            "На тех же13 случаях диагностический допуск: baseline5, только ranking6, только English gate11, "
            "ranking+English gate13. Это не дополнительные ответы и не scientific acceptance. "
            "Неполное покрытие указанных reference-page ranges среди этих13:10→6.\n\n"
            "[Все20 сравнений и исходные API/native файлы](../review_v01/review.html) · "
            "[Точные source witnesses](assessment.json)\n\n|Вопрос|Предварительная сверка|\n|---|---|\n")
    text += ''.join('|'+r['id']+'|'+r['note']+'|\n' for r in rows)
    text += ("\nОценка exposed-assistant post-hoc. Баллы/независимая точность не вычислялись. "
             "Улучшение доступности не означает11 правильных ответов. Остаются причинные ошибки, пропуски условий/знаменателей, "
             "потеря релевантных страниц и drift при переводе. Требования LLM были только диагностикой.\n")
    f.save(out / "assessment.md", text.encode())
    f.verify(value["bindings"])
    f.manifest(out)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
