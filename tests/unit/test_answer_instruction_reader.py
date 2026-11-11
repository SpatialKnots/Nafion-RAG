"""Recover original and delivered question separately; never invent attribution."""

import pytest

from scripts.prepare_answer_instruction_experiment_v02_20261110 import delivered_question


@pytest.mark.parametrize("prefix", ["", "По статье Example (2041): "])
def test_recovers_only_exact_saved_question_with_or_without_existing_attribution(prefix):
    original = "Как измеряли проводимость?"
    prompt = "Existing instructions\n\nQuestion:\n" + prefix + original + "\n\nEvidence:\n\n[E1] raw text"
    request = {"messages": [{"role": "system", "content": "unchanged"}, {"role": "user", "content": prompt}]}
    assert delivered_question(request, original) == prefix + original
    assert request["messages"][1]["content"] == prompt


@pytest.mark.parametrize("prompt", [
    "instructions\n\nQuestion:\nA different question\n\nEvidence:\n\n[E1] text",
    "instructions\n\nQuestion:\nOriginal question with changed scope\n\nEvidence:\n\n[E1] text",
    "instructions\n\nQuestion:\nOriginal question\n\nEvidence:\n\n",
    "instructions with no question boundaries",
])
def test_refuses_changed_question_or_missing_boundaries(prompt):
    request = {"messages": [{"role": "system", "content": "unchanged"}, {"role": "user", "content": prompt}]}
    with pytest.raises(ValueError):
        delivered_question(request, "Original question")
