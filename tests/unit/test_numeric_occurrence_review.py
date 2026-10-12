import pytest

from app.db.models import Chunk
from scripts.stage3_numeric_change_review import validate_occurrence_label


def fixture() -> tuple[Chunk, dict]:
    text = '423–523 K\nat 523 K'
    return Chunk(text=text), {
        'candidate': {'field_value_text': '523 K'}, 'text': 'at 523 K',
        'chunk_occurrence_start': 13, 'chunk_occurrence_end': 18,
        'occurrence_decision': 'accepted', 'occurrence_reason': 'selected',
    }


def test_later_accepted_occurrence_is_bound() -> None:
    chunk, label = fixture()
    validate_occurrence_label(chunk, label)


def test_same_lexeme_cannot_replace_accepted_occurrence_with_range() -> None:
    chunk, label = fixture()
    label.update(chunk_occurrence_start=4, chunk_occurrence_end=9)
    with pytest.raises(ValueError, match='decision changed'):
        validate_occurrence_label(chunk, label)


def test_wrong_fragment_is_rejected_even_with_same_lexeme() -> None:
    chunk, label = fixture()
    label['text'] = '423–523 K'
    with pytest.raises(ValueError, match='occurrence line'):
        validate_occurrence_label(chunk, label)


def test_partial_binding_is_not_silently_ignored() -> None:
    chunk, label = fixture()
    del label['occurrence_reason']
    with pytest.raises(ValueError, match='Incomplete occurrence'):
        validate_occurrence_label(chunk, label)
