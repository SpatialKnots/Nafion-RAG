from unittest.mock import patch

import pytest

import app.facts.extraction as extraction
from app.db.models import Chunk
from scripts.stage3_numeric_cap_audit import extract_keys


def test_trial_cap_recovers_later_value_without_rescuing_range_endpoint() -> None:
    chunk = Chunk(text="423–523 K\n" + "\n".join(f"{i} K" for i in range(12)) + "\nat 523 K")
    original = extraction.MAX_FACTS_PER_CHUNK
    target = ("temperature", "523 K", "523", "K")
    assert target not in extract_keys(chunk, 12)
    assert target in extract_keys(chunk, 16)
    assert extraction.MAX_FACTS_PER_CHUNK == original
    assert target not in extract_keys(Chunk(text="423–523 K"), 16)


def test_trial_cap_is_restored_when_extraction_fails() -> None:
    original = extraction.MAX_FACTS_PER_CHUNK
    with patch.object(extraction, "extract_structured_fact_candidates_from_chunk", side_effect=RuntimeError("probe failure")):
        with pytest.raises(RuntimeError, match="probe failure"):
            extract_keys(Chunk(text="523 K"), 16)
    assert extraction.MAX_FACTS_PER_CHUNK == original
