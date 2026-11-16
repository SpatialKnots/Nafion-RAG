"""Read-only replay of the 26 archived plans through the web pipeline; no model network.

Only PostgreSQL and original PDFs are read. GigaChat transport is intercepted before
either OAuth or chat networking, and saved answers are supplied only after exact
native answer-request byte equality. Never reuse an experiment allowance or ledger.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.generation import current_answer
from app.generation.gigachat import GigaChatAnswerProvider


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify(output: Path) -> None:
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    root = Path("output/fan_doi_besenhard_rewriting_20261113")
    answers = Path("output/fan_doi_besenhard_answer_live_20261113/live")
    plans = [r for r in read(root / "plans_freeze_v01/plans.json")["cases"] if r["accepted"]]
    if len(plans) != 26:
        raise ValueError("Expected the 26 archived accepted rewrite plans")
    settings = get_settings()
    results = []
    for row in plans:
        identifier = row["id"]
        old = root / "prepared_v01" / identifier
        actual = answers / identifier
        options = {"library_source_id": None, **read(old / "api_request.json")}
        observations = {"rewrite_request_equal": False, "answer_request_equal": None, "intercepted_operations": 0}

        def transport(self, url, body, authorization, *, oauth=False,
                      observations=observations, identifier=identifier, actual=actual):
            observations["intercepted_operations"] += 1
            if oauth:
                return b'{"access_token":"offline-replay-token"}'
            native = json.loads(body)
            if "english_question" in native["response_format"]["schema"].get("properties", {}):
                observations["rewrite_request_equal"] = body == (root / "rewrites" / identifier / "request.json").read_bytes()
                return (root / "rewrites" / identifier / "response.bin").read_bytes()
            observations["answer_request_equal"] = body == (actual / "request.json").read_bytes()
            if not observations["answer_request_equal"]:
                raise ValueError("Offline replay stopped: native answer request differs from archived request")
            return (actual / "response.bin").read_bytes()

        with SessionLocal() as session, patch.object(GigaChatAnswerProvider, "_post", transport):
            session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            try:
                code, result, _ = current_answer.run(session, settings, options)
            finally:
                session.rollback()
        expected = read(actual / "api_response.json")["body"]
        trace = read(old / "trace.json")
        checks = {"answer_equal": result["answer"] == expected["answer"],
                  "review_equal": result["review"] == expected["review"],
                  "delivery_equal": result["delivery_status"] == expected["delivery_status"],
                  "retrieval_equal": result.get("preparation", {}).get("retrieval") == trace["retrieval"],
                  "evidence_equal": result.get("preparation", {}).get("evidence") == trace["evidence"],
                  "metadata_equal": result.get("preparation", {}).get("metadata") == trace["metadata"],
                  "title_context_equal": result["rewriting"]["plan"] is not None and
                      result["rewriting"]["plan"]["article_context"] == row["plan"]["article_context"]}
        record = {"id": identifier, "http_code": code, "status": result["status"], **observations, "checks": checks,
                  "passed": code == 200 and all(checks.values()) and observations["answer_request_equal"] is True,
                  "error": result.get("error")}
        (output / (identifier + ".json")).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        results.append(record)
        print(identifier, "PASS" if record["passed"] else "DIFFERENCE", flush=True)
    summary = {"cases": len(results), "passed": sum(r["passed"] for r in results), "results": results,
               "real_model_calls": 0, "real_oauth_calls": 0, "database_mode": "read_only_rollback",
               "scientific_acceptance": "not_evaluated", "saved_rewrites_have_historical_manual_meaning_review": True}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}), flush=True)
    if summary["passed"] != 26:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    verify(parser.parse_args().output)
