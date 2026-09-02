from __future__ import annotations

import uuid
from decimal import Decimal

from app import main
from app.db.models import Article, Chunk, StructuredFact


class FakeScalarResult:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


class FakeSession:
    def __init__(self) -> None:
        self.article = Article(
            id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            collection_id=uuid.uuid4(),
            title="Conductivity table paper",
            doi="10.1000/fact",
            pdf_original_path="data/pdf/paper.pdf",
            checksum_sha256="a" * 64,
            status="indexed",
        )
        self.chunk = Chunk(
            id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            article_id=self.article.id,
            chunk_index=0,
            page_start=3,
            page_end=4,
            source_type="table",
            text_layer="original",
            text="Conductivity 1.2e-3 S cm-1",
            char_count=29,
        )
        self.fact = StructuredFact(
            id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
            article_id=self.article.id,
            source_chunk_id=self.chunk.id,
            entity_type="numeric_measurement",
            field_name="conductivity",
            field_value_text="1.2e-3 S cm-1",
            field_value_numeric=Decimal("0.0012"),
            unit="S cm-1",
            confidence=Decimal("0.80"),
            source="rule_based_numeric_v1",
        )

    def scalars(self, statement: object) -> FakeScalarResult:
        if "FROM structured_facts" in str(statement):
            return FakeScalarResult([self.fact])
        return FakeScalarResult([])

    def get(self, model: type[object], row_id: object) -> object | None:
        if model is Article and row_id == self.article.id:
            return self.article
        if model is Chunk and row_id == self.chunk.id:
            return self.chunk
        return None


def test_facts_api_lists_structured_facts() -> None:
    payload = main.facts(FakeSession(), field_name="conductivity")  # type: ignore[arg-type]

    assert payload["summary"] == {
        "count": 1,
        "by_field": {"conductivity": 1},
        "by_unit": {"S cm-1": 1},
        "by_source": {"rule_based_numeric_v1": 1},
    }
    item = payload["items"][0]
    assert item["title"] == "Conductivity table paper"
    assert item["field_value_numeric"] == "0.0012"
    assert item["pdf_page_url"] == "/articles/11111111-1111-1111-1111-111111111111/pdf?layer=original#page=3"
