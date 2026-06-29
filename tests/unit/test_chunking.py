from __future__ import annotations

from app.chunking.simple import PageText, chunk_pages


def test_chunk_pages_preserves_page_ranges() -> None:
    pages = [
        PageText(page_number=1, text="A first paragraph about Nafion.\n\nSecond paragraph."),
        PageText(page_number=2, text="A third paragraph about Li-Nafion conductivity."),
    ]

    chunks = chunk_pages(pages, target_chars=60, overlap_chars=0)

    assert len(chunks) >= 2
    assert chunks[0].page_start == 1
    assert chunks[-1].page_end == 2
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_chunk_pages_rejects_invalid_target() -> None:
    try:
        chunk_pages([], target_chars=0, overlap_chars=0)
    except ValueError as exc:
        assert "target_chars" in str(exc)
    else:
        raise AssertionError("expected ValueError")
