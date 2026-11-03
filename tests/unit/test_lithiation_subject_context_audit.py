"""Explicit subject proposals must preserve material, form and operation boundaries."""

import pytest

from scripts import lithiation_operation_audit as operation
from scripts.lithiation_subject_context_audit import audit
from scripts.run_lithiation_operation_audit import validate_spans

HEADING = "2.1. Подготовка мембран Nafion\n\n"
BODY = "Проводили литирование ионным обменом в 2.0 М LiOH при 60 °C в течение 120 мин."
CAPTION = "Рисунок 2.1 — Схема подготовки мембран Nafion: очистка мембран (а); литирование мембраны (б)\n\n"
REF_BODY = "На втором этапе (см. рисунок 2.1б) проводили литирование ионным обменом в LiOH."


def body_attempt(result):
    return result["attempts"][-1]


def candidates(result):
    return [link for attempt in result["attempts"] for link in attempt["links"]
            if link["state"] == "context_subject_candidate_unverified"]


@pytest.mark.parametrize("heading,body", [
    (HEADING, BODY),
    ("2.2.1. Литирование водно-спиртовой дисперсии Nafion\n\n", "Литирование проводили раствором LiOH."),
    ("2.1 Preparation of Nafion membranes\n\n", "Lithiation was performed in LiOH for 2 hours."),
    ("2.1 Preparation of Naﬁon membranes\n\n", "Lithiation was performed in LiOH."),
])
def test_nearest_explicit_heading_can_propose_subject_without_proving_owner(heading, body):
    text = heading + body
    result = audit(text)
    assert body_attempt(result)["state"] == "context_subject_candidate_unverified"
    assert candidates(result)[-1]["kind"] == "nearest_numbered_heading"
    assert result["baseline"] == operation.audit(text)
    assert not result["values_or_conditions_propagated"] and not result["runtime_admission"]
    assert not body_attempt(result)["material_owner_established"]
    validate_spans(text, result)


@pytest.mark.parametrize("extra", [
    "2.2. Литирование мембран полиэтилена\n\n",
    "2.1.1. Измерения\n\n",
    "2.2. Получение дисперсии Nafion\n\n",
])
def test_new_section_never_reuses_previous_heading(extra):
    text = HEADING + extra + BODY
    result = audit(text)
    if "дисперсии Nafion" in extra:
        assert candidates(result)[-1]["subject_heading"]["number"] == "2.2"
        assert candidates(result)[-1]["subject_heading"]["form_cues"] == ["dispersion"]
    else:
        assert body_attempt(result)["state"] == "blocked_or_unresolved"


@pytest.mark.parametrize("body", [
    "Проводили литирование полиэтилена в LiOH.",
    "Проводили литирование полипропилена в LiOH.",
    "Другой материал PBI использовали в работе. " + BODY,
    "Применяли мембраны Aquivion. " + BODY,
    "Исследовали дисперсию Nafion. " + BODY,
    "На другом этапе выполняли обработку. " + BODY,
    "Литирование не проводили.",
    "В будущем планируется литирование ионным обменом.",
    "Если проводили литирование, условия уточняли.",
    "Проводили литирование под теми же условиями.",
])
def test_material_form_step_status_and_reference_changes_block_heading_inheritance(body):
    assert body_attempt(audit(HEADING + body))["state"] == "blocked_or_unresolved"


@pytest.mark.parametrize("heading", [
    "2.1. Планируемое литирование мембран Nafion\n\n",
    "2.1. Подготовка мембран Nafion/PBI\n\n",
    "2.1. Подготовка Nafion-like membranes\n\n",
    "2.1. Подготовка мембран и дисперсий Nafion\n\n",
    "2.1. Подготовка Nafion\n\n",
])
def test_unclear_heading_does_not_supply_material_scope(heading):
    assert body_attempt(audit(heading + BODY))["state"] == "blocked_or_unresolved"


def test_operation_mentioned_in_heading_never_establishes_execution():
    result = audit(HEADING + "2.2. Проводили литирование\n\n")
    assert not candidates(result)


def test_explicit_caption_subpanel_can_narrow_mixed_section_scope():
    text = HEADING + "Дополнительно применяли дисперсию Nafion.\n\n" + CAPTION + REF_BODY
    result = audit(text)
    links = body_attempt(result)["links"]
    assert links[0]["state"] == "blocked_or_unresolved"
    assert "material_form_change_or_mixed_scope" in links[0]["diagnostics"]
    selected, = candidates(result)
    assert selected["kind"] == "explicit_figure_subpanel_reference"
    assert selected["subpanel"]["label"] == "б"
    assert selected["subpanel"]["form_cues"] == ["membrane"]
    validate_spans(text, result)


@pytest.mark.parametrize("reference", ["рисунок 2.1а", "рисунок 2.1", "рисунок 2.2б", "рисунок 2.1b"])
def test_reference_must_name_exact_lithiation_subpanel(reference):
    text = HEADING + "Дополнительно использовали дисперсию Nafion.\n\n" + CAPTION
    result = audit(text + REF_BODY.replace("рисунок 2.1б", reference))
    assert not candidates(result)


@pytest.mark.parametrize("between", [
    "2.2. Подготовка мембран полиэтилена\n\n",
    "Использовали мембраны Aquivion.\n\n",
    "На другом этапе применяли другой материал.\n\n",
])
def test_caption_reference_never_bypasses_new_material_or_section(between):
    result = audit(HEADING + CAPTION + between + REF_BODY)
    assert not candidates(result)


def test_duplicate_caption_identity_stays_unresolved():
    result = audit(HEADING + CAPTION + CAPTION + REF_BODY)
    figure_link = body_attempt(result)["links"][-1]
    assert figure_link["state"] == "blocked_or_unresolved"
    assert "figure_caption_not_unique_or_missing" in figure_link["diagnostics"]


def test_caption_parent_title_cannot_turn_cleaning_subpanel_into_lithiation():
    caption = CAPTION.replace("Схема подготовки", "Схема литирования")
    result = audit(HEADING + "Использовали дисперсию Nafion.\n\n" + caption + REF_BODY.replace("2.1б", "2.1а"))
    assert not candidates(result)


def test_context_call_has_no_memory_or_cross_document_subject():
    assert candidates(audit(HEADING + BODY))
    assert not candidates(audit(BODY))


def test_context_never_inherits_cleaning_values_or_rewrites_baseline():
    text = HEADING + "Мембраны очищали 2 ч при 80 °C.\n\n" + BODY
    result = audit(text)
    assert result["baseline"] == operation.audit(text)
    final = result["baseline"]["operations"][-1]
    assert {field["span"]["text"] for field in final["fields"] if field["field"] == "duration"} == {"120 мин"}
    assert not result["values_or_conditions_propagated"]


def test_direct_local_target_keeps_original_unverified_state():
    result = audit("Проводили литирование мембран Nafion в LiOH.")
    assert result["attempts"][0]["state"] == "local_target_already_present"
    assert not result["attempts"][0]["material_owner_established"]


@pytest.mark.parametrize("prefix", ["Затем ", "На втором этапе ", "Then "])
def test_plain_heading_inheritance_stops_at_a_step_transition(prefix):
    result = audit(HEADING + prefix + BODY)
    assert not candidates(result)
    assert "step_transition_requires_explicit_reference" in body_attempt(result)["links"][0]["diagnostics"]


def test_unknown_named_subpanel_material_never_borrows_parent_nafion():
    caption = CAPTION.replace("литирование мембраны (б)", "литирование мембран полипропилена (б)")
    result = audit(HEADING + caption + REF_BODY)
    assert not candidates(result)
    assert "explicit_material_object_not_resolved_as_section_target" in body_attempt(result)["links"][-1]["diagnostics"]


def test_colon_after_first_subpanel_does_not_create_invalid_raw_span():
    text = ("Figure 1 — Nafion membranes (a); conditions: lithiation of membrane (b)\n\n"
            "Lithiation was performed (see Figure 1b).")
    result = audit(text)
    assert not result["captions"][0]["parts"][0]["parent_prefix_excluded"]
    validate_spans(text, result)


@pytest.mark.parametrize("prefix", [HEADING, HEADING + CAPTION])
def test_unknown_material_in_intervening_membrane_object_blocks_old_subject(prefix):
    text = prefix + "Очищали мембраны полипропилена.\n\n" + REF_BODY
    assert not candidates(audit(text))
