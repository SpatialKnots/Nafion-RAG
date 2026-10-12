from pathlib import Path

from app.retrieval import cross_lingual


def test_packaged_glossary_matches_authoritative_source() -> None:
    root = Path(__file__).resolve().parents[2]
    packaged = Path(cross_lingual.__file__).with_name("cross_lingual_glossary.yaml")
    assert packaged.read_bytes() == (root / "docs" / "cross_lingual_glossary.yaml").read_bytes()
