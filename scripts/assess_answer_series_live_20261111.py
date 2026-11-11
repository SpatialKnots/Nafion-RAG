"""Unblinded post-hoc source observations after closure; no independent accuracy scores."""

from __future__ import annotations

import json
import re

from scripts import gigachat_answer_smoke as f
from scripts import run_answer_series_live_20261111 as run

NOTES = {
    "Kondo_04": ("incomplete_reaction_coverage_and_term_drift",
        "0/18.7/41.5 кДж/моль совпали. Для F3MEE пропущены пониженная обратимая ёмкость и неполное подавление "
        "cointercalation. В описании DME написано «Li-солевой-графит», тогда как источник говорит Li–solvent–graphite."),
    "Nambu_02": ("main_conditions_agree_name_typo",
        "Реагенты/ацетонитрил/NaOH/около23%/две дистилляции/GC/>99.9% воспроизведены. В русском названии спирта "
        "опечатка «трифтроэтокси». Это не полная проверка химической номенклатуры."),
    "Nambu_03": ("main_order_agrees_temperature_statement_broader_than_literal_text",
        "Основной порядок FETFEE>ETFEE≈EFEE>DEE совпадает. Ответ распространяет линейное уменьшение на все "
        "исследованные растворители; буквальное предложение источника перечисляет FETFEE/EFEE/ETFEE. "
        "Поведение DEE этой текстовой привязкой не подтверждено; график заново не оцифрован."),
    "Nambu_04": ("requested_order_and_values_agree",
        "Порядок вязкости и все четыре энергии16.17/14.36/12.09/10.27 совпали с source respectively binding. "
        "В источнике энергии названы apparent; отдельной физической верификации модели Andrade не было."),
    "Nambu_10": ("unsupported_confirmation_status",
        "Около120 мА·ч/г на50-м цикле совпало. Ответ утверждает, что плёнка «включает» органофторсодержащие "
        "соединения/фторированные алкоксиды. Источник использует can form/may; подтверждённый химический "
        "состав из этого не следует. Запрошенное различие гипотезы и идентификации потеряно."),
    "Peng_01": ("incomplete_salt_conditions_and_TFEE_name_drift",
        "Наборы кодов растворителей и volume/mass ratios совпали. Во всех четырёх составах опущен1M LiPF6. "
        "Раскрытие TFEE как «тетрафторэтоксиметиловый эфир» не воспроизводит исходное "
        "1,2-bis(1,1,2,2-tetrafluoroethoxy)ethane. Сервер не исправлял native ответ."),
    "Peng_03": ("main_trends_agree_cell_and_epistemic_scope_caveats",
        "Низкая проводимость/повышенная вязкость/пониженная donor ability и лучшее электрохимическое поведение FFT "
        "отражены. Режим3C в источнике относится к LCO/Li half-cell; ответ не отделяет его явно от full-cell. "
        "Источник предлагает интерпретацию suggests/ought to; ответ передаёт предотвращение окисления как установленную причину."),
    "Peng_04": ("requested_voltage_ranges_agree",
        "Все три запрошенных диапазона совпали: LCO/Li3–4.6V, MCMB/Li0.01–2V, LCO/MCMB3–4.45V. "
        "Это проверка конкретного перечисления, не независимая научная приёмка."),
    "Peng_09": ("main_cathode_limitation_agrees",
        "Главный вывод о большей роли катодного ограничения для высоковольтной полной ячейки прямо присутствует "
        "в процитированном E1. Детального разбора состава EET/CEI ответ не даёт."),
}
PATTERNS = {
    "Kondo_04": [("E1", r"Li.solvent.graphite intercalation compounds.*?1\.11 nm"),
                 ("E1", r"In moderately solvating F3MEE.*?incomplete inhibition of Li.*?solvent cointercalation\.")],
    "Nambu_02": [("E1", r"We synthesized FETFEE from.*?yield of about 23%\."),
                 ("E1", r"FETFEE was puriﬁed.*?99\.9%.*?gas\s+chromatograph")],
    "Nambu_03": [("E2", r"The relative permittivities of FETFEE,.*?The relative permittivity of FETFEE was higher")],
    "Nambu_04": [("E2", r"FETFEE >\s*EFEE > ETFEE > DEE\."),
                 ("E2", r"The\s+apparent\s+activation\s+energy\s+was\s+determined.*?respectively\.")],
    "Nambu_10": [("E2", r"The discharge capacity in the EC.FETFEE system.*?50th cycle\."),
                 ("E2", r"The cathodic decomposition of the FETFEE.based.*?surface\s+ﬁlm\.")],
    "Peng_01": [("E1", r"1,2.Bis.*?\(TFEE, 99\.66%\)"),
                ("E1", r"The\s+base electrolyte was 1 M LiPF6.*?2\.2\s+Cell assembly")],
    "Peng_03": [("E2", r"Electrochemical properties of LCO/Li half cells.*?C-rate performance\."),
                ("E2", r"FFT\s+electrolyte also.*?restrict possible parasitic reaction between them")],
    "Peng_04": [("E2", r"The LCO/Li, MCMB/Li and LCO/MCMB cell were cycled.*?respectively,")],
    "Peng_09": [("E1", r"It is concluded that the electrochemical property.*?on the anode\.")],
}


def main():
    closed = run.read(run.BASE / "scope_closed_v01.json")
    run.require(closed["remaining_allowance"] == 0, "Assessment requires closed scope")
    output, duplicates = {}, []
    for cid, (category, note) in NOTES.items():
        trace = run.read(run.BASE / "prepared_v01" / cid / "trace.json")
        sources = {e["citation_id"]: e for e in trace["evidence"]}
        anchors = []
        for eid, pattern in PATTERNS[cid]:
            source = sources[eid]
            matches = list(re.finditer(pattern, source["text"], re.S))
            run.require(len(matches) == 1, "Missing/ambiguous post-hoc witness: " + cid + "/" + eid)
            match, = matches
            anchors.append({"citation_id": eid, "article_id": source["article_id"], "chunk_id": source["chunk_id"],
                "pages": [source["page_start"], source["page_end"]], "raw_sha256": f.sha(source["text"].encode()),
                "start": match.start(), "end": match.end(), "text": match[0]})
        output[cid] = {"category": category, "note": note, "source_witnesses": anchors,
                       "reviewer": "implementation_assistant_unblinded_posthoc", "score": None,
                       "scientific_accuracy": None, "native_output_modified": False}
    for row in closed["cases"]:
        cid = row["id"]
        api = run.read(run.BASE / "live" / cid / "api_response.json")
        if api["http_status"] != 502:
            continue
        native = run.read(run.BASE / "live" / cid / "response.bin")
        selected = json.loads(native["choices"][0]["message"]["content"])
        claims = selected["claims"]
        run.require(len(claims) > 1 and all(c == claims[0] for c in claims) and claims[0]["text"] == "F1",
                    "HTTP502 is not identical repeated F1")
        duplicates.append({"id": cid, "identical_F1_copies": len(claims), "citation_ids": claims[0]["citation_ids"]})
        output[cid] = {"category": "duplicate_ID_selection", "note":
            f"Модель повторила один F1 {len(claims)} раз; strict parser отклонил ответ. Повтора запроса/исправления native нет.",
            "reviewer": "implementation_assistant_unblinded_posthoc", "score": None,
            "scientific_accuracy": None, "native_output_modified": False}
    f.write(run.BASE / "posthoc_source_review_v01.json", output)
    f.write(run.BASE / "duplicate_ID_diagnosis_v01.json", {"cases": duplicates, "app_changed": False,
        "model_calls": 0, "causal_explanation_for_model_behavior": "not_established"})
    print(json.dumps({"raw_answer_cases_reviewed": len(NOTES), "source_witnesses": sum(len(v) for v in PATTERNS.values()),
                      "duplicate_ID_failures": len(duplicates), "scientific_accuracy": None}))


if __name__ == "__main__":
    main()
