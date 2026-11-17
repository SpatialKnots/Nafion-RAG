"""Exposed post-hoc qualitative comparison, with exact source and prompt witnesses."""

from __future__ import annotations

import html
import json
import re
from collections import Counter
from pathlib import Path

from app.generation.providers import _clean_generation_evidence_text
from scripts import run_fan_doi_besenhard_answers_20261113 as run

f, profile = run.f, run.profile
NOTES = {
    'F1': (
        'provider_abstained',
        (
            'Модель отказалась. Пять критериев прямо перечислены в Methods PDF9; ниже отдельно проверено, по'
            'пал ли этот абзац в выбранный контекст.'
        ),
    ),
    'F2': (
        'core_supported',
        (
            'Сохранены эфиры/карбонаты, приблизительные 95–99%/<90% и 4.0/4.3 В. Это обзор классов в Introdu'
            'ction, не единый идентичный опыт всех составов.'
        ),
    ),
    'F3': (
        'partial_or_wording_issue',
        (
            '341/290/266 мкм и ~10 мкм совпадают. Но non-dendritic mounds превращены в бессмысленные «нелине'
            'йные монтированные структуры»; исходная фольга 250 мкм не названа.'
        ),
    ),
    'F4': (
        'partial_or_wording_issue',
        (
            '~1 мкм и интерпретация LiF-rich layer подтверждаются; ToF-SIMS действительно назван в Methods P'
            'DF9. Пропущен EC/DMC comparator >15 мкм, поэтому сравнение неполно.'
        ),
    ),
    'F5': (
        'partial_or_wording_issue',
        (
            'Приведены только >99.2% и ~80%. Не названы DMC ~20%, carbonate/ether 60–85%, FEC/DMC ~95% и усл'
            'овия 0.2 мА/см²/1 мА·ч/см².'
        ),
    ),
    'F6': (
        'rewrite_rejected',
        (
            'Ответ не запрашивался: отдельное консервативное решение смыслового review перевода. Не считать '
            'ошибкой ответа GigaChat.'
        ),
    ),
    'F7': (
        'provider_abstained',
        (
            'Модель отказалась. Основной текст PDF3 содержит 170 мА·ч/г при 2C и Cu/NMC811 78 мА·ч/г после 3'
            '0 циклов/60-fold; Supplementary не требуются для этих явно приведённых величин.'
        ),
    ),
    'F8': (
        'substantive_discrepancy',
        (
            'Подменена величина и объект: 10.7/2.4/4.0 — F/O в катодной CEI на LCP, а не содержание F в сост'
            'авах электролитов. Для электролитов текст даёт 22/1.8/0 M. Это два разных source frames.'
        ),
    ),
    'F9': (
        'partial_or_wording_issue',
        (
            'Верно передан только порядок энергетической выгодности. Запрошенные четыре DFT энергии −2.10/−0'
            '.19/−0.28/+0.11 эВ отсутствуют, хотя они есть в Fig6 и извлечённом тексте.'
        ),
    ),
    'F10': (
        'core_supported',
        (
            'Ключевой запрет категорического вывода передан: ring opening FEC•(-H) может давать газ, реакция'
            ' медленная. Дополнительная рекомендация малого содержания FEC из эталона не названа.'
        ),
    ),
    'D1': (
        'core_supported',
        (
            'Основная цель — снизить вязкость/концентрацию без потери окислительной стойкости — передана. По'
            'дробности низкого DMC/Li и сольватации не развёрнуты.'
        ),
    ),
    'D2': (
        'core_supported',
        (
            '8.67 моль/кг, DMC/Li=1.28 и 310 мПа·с совпадают. Температура/приближённость не обозначены. Отде'
            'льное замечание к reference hint: прямое упоминание 310 мПа·с находится на PDF6, а не только PD'
            'F3–4.'
        ),
    ),
    'D3': (
        'core_supported',
        (
            '916/около934 см⁻¹ и ~96% при 8.67 моль/кг соответствуют Raman analysis. В тексте также есть сме'
            'щение вершины связанного DMC к936 см⁻¹; формулировка 934–936 полнее.'
        ),
    ),
    'D4': (
        'provider_abstained',
        (
            'Модель отказалась. PDF4 содержит сдвиг полос 766/774/783 см⁻¹ к большим частотам и увеличение i'
            'onic association; наличие этого абзаца в prompt проверено отдельно.'
        ),
    ),
    'D5': (
        'core_supported',
        (
            'Все шесть процентов и соответствие трём концентрациям совпадают с Table1: CE82.6/86.5/88.9, ret'
            'ention82.2/90.0/92.2. Table1 визуально проверена.'
        ),
    ),
    'D6': (
        'partial_or_wording_issue',
        (
            'Направление HFE/TFEE передано, но не приведены 43.8/44.6/55.8%. «Примерно10%» есть в авторском '
            'тексте; без basis нельзя считать это точным относительным расчётом из Table2.'
        ),
    ),
    'D7': (
        'core_supported',
        (
            '3.6 мПа·с,1.52 моль/кг,DMC:HFE1:1по объёму,DMC/Li3.00 совпадают. Ответ не утверждает, что перех'
            'од310→3.6 выполнен при неизменной концентрации.'
        ),
    ),
    'D8': (
        'substantive_discrepancy',
        (
            'В ответ о HFE50→67об.% перенесена vulnerability TFEE >4.5В из соседнего эксперимента. Пропущены'
            ' HFE solubility/miscibility,0.73 моль/кг и DMC/Li3.96; причины разных составов смешаны.'
        ),
    ),
    'D9': (
        'substantive_discrepancy',
        (
            'Запрошенное значение после50циклов —186 мА·ч/г и93.4%. Ответ заменяет его приблизительным200 мА'
            '·ч/г и не сообщает retention. Source paragraph с186/93.4 визуально проверен.'
        ),
    ),
    'D10': (
        'withheld_by_guard',
        (
            'Доставленный ответ удержан finite guard, это не отказ модели. Native правильно относит784Вт·ч/к'
            'г к NCM523 cathode и называет volatility/1.52molkg; интегрирование кривых и точная mass basis н'
            'е разъяснены. Формулировка DMC/Li<3 встречается в источнике, несмотря на состав3.00. Guard не у'
            'станавливал научную ошибку.'
        ),
    ),
    'B1': (
        'core_supported',
        (
            'Числа Li3862/Na1166/Mg2205 и причина выбора лёгких металлов совпадают с Table1. Единица «Ах/кг»'
            ' в русском ответе типографически испорчена; в PDF написано Ahkg−1, то есть А·ч/кг.'
        ),
    ),
    'B2': (
        'rewrite_rejected',
        (
            'Ответ не запрашивался: Li→lithium нарушил frozen literal-ID contract, без исправления или повто'
            'рной отправки.'
        ),
    ),
    'B3': (
        'rewrite_rejected',
        (
            'Ответ не запрашивался: Li→lithium нарушил frozen literal-ID contract. Это не доказанная химичес'
            'кая ошибка перевода.'
        ),
    ),
    'B4': (
        'core_supported',
        (
            'Верно переданы блокирующая пассивация Mg и кинетически затруднённый перенос Mg²⁺.'
        ),
    ),
    'B5': (
        'core_supported',
        (
            'Класс organohaluminate, Mg(AlCl2BuEt)2/THF/glymes и недостаточная oxidation stability Grignard '
            'согласуются с PDF3. Название класса по-русски написано неудачно; формула и область сохраняются.'
        ),
    ),
    'B6': (
        'substantive_discrepancy',
        (
            'В PDF3 напечатан диапазон1.3–1.0В, а raw extraction и actual prompt содержат1.3 ± 1.0В. Ответ п'
            'овторил искажение как ±.122А·ч/кг и>2000циклов верны; сравнение122 относится к Li-ion cathodes,'
            ' не массе всей батареи.'
        ),
    ),
    'B7': (
        'partial_or_wording_issue',
        (
            'Pb-acid/Ni-Cd и экологический аргумент переданы. Не раскрыты proposed >60Вт·ч/кг, сравнение Li-'
            'ion120–150 и Ni-MH как возможный true competitor; прогнозный статус сглажен.'
        ),
    ),
    'B8': (
        'rewrite_rejected',
        (
            'Ответ не запрашивался: Mg→magnesium нарушил frozen literal-ID contract. Raw перевод сохранён, н'
            'е ремонтировался.'
        ),
    ),
    'B9': (
        'core_supported',
        (
            'Верно отличена conversion MO→M+Li2O от intercalation/alloying и сохранено условие нанодисперсно'
            'сти для обратной реакции. Слова об активности Li2O относятся к этому nanocomposite context, не '
            'к любому bulk Li2O.'
        ),
    ),
    'B10': (
        'partial_or_wording_issue',
        (
            'Первичные потери и hysteresis до1В переданы. Пропущены600/372А·ч/кг с mass basis, возможное пов'
            'торное образование SEI и unknown long-term effects; причинная формулировка о необратимости чрез'
            'мерно сжата.'
        ),
    ),
}
# Exact raw-source locators, never answer repair or runtime normalization.
SPEC = {
    "F1": [("Fan",9,r"At least five",0,570)],
    "F2": [("Fan",1,r"Early investigations",0,1150)],
    "F3": [("Fan",2,r"non-dendritic",320,520)],
    "F4": [("Fan",3,r"Almost all",120,900),("Fan",9,r"ToF-SIMS",150,300)],
    "F5": [("Fan",2,r"Coulombic efficiencies of",150,850)],
    "F7": [("Fan",3,r"A reversible capacity of\s+170",100,850)],
    "F8": [("Fan",5,r"22\s*M",190,480),("Fan",7,r"F/O ratio",230,500)],
    "F9": [("Fan",6,r"[–−-]2\.10",20,600)],
    "F10": [("Fan",9,r"gas generation",130,330)],
    "D1": [("Doi",2,r"To reduce the viscosity",100,850)],
    "D2": [("Doi",6,r"310",80,250),("Doi",4,r"DMC/Li\+=1.28",100,250)],
    "D3": [("Doi",4,r"96\s*%",150,460)],
    "D4": [("Doi",4,r"bands at 766",230,730)],
    "D5": [("Doi",5,r"Table 1\.\s+Charge, discharge",0,1600)],
    "D6": [("Doi",6,r"43\.8",280,430),("Doi",7,r"about 10",220,320)],
    "D7": [("Doi",6,r"3\.6",240,350)],
    "D8": [("Doi",6,r"3\.96",350,250),("Doi",7,r"vulnerable TFEE",170,600)],
    "D9": [("Doi",7,r"186",190,530)],
    "D10": [("Doi",7,r"784",220,160),("Doi",8,r"volatile",180,500)],
    "B1": [("Besenhard",1,r"3862",180,330)],
    "B4": [("Besenhard",3,r"transport of Mg",160,450)],
    "B5": [("Besenhard",3,r"Mg\(AlCl2R1R2\)2",650,1100)],
    "B6": [("Besenhard",3,r"1\.3\s*±\s*1\.0",220,470)],
    "B7": [("Besenhard",3,r"60\s*Wh",200,950),("Besenhard",4,r"true competitor",250,330)],
    "B9": [("Besenhard",5,r"in most part electrochemically active",400,1100)],
    "B10": [("Besenhard",5,r"1 V",700,1600),("Besenhard",4,r"372",180,220)],
}


def main():
    closure = run.read(run.BASE / "scope_closed_v01.json")
    run.require(closure["remaining_model_allowance"] == closure["remaining_oauth_allowance"] == 0, "Close scope first")
    f.verify_manifest(run.BASE / "review_v01")
    report = run.read(run.BASE / "review_v01/report.json")
    run.require(set(NOTES) == set(profile.baseline.IDS), "Incomplete qualitative review")
    pages = {(p["article"], p["pdf_page"]): p for p in run.read(run.BASE / "source_review_v01/fresh_pages.json")["pages"]}
    rows, anchors = [], []
    for case in report["cases"]:
        cid, (category, note) = case["id"], NOTES[case["id"]]
        prepared = profile.BASE / "prepared_v01" / cid
        selected = run.read(prepared / "trace.json")["evidence"] if (prepared / "trace.json").exists() else []
        wire = run.BASE / "live" / cid / "request.json"
        prompt = json.loads(wire.read_bytes())["messages"][1]["content"] if wire.exists() else ""
        claims = case.get("api", {}).get("body", {}).get("answer", {}).get("claims", [])
        cited = {x for c in claims for x in c["citation_ids"]}
        case_anchors = []
        for label, page, pattern, before, after in SPEC.get(cid, []):
            source = pages[label, page]
            matches = list(re.finditer(pattern, source["text"], re.I))
            run.require(bool(matches), "Source locator missing: " + cid + " / " + pattern)
            match = matches[0]
            start, end = max(0, match.start() - before), min(len(source["text"]), match.end() + after)
            quote = source["text"][start:end]
            normalized = _clean_generation_evidence_text(quote)
            ids = [e["citation_id"] for e in selected if re.search(pattern, e["text"], re.I)]
            anchor = {"id": cid, "article": label, "pdf_page": page, "original_pdf_path": source["original_pdf_path"],
                "original_pdf_sha256": source["original_pdf_sha256"], "page_text_sha256": source["text_sha256"],
                "raw_start": start, "raw_end": end, "raw_quote": quote, "locator_pattern": pattern,
                "selected_citations_with_locator": ids, "cited_citations_with_locator": sorted(set(ids) & cited),
                "whole_quote_in_actual_prompt": bool(prompt) and normalized in prompt,
                "prompt_transform": "existing _clean_generation_evidence_text; no scientific repair"}
            anchors.append(anchor)
            case_anchors.append(anchor)
        rows.append({"id": cid, "category": category, "note": note, "score": None,
                     "reviewer": "implementation_assistant_exposed_posthoc", "anchors": case_anchors})
    summary = {"cases": len(rows), "categories": dict(Counter(x["category"] for x in rows)),
        "raw_source_witnesses": len(anchors), "independent_accuracy": None, "numeric_score": None,
        "rubric_status": "supplied rubric not prospectively adopted as scientific acceptance score",
        "new_model_calls": 0, "new_oauth_calls": 0, "visual_source_pages_reviewed": 6,
        "diagnostics": "Doi PyMuPDF stream/colorspace warnings preserved; relevant pages also rendered with Poppler",
        "limitations": "Source witnesses and qualitative notes are exposed assistant review, not general semantic validation"}
    output = run.BASE / "assessment_v01"
    output.mkdir(exist_ok=False)
    f.write(output / "assessment.json", {"summary": summary, "cases": rows, "anchors": anchors})
    parts = ['<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE: содержательная сверка</title>',
        '<style>body{font:16px/1.5 system-ui;max-width:1450px;margin:30px auto;padding:0 20px}',
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f5f8;padding:12px}',
        'section{border-top:1px solid #aab;margin-top:22px}summary{cursor:pointer}</style>',
        '<h1>Содержательная сверка реальных ответов</h1><p>30 вопросов;22 выданных ответа,3 отказа модели,1 удержанный '
        'ответ,4 отклонённых перевода. Ни текст модели, ни пользовательские эталоны не исправлялись. '
        'Это предварительная оценка знакомого с набором ассистента, не независимая scientific accuracy.</p>',
        '<a href="' + (run.BASE / 'review_v01/review.html').as_uri() + '">Полные исходные результаты</a>',
        '<pre>' + html.escape(json.dumps(summary, ensure_ascii=False, indent=2)) + '</pre>']
    originals = {x["id"]: x for x in report["cases"]}
    for row in rows:
        case = originals[row["id"]]
        answer = case.get("api", {}).get("body", {}).get("answer", {}).get("answer")
        parts.append('<section><h2>' + row["id"] + ' — ' + html.escape(case["question_original"]) + '</h2><p><b>'
            + row["category"] + '</b>: ' + html.escape(row["note"]) + '</p><pre>'
            + html.escape(answer or 'Ответ пользователю не выдан') + '</pre><details><summary>Исходный эталон</summary><pre>'
            + html.escape(case["reference_answer_verbatim"]) + '</pre></details>')
        for anchor in row["anchors"]:
            link = Path(anchor["original_pdf_path"]).as_uri() + '#page=' + str(anchor["pdf_page"])
            parts.append('<details><summary>Source witness: PDF ' + str(anchor["pdf_page"]) + '</summary><a href="'
                + link + '">Оригинальная страница</a><pre>' + html.escape(anchor["raw_quote"]) + '</pre>'
                + '<p>Locator в выбранных citations: ' + html.escape(str(anchor["selected_citations_with_locator"]))
                + '; целая цитата в prompt: ' + str(anchor["whole_quote_in_actual_prompt"]) + '</p></details>')
        parts.append('</section>')
    parts.append('<h2>Визуальная сверка источников</h2>')
    for image in sorted((run.BASE / "source_review_v01").glob("*.png")):
        parts.append('<details><summary>' + html.escape(image.name) + '</summary><img style="max-width:100%" src="'
                     + image.as_uri() + '"></details>')
    parts.append('</html>')
    f.save(output / "review.html", ''.join(parts).encode())
    f.save(output / "executed_script.py", Path(__file__).read_bytes())
    f.write(output / "bindings.json", f.bindings([Path(__file__), run.BASE / "review_v01/manifest.json",
        run.BASE / "scope_closed_v01.json", run.BASE / "source_review_v01/fresh_pages.json",
        *sorted((run.BASE / "source_review_v01").glob("*.png"))]))
    f.manifest(output)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
