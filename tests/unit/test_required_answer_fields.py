"""Finite field/source controls; synthetic values are not scientific ground truth."""

import copy
from dataclasses import asdict, replace

import pytest

from app.generation.providers import Evidence, GeneratedClaim
from app.generation.required_answer_fields import (
    RequirementGuidedAnswerProvider,
    build,
    check,
    extend_preparation,
    validate,
)

QUESTION = "Как изменяется плотность ABCD при его трифторировании и каковы значения при 27 °C?"
TEXT = ("The structures of UVWX and ABCD as linear ethers. "
        "Trifluorination of ABCD and JKLM increased the mass and volume of the molecule. "
        "The mass densities decreased in the following order: UVWX (1.2345 × 103 kg m−3 at 27 ºC) > "
        "ABCD (0.9876 × 103 kg m−3 at 27 ºC).")
ENERGY_Q = "Какую удельную энергию получили и каковы ограничения?"
ENERGY = ("A high energy density of >731 Wh kg−1 based on the total cathode/anode masses is achieved. "
          "The Li metal was depleted after 143 cycles.")


def source(text=TEXT, cid="E1", article="work"):
    return Evidence(cid, article, "chunk-" + cid, "Constructed", None, 3, 4, "main_text", text, 1, "frozen", {}, {})


def claims(*texts, cid="E1"):
    return [GeneratedClaim(t, [cid]) for t in texts]


def report(texts, question=QUESTION, sources=None):
    return check(question, claims(*texts), sources or [source()])


def test_source_paired_objects_and_exact_raw_anchors_without_input_mutation():
    evidence = [source()]
    before = [asdict(e) for e in evidence]
    plan = build(QUESTION, evidence)
    assert [r['id'] for r in plan['requirements']] == ['density:ABCD', 'density:UVWX']
    for row in plan['requirements']:
        assert row['state'] == 'recognized_source_pattern'
        for obs in row['observations']:
            a = obs['anchor']
            assert TEXT[a['start']:a['end']] == a['text']
            assert obs['scientific_support'] == 'not_evaluated'
    assert [asdict(e) for e in evidence] == before
    validate(plan, QUESTION, evidence)


def test_correct_object_value_unit_scale_and_temperature_are_retained():
    result = report(["Плотность ABCD при 27°C составляет 0.9876 × 10³ кг/м³.",
                     "Плотность UVWX при 27°C составляет 1.2345 × 10³ кг/м³."])
    assert result['decision'] == 'not_blocked_by_required_field_checks'
    assert all(r['coverage'] for r in result['rows'])


@pytest.mark.parametrize('text', [
    "ABCD при 27°C: 1.2345 × 10³ кг/м³; UVWX при 27°C: 0.9876 × 10³ кг/м³.",
    "UVWX при 27°C: 0.9876 × 10³ кг/м³, ABCD при 27°C: 1.2345 × 10³ кг/м³.",
    "ABCD при 27°C: 0.9876 кг/м³; UVWX при 27°C: 1.2345 кг/м³.",
    "ABCD при 27°C: 0.9876 × 10³ г/м³; UVWX при 27°C: 1.2345 × 10³ г/м³.",
    "ABCD при 27°C: 0.9876 × 10³ кг/м³; UVWX при 49°C: 1.2345 × 10³ кг/м³.",
    "ABCD при 27°C: 0.9876 × 10³ кг/м³; UVWX при 27°C: 1.2346 × 10³ кг/м³.",
    "ABCD не имеет плотность 0.9876 × 10³ кг/м³ при 27°C; UVWX: 1.2345 × 10³ кг/м³ при 27°C.",
    "ABCD может иметь плотность 0.9876 × 10³ кг/м³ при 27°C; UVWX: 1.2345 × 10³ кг/м³ при 27°C.",
    "ABCD при 27°C: 0.9876 × 10³ кг/м³.",
])
def test_wrong_or_missing_density_fields_do_not_pass(text):
    assert report([text])['decision'] == 'required_fields_unresolved'


@pytest.mark.parametrize('body', [TEXT.replace('27 ºC', '49 ºC'), TEXT.replace('kg m−3', 'mol dm−3'),
    TEXT.replace('mass densities', 'molar masses'), TEXT +
    ' The mass densities decreased in the following order: ABCD (0.9999 × 103 kg m−3 at 27 ºC).'])
def test_wrong_source_temperature_property_unit_or_conflicting_value_stays_unresolved(body):
    plan = build(QUESTION, [source(body)])
    assert any(r['state'] != 'recognized_source_pattern' for r in plan['requirements'])


@pytest.mark.parametrize('prefix', ['Hypothetical: ', 'Previous work reported: ', 'Incorrectly: '])
def test_noncurrent_source_density_list_never_becomes_required_values(prefix):
    body = TEXT.replace('The mass densities', prefix + 'The mass densities')
    plan = build(QUESTION, [source(body)])
    assert all(not row['observations'] for row in plan['requirements'])


def test_only_explicit_objects_are_required_without_source_pair_inference():
    plan = build("Compare density values of ABCD and UVWX at 27 °C", [source(TEXT.split('. ', 1)[1])])
    assert plan['status'] == 'mapped' and not plan['relations']
    unsupported = build(QUESTION, [source(TEXT.split('. ', 1)[1])])
    assert unsupported['status'] == 'not_applicable'


@pytest.mark.parametrize('change', ['cross_work', 'derived', 'duplicate', 'ambiguous_pair'])
def test_bad_source_or_identity_scopes_are_never_silently_joined(change):
    evidence = [source()]
    if change == 'cross_work':
        evidence.append(source(TEXT, 'E2', 'other-work'))
    elif change == 'derived':
        evidence = [replace(evidence[0], source_type='source_fact_derived')]
    elif change == 'duplicate':
        with pytest.raises(ValueError, match='Duplicate'):
            build(QUESTION, evidence + evidence)
        return
    else:
        evidence.append(source('The structures of OTHER and ABCD as linear ethers. ' + TEXT, 'E2'))
    assert build(QUESTION, evidence)['status'] == 'not_applicable'


@pytest.mark.parametrize('change', ['question', 'text', 'page', 'plan'])
def test_stale_or_tampered_map_is_rejected(change):
    q, evidence = QUESTION, [source()]
    plan = build(q, evidence)
    if change == 'question':
        q += ' Extra constraint.'
    elif change == 'text':
        evidence = [source(TEXT + ' More source.')]
    elif change == 'page':
        evidence = [replace(evidence[0], page_end=5)]
    else:
        plan['requirements'][0]['observations'][0]['fields']['value'] = '999'
    with pytest.raises(ValueError, match='Stale'):
        validate(plan, q, evidence)


def test_energy_definition_and_limitation_cover_own_cited_source():
    result = report(["Удельная энергия >731 Вт·ч/кг по суммарной массе катода и анода.",
        "Металлический литий истощился после 143 циклов."], ENERGY_Q, [source(ENERGY)])
    assert result['decision'] == 'not_blocked_by_required_field_checks'


@pytest.mark.parametrize('answer', [
    'Удельная энергия >731 Вт·ч/кг.',
    'Удельная энергия >731 Вт·ч/кг по массе катода.',
    'Удельная энергия >731 Вт·ч/кг по общей массе катода и анода. Литий истощился после 144 циклов.',
    'Удельная энергия >731 Вт·ч/кг не рассчитана по общей массе катода и анода. Литий истощился после 143 циклов.',
])
def test_missing_or_negated_energy_fields_are_diagnosed(answer):
    assert report([answer], ENERGY_Q, [source(ENERGY)])['decision'] == 'required_fields_unresolved'


def test_role_label_does_not_prove_causal_mechanism_or_allow_wrong_role():
    evidence = [source('LiF-rich SEI. CFx-rich CEI.')]
    q = 'Каков состав SEI и почему он подавляет дендриты?'
    result = check(q, claims('SEI содержит LiF и подавляет дендриты.'), evidence)
    assert result['rows'][0]['coverage'] and not result['rows'][1]['coverage']
    wrong = check('Каков состав SEI?', claims('CEI содержит LiF.'), evidence)
    assert wrong['decision'] == 'required_fields_unresolved'


def test_explicit_causal_source_pattern_can_be_covered_without_unnecessary_refusal():
    text = 'LiF-rich SEI suppresses dendrite growth by promoting uniform Li deposition.'
    result = check('What is SEI composition and why does it suppress dendrites?', claims(text), [source(text)])
    assert result['decision'] == 'not_blocked_by_required_field_checks'


@pytest.mark.parametrize('body', ['LiF-rich CEI.', 'LiF-rich SEI. MgF2-rich SEI.', 'LiF-rich SEI may suppress dendrites.'])
def test_other_role_ambiguity_and_unrecognized_mechanism_are_explicit(body):
    plan = build('What is SEI composition and why does it suppress dendrites?', [source(body)])
    assert plan['requirements'][-1]['state'] == 'unresolved_in_finite_selected_context'
    assert plan['scientific_support'] == 'not_evaluated'


def test_unknown_citations_cannot_cover_a_field():
    with pytest.raises(ValueError, match='citations'):
        check(QUESTION, claims('ABCD 0.9876 × 10³ кг/м³ при 27°C.', cid='E99'), [source()])
    result = check(QUESTION, claims('ABCD 0.9876 × 10³ кг/м³ при 27°C.', cid='E2'), [source(), source('Unrelated.', 'E2')])
    assert not any(row['coverage'] for row in result['rows'])


def test_legacy_preparation_map_and_blockers_remain_intact():
    from test_answer_requirements import REAL

    from app.generation.answer_requirements import build_requirements
    parent = copy.deepcopy(REAL)
    before = copy.deepcopy(parent)
    result = extend_preparation(parent)
    assert result['legacy'] == build_requirements(parent)
    assert parent == before and not result['admission_changed']


@pytest.mark.parametrize('kind', ['procedure_derived', 'comparison_derived', 'reference_quote_derived', 'source_fact_derived'])
def test_exact_selection_error_behavior_is_inherited(kind):
    from app.generation.providers import GenerationOutputError
    active = RequirementGuidedAnswerProvider(credentials='offline-key', scope='GIGACHAT_API_PERS', model='GigaChat-2-Max',
                                            max_tokens=1200, timeout_seconds=120)
    with pytest.raises(GenerationOutputError):
        active._user_prompt(QUESTION, [replace(source(), source_type=kind, text='invalid JSON')])


def test_unsupported_questions_have_identical_previous_experiment_prompt():
    from app.generation.answer_instruction_experiment import ExperimentalScientificAnswerProvider
    options = dict(credentials='offline-key', scope='GIGACHAT_API_PERS', model='GigaChat-2-Max',
                   max_tokens=1200, timeout_seconds=120)
    question = 'What products have not been identified?'
    assert RequirementGuidedAnswerProvider(**options)._user_prompt(question, [source()]) == (
        ExperimentalScientificAnswerProvider(**options)._user_prompt(question, [source()]))


def test_source_pair_without_literal_transformation_topic_is_not_inferred():
    assert build(QUESTION, [source(TEXT.replace('Trifluorination', 'Treatment'))])['status'] == 'not_applicable'


def test_card_budget_failure_is_explicit_not_silent_truncation():
    from app.generation.providers import GenerationOutputError
    active = RequirementGuidedAnswerProvider(credentials='offline-key', scope='GIGACHAT_API_PERS', model='GigaChat-2-Max',
                                            max_tokens=1200, timeout_seconds=120)
    with pytest.raises(GenerationOutputError, match='12000-character'):
        active._user_prompt(QUESTION, [source(TEXT * 30)])


@pytest.mark.parametrize('change', ['none', 'pinned_id', 'parent'])
def test_existing_packet_adapter_requires_exact_pinned_parent_and_preserves_packet(change):
    from test_answer_evidence_packet import wrapped

    from app.generation.answer_evidence_packet import build_packet
    from app.generation.required_answer_fields import extend_packet

    parent = wrapped()
    packet = build_packet(parent)
    before = copy.deepcopy(packet)
    pinned = packet['packet_id']
    if change == 'pinned_id':
        pinned = '0' * 64
    elif change == 'parent':
        parent['preparation']['question'] += ' changed'
    if change != 'none':
        with pytest.raises(ValueError):
            extend_packet(packet, parent, expected_packet_id=pinned)
    else:
        result = extend_packet(packet, parent, expected_packet_id=pinned)
        assert not result['packet_changed'] and not result['admission_changed']
        assert result['packet_id'] == packet['packet_id']
    assert packet == before
