"""Read-only access to recorded metadata proposals and exact source evidence."""

from __future__ import annotations

import json
from html import escape
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Article
from app.db.session import get_session
from app.documents.service import DocumentAccessError, build_pdf_url
from app.metadata.bibliography import recorded
from app.ui import _layout

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]


@router.get('/articles/{article_id}/bibliography')
def metadata_api(session: SessionDep, article_id: UUID) -> dict[str, Any]:
    article = session.get(Article, article_id)
    if article is None:
        raise HTTPException(404, 'Article not found')
    try:
        return recorded(session, get_settings(), article)
    except DocumentAccessError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get('/ui/articles/{article_id}/bibliography', response_class=HTMLResponse)
def metadata_page(session: SessionDep, article_id: UUID) -> HTMLResponse:
    result = metadata_api(session, article_id)
    links = ''.join('<a href="' + escape(build_pdf_url(str(article_id), 'original', r['page_number']), quote=True)
        + '">Оригинальный PDF, страница ' + str(r['page_number']) + '</a> '
        for r in result.get('payload', {}).get('sources', {}).get('regions', []))
    return _layout('Происхождение метаданных', '<h1>Авторы, журнал и год: происхождение</h1>'
        '<p>Значения извлечены алгоритмом и не являются независимым подтверждением библиографии. '
        'Неоднозначности и исходные цитаты сохранены.</p>' + links + '<pre>'
        + escape(json.dumps(result, ensure_ascii=False, indent=2)) + '</pre>')
