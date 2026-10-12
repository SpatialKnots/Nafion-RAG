import pytest

from scripts.profile_li_nafion import LITHIUM_NAFION


@pytest.mark.parametrize("source", ["Li-Nafion", "Li-Нафион", "литиевая форма Нафиона", "lithiated\nNafion", "Li-Naﬁon", "Lithiated Naﬁon"])
def test_profile_retains_exact_multilingual_anchor(source: str) -> None:
    match = LITHIUM_NAFION.search(source)
    assert match is not None
    assert match.group() == source


def test_profile_does_not_classify_proton_form_as_lithium_anchor() -> None:
    assert LITHIUM_NAFION.search("Proton conductivity of H-Nafion") is None
