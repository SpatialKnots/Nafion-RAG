"""Serve only the new HTTP UI on loopback with explicitly synthetic preparation seams."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db.session import get_session
from app.generation import claim_review_routes as routes
from app.generation.answer_evidence_packet import build_packet, serialize_packet
from app.generation.answer_requirements import build_requirements
from app.generation.claim_checks import fact_assertion
from scripts import gigachat_answer_smoke as files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    policy = files.NetworkPolicy()
    sys.addaudithook(policy)
    case = json.loads((files.ROOT / "output/answer_requirements_20261109/controls_v01.json").read_bytes())[0]
    observed = []

    def prepare(session, request):
        parent = copy.deepcopy(case["parent"])
        wrapped = {"version": "answer_requirements_preparation_v0.1", "preparation": parent,
            "requirements": build_requirements(parent, request.model_dump(mode="json")), "generation_performed": False,
            "external_request_constructed": False, "network_ready": False}
        packet = build_packet(wrapped)
        observed.append({"request_scope": request.model_dump(mode="json"), "packet_id": packet["packet_id"]})
        files.save(args.output / f"packet_{len(observed):03}.json", serialize_packet(packet))
        return packet

    routes.prepare_packet = prepare
    original_layout = routes._layout

    def layout(title, body):
        return original_layout(title, "<aside class='panel'>Локальный UI-тест: synthetic preparation с раскрытым real raw. "
            "БД, модель, OAuth и context action не вызываются.</aside>" + body)

    routes._layout = layout
    app = FastAPI(title="ARIADNE synthetic claim-review UI test")
    app.mount("/ui/assets/brand", StaticFiles(directory=files.ROOT / "app/static/brand"), name="brand")
    app.dependency_overrides[get_session] = lambda: object()
    app.include_router(routes.router)
    request = routes.PreparationRequest(question=case["parent"]["question"])
    packet = prepare(None, request)
    row = next(r for r in packet["content"]["facts"] if r["fact"]["property"] == "capacity_retention")
    assertion = fact_assertion(row["fact"])
    assertion["sample"]["text"] = "WRONG_CELL_CONSTRUCTED"
    claims = [{"id": "constructed_wrong_cell", "kind": "fact", "fact_ref": row["id"], "assertion": assertion}]
    data = {"question": request.question, "claims": claims, "packet_id": packet["packet_id"],
            "ui_path": routes.UI_PATH, "synthetic_preparation": True, "model_calls": 0, "DB_calls": 0}
    files.write(args.output / "inputs.json", data)
    print(json.dumps(data, ensure_ascii=True), flush=True)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="info"))

    @app.post("/_test/shutdown")
    def shutdown():
        server.should_exit = True
        return {"stopping_synthetic_test_server": True}

    try:
        server.run()
    finally:
        files.write(args.output / "result.json", {"preparations": observed, "external_network_denials": policy.denied,
                    "synthetic_preparation": True, "real_model_calls": 0, "real_oauth_calls": 0, "real_DB_calls": 0})
        files.manifest(args.output)


if __name__ == "__main__":
    main()
