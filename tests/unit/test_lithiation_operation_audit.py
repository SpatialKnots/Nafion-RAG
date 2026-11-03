"""Operation/target/status boundaries, raw offsets and field isolation."""

import pytest

from scripts.lithiation_operation_audit import audit


@pytest.mark.parametrize("text", [
    "Проводили литирование мембран Nafion в 2.0 M LiOH при 60–80 °C в течение 120 мин.",
    "Nafion was lithiated in 2.0 M LiOH at 60 °C for 2 hours.",
    "Lithiation of Nafion was performed in lithium hydroxide for 2 hours.",
    "Для литирования Nafion использовали водный раствор LiOH.",
])
def test_explicit_affirmative_target_is_candidate_not_confirmation(text):
    result = audit(text)
    row, = result["operations"]
    assert row["state"] == "local_target_action_candidate_unverified"
    assert row["status"] == "affirmative_action_cue_unverified"
    assert not row["performed_established"] and not row["material_owner_established"]
    assert result["method_catalogue_completeness"] == "not_established"
    assert not result["runtime_admission"]


@pytest.mark.parametrize("text,status", [
    ("Литирование Nafion не проводили.", "explicit_nonperformance_cue"),
    ("Nafion was not lithiated.", "explicit_nonperformance_cue"),
    ("В будущем планируется литирование Nafion.", "future_cue"),
    ("Lithiation of Nafion will be performed.", "future_cue"),
    ("Если проводили литирование Nafion, условия уточняли.", "conditional_or_uncertain_cue"),
    ("It is not known whether Nafion was lithiated.", "conditional_or_uncertain_cue"),
    ("Литирование Nafion.", "status_unresolved"),
    ("Литированный Nafion исследовали.", None),
])
def test_nonperformance_future_uncertainty_and_headings_never_admitted(text, status):
    rows = audit(text)["operations"]
    if status is None:
        assert not rows
    else:
        assert rows and all(row["status"] == status for row in rows)
        assert all(row["state"] == "blocked_or_unresolved" for row in rows)


@pytest.mark.parametrize("text", [
    "Nafion. Проводили литирование полиэтилена в LiOH.",
    "Проводили литирование полиэтилена в присутствии Nafion.",
    "Nafion был очищен. Проводили литирование мембран в LiOH.",
    "Lithiation was performed on polyethylene; Nafion was used without treatment.",
])
def test_nearby_target_does_not_supply_material_owner(text):
    rows = audit(text)["operations"]
    assert rows and all(not row["target_links"] for row in rows)
    assert all(row["state"] == "blocked_or_unresolved" for row in rows)


def test_cleaning_time_not_copied_to_lithiation_and_no_subject_inheritance():
    rows = audit("Nafion cleaned for 2 hours, then lithiated in LiOH.")["operations"]
    assert len(rows) == 1 and not rows[0]["target_links"]
    assert not [field for field in rows[0]["fields"] if field["field"] == "duration"]
    assert rows[0]["state"] == "blocked_or_unresolved"


def test_two_operation_kinds_with_shared_values_stay_unresolved():
    row, = audit("Nafion was cleaned and lithiated in LiOH for 2 hours.")["operations"]
    assert "multiple_operation_kinds_unresolved" in row["diagnostics"]
    assert all(field["relation"] == "region_scope_unresolved" for field in row["fields"])


def test_same_conditions_reference_not_silently_resolved():
    row, = audit("Nafion was lithiated under the same conditions in LiOH.")["operations"]
    assert "reference_or_shared_scope_unresolved" in row["diagnostics"]


def test_raw_unicode_offsets_and_number_boundaries_survive_dehyphenation():
    text = "α. Проводили литиро-\nвание мембран Nafion в 2.0 M LiOH при 60–80 °C в течение 120 мин."
    row, = audit(text)["operations"]
    assert row["state"] == "local_target_action_candidate_unverified"
    spans = [row["region"], *row["operation_spans"], *row["target_links"], *[f["span"] for f in row["fields"]]]
    spans += [span for values in row["status_cues"].values() for span in values]
    for span in spans:
        assert text[span["start"]:span["end"]] == span["text"]
    assert {f["field"]: f["span"]["text"] for f in row["fields"]} == {
        "reagent": "LiOH", "concentration": "2.0 M", "temperature": "60–80 °C", "duration": "120 мин",
    }


def test_repeated_values_stay_in_their_own_regions():
    text = "Nafion was lithiated for 2 hours. Nafion was not lithiated for 2 hours."
    first, second = audit(text)["operations"]
    assert first["state"] == "local_target_action_candidate_unverified"
    assert second["state"] == "blocked_or_unresolved"
    a, = [f["span"] for f in first["fields"] if f["field"] == "duration"]
    b, = [f["span"] for f in second["fields"] if f["field"] == "duration"]
    assert a["text"] == b["text"] and a["start"] != b["start"]


def test_unrelated_negation_does_not_become_nonperformance():
    row, = audit("Проводили литирование Nafion при температуре не ниже 60 °C.")["operations"]
    assert row["state"] == "local_target_action_candidate_unverified"
    assert row["status"] == "affirmative_action_cue_unverified"


def test_empty_and_invalid_source_are_not_hidden():
    assert audit("")["operations"] == []
    with pytest.raises(TypeError, match="Source text"):
        audit(None)


@pytest.mark.parametrize("text,diagnostic", [
    ("После очистки Nafion в течение 2 ч проводили литирование Nafion в LiOH.",
     "multiple_operation_kinds_unresolved"),
    ("Для литирования Nafion не использовали LiOH.", "reagent_use_negation_unresolved"),
    ("Литирование Nafion проводили?", "interrogative_statement_unresolved"),
])
def test_unresolved_statement_cannot_supply_operation_conditions(text, diagnostic):
    row, = audit(text)["operations"]
    assert diagnostic in row["diagnostics"]
    assert row["state"] == "blocked_or_unresolved"
    assert all(field["relation"] == "region_scope_unresolved" for field in row["fields"])


def test_counterfactual_is_not_performed():
    row, = audit("Литирование Nafion проводили бы при 60 °C.")["operations"]
    assert row["status"] == "conditional_or_uncertain_cue"


def test_values_without_lithiation_region_preserved_as_unassigned():
    text = "Nafion was cleaned for 2 hours at 60 °C. It was lithiated in LiOH."
    result = audit(text)
    assert {f["field"] for f in result["unassigned_fields"]} == {"duration", "temperature"}
    row, = result["operations"]
    assert not row["target_links"] and row["state"] == "blocked_or_unresolved"
    assert [f["field"] for f in row["fields"]] == ["reagent"]
    assert all(not f["owner_established"] for f in [*row["fields"], *result["unassigned_fields"]])


def test_decimal_and_purity_abbreviation_do_not_split_ion_exchange_conditions():
    row, = audit("Проводили литирование Nafion в 2.0 М LiOH (ч., ТУ 1) при 60 °C в течение 120 мин.")["operations"]
    assert {field["field"] for field in row["fields"]} == {"concentration", "reagent", "temperature", "duration"}


@pytest.mark.parametrize("text,form", [
    ("Проводили литирование водно-спиртовой дисперсии Nafion в растворе LiOH.", "dispersion"),
    ("Lithiation of dispersion of Nafion was performed in LiOH.", "dispersion"),
    ("Проводили литирование мембран Nafion в LiOH.", "membrane"),
    ("Проводили литирование Nafion в LiOH.", "not_explicit"),
])
def test_membrane_and_dispersion_cues_not_silently_equated(text, form):
    row, = audit(text)["operations"]
    assert row["state"] == "local_target_action_candidate_unverified"
    assert {link["form_cue"] for link in row["target_links"]} == {form}


def test_pdf_ligature_expansion_keeps_raw_target_offsets():
    text = "Naﬁon membranes were lithiated in LiOH."
    row, = audit(text)["operations"]
    assert row["state"] == "local_target_action_candidate_unverified"
    link, = row["target_links"]
    assert "Naﬁon" in link["text"] and text[link["start"]:link["end"]] == link["text"]


def test_lowercase_length_unit_not_silently_read_as_molar_concentration():
    row, = audit("Nafion was lithiated; Nafion was lithiated in LiOH along a 2.0 m strip.")["operations"][1:]
    assert not [field for field in row["fields"] if field["field"] == "concentration"]
