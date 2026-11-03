"""Source-check an external reference separately from frozen inference preparation."""

from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import gigachat_answer_smoke as files  # noqa: E402

POPPLER = Path(r"C:\Users\unive\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe")


def run(prepared: Path, output: Path) -> dict[str, Any]:
    import fitz

    if output.exists():
        raise FileExistsError(output)
    files.verify_manifest(prepared)
    contract = json.loads((prepared / "contract.json").read_bytes())
    files.verify(contract["input_bindings"])
    original = json.loads((prepared / "user_reference_original.json").read_bytes())
    case, = original["cases"]
    pdf = ROOT / case["source_pdf_path"]
    bindings = {**contract["input_bindings"], **files.bindings([Path(__file__), pdf, POPPLER,
                *[p for p in prepared.iterdir() if p.is_file()]])}
    with fitz.open(pdf) as document:
        texts = [page.get_text() for page in document]
    for text in texts:
        if "10.1021/ma502538k" not in text:
            raise ValueError("Unexpected reference PDF/DOI")
    observations = []

    def window(label: str, page: int, start: str, end: str, note: str) -> None:
        raw = texts[page - 1]
        a = raw.index(start)
        b = raw.index(end, a) + len(end)
        observations.append({"label": label, "pdf_page": page, "printed_page": raw.splitlines()[-1],
                             "start": a, "end": b, "exact_text": raw[a:b], "text_layer": "original",
                             "page_text_sha256": files.sha(raw.encode()), "original_pdf_path": str(pdf),
                             "original_pdf_sha256": files.sha(pdf.read_bytes()),
                             "assistant_scope_note": note, "origin": "assistant_source_check_not_user_gold_rewrite"})

    window("Sample form", 2, "2.1. Materials.", "The prepared Na+ form membranes were stored in deionized water\nuntil use.",
           "The study uses Na+ form prepared from Nafion NRE-212. Do not silently generalize to every ionic form.")
    window("NMP microgel interpretation", 5, "This result suggests", "dominated by the individual chains.",
           "Microgel is a model-based likely interpretation for2.5wt% NMP; competing Debye/network fits are discussed.")
    window("Glycerol dimensions", 6, "In glycerol at 2.5 wt %", "length of 150 Å.16",
           "22Å=2.2nm and150Å=15nm by assistant SI arithmetic;2.5wt% and citation16 must remain visible.")
    window("Large swollen clusters", 6, "For 2.5 wt % Naﬁon in a water/2-propanol mixture", "fuzzy interface.16",
           "The >200nm statement refers to the2.5wt% water/2-propanol1:1 volume-ratio dispersion.")
    window("Fixed-concentration solvent-ratio series", 7, "These changes in Naﬁon morphology", "ratio.",
           "Distinguish Figure3a solvent-ratio change at2.5wt% from evaporation/composition co-change in Figure2c.")
    window("Constant-ratio concentration control", 7, "To understand more about the concentration",
           "maintained; thus, mobilities of the backbone and side chains\nremains high.",
           "At fixed1:1 ratio, increasing concentration does not cause the lamellar ordering "
           "observed during composition-changing evaporation.")
    window("Gelation classes and exceptions", 4, "Three types of gels", "dispersion in Figure 1e,f.",
           "NMP/DMAc/DMF/DMSO show HR; NMF is an aprotic exception with IHIR-F. Water/monohydric-alcohol gives precipitation.")
    window("Figure4 caption", 8, "Figure 4.", "dispersion (IHIR-P).",
           "The schematic compares representative NMP, glycerol and water/2-propanol systems, not all solvents without qualification.")
    trace = json.loads((prepared / "trace.json").read_bytes())
    selected = json.loads((prepared / "articles.json").read_bytes())
    expected_selected = any(Path(a["original_pdf_path"]).resolve() == pdf.resolve() for a in selected)
    ref_article = {"title": "Origin of Toughness in Dispersion-Cast Nafion Membranes",
                   "authors": ["Yu Seung Kim", "Cynthia F. Welch", "Rex P. Hjelm", "Nathan H. Mack", "Andrea Labouriau", "E. Bruce Orler"],
                   "journal": "Macromolecules", "year": 2015, "abstract": None, "conclusions": None, "terms": None,
                   "original_pdf_path": str(pdf), "metadata_basis": "PDF header/DOI/footer source check; unextracted fields retained null",
                   "roles": ["user_reference_source"], "doi": "10.1021/ma502538k"}
    first = " ".join(texts[0].split())
    if any(author not in first for author in ref_article["authors"]):
        raise ValueError("Author header mismatch")
    articles = [{**article, "roles": ["selected_runtime_evidence"]} for article in selected]
    if not expected_selected:
        articles.append(ref_article)
    else:
        for article in articles:
            if Path(article["original_pdf_path"]).resolve() == pdf.resolve():
                article["roles"].append("user_reference_source")
    overlap = ["docs/evaluation_questions.yaml: q05_kim_dispersion_cast_toughness_2015",
               "docs/evaluation_questions_extended.yaml: qext009/qext010/qext011 Kim2015 retrieval cases",
               "tests/unit/test_cross_lingual_retrieval.py: related solution-casting morphology concepts"]
    output.mkdir(parents=True)
    (output / "source_pdf_views").mkdir()
    for page in range(2, 9):
        subprocess.run([str(POPPLER), "-f", str(page), "-l", str(page), "-scale-to", "1600", "-png", "-singlefile",
                        str(pdf), str(output / "source_pdf_views" / f"kim_p{page}")], check=True, capture_output=True)
    summary = {"user_reference_cases": 1, "source_observations": len(observations), "source_pages_rendered": 7,
               "reference_pdf_selected_by_runtime": expected_selected, "selected_works": len(selected),
               "tac_works_including_reference": len(articles), "native_request_bytes": contract["request_bytes"],
               "generation_reached": contract["generation_reached"], "new_real_model_oauth_calls": 0,
               "live_authorization": False, "slot_reservations": 0, "reference_passed_to_model": False,
               "model_answer": None, "scientific_scores": None, "scientific_acceptance": "not_established",
               "independence": "external_user_reference_method_undeclared_known_topic_exposure"}
    report = {"version": "external_user_reference_source_check_v0.1", "bindings": bindings, "user_original": original,
              "preparation_contract": contract, "trace": trace, "source_observations": observations,
              "known_topic_overlap": overlap, "articles": articles, "summary": summary,
              "reference_content_policy": "Original unchanged; assistant source notes separate and not independent labels"}
    files.verify(bindings)
    files.write(output / "report.json", report)
    render(report, output)
    (output / "source_snapshot").mkdir()
    files.save(output / "source_snapshot" / Path(__file__).name, Path(__file__).read_bytes())
    files.manifest(output)
    return summary


def render(report: dict[str, Any], output: Path) -> None:
    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    def detail(label: str, value: Any) -> str:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return '<details><summary>' + esc(label) + '</summary><pre>' + esc(text) + '</pre></details>'

    body = ('<!doctype html><html lang="ru"><meta charset="utf-8"><title>ARIADNE — внешний эталон1</title>'
            '<style>body{font:16px system-ui;margin:24px;color:#18333f}pre{white-space:pre-wrap;overflow-wrap:anywhere}'
            'table{border-collapse:collapse;width:100%}td,th{border:1px solid #abc;padding:8px;vertical-align:top}'
            '[hidden]{display:none!important}</style><h1>Первый пользовательский эталон и отдельная сверка</h1>'
            '<p>Эталон сохранён дословно. Нового ответа GigaChat нет; reference/ожидаемый PDF не переданы '
            'в retrieval или модель. Только вопрос прошёл текущую frozen /answer подготовку. '
            'Тема/источник Kim2015 уже встречаются в retrieval tests; unseen-topic independence не заявляется.</p>'
            + detail("Исходный вопрос, ответ и ссылка пользователя", report["user_original"])
            + '<h2>Отдельные source notes ассистента</h2>')
    for row in report["source_observations"]:
        url = Path(row["original_pdf_path"]).as_uri() + '#page=' + str(row["pdf_page"])
        body += ('<h3>' + esc(row["label"]) + '</h3><p>' + esc(row["assistant_scope_note"])
                 + ' <a href="' + esc(url) + '">Оригинал: PDFс.' + str(row["pdf_page"])
                 + ', журнальнаяс.' + esc(row["printed_page"]) + '</a></p>' + detail("Exact source/layer/offsets", row))
    body += ('<h2>Фактическая подготовка</h2>' + detail("Contract / нулевая live authorization", report["preparation_contract"])
             + '<p>Kim не выбран исходным runtime top-k в этом прогоне. Альтернативные источники могут содержать '
             'релевантные сведения; это наблюдение о выбранном evidence, не готовая оценка качества ещё отсутствующего ответа.</p>'
             + detail("Полный текущий trace без oracle injection", report["trace"])
             + detail("Известный topic/source overlap", report["known_topic_overlap"])
             + '<h2>TAC: все выбранные работы и источник эталона</h2><label>Поиск <input id="q" type="search"></label>'
             '<table id="tac"><thead><tr>' + ''.join('<th>' + h + '</th>' for h in
             ('Title', 'Authors', 'Journal', 'Year', 'Abstract', 'Conclusions', 'Terms', 'hyperlink to original file'))
             + '</tr></thead><tbody>')
    for article in report["articles"]:
        body += '<tr>'
        for key in ('title', 'authors', 'journal', 'year', 'abstract', 'conclusions', 'terms'):
            value = article.get(key)
            body += '<td>' + (detail("Полный текст / metadata", value) if value is not None else 'Неизвестно / не собрано') + '</td>'
        body += ('<td><a href="' + esc(Path(article["original_pdf_path"]).as_uri()) + '">Оригинальный PDF</a>'
                 + detail("Роли / provenance", article) + '</td></tr>')
    body += ('</tbody></table>' + detail("Итоги и ограничения", report["summary"])
             + '<script>document.getElementById("q").addEventListener("input",e=>{const s=e.target.value.toLowerCase();'
             'document.querySelectorAll("#tac tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(s))});'
             '</script></html>')
    files.save(output / "review.html", body.encode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    summary = run(args.prepared, args.output)
    if policy.denied:
        raise ValueError("Unexpected network attempt")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
