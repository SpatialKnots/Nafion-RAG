from __future__ import annotations

from types import SimpleNamespace

from app.classification.rules import classify_source_type, detect_sections, extract_tags


def test_extract_tags_detects_scientific_entities() -> None:
    text = "Li-Nafion membrane was saturated with NMP. Ionic conductivity was measured by EIS. TGA-MS was also performed."

    tags = {(tag.tag_type, tag.tag_value) for tag in extract_tags(text)}

    assert ("ion_form", "Li") in tags
    assert ("solvent", "NMP") in tags
    assert ("method", "conductivity") in tags
    assert ("method", "EIS") in tags
    assert ("method", "TGA-MS") in tags
    assert ("sample_type", "membrane") in tags
    assert ("evidence_type", "method_description") in tags


def test_classify_source_type_detects_table_figure_and_method() -> None:
    assert classify_source_type("Table 2. Conductivity values") == "table_caption"
    assert classify_source_type("Sample 1 2 3 4\nA 5 6 7 8\nB 6 7 8 9\nC 7 8 9 10\nD 8 9 10 11") == "table"
    assert classify_source_type("Fig. 3. Temperature dependence of conductivity.") == "figure_caption"
    assert classify_source_type("The membranes were prepared and conductivity was measured.") == "method"
    assert classify_source_type("Nafion is a perfluorosulfonated ionomer.") == "main_text"


def test_classify_source_type_detects_russian_caption_and_formula_blocks() -> None:
    assert classify_source_type("\u0422\u0430\u0431\u043b\u0438\u0446\u0430 2. \u0414\u0430\u043d\u043d\u044b\u0435") == "table_caption"
    assert classify_source_type("IEC = nSO3H / m\nlambda = 14\nplain text") == "formula_block"


def test_classify_source_type_detects_russian_film_casting_methods() -> None:
    text = "Раствор Nafion готовили в НМП, затем проводили отлив пленок и сушили образцы."

    assert classify_source_type(text) == "method"


def test_classify_source_type_does_not_treat_computational_methods_as_experimental() -> None:
    text = "МЕТОДИКА РАСЧЕТОВ: квантово-химические расчеты проводили в программном продукте GAUSS."

    assert classify_source_type(text) == "main_text"


def test_detect_sections_from_page_headings() -> None:
    pages = [
        SimpleNamespace(page_number=1, text="Abstract\nShort summary\nIntroduction\nBackground"),
        SimpleNamespace(page_number=2, text="Experimental\nThe membranes were prepared."),
        SimpleNamespace(page_number=4, text="Conclusions\nFinal statements."),
    ]

    sections = detect_sections(pages)  # type: ignore[arg-type]

    assert [section.normalized_name for section in sections] == ["abstract", "introduction", "experimental", "conclusions"]
    assert sections[0].page_start == 1
    assert sections[-1].page_end == 4
