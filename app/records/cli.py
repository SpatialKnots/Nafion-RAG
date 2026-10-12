"""Experimental record source export and integrity validation CLI."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import text

from app.core.config import get_settings
from app.documents.service import PageLayer
from app.records.readiness import assess_readiness
from app.records.review import render_review_packet
from app.records.runs import build_manifest
from app.records.schema import CandidateBundle
from app.records.sources import source_region_from_page, source_regions_from_pages, verify_live_region


def write_new(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(content + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    schema = commands.add_parser("schema", help="Write draft JSON Schema; refuse overwrite")
    schema.add_argument("--output", type=Path, required=True)
    source = commands.add_parser("source", help="Export exact stored page region; read-only transaction")
    source.add_argument("--article-id", type=UUID, required=True)
    source.add_argument("--page", type=int, required=True)
    source.add_argument("--layer", choices=("selected", "original", "ocr"), default="selected")
    source.add_argument("--start", type=int, default=0)
    source.add_argument("--end", type=int)
    source.add_argument("--selection-basis", choices=("manual_development", "expert_oracle", "fixed_page", "retrieval"), required=True)
    source.add_argument("--selection-note", required=True)
    source.add_argument("--output", type=Path, required=True)
    pages = commands.add_parser("source-pages", help="Export separate complete pages in declared order; read-only")
    pages.add_argument("--article-id", type=UUID, required=True)
    pages.add_argument("--pages", type=int, nargs="+", required=True)
    pages.add_argument("--layer", choices=("selected", "original", "ocr"), default="selected")
    pages.add_argument("--selection-basis", choices=("manual_development", "expert_oracle", "fixed_page", "retrieval"), required=True)
    pages.add_argument("--selection-note", required=True)
    pages.add_argument("--output", type=Path, required=True)
    validate = commands.add_parser("validate", help="Validate structure and exact evidence; no scientific admission")
    validate.add_argument("input", type=Path)
    validate.add_argument("--live", action="store_true", help="Also verify PDF bytes and stored text against local corpus")
    manifest = commands.add_parser("manifest", help="Fingerprint a validated artifact and current source code")
    manifest.add_argument("input", type=Path)
    manifest.add_argument("--output", type=Path, required=True)
    manifest.add_argument("--source-root", type=Path, default=Path("."))
    manifest.add_argument("--operation", choices=("context_export", "manual_candidate", "integrity_validation"), required=True)
    review = commands.add_parser("review-packet", help="Write offline Markdown review worksheet; no human decisions or gold")
    review.add_argument("input", type=Path)
    review.add_argument("--output", type=Path, required=True)
    smoke = commands.add_parser("smoke", help="Local-only structured field smoke; preserve responses and failures")
    smoke.add_argument("input", type=Path)
    smoke.add_argument("--output-dir", type=Path, required=True)
    smoke.add_argument("--task", required=True)
    smoke.add_argument("--endpoint", default="http://127.0.0.1:18086")
    smoke.add_argument("--model", required=True)
    smoke.add_argument("--runtime-manifest", type=Path, required=True)
    smoke.add_argument("--source-root", type=Path, default=Path("."))
    smoke.add_argument("--max-tokens", type=int, default=1536)
    smoke.add_argument("--timeout-seconds", type=int, default=600)
    smoke.add_argument("--seed", type=int, default=42)
    smoke.add_argument("--field", choices=(
        "sample_label", "property_name", "value", "unit", "temperature", "medium",
        "medium_composition", "composition_basis", "method", "data_origin",
    ), help="Use explicit v0.2 single-field contract; omitted preserves v0.1 ten-field contract")
    smoke.add_argument("--field-format", choices=("observation", "span"), default="observation",
                       help="With --field: observation uses v0.2; span uses explicit two-key v0.3 contract")
    comparison = commands.add_parser("compare", help="Compare saved field batches with provisional source-bound expectations")
    comparison.add_argument("--reference", type=Path, required=True)
    comparison.add_argument("--batches", type=Path, nargs="+", required=True)
    comparison.add_argument("--output-dir", type=Path, required=True)
    comparison.add_argument("--source-root", type=Path, default=Path("."))
    args = parser.parse_args()
    if args.command == "compare":
        from app.records.comparison import compare_batches

        report = compare_batches(args.reference, args.batches, args.output_dir, source_root=args.source_root)
        print(json.dumps({"reference_status": report["reference_status"], "scientific_admission": "not_evaluated",
                          "batches": [{"path": batch["path"], "summary": batch["summary"]} for batch in report["batches"]]}))
        return
    if args.command == "smoke":
        from app.records.smoke import run_smoke

        result = run_smoke(
            args.input, args.output_dir, task=args.task, endpoint=args.endpoint, model=args.model,
            runtime_manifest=args.runtime_manifest, source_root=args.source_root,
            max_tokens=args.max_tokens, timeout_seconds=args.timeout_seconds, seed=args.seed,
            field=args.field,
            field_format=args.field_format,
        )
        print(json.dumps(result, ensure_ascii=False))
        if result["status"] != "integrity_valid":
            raise SystemExit(1)
        return
    if args.command == "schema":
        write_new(args.output, json.dumps(CandidateBundle.model_json_schema(), ensure_ascii=False, indent=2))
        print(json.dumps({"output": str(args.output), "status": "draft_schema"}))
        return
    if args.command == "manifest":
        result = build_manifest(
            args.input, operation=cast(Literal["context_export", "manual_candidate", "integrity_validation"], args.operation),
            source_root=args.source_root,
        )
        write_new(args.output, json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps({"output": str(args.output), "status": "development_manifest"}))
        return
    if args.command == "review-packet":
        bundle = CandidateBundle.model_validate_json(args.input.read_bytes())
        write_new(args.output, render_review_packet(bundle))
        print(json.dumps({"output": str(args.output), "records": len(bundle.records), "review_state": "needs_review"}))
        return
    if args.command == "validate":
        bundle = CandidateBundle.model_validate_json(args.input.read_text(encoding="utf-8"))
        if args.live:
            from app.db.session import SessionLocal

            with SessionLocal() as session:
                session.execute(text("SET TRANSACTION READ ONLY"))
                for region in bundle.regions:
                    verify_live_region(session, get_settings(), region)
        print(json.dumps({
            "status": "evidence_integrity_valid", "live_verified": args.live,
            "regions": len(bundle.regions), "records": len(bundle.records), "scientific_admission": "not_evaluated",
            "readiness": [assess_readiness(record).to_dict() for record in bundle.records],
        }))
        return
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        session.execute(text("SET TRANSACTION READ ONLY"))
        basis = cast(Literal["manual_development", "expert_oracle", "fixed_page", "retrieval"], args.selection_basis)
        if args.command == "source-pages":
            regions = source_regions_from_pages(
                session, get_settings(), args.article_id, args.pages,
                layer=cast(PageLayer, args.layer), selection_basis=basis, selection_note=args.selection_note,
            )
        else:
            regions = (source_region_from_page(
                session, get_settings(), args.article_id, args.page,
                layer=cast(PageLayer, args.layer), start=args.start, end=args.end,
                selection_basis=basis, selection_note=args.selection_note,
            ),)
    bundle = CandidateBundle(run_id=uuid4(), created_at=datetime.now(UTC), producer="ariadne.records.source_v0.1", regions=regions)
    write_new(args.output, bundle.model_dump_json(indent=2))
    if args.command == "source-pages":
        print(json.dumps({"output": str(args.output), "region_ids": [region.region_id for region in regions], "records": 0}))
    else:
        print(json.dumps({"output": str(args.output), "region_id": regions[0].region_id, "records": 0}))


if __name__ == "__main__":
    main()
