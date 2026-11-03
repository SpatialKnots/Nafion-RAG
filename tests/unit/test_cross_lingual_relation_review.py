import copy
import json

import pytest

from app.core.config import get_settings
from scripts.run_cross_lingual_relation_audit import CAPTURE, replay_service, validate_sources
from scripts.verify_cross_lingual_relation_review import check_span


def test_corrupted_raw_source_rejected():
    value = json.loads((CAPTURE / "cases/000_baseline.json").read_bytes())
    corpus = json.loads((CAPTURE / "corpus.json").read_bytes())
    validate_sources(value["trace"], corpus)
    value["trace"]["retrieval"]["results"][0]["full_text"] += " corrupt"
    with pytest.raises(ValueError, match="Frozen raw retrieval source differs: full_text"):
        validate_sources(value["trace"], corpus)


def test_real_service_trace_matches_and_corrupted_expected_metadata_rejected():
    value = json.loads((CAPTURE / "cases/000_baseline.json").read_bytes())
    original = copy.deepcopy(value)
    assert replay_service(value, get_settings())["full_trace_identical"]
    assert value == original
    value["trace"]["metadata"]["evidence_adequacy"]["reason"] = "corrupt"
    with pytest.raises(ValueError, match="Frozen full service trace or status differs"):
        replay_service(value, get_settings())


def test_wrong_raw_anchor_is_rejected_even_if_its_length_matches():
    check_span("Nafion", {"start": 0, "end": 6, "text": "Nafion"})
    with pytest.raises(ValueError, match="Raw span differs"):
        check_span("Nafion", {"start": 0, "end": 6, "text": "PVDFxx"})
