from uuid import uuid4

from fastapi.testclient import TestClient

from app import main
from app.db.session import get_session


def test_page_context_url_reaches_range_handler(monkeypatch) -> None:
    article = object()
    calls = []

    def context(session, settings, selected_article, **kwargs):
        calls.append((selected_article, kwargs))
        return {"text": "source evidence"}

    monkeypatch.setattr(main, "_get_article_or_404", lambda session, article_id: article)
    monkeypatch.setattr(main, "get_page_range_context", context)
    monkeypatch.setattr(main, "page_range_context_to_dict", lambda value: value)
    main.app.dependency_overrides[get_session] = lambda: object()
    try:
        with TestClient(main.app) as client:
            response = client.get(f"/articles/{uuid4()}/pages/context?page_start=1&page_end=2&layer=selected")
        assert response.status_code == 200
        assert response.json() == {"text": "source evidence"}
        assert calls[0][0] is article
        assert calls[0][1]["page_start"] == 1
        assert calls[0][1]["page_end"] == 2
    finally:
        main.app.dependency_overrides.pop(get_session, None)


def test_missing_library_file_does_not_show_processing_spinner() -> None:
    from app.ui import _stage_line

    markup = _stage_line("missing")
    assert "stage-spinner" not in markup
    assert "stage-dot error" in markup
