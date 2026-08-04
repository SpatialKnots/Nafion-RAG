from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.retrieval.vector_index import (
    build_local_vector_index,
    build_local_vector_index_generation,
    build_vector_index_generation_manifest,
    build_vector_index_manifest,
    chunk_text_checksum,
    clear_vector_index_cache,
    corpus_fingerprint_sha256,
    load_current_vector_index_generation,
    load_local_vector_index,
    safe_index_name,
    vector_index_generation_root,
    write_vector_index_manifest,
)


class FakeSession:
    def __init__(self, collection: object | None, rows: list[tuple[object, object]]) -> None:
        self.collection = collection
        self.rows = rows

    def scalar(self, statement: object) -> object | None:
        return self.collection

    def execute(self, statement: object) -> object:
        result = SimpleNamespace(all=lambda: self.rows)
        result.tuples = lambda: result
        return result


class FakeLifecycleSession(FakeSession):
    def __init__(self, collection: object, rows: list[tuple[object, object]], state: object | None) -> None:
        super().__init__(collection, rows)
        self.state = state

    def scalar(self, statement: object) -> object | None:
        text = str(statement)
        if "FROM vector_index_states" in text:
            return self.state
        return self.collection


def test_chunk_text_checksum_is_stable() -> None:
    assert chunk_text_checksum("Nafion chunk text") == chunk_text_checksum("Nafion chunk text")
    assert chunk_text_checksum("Nafion chunk text") != chunk_text_checksum("different text")


def test_safe_index_name_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="embedding model"):
        safe_index_name(" / ")


def test_build_vector_index_manifest_records_chunk_evidence(tmp_path) -> None:
    collection = SimpleNamespace(id=uuid.uuid4(), name="literature")
    article = SimpleNamespace(
        id=uuid.uuid4(),
        collection_id=collection.id,
        checksum_sha256="article-checksum",
    )
    chunk = SimpleNamespace(
        id=uuid.uuid4(),
        article_id=article.id,
        chunk_index=3,
        page_start=4,
        page_end=5,
        source_type="method",
        text_layer="ocr",
        char_count=17,
        text="Li-Nafion evidence",
    )
    corpus_manifest = tmp_path / "corpus_manifest.json"
    corpus_manifest.write_text('{"articles": []}', encoding="utf-8")

    payload = build_vector_index_manifest(
        FakeSession(collection, [(chunk, article)]),  # type: ignore[arg-type]
        collection="literature",
        embedding_model="test/model",
        embedding_dimension=384,
        backend="local_vector_index",
        corpus_manifest_path=corpus_manifest,
        build_command="build command",
        created_at=datetime(2026, 8, 3, tzinfo=UTC),
    )

    assert payload["schema_version"] == 2
    assert payload["status"] == "manifest_only"
    assert payload["backend"] == "local_vector_index"
    assert payload["collection"] == "literature"
    assert payload["embedding_model"] == "test/model"
    assert payload["embedding_dimension"] == 384
    assert payload["chunk_count"] == 1
    assert payload["article_checksums"] == ["article-checksum"]
    assert payload["corpus_manifest_path"] == str(corpus_manifest)
    assert payload["corpus_manifest_sha256"]
    assert payload["chunks"][0]["chunk_id"] == str(chunk.id)
    assert payload["chunks"][0]["source_text_checksum_sha256"] == chunk_text_checksum(chunk.text)
    assert payload["similarity"] == "cosine"
    assert payload["vectors_normalized"] is True


def test_build_vector_index_manifest_rejects_unknown_collection() -> None:
    with pytest.raises(ValueError, match="Unknown collection"):
        build_vector_index_manifest(
            FakeSession(None, []),  # type: ignore[arg-type]
            collection="missing",
            embedding_model="test-model",
            embedding_dimension=384,
            backend="local_vector_index",
        )


def test_write_vector_index_manifest_uses_model_directory(tmp_path) -> None:
    payload = {
        "embedding_model": "BAAI/bge-m3",
        "chunk_count": 0,
    }

    output_path = write_vector_index_manifest(payload, tmp_path)

    assert output_path == tmp_path / "processed" / "vector_indexes" / "BAAI_bge-m3" / "manifest.json"
    assert json.loads(output_path.read_text(encoding="utf-8"))["embedding_model"] == "BAAI/bge-m3"


def test_build_local_vector_index_writes_rebuildable_artifacts(tmp_path) -> None:
    collection = SimpleNamespace(id=uuid.uuid4(), name="literature")
    article = SimpleNamespace(
        id=uuid.uuid4(),
        collection_id=collection.id,
        checksum_sha256="article-checksum",
    )
    chunk_1 = SimpleNamespace(
        id=uuid.uuid4(),
        article_id=article.id,
        chunk_index=0,
        page_start=1,
        page_end=1,
        source_type="body",
        text_layer="original",
        char_count=5,
        text="alpha",
    )
    chunk_2 = SimpleNamespace(
        id=uuid.uuid4(),
        article_id=article.id,
        chunk_index=1,
        page_start=2,
        page_end=2,
        source_type="body",
        text_layer="original",
        char_count=4,
        text="beta",
    )

    def fake_embedder(texts: list[str], batch_size: int) -> list[list[float]]:
        assert texts == ["alpha", "beta"]
        assert batch_size == 2
        return [[1.0, 0.0], [0.0, 1.0]]

    output_path = build_local_vector_index(
        FakeSession(collection, [(chunk_1, article), (chunk_2, article)]),  # type: ignore[arg-type]
        data_root=tmp_path,
        collection="literature",
        embedding_model="test/model",
        backend="local_vector_index",
        batch_size=2,
        embedder=fake_embedder,
    )

    import numpy as np

    index_dir = tmp_path / "processed" / "vector_indexes" / "test_model"
    manifest = json.loads(output_path.read_text(encoding="utf-8"))
    matrix = np.load(index_dir / "embeddings.npy")
    chunk_ids = json.loads((index_dir / "chunk_ids.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "built"
    assert manifest["embedding_dimension"] == 2
    assert [item["name"] for item in manifest["index_files"]] == ["embeddings.npy", "chunk_ids.json"]
    assert all(item["sha256"] for item in manifest["index_files"])
    assert matrix.shape == (2, 2)
    assert chunk_ids == [str(chunk_1.id), str(chunk_2.id)]


def test_build_local_vector_index_generation_writes_v3_immutable_generation(tmp_path) -> None:
    collection, article, chunks = _vector_fixture()
    session = FakeSession(collection, [(chunks[0], article), (chunks[1], article)])

    generation = build_local_vector_index_generation(
        session,  # type: ignore[arg-type]
        data_root=tmp_path,
        collection="literature",
        embedding_model="test/model",
        target_revision=7,
        embedding_dimension=2,
        batch_size=2,
        generation_id="generation-1",
        build_id="build-1",
        embedder=lambda texts, batch_size: [[1.0, 0.0], [0.0, 1.0]],
    )

    import numpy as np

    expected_root = tmp_path / "processed" / "vector_indexes" / "literature" / "test_model"
    assert generation.root == expected_root
    assert generation.manifest_path == expected_root / "generations" / "generation-1" / "manifest.json"
    assert generation.current_pointer_path == expected_root / "current.json"
    assert not (expected_root / "staging" / "build-1").exists()

    manifest = json.loads(generation.manifest_path.read_text(encoding="utf-8"))
    current = json.loads(generation.current_pointer_path.read_text(encoding="utf-8"))
    matrix = np.load(generation.manifest_path.parent / "embeddings.npy")
    chunk_ids = json.loads((generation.manifest_path.parent / "chunk_ids.json").read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 3
    assert manifest["collection"] == "literature"
    assert manifest["collection_id"] == str(collection.id)
    assert manifest["generation_id"] == "generation-1"
    assert manifest["build_id"] == "build-1"
    assert manifest["target_revision"] == 7
    assert manifest["corpus_fingerprint_sha256"] == generation.corpus_fingerprint_sha256
    assert [item["name"] for item in manifest["index_files"]] == ["embeddings.npy", "chunk_ids.json"]
    assert current == {
        "generation_id": "generation-1",
        "manifest_sha256": generation.manifest_sha256,
        "target_revision": 7,
    }
    assert matrix.shape == (2, 2)
    assert chunk_ids == [str(chunks[0].id), str(chunks[1].id)]


def test_build_local_vector_index_generation_keeps_legacy_v2_artifacts_separate(tmp_path) -> None:
    collection, article, chunks = _vector_fixture()
    session = FakeSession(collection, [(chunks[0], article), (chunks[1], article)])
    legacy_manifest = build_local_vector_index(
        session,  # type: ignore[arg-type]
        data_root=tmp_path,
        collection="literature",
        embedding_model="test/model",
        embedding_dimension=2,
        embedder=lambda texts, batch_size: [[1.0, 0.0], [0.0, 1.0]],
    )

    build_local_vector_index_generation(
        session,  # type: ignore[arg-type]
        data_root=tmp_path,
        collection="literature",
        embedding_model="test/model",
        target_revision=1,
        embedding_dimension=2,
        generation_id="generation-1",
        build_id="build-1",
        embedder=lambda texts, batch_size: [[1.0, 0.0], [0.0, 1.0]],
    )

    assert legacy_manifest == tmp_path / "processed" / "vector_indexes" / "test_model" / "manifest.json"
    assert json.loads(legacy_manifest.read_text(encoding="utf-8"))["schema_version"] == 2
    assert (tmp_path / "processed" / "vector_indexes" / "literature" / "test_model" / "current.json").is_file()


def test_load_current_vector_index_generation_requires_ready_v3_state(tmp_path) -> None:
    from app.db.models import VectorIndexState

    collection, article, chunks = _vector_fixture()
    build_session = FakeSession(collection, [(chunks[0], article), (chunks[1], article)])
    generation = build_local_vector_index_generation(
        build_session,  # type: ignore[arg-type]
        data_root=tmp_path,
        collection="literature",
        embedding_model="test/model",
        target_revision=2,
        embedding_dimension=2,
        generation_id="generation-1",
        build_id="build-1",
        embedder=lambda texts, batch_size: [[1.0, 0.0], [0.0, 1.0]],
    )
    state = VectorIndexState(
        collection_id=collection.id,
        embedding_model="test/model",
        status="ready",
        desired_revision=2,
        active_revision=2,
        active_generation_id=generation.generation_id,
        active_manifest_sha256=generation.manifest_sha256,
        attempt_count=1,
    )
    session = FakeLifecycleSession(collection, [(chunks[0], article), (chunks[1], article)], state)

    loaded = load_current_vector_index_generation(
        session,  # type: ignore[arg-type]
        data_root=tmp_path,
        collection="literature",
        embedding_model="test/model",
    )

    assert loaded.manifest["schema_version"] == 3
    assert loaded.manifest["generation_id"] == "generation-1"
    assert loaded.chunk_ids == [str(chunks[0].id), str(chunks[1].id)]


def test_current_vector_index_generation_cache_reuses_ready_generation(tmp_path) -> None:
    from app.db.models import VectorIndexState

    clear_vector_index_cache()
    collection, article, chunks = _vector_fixture()
    generation = build_local_vector_index_generation(
        FakeSession(collection, [(chunks[0], article), (chunks[1], article)]),  # type: ignore[arg-type]
        data_root=tmp_path,
        collection="literature",
        embedding_model="test/model",
        target_revision=2,
        embedding_dimension=2,
        generation_id="generation-1",
        build_id="build-1",
        embedder=lambda texts, batch_size: [[1.0, 0.0], [0.0, 1.0]],
    )
    state = VectorIndexState(
        collection_id=collection.id,
        embedding_model="test/model",
        status="ready",
        desired_revision=2,
        active_revision=2,
        active_generation_id=generation.generation_id,
        active_manifest_sha256=generation.manifest_sha256,
        attempt_count=1,
    )
    session = FakeLifecycleSession(collection, [(chunks[0], article), (chunks[1], article)], state)

    first = load_current_vector_index_generation(
        session,  # type: ignore[arg-type]
        data_root=tmp_path,
        collection="literature",
        embedding_model="test/model",
        cache_enabled=True,
    )
    second = load_current_vector_index_generation(
        session,  # type: ignore[arg-type]
        data_root=tmp_path,
        collection="literature",
        embedding_model="test/model",
        cache_enabled=True,
    )

    assert second is first


def test_current_vector_index_generation_cache_does_not_serve_stale_state(tmp_path) -> None:
    from app.db.models import VectorIndexState

    clear_vector_index_cache()
    collection, article, chunks = _vector_fixture()
    generation = build_local_vector_index_generation(
        FakeSession(collection, [(chunks[0], article), (chunks[1], article)]),  # type: ignore[arg-type]
        data_root=tmp_path,
        collection="literature",
        embedding_model="test/model",
        target_revision=2,
        embedding_dimension=2,
        generation_id="generation-1",
        build_id="build-1",
        embedder=lambda texts, batch_size: [[1.0, 0.0], [0.0, 1.0]],
    )
    state = VectorIndexState(
        collection_id=collection.id,
        embedding_model="test/model",
        status="ready",
        desired_revision=2,
        active_revision=2,
        active_generation_id=generation.generation_id,
        active_manifest_sha256=generation.manifest_sha256,
        attempt_count=1,
    )
    session = FakeLifecycleSession(collection, [(chunks[0], article), (chunks[1], article)], state)

    load_current_vector_index_generation(
        session,  # type: ignore[arg-type]
        data_root=tmp_path,
        collection="literature",
        embedding_model="test/model",
        cache_enabled=True,
    )
    state.status = "stale"
    state.desired_revision = 3

    with pytest.raises(ValueError, match="state is stale"):
        load_current_vector_index_generation(
            session,  # type: ignore[arg-type]
            data_root=tmp_path,
            collection="literature",
            embedding_model="test/model",
            cache_enabled=True,
        )


def test_vector_index_generation_root_includes_collection_and_model(tmp_path) -> None:
    assert vector_index_generation_root(tmp_path, "lit/erature", "BAAI/bge-small-en-v1.5") == (
        tmp_path / "processed" / "vector_indexes" / "lit_erature" / "BAAI_bge-small-en-v1.5"
    )


def test_corpus_fingerprint_changes_when_chunk_evidence_changes() -> None:
    base = [{"chunk_id": "1", "chunk_index": 0, "source_text_checksum_sha256": "a"}]
    changed = [{"chunk_id": "1", "chunk_index": 0, "source_text_checksum_sha256": "b"}]

    assert corpus_fingerprint_sha256(base) == corpus_fingerprint_sha256(list(base))
    assert corpus_fingerprint_sha256(base) != corpus_fingerprint_sha256(changed)


def test_build_vector_index_generation_manifest_records_lifecycle_fields() -> None:
    collection, article, chunks = _vector_fixture()

    manifest = build_vector_index_generation_manifest(
        FakeSession(collection, [(chunks[0], article), (chunks[1], article)]),  # type: ignore[arg-type]
        collection="literature",
        embedding_model="test/model",
        embedding_dimension=2,
        generation_id="generation-1",
        build_id="build-1",
        target_revision=3,
        build_command="vector rebuild",
        batch_size=5,
        snapshot_created_at=datetime(2026, 8, 3, tzinfo=UTC),
        build_started_at=datetime(2026, 8, 3, tzinfo=UTC),
        build_finished_at=datetime(2026, 8, 3, tzinfo=UTC),
    )

    assert manifest["schema_version"] == 3
    assert manifest["status"] == "built"
    assert manifest["collection_id"] == str(collection.id)
    assert manifest["generation_id"] == "generation-1"
    assert manifest["target_revision"] == 3
    assert manifest["batch_size"] == 5
    assert manifest["build_command"] == "vector rebuild"
    assert manifest["corpus_fingerprint_sha256"]
    assert manifest["chunk_count"] == 2


def test_build_local_vector_index_normalizes_vectors(tmp_path) -> None:
    collection, article, chunks = _vector_fixture()

    output_path = build_local_vector_index(
        FakeSession(collection, [(chunks[0], article), (chunks[1], article)]),  # type: ignore[arg-type]
        data_root=tmp_path,
        collection="literature",
        embedding_model="test/model",
        embedding_dimension=2,
        embedder=lambda texts, batch_size: [[3.0, 4.0], [0.0, 2.0]],
    )

    import numpy as np

    matrix = np.load(output_path.parent / "embeddings.npy")
    assert np.allclose(np.linalg.norm(matrix, axis=1), 1.0)


def test_load_local_vector_index_validates_and_returns_database_rows(tmp_path) -> None:
    collection, article, chunks = _vector_fixture()
    session = FakeSession(collection, [(chunks[0], article), (chunks[1], article)])
    build_local_vector_index(
        session,  # type: ignore[arg-type]
        data_root=tmp_path,
        collection="literature",
        embedding_model="test/model",
        embedding_dimension=2,
        embedder=lambda texts, batch_size: [[1.0, 0.0], [0.0, 1.0]],
    )

    loaded = load_local_vector_index(
        session,  # type: ignore[arg-type]
        data_root=tmp_path,
        collection="literature",
        embedding_model="test/model",
    )

    assert loaded.chunk_ids == [str(chunks[0].id), str(chunks[1].id)]
    assert loaded.rows_by_chunk_id[str(chunks[0].id)][0] is chunks[0]
    assert loaded.manifest_sha256


def test_load_local_vector_index_rejects_schema_v1(tmp_path) -> None:
    collection, article, chunks = _vector_fixture()
    session = FakeSession(collection, [(chunks[0], article), (chunks[1], article)])
    manifest_path = _build_fixture_index(tmp_path, session)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["schema_version"] = 1
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="schema_version"):
        load_local_vector_index(
            session,  # type: ignore[arg-type]
            data_root=tmp_path,
            collection="literature",
            embedding_model="test/model",
        )


def test_load_local_vector_index_rejects_artifact_checksum_mismatch(tmp_path) -> None:
    collection, article, chunks = _vector_fixture()
    session = FakeSession(collection, [(chunks[0], article), (chunks[1], article)])
    manifest_path = _build_fixture_index(tmp_path, session)
    (manifest_path.parent / "chunk_ids.json").write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="checksum mismatch"):
        load_local_vector_index(
            session,  # type: ignore[arg-type]
            data_root=tmp_path,
            collection="literature",
            embedding_model="test/model",
        )


def test_load_local_vector_index_rejects_changed_chunk_text(tmp_path) -> None:
    collection, article, chunks = _vector_fixture()
    session = FakeSession(collection, [(chunks[0], article), (chunks[1], article)])
    _build_fixture_index(tmp_path, session)
    chunks[0].text = "changed after index build"

    with pytest.raises(ValueError, match="metadata mismatch"):
        load_local_vector_index(
            session,  # type: ignore[arg-type]
            data_root=tmp_path,
            collection="literature",
            embedding_model="test/model",
        )


def test_load_local_vector_index_rejects_non_normalized_matrix(tmp_path) -> None:
    collection, article, chunks = _vector_fixture()
    session = FakeSession(collection, [(chunks[0], article), (chunks[1], article)])
    manifest_path = _build_fixture_index(tmp_path, session)

    import numpy as np

    embeddings_path = manifest_path.parent / "embeddings.npy"
    np.save(embeddings_path, np.asarray([[2.0, 0.0], [0.0, 2.0]], dtype=np.float32))
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in payload["index_files"]:
        if item["name"] == "embeddings.npy":
            item["sha256"] = hashlib.sha256(embeddings_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="not cosine-normalized"):
        load_local_vector_index(
            session,  # type: ignore[arg-type]
            data_root=tmp_path,
            collection="literature",
            embedding_model="test/model",
        )


def test_build_local_vector_index_rejects_zero_vector(tmp_path) -> None:
    collection, article, chunks = _vector_fixture()
    with pytest.raises(ValueError, match="zero-length"):
        build_local_vector_index(
            FakeSession(collection, [(chunks[0], article), (chunks[1], article)]),  # type: ignore[arg-type]
            data_root=tmp_path,
            collection="literature",
            embedding_model="test/model",
            embedding_dimension=2,
            embedder=lambda texts, batch_size: [[0.0, 0.0], [0.0, 1.0]],
        )


def _vector_fixture() -> tuple[object, object, list[object]]:
    collection = SimpleNamespace(id=uuid.uuid4(), name="literature")
    article = SimpleNamespace(id=uuid.uuid4(), collection_id=collection.id, checksum_sha256="article-checksum")
    chunks = [
        SimpleNamespace(
            id=uuid.uuid4(),
            article_id=article.id,
            chunk_index=0,
            page_start=1,
            page_end=1,
            source_type="body",
            text_layer="original",
            char_count=5,
            text="alpha",
        ),
        SimpleNamespace(
            id=uuid.uuid4(),
            article_id=article.id,
            chunk_index=1,
            page_start=2,
            page_end=2,
            source_type="method",
            text_layer="original",
            char_count=4,
            text="beta",
        ),
    ]
    return collection, article, chunks


def _build_fixture_index(tmp_path, session: FakeSession):
    return build_local_vector_index(
        session,  # type: ignore[arg-type]
        data_root=tmp_path,
        collection="literature",
        embedding_model="test/model",
        embedding_dimension=2,
        embedder=lambda texts, batch_size: [[1.0, 0.0], [0.0, 1.0]],
    )
