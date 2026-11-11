"""Post-hoc exposed scientific cautions and exact cited-source witnesses for v0.2."""

import json
import re
from pathlib import Path

from app.generation.providers import _clean_generation_evidence_text
from scripts import gigachat_answer_smoke as f
from scripts import run_query_rewriting_v02_20261110 as run


def main():
    base = run.BASE
    if json.loads((base / "answers_closed_v01.json").read_bytes())["remaining_allowance"]:
        raise ValueError("Answer scope must close")
    f.verify_manifest(base / "review_v01")
    report = json.loads((base / "review_v01/report.json").read_bytes())
    notes = {
        "Satoh_01": "Коды TFEME/TFEMEE и EME/EMEE перечислены, но развёрнутые химические названия в ответе искажены. "
                    "Например, methoxyethane превращено в метоксиметан. Это не полностью корректный химический ответ.",
        "Satoh_02": "Смысловой отказ: diethers/triethers заменены на dialkyl/trialkyl ethers; перевод не исправлялся вручную.",
        "Satoh_03": "Направление изменения и исходная плотность EME указаны, но требуемая плотность TFEME1.1508 не названа. "
                    "По полноте чисел это хуже v0.1, несмотря на наличие значения в source.",
        "Satoh_04": "Основной механизм donor ability/solvation/dissociation теперь восстановлен по E4. "
                    "Добавка про общую подвижность ионов отдельно не проверена; полного научного принятия нет.",
        "Satoh_05": "Четыре приблизительных потенциала с веществами/отсчётом сохранены; LSV/25°C/5mV/s указаны по источнику.",
        "Satoh_06": "60%/30циклов указаны, но сравнение20%/15циклов и явное EC–эфир условие пропущены.",
        "Satoh_07": "Существенная ошибка: ответ говорит об идентификации продуктов, тогда как цитируемый текст явно "
                    "содержит not been identified и лишь possible organofluorine compounds. Предположение подано как идентификация.",
        "Satoh_08": "Exact-input reuse v0.1, не новый ответ. Четыре энергии/единицы ранее совпали с источником.",
        "Satoh_09": "Тренды температуры/вязкости/проводимости переданы; оговорка об отсутствии простой обратной "
                    "пропорциональности всё ещё отсутствует.",
        "Satoh_10": "EC–TFEME и сравнение с EC–EME явно восстановлены; эффект замедления потери ёмкости изложен неполно.",
        "Fan_01": "Exact-input reuse v0.1. Сохранились неверное развёрнутое название HFE и неполная/неподтверждённая привязка функций.",
        "Fan_02": "Модель снова отказалась: нужная PDF2 не отобрана. Требуется изменение retrieval, не нормализации полей.",
        "Fan_03": "Основные три CE и привязка к аноду/катодам совпадают; знак > для анода и различие условий сглажены.",
        "Fan_04": "90%/450циклов и93%/1000циклов с правильными ячейками сохранены.",
        "Fan_05": "Существенная ошибка SEI/CEI: сведения о катодной CEI (CFx/POxFy,5–10nm) приписаны SEI. "
                  "Указанный E2 содержит CEI on LCP; запрошенная LiF-rich SEI/дендриты не раскрыта корректно.",
        "Fan_06": "Exact-input reuse v0.1: F/O comparison есть, CFx/POxFy и толщина полного эталона не названы.",
        "Fan_07": "Перевод hold исправлен, но модель отказалась: PDF5 с объяснением не отобрана.",
        "Fan_08": "Появился ответ про flammability tests и DSC. Основной текст подтверждает методы; "
                  "Supplementary figures/videos отсутствуют и самостоятельно не проверялись.",
        "Fan_09": "Новый provider output пустой/no assistant role, API502. Не ремонтировался и не повторялся.",
        "Fan_10": "Новый provider output пустой/no assistant role, API502; прежний неполный ответ v0.1 сохранён отдельно.",
    }
    patterns = {
        "Satoh_07": r"Although the\s+organofluorine compounds have not been identified.*?lithium alkoxides\.",
        "Fan_05": r"XPS confirmed.*?formed by the all-fluorinated electrolyte on LCP",
        "Satoh_04": r"This effect results\s+in the decreased solvation.*?lower degree of ionic\s+dissociation\.",
        "Fan_08": r"eval-?\s*uated by differential scanning calorimetry.*?much higher temperature for the all-\s*fluorinated electrolyte\.",
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
                match = re.search(patterns[cid], e["text"], re.S | re.I)
                if not match:
                    continue
                native_path = Path(c["effective_native_folder"]) / "request.json"
                prompt = json.loads(native_path.read_bytes())["messages"][1]["content"]
                quote = _clean_generation_evidence_text(match[0])
                start = prompt.find(quote)
                if start < 0:
                    raise ValueError("Cited witness absent from actual prompt")
                anchors.append({"id": cid, "citation_id": e["citation_id"], "chunk_id": e["chunk_id"],
                    "article_id": e["article_id"], "PDF_range": [e["page_start"], e["page_end"]],
                    "raw_text_sha256": f.sha(e["text"].encode()), "raw_start": match.start(), "raw_end": match.end(),
                    "raw_quote": match[0], "actual_prompt_start": start, "actual_prompt_end": start + len(quote),
                    "actual_quote": quote, "transform": "existing whitespace collapse only"})
                found = True
                break
            if not found:
                raise ValueError("Declared source witness unresolved: " + cid)
        rows.append({"id": cid, "note": notes[cid], "score": None,
                     "reviewer": "implementation_assistant_exposed_posthoc", "scientific_validity": "not_evaluated"})
    gained = [c["id"] for c in report["cases"] if c["v01_answer"].get("status") != "answered"
              and c["answer"].get("status") == "answered"]
    lost = [c["id"] for c in report["cases"] if c["v01_answer"].get("status") == "answered"
            and c["answer"].get("status") != "answered"]
    out = base / "assessment_v01"
    value = {"cases": rows, "anchors": anchors, "newly_answered_vs_v01": gained, "lost_vs_v01": lost,
             "independent_accuracy": None, "score": None,
             "bindings": f.bindings([Path(__file__), base / "review_v01/manifest.json", base / "answers_closed_v01.json"])}
    f.verify(value["bindings"])
    out.mkdir(exist_ok=False)
    f.write(out / "assessment.json", value)
    text = ("# Query rewriting v0.2: содержательная сверка\n\n"
            "Доступных ответов4→11→15/20. V0.2:12 новых ответов+3 exact-input reuse, "
            "2 model abstentions,2 provider/API502,1 meaning rejection. Это не15 корректных ответов.\n\n"
            "[Все20 сравнений и исходные ответы](../review_v01/review.html) · "
            "[Raw→actual prompt witnesses](assessment.json)\n\n"
            "Существенные новые ошибки: Satoh07 превращает предположение в идентификацию; "
            "Fan05 переносит катодную CEI на SEI. Satoh01 искажает развёрнутые химические имена. "
            "Эти случаи нельзя принимать как научно корректные.\n\n|Вопрос|Предварительная оценка|\n|---|---|\n")
    text += ''.join('|'+r['id']+'|'+r['note']+'|\n' for r in rows)
    text += ("\nExposed-agent review, не независимая экспертная оценка. Исходные raw/API ответы сохранены без ремонта. "
             "Шаги3–4 (retrieval coverage/проверка научного статуса и полноты) остаются необходимыми; "
             "default app не менялся.\n")
    f.save(out / "assessment.md", text.encode())
    f.manifest(out)
    print(json.dumps({"cases": len(rows), "source_witnesses": len(anchors), "gained": gained, "lost": lost, "new_model_calls": 0}))


if __name__ == "__main__":
    main()
