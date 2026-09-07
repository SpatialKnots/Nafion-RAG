"""Isolated PostgreSQL/API smoke; schema rolls back, fixtures stay in tmp."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import fitz
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema

from app import main
from app.core.config import get_settings
from app.db.base import Base
from app.db.models import Article, Collection, IngestionJob, VectorIndexState
from app.db.session import engine, get_session
from app.ingestion.queue import claim_next_job, process_one_job, recover_stale_jobs
from app.retrieval.index_worker import process_one_vector_rebuild

root = Path("tmp/stage1_smoke_" + uuid4().hex).resolve()
root.mkdir(parents=True)
watched = root / "watched"
watched.mkdir()
pdf = watched / "synthetic.pdf"
doc = fitz.open()
page = doc.new_page()
page.insert_text(
    (50, 60), "ARIADNE synthetic pipeline fixture. Not scientific evidence.\nNafion membrane auditmarker conductivity transport test.\n" * 5
)
doc.save(pdf)
doc.close()
original = pdf.read_bytes()
settings = get_settings().model_copy(update={"data_root": root / "data", "vector_rebuild_debounce_seconds": 0})
schema = "audit_" + uuid4().hex
report = {"root": str(root), "schema": schema, "checks": []}


def check(name, condition, detail=None):
    report["checks"].append({"name": name, "passed": bool(condition), "detail": detail})
    print(name, bool(condition), detail, flush=True)
    assert condition, name


connection = engine.connect()
transaction = connection.begin()
connection.execute(CreateSchema(schema))
connection = connection.execution_options(schema_translate_map={None: schema})
Base.metadata.create_all(connection)
session = Session(connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
session.add(Collection(name="literature"))
session.commit()


def dependency():
    yield session


old_settings = main.get_settings
main.get_settings = lambda: settings
main.app.dependency_overrides[get_session] = dependency
try:
    with TestClient(main.app) as client:
        response = client.post("/libraries", json={"name": "synthetic audit", "path": str(watched)})
        check("create library", response.status_code == 200, response.text[:350])
        library_id = response.json()["id"]
        response = client.post(f"/libraries/{library_id}/scan")
        check("scan queues new PDF", response.status_code == 200 and response.json()["queued"] == 1, response.json())
        response = client.post(f"/libraries/{library_id}/scan")
        check("repeat scan creates no new job", response.json()["queued"] == 0, response.json())
        job = process_one_job(session, settings, "isolated-smoke")
        check("worker indexes PDF", job is not None and job.status == "indexed")
        article_id = str(job.article_id)
        check("watched original preserved", pdf.read_bytes() == original)
        check("index marked stale", session.scalar(select(VectorIndexState)).status == "stale")
        check("vector worker claims build", process_one_vector_rebuild(session, settings, "isolated-vector"))
        session.expire_all()
        state = session.scalar(select(VectorIndexState))
        check("index ready", state.status == "ready" and state.active_revision == state.desired_revision, state.last_error_message)
        for method in ["exact", "semantic", "hybrid", "hybrid_cross_lingual"]:
            response = client.get("/search", params={"q": "Nafion membrane auditmarker", "method": method})
            check("search " + method, response.status_code == 200 and bool(response.json()["results"]), response.text[:160])
            hit = response.json()["results"][0]
            check("article trace " + method, hit["article_id"] == article_id)
        response = client.get(f"/articles/{article_id}/pdf?layer=original")
        check(
            "PDF exact bytes",
            response.status_code == 200 and hashlib.sha256(response.content).digest() == hashlib.sha256(original).digest(),
        )
        response = client.get(f"/articles/{article_id}/pages/1")
        check("page text trace", response.status_code == 200 and "auditmarker" in response.text)
        response = client.get(f"/articles/{article_id}/chunks/{hit['chunk_id']}/context")
        check("chunk context", response.status_code == 200 and "auditmarker" in response.text)
        response = client.get(f"/articles/{article_id}/pages/context?page_start=1&page_end=1")
        check("page range context", response.status_code == 200 and "auditmarker" in response.text)
        response = client.post("/ingestion/uploads", files={"files": ("duplicate.pdf", original, "application/pdf")})
        check("duplicate upload", response.json()["items"][0]["status"] == "duplicate", response.json())
        response = client.post("/ingestion/uploads", files={"files": ("broken.pdf", b"%PDF-1.4 corrupt", "application/pdf")})
        check("corrupt upload rejected", response.json()["items"][0]["status"] == "failed", response.json())
        (watched / "broken.pdf").write_bytes(b"%PDF-1.4 corrupt")
        client.post(f"/libraries/{library_id}/scan")
        failed = process_one_job(session, settings, "isolated-smoke")
        check("corrupt library PDF fails visibly", failed.status == "failed" and bool(failed.error_type), failed.error_type)
        collection_id = session.scalar(select(Collection.id))
        missing = IngestionJob(collection_id=collection_id, input_path=str(root / "absent.pdf"), status="queued")
        session.add(missing)
        session.commit()
        claimed = claim_next_job(session, settings, "interrupted-worker")
        session.commit()
        check("job claimed before interruption", claimed.id == missing.id and claimed.status == "processing")
        claimed.heartbeat_at = datetime.now(UTC) - timedelta(seconds=settings.ingestion_lease_seconds + 1)
        session.commit()
        check("expired lease recovered", recover_stale_jobs(session, settings) == 1 and claimed.status == "queued")
        session.commit()
        failed = process_one_job(session, settings, "replacement-worker")
        check("missing queued file diagnostic", failed.status == "failed" and failed.error_type == "MissingStagedFile")
        check("failures created no articles", len(list(session.scalars(select(Article)))) == 1)
        check("original still immutable", pdf.read_bytes() == original)
        raster_source = fitz.open(stream=original, filetype="pdf")
        pixmap = raster_source[0].get_pixmap(matrix=fitz.Matrix(2, 2))
        scanned = fitz.open()
        scanned_page = scanned.new_page()
        scanned_page.insert_image(scanned_page.rect, stream=pixmap.tobytes("png"))
        scanned_bytes = scanned.tobytes()
        scanned.close()
        raster_source.close()
        response = client.post("/ingestion/uploads", files={"files": ("scan.pdf", scanned_bytes, "application/pdf")})
        check("scanned upload queued", response.json()["items"][0]["job"]["status"] == "queued")
        ocr_job = process_one_job(session, settings, "isolated-ocr")
        check("OCR ingestion succeeds", ocr_job.status == "indexed", ocr_job.error_message)
        ocr_article = session.get(Article, ocr_job.article_id)
        check("OCR copy exists", bool(ocr_article.pdf_ocr_path) and Path(ocr_article.pdf_ocr_path).is_file())
        response = client.get(f"/articles/{ocr_article.id}/pdf?layer=original")
        check("scanned original unchanged", response.content == scanned_bytes)
        response = client.get(f"/articles/{ocr_article.id}/pages/1")
        check("OCR page contains recovered text", response.status_code == 200 and "Nafion" in response.text)
finally:
    main.get_settings = old_settings
    main.app.dependency_overrides.clear()
    session.close()
    transaction.rollback()
    connection.close()
    report["schema_rolled_back"] = True
    (root / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("REPORT", root / "report.json", flush=True)
