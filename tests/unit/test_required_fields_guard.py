"""Whole-answer guard controls; native results remain separate from delivery."""

from copy import deepcopy
from dataclasses import asdict

import pytest

from app.generation.providers import GeneratedClaim, GenerationOutputError, ProviderResult
from app.generation.required_fields_guard import RequiredFieldsGuardProvider, evaluate


class Provider:
    def __init__(self, result):
        self.result, self.calls, self.arguments = result, 0, []

    def generate(self, question, evidence, **kwargs):
        self.calls += 1
        self.arguments.append((question, evidence, kwargs))
        return self.result


def inputs(text):
    from test_required_answer_fields import ENERGY, ENERGY_Q, source

    return ENERGY_Q, [source(ENERGY)], ProviderResult(True, [GeneratedClaim(text, ['E1'])], 'synthetic', 'frozen')


@pytest.mark.parametrize('text,decision,blocked', [
    ('Specific energy >731 Wh/kg based on total cathode/anode masses. Li metal depleted after 143 cycles.',
     'required_literal_fields_present', False),
    ('Specific energy >731 Wh/kg.', 'insufficient_confirmation', True),
    ('Specific energy >731 Wh/kg using combined positive and negative electrode masses. Li metal depleted after 143 cycles.',
     'insufficient_confirmation', True),
])
def test_native_is_retained_and_only_one_call_is_made(text, decision, blocked):
    q, evidence, native = inputs(text)
    before = deepcopy(asdict(native))
    provider, reports = Provider(native), []
    result = RequiredFieldsGuardProvider(provider, on_review=reports.append).generate(q, evidence,
        answer_style='claims', answer_language='en')
    assert provider.calls == 1
    assert provider.arguments[0][2] == {'answer_style': 'claims', 'answer_language': 'en'}
    assert asdict(native) == before and reports[0]['native_result'] == before
    assert reports[0]['decision'] == decision and reports[0]['withheld'] == blocked
    assert reports[0]['scientific_support'] == 'not_evaluated'
    if blocked:
        assert not result.answerable and not result.claims and result.provider == native.provider
    else:
        assert result is native


def test_unrecognized_answer_wording_is_not_called_a_scientific_error():
    q, evidence, native = inputs('Specific energy >731 Wh/kg using combined positive and negative electrode masses. '
                                'Li metal depleted after 143 cycles.')
    report = evaluate(q, evidence, native)
    assert report['reasons'] == [{'id': 'energy_value_and_basis', 'state': 'answer_wording_or_binding_not_recognized',
                                 'scientific_error_established': False}]


def test_missing_literal_has_different_reason_from_unknown_wording():
    q, evidence, native = inputs('Specific energy was measured.')
    report = evaluate(q, evidence, native)
    assert all(r['state'] == 'required_literal_not_observed' for r in report['reasons'])
    assert not report['scientific_error_established']


@pytest.mark.parametrize('surface', ['731Wh/kg', '731 Wh/kg', '731Вт·ч/кг'])
def test_numeric_value_adjacent_to_unit_is_wording_gap_not_absent_value(surface):
    q, evidence, native = inputs('Specific energy ' + surface + ' using combined positive and negative electrode masses. '
                                'Li metal depleted after 143 cycles.')
    report = evaluate(q, evidence, native)
    assert report['reasons'][0]['state'] == 'answer_wording_or_binding_not_recognized'


def test_unresolved_source_mechanism_is_not_literature_absence():
    from test_required_answer_fields import source

    native = ProviderResult(True, [GeneratedClaim('LiF-rich SEI suppresses dendrites because it is dense.', ['E1'])], 'stub', None)
    report = evaluate('What is SEI composition and why does it suppress dendrites?', [source('LiF-rich SEI.')], native)
    assert report['withheld'] and report['reasons'][-1]['state'] == 'source_support_not_established_by_finite_grammar'
    assert not report['reasons'][-1]['scientific_error_established']


def test_ambiguous_source_values_are_distinguished():
    from test_required_answer_fields import ENERGY, ENERGY_Q, source

    body = ENERGY + ' A high energy density of >744 Wh kg−1 based on the total cathode/anode masses is achieved.'
    native = ProviderResult(True, [GeneratedClaim('Specific energy >731 Wh/kg based on total cathode/anode masses.', ['E1'])], 'stub', None)
    report = evaluate(ENERGY_Q, [source(body)], native)
    assert report['reasons'][0]['state'] == 'source_candidates_ambiguous'


def test_callback_cannot_modify_delivery_or_native():
    q, evidence, native = inputs('Specific energy >731 Wh/kg.')
    provider = Provider(native)

    def tamper(report):
        report['withheld'] = False
        report['native_result']['claims'][0]['text'] = 'invented'

    result = RequiredFieldsGuardProvider(provider, on_review=tamper).generate(q, evidence)
    assert not result.answerable and native.claims[0].text == 'Specific energy >731 Wh/kg.'


def test_callback_failure_is_visible_and_not_retried():
    q, evidence, native = inputs('Specific energy >731 Wh/kg.')
    provider = Provider(native)

    def fail(report):
        raise OSError('synthetic review-storage failure')

    with pytest.raises(OSError, match='storage'):
        RequiredFieldsGuardProvider(provider, on_review=fail).generate(q, evidence)
    assert provider.calls == 1 and native.answerable


def test_unknown_question_family_keeps_native_with_explicit_not_evaluated_status():
    q, evidence, native = inputs('A qualitative observation.')
    report = evaluate('What qualitative observation is reported?', evidence, native)
    assert report['decision'] == 'not_evaluated' and not report['withheld']


def test_original_provider_abstention_is_not_replaced_by_guard_abstention():
    q, evidence, native = inputs('unused')
    native = ProviderResult(False, [], native.provider, native.model)
    provider, reports = Provider(native), []
    result = RequiredFieldsGuardProvider(provider, on_review=reports.append).generate(q, evidence)
    assert result is native and reports[0]['decision'] == 'provider_abstained' and not reports[0]['withheld']


@pytest.mark.parametrize('native', [ProviderResult(True, [], 'stub', None),
    ProviderResult(False, [GeneratedClaim('Text', ['E1'])], 'stub', None),
    ProviderResult(True, [GeneratedClaim('Text', ['E99'])], 'stub', None)])
def test_invalid_native_contract_is_not_repaired(native):
    q, evidence, _ = inputs('unused')
    provider = Provider(native)
    with pytest.raises(GenerationOutputError):
        RequiredFieldsGuardProvider(provider, on_review=lambda r: None).generate(q, evidence)
    assert provider.calls == 1


def test_invalid_input_stops_before_provider():
    q, evidence, native = inputs('unused')
    provider = Provider(native)
    with pytest.raises(ValueError):
        RequiredFieldsGuardProvider(provider, on_review=lambda r: None).generate(' ', evidence)
    assert provider.calls == 0


def test_provider_exception_propagates_without_retry():
    q, evidence, native = inputs('unused')
    provider = Provider(native)

    def fail(*args, **kwargs):
        provider.calls += 1
        raise RuntimeError('synthetic underlying failure')

    provider.generate = fail
    with pytest.raises(RuntimeError, match='underlying'):
        RequiredFieldsGuardProvider(provider, on_review=lambda r: None).generate(q, evidence)
    assert provider.calls == 1
