from __future__ import annotations

import uuid

from app.retrieval.reranking import rerank_cross_lingual_results
from app.retrieval.search import SearchResult


def test_rerank_prefers_protected_token_and_query_coverage() -> None:
    weak = _result(
        uuid.UUID(int=1),
        "General Nafion paper",
        "Nafion membranes show conductivity in water.",
        ranks={"lexical_original": 1},
    )
    strong = _result(
        uuid.UUID(int=2),
        "Sanginov 2021",
        "Li-Nafion membranes with EC and SL show ionic conductivity.",
        ranks={"glossary_en_1": 8},
    )

    reranked = rerank_cross_lingual_results(
        [weak, strong],
        original_query="Как EC и SL влияют на ионную проводимость Li-Nafion?",
        query_language="ru",
        query_variants=[
            ("original", "Как EC и SL влияют на ионную проводимость Li-Nafion?"),
            ("glossary", "ionic conductivity ethylene carbonate sulfolane li-nafion"),
        ],
    )

    assert [result.title for result in reranked.results] == ["Sanginov 2021", "General Nafion paper"]
    assert reranked.metadata["reranked"] is True
    assert reranked.metadata["top_features"][0]["protected_matches"] >= 3  # type: ignore[index]


def test_rerank_uses_saturated_article_support() -> None:
    article_id = str(uuid.UUID(int=100))
    first = _result(
        uuid.UUID(int=1),
        "Dai 2017",
        "Casting solvent affects recast Nafion membranes.",
        article_id=article_id,
        ranks={"lexical_original": 5},
    )
    second = _result(
        uuid.UUID(int=2),
        "Dai 2017",
        "Annealing temperature changes vanadium permeability.",
        article_id=article_id,
        ranks={"semantic_multilingual": 7},
    )
    isolated = _result(
        uuid.UUID(int=3),
        "Unrelated paper",
        "Casting appears in a short reference list.",
        ranks={"lexical_original": 1},
    )

    reranked = rerank_cross_lingual_results(
        [isolated, first, second],
        original_query="Где исследовано влияние растворителя кастинга и температуры отжига на recast Nafion membranes?",
        query_language="ru",
        query_variants=[("original", "растворителя кастинга температуры отжига recast Nafion membranes")],
    )

    assert reranked.results[0].title == "Dai 2017"
    assert reranked.metadata["top_features"][0]["article_score"] > reranked.metadata["top_features"][2]["article_score"]  # type: ignore[index]


def test_rerank_prefers_title_phrase_match_over_loose_terms() -> None:
    loose = _result(
        uuid.UUID(int=1),
        "General EC SL notes",
        "Nafion membranes mention ethylene carbonate and sulfolane in a reference list.",
        ranks={"glossary_en_1": 1},
    )
    title_match = _result(
        uuid.UUID(int=2),
        "Influence of Mixing Temperature on the Physicochemical Properties",
        "Li-Nafion membrane plasticised with ethylene carbonate and sulfolane.",
        ranks={"glossary_en_1": 8},
    )

    reranked = rerank_cross_lingual_results(
        [loose, title_match],
        original_query="Какая работа изучает mixing temperature and physicochemical properties Li-Nafion?",
        query_language="mixed",
        query_variants=[("glossary", "mixing temperature physicochemical properties swelling degree")],
    )

    assert reranked.results[0].title == "Influence of Mixing Temperature on the Physicochemical Properties"
    assert reranked.metadata["top_features"][0]["title_phrase_matches"] >= 1  # type: ignore[index]


def test_rerank_maps_russian_highest_plasticizer_conductivity_terms() -> None:
    generic = _result(
        uuid.UUID(int=1),
        "Lithium salt background",
        "Lithium salts in carbonates have bipolar charge transport.",
        ranks={"glossary_ru_1": 1},
    )
    conductivity = _result(
        uuid.UUID(int=2),
        "Istomina 2021",
        (
            "Li-Nafion membrane plasticised with EC/SL binary plasticiser. "
            "The best transport properties of Li-Nafion provided EC/SL mixtures enriched "
            "with ethylene carbonate, and conductivity rapidly decreases with sulfolane."
        ),
        ranks={"glossary_en_2": 8},
    )

    reranked = rerank_cross_lingual_results(
        [generic, conductivity],
        original_query="В каких пластификаторах наибольшую проводимость дают Li-Nafion",
        query_language="ru",
        query_variants=[
            ("original", "В каких пластификаторах наибольшую проводимость дают Li-Nafion"),
            ("glossary", "ionic conductivity binary plasticiser li-nafion"),
        ],
    )

    assert reranked.results[0].title == "Istomina 2021"
    assert reranked.metadata["top_features"][0]["term_matches"] >= 4  # type: ignore[index]
    assert reranked.metadata["top_features"][0]["conductivity_plasticizer_bonus"] == 3  # type: ignore[index]


def test_rerank_prefers_specific_conductivity_table_over_background_article_support() -> None:
    article_id = str(uuid.UUID(int=100))
    background = _result(
        uuid.UUID(int=1),
        "Диссертация Чернюк С.Д.",
        "Li-Nafion применяют в ЛИА; растворы солей лития в карбонатах имеют биполярный перенос заряда.",
        article_id=article_id,
        ranks={"glossary_ru_1": 1},
    )
    table = _result(
        uuid.UUID(int=2),
        "Диссертация Чернюк С.Д.",
        (
            "Таблица 4.6 — Ионная проводимость мембраны Li-Nafion при 25 °C, "
            "пластифицированных растворителями различной природы. DMF, DMSO, NMP, "
            "NMF and DMAA show highest ionic conductivities."
        ),
        article_id=article_id,
        ranks={"original_ru_0": 8},
    )

    reranked = rerank_cross_lingual_results(
        [background, table],
        original_query="В каких пластификаторах наибольшую проводимость дают Li-Nafion",
        query_language="ru",
        query_variants=[("glossary", "ionic conductivity binary plasticiser li-nafion")],
    )

    assert reranked.results[0].chunk_id == table.chunk_id
    assert reranked.metadata["top_features"][0]["conductivity_plasticizer_bonus"] == 3  # type: ignore[index]


def test_rerank_prefers_plasticizer_conductivity_survey_evidence_over_ec_sl_background() -> None:
    ec_sl_background = _result(
        uuid.UUID(int=1),
        "Sanginov 2021",
        (
            "Li-Nafion membrane plasticised with EC/SL binary plasticiser. "
            "The best transport properties of Li-Nafion provided EC/SL mixtures enriched "
            "with ethylene carbonate."
        ),
        ranks={"glossary_en_2": 4},
    )
    survey_table = _result(
        uuid.UUID(int=2),
        "Диссертация Чернюк С.Д.",
        (
            "Таблица 4.6 — Ионная проводимость мембраны Li-Nafion при 25 °C, "
            "пластифицированных растворителями различной природы. DMF, DMSO, NMP, "
            "NMF and DMAA show highest ionic conductivities."
        ),
        ranks={"original_ru_0": 5},
    )

    reranked = rerank_cross_lingual_results(
        [ec_sl_background, survey_table],
        original_query="В каких пластификаторах наибольшую проводимость дают Li-Nafion",
        query_language="ru",
        query_variants=[("glossary", "ionic conductivity binary plasticiser li-nafion")],
    )

    assert reranked.results[0].chunk_id == survey_table.chunk_id
    assert "plasticizer_conductivity_survey" in reranked.metadata["query_intents"]  # type: ignore[operator]
    assert reranked.metadata["top_features"][0]["intent_match_bonus"] >= 6  # type: ignore[index]


def test_rerank_prefers_swelling_comparison_numeric_table() -> None:
    generic = _result(
        uuid.UUID(int=1),
        "General swelling discussion",
        "Li-Nafion and H-Nafion swelling degree is discussed in organic solvents.",
        ranks={"glossary_ru_1": 1},
    )
    table = _result(
        uuid.UUID(int=2),
        "Диссертация Чернюк С.Д.",
        (
            "Таблица 4.5 — Равновесная степень набухания и энтальпия набухания "
            "H-Nafion and Li-Nafion. Растворитель H-Nafion Li-Nafion αH αLi "
            "диметилсульфоксид 0.89 1.12 N,N-диметилформамид 0.72 1.15 "
            "N-метил-2-пирролидон 0.64 1.37"
        ),
        ranks={"glossary_ru_1": 5},
    )

    reranked = rerank_cross_lingual_results(
        [generic, table],
        original_query="In what solvents Li-Nafion has more swelling degree than H-Nafion?",
        query_language="en",
        query_variants=[("glossary", "степень набухания αH αLi H-Nafion Li-Nafion")],
    )

    assert reranked.results[0].title == "Диссертация Чернюк С.Д."
    assert reranked.metadata["top_features"][0]["numeric_table_bonus"] == 2  # type: ignore[index]


def test_rerank_prefers_mixing_temperature_swelling_intent() -> None:
    broad_transport = _result(
        uuid.UUID(int=1),
        "Kayumov 2021",
        "Li-Nafion membranes with ethylene carbonate and sulfolane have electrical conductivity.",
        ranks={"original_ru_0": 1},
    )
    target = _result(
        uuid.UUID(int=2),
        "Istomina 2021",
        (
            "Li-Nafion membrane plasticised with ethylene carbonate/sulfolane: influence "
            "of mixing temperature on the physicochemical properties. The study evaluated "
            "the influence of mixing temperature on the swelling degree of Li-Nafion in EC/SL."
        ),
        ranks={"glossary_en_2": 8},
    )

    reranked = rerank_cross_lingual_results(
        [broad_transport, target],
        original_query="Как температура смешения влияет на набухание литированной мембраны Nafion в EC/SL?",
        query_language="mixed",
        query_variants=[
            ("original", "Как температура смешения влияет на набухание литированной мембраны Nafion в EC/SL?"),
            ("glossary", "mixing temperature swelling degree Li-Nafion ethylene carbonate sulfolane"),
        ],
    )

    assert reranked.results[0].title == "Istomina 2021"
    assert "mixing_temperature_li_nafion" in reranked.metadata["query_intents"]  # type: ignore[operator]
    assert reranked.metadata["top_features"][0]["intent_match_bonus"] >= 4  # type: ignore[index]


def test_rerank_prefers_standalone_water_thermodynamics_article_over_reference_context() -> None:
    bibliography = _result(
        uuid.UUID(int=1),
        "Диссертация Чернюк С.Д.",
        (
            "References include Sorption in proton-exchange membranes and "
            "Thermodynamics of high polymer solutions in Nafion literature."
        ),
        doi=None,
        source_type="method",
        ranks={"original_en_0": 1},
    )
    standalone_article = _result(
        uuid.UUID(int=2),
        "Чернюк 2023",
        (
            "Термодинамика взаимодействия полиперфторсульфоновой кислоты Nafion с водой. "
            "Рассмотрены сорбции воды, параметр Флори-Хаггинса, энергия Гиббса и энтальпия."
        ),
        doi="10.31857/s2308112023700463",
        source_type="main_text",
        ranks={"glossary_ru_1": 8},
    )

    reranked = rerank_cross_lingual_results(
        [bibliography, standalone_article],
        original_query="Which Russian paper discusses Nafion-water sorption thermodynamics?",
        query_language="en",
        query_variants=[
            ("glossary", "набухание термодинамика взаимодействия вода водой"),
            ("glossary", "water sorption thermodynamic interaction"),
        ],
    )

    assert reranked.results[0].chunk_id == standalone_article.chunk_id
    assert "nafion_water_thermodynamics" in reranked.metadata["query_intents"]  # type: ignore[operator]
    assert reranked.metadata["top_features"][0]["intent_match_bonus"] > reranked.metadata["top_features"][1]["intent_match_bonus"]  # type: ignore[index]


def test_rerank_prefers_dissertation_li_thermodynamic_relaxation_evidence() -> None:
    english_reference = _result(
        uuid.UUID(int=1),
        "Sanginov 2021",
        "References mention thermodynamic stabilisation and a Nafion membrane.",
        doi="10.1016/j.electacta.2021.137914",
        source_type="main_text",
        ranks={"glossary_en_2": 2},
    )
    dissertation = _result(
        uuid.UUID(int=2),
        "Диссертация Чернюк С.Д.",
        (
            "Определить термодинамические характеристики взаимодействия мембран "
            "H-Nafion и Li-Nafion с растворителями и релаксационные свойства."
        ),
        source_type="main_text",
        ranks={"glossary_ru_1": 8},
    )

    reranked = rerank_cross_lingual_results(
        [english_reference, dissertation],
        original_query="How do lithium ions affect thermodynamic and relaxation properties of Nafion membranes?",
        query_language="en",
        query_variants=[("glossary", "ионы лития литиевая форма релаксационные свойства")],
    )

    assert reranked.results[0].chunk_id == dissertation.chunk_id
    assert "li_nafion_thermodynamic_relaxation" in reranked.metadata["query_intents"]  # type: ignore[operator]


def test_rerank_prefers_li_nafion_alcohol_enthalpy_evidence() -> None:
    background = _result(
        uuid.UUID(int=1),
        "Sanginov 2021",
        "Li-Nafion membranes were swollen with EC/SL mixtures and conductivity was measured.",
        doi="10.1016/j.electacta.2021.137914",
        ranks={"original_en_0": 3},
    )
    alcohol_enthalpy = _result(
        uuid.UUID(int=2),
        "Чернюк 2024",
        (
            "Водно-спиртовые смеси обеспечивают набухание Li-Nafion. "
            "Энтальпия взаимодействия литированной мембраны со спиртовыми растворами отрицательна."
        ),
        source_type="main_text",
        ranks={"glossary_ru_1": 8},
    )

    reranked = rerank_cross_lingual_results(
        [background, alcohol_enthalpy],
        original_query="What is the enthalpy of interaction of lithiated Nafion with aqueous alcohol solutions?",
        query_language="en",
        query_variants=[("glossary", "вода водой ионы лития литиевая форма")],
    )

    assert reranked.results[0].chunk_id == alcohol_enthalpy.chunk_id
    assert "li_nafion_alcohol_enthalpy" in reranked.metadata["query_intents"]  # type: ignore[operator]


def test_rerank_prefers_russian_ec_sl_diglyme_conductivity_article() -> None:
    english_ec_sl = _result(
        uuid.UUID(int=1),
        "Sanginov 2021",
        "Li-Nafion conductivity was measured in ethylene carbonate and sulfolane mixtures.",
        doi="10.1016/j.electacta.2021.137914",
        ranks={"original_en_0": 1},
    )
    russian_diglyme = _result(
        uuid.UUID(int=2),
        "Каюмов 2021",
        (
            "Lithium-conducting Nafion membranes plasticized by binary and ternary mixtures "
            "in the sulfolane-ethylene carbonate-diglyme system show electrical conductivity."
        ),
        doi="10.31857/s0424857021060049",
        source_type="main_text",
        ranks={"glossary_en_2": 8},
    )

    reranked = rerank_cross_lingual_results(
        [english_ec_sl, russian_diglyme],
        original_query=(
            "Which Russian paper discusses electrical conductivity of lithium-conducting "
            "Nafion membranes with sulfolane ethylene carbonate and diglyme?"
        ),
        query_language="en",
        query_variants=[
            ("glossary", "этиленкарбонат сульфолан диглим ионная проводимость"),
            ("glossary", "ethylene carbonate sulfolane diglyme electrical conductivity"),
        ],
    )

    assert reranked.results[0].chunk_id == russian_diglyme.chunk_id
    assert "russian_ec_sl_diglyme_conductivity" in reranked.metadata["query_intents"]  # type: ignore[operator]


def _result(
    chunk_id: uuid.UUID,
    title: str,
    text: str,
    *,
    article_id: str | None = None,
    doi: str | None = None,
    source_type: str = "body",
    ranks: dict[str, int] | None = None,
) -> SearchResult:
    return SearchResult(
        article_id=article_id or str(uuid.UUID(int=chunk_id.int + 100)),
        chunk_id=str(chunk_id),
        title=title,
        doi=doi,
        page_start=1,
        page_end=1,
        source_type=source_type,
        snippet=text,
        full_text=text,
        score=1.0,
        retrieval_method="hybrid_cross_lingual_rrf",
        method_ranks=ranks or {},
    )
