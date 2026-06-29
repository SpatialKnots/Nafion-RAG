from __future__ import annotations

from app.metadata.doi import extract_first_doi


def test_extract_first_doi() -> None:
    text = "See https://doi.org/10.1016/j.memsci.2022.120123 for details."

    assert extract_first_doi(text) == "10.1016/j.memsci.2022.120123"


def test_extract_first_doi_missing() -> None:
    assert extract_first_doi("No identifier here") is None
