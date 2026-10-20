"""Run local region OCR on an explicitly frozen stage12 scope; no DB or model calls."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from html import escape
from html.parser import HTMLParser
from pathlib import Path

import fitz

from app.evaluation.region_ocr import (
    VERSION,
    file_sha,
    inspect_engine,
    json_dump,
    render_region,
    run_region_ocr,
    verify_files,
)
from app.evaluation.source_gaps import VERSION as GAP_VERSION
from app.evaluation.source_gaps import RegisteredLine, SourceGaps, VisualAsset


def load_source(raw):
    fields = dict(raw)
    for name in ("media_box", "crop_box", "page_rect", "diagnostics"):
        fields[name] = tuple(fields[name])
    fields["lines"] = tuple(RegisteredLine(**{**line, "bbox": tuple(line["bbox"])}) for line in fields["lines"])
    fields["assets"] = tuple(VisualAsset(**{**asset, "bbox": tuple(asset["bbox"]),
        "overlapping_line_indices": tuple(asset["overlapping_line_indices"])}) for asset in fields["assets"])
    return SourceGaps(**fields)


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json_dump(value))


def details(title, value):
    text = value if isinstance(value, str) else json_dump(value)
    return f'<details><summary>{escape(title)}</summary><pre>{escape(text)}</pre></details>'


class ReviewParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = 0
        self.images = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == "tr" and fields.get("data-region"):
            self.rows += 1
        if tag == "img":
            self.images.append(fields["src"])
        if tag == "a":
            self.links.append(fields["href"])


def run(stage12, scope_path, output, protocol, *, command="tesseract", tessdata_dir=Path("data/tessdata")):
    previous = json.loads((stage12 / "report.json").read_bytes())
    prior_manifest = json.loads((stage12 / "input_manifest.json").read_bytes())
    scope = json.loads(scope_path.read_bytes())
    if previous["version"] != GAP_VERSION or scope["version"] != VERSION:
        raise ValueError("Region OCR requires the declared stage12 and scope versions")
    if scope["stage12_report_sha256"] != file_sha(stage12 / "report.json"):
        raise ValueError("Region OCR scope is not bound to this stage12 report")
    regions = scope["regions"]
    if not regions or len(regions) != scope["declared_region_count"]:
        raise ValueError("Region OCR scope is empty or differs from its declared count")
    if len({r["id"] for r in regions}) != len(regions):
        raise ValueError("Region OCR scope has duplicate region IDs")
    inputs = dict(prior_manifest["inputs"])
    inputs.update(prior_manifest["code"])
    for path in (stage12 / "report.json", stage12 / "input_manifest.json", scope_path, protocol):
        inputs[str(path.resolve())] = file_sha(path)
    prepared = []
    for region in regions:
        if not region["id"] or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for c in region["id"]):
            raise ValueError("Region ID must be a safe lowercase output directory name")
        case = next(c for c in previous["cases"] if c["id"] == region["case_id"])
        registry_path = stage12 / case["id"] / "source_gap_registry.json"
        if file_sha(registry_path) != case["source_gaps_sha256"]:
            raise ValueError("Frozen stage12 source-gap registry hash mismatch")
        inputs[str(registry_path.resolve())] = file_sha(registry_path)
        registry = json.loads(registry_path.read_bytes())
        entries = [e for e in registry if (e["source"]["article_id"], e["source"]["page"], e["source"]["layer_id"])
                   == (region["article_id"], region["page"], region["layer_id"])]
        if len(entries) != 1:
            raise ValueError("Region OCR source page identity is missing or ambiguous")
        source = load_source(entries[0]["source"])
        reference = region["reference"]
        if reference["kind"] == "raster_image":
            matches = [a.bbox for a in source.assets if a.asset_id == reference["asset_id"]
                       and a.kind == "raster_image" and a.geometry_valid]
        elif reference["kind"] == "closed_ruled_table_proposal":
            matches = [tuple(g["bbox"]) for t in case["table_protection"]
                       if (t["article_id"], t["page"], t["layer_id"]) == (source.article_id, source.page, source.layer_id)
                       for g in t["groups"] if g["kind"] == reference["kind"]
                       and g["caption_blocks"] == reference["caption_blocks"]]
        else:
            raise ValueError("Unsupported region source reference")
        if len(matches) != 1 or tuple(region["bbox"]) != matches[0]:
            raise ValueError("Region rectangle is not its exact frozen source reference")
        title = next(s["title"] for s in case["source_registry"] if s["article_id"] == source.article_id)
        inputs[source.original_pdf_path] = source.original_pdf_sha256
        inputs[source.selected_pdf_path] = source.selected_pdf_sha256
        prepared.append((region, source, title))
    verify_files(inputs)
    engine = inspect_engine(command, tessdata_dir)
    code = {str(path.resolve()): file_sha(path) for path in (Path(__file__), Path("app/evaluation/region_ocr.py"),
                                                           Path("app/extraction/ocr.py"))}
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"version": VERSION, "mode": "offline_local_ocr_candidates", "api_calls": 0, "inputs": inputs,
                "code": code, "engine": asdict(engine), "pymupdf_version": fitz.VersionBind, "scope": scope}
    write(output / "input_manifest.json", manifest)
    results = []
    rows = []
    for region, source, title in prepared:
        try:
            rendered = render_region(source, tuple(region["bbox"]), output / region["id"])
            result = {"id": region["id"], "title": title, "scope": region, **run_region_ocr(rendered, engine)}
        except (OSError, ValueError, RuntimeError) as exc:
            write(output / "failure.json", {"region": region, "error_type": type(exc).__name__, "error": str(exc),
                                           "completed_region_ids": [r["id"] for r in results], "status": "failed"})
            raise
        write(output / region["id"] / "result.json", result)
        results.append(result)
        link = Path(source.original_pdf_path).as_uri() + "#page=" + str(source.page)
        image = region["id"] + "/source.png"
        diagnostics = {"ocr": result["diagnostics"], "comparison": result["native_comparison"]}
        rows.append(f'<tr data-region="{escape(region["id"], quote=True)}"><td>{escape(title)} · p. {source.page}'
            f'<p>{escape(region["purpose"])}</p><a href="{escape(link, quote=True)}">Original PDF page</a>'
            f'<img src="{escape(image, quote=True)}" alt="Exact frozen source crop">'
            f'{details("Source identity and render geometry", result["render"])}</td>'
            f'<td><pre>{escape(result["text"])}</pre>{details("All words, confidences and exact PDF coordinates", result["words"])}</td>'
            f'<td>{details("Discrepancies and uncertainties - not a scientific score", diagnostics)}'
            f'{details("Frozen scope and local engine", {"scope": region, "engine": result["engine"]})}</td></tr>')
    verify_files(inputs)
    verify_files(code)
    verify_files(engine.file_hashes)
    for result in results:
        verify_files(result["artifact_hashes"])
        verify_files({result["render"]["image_path"]: result["render"]["image_sha256"]})
    html = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>ARIADNE region OCR candidates</title>'
        '<style>body{font:15px system-ui;margin:24px}table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #bbb;padding:12px;vertical-align:top}td{max-width:36vw}'
        'img{display:block;max-width:100%;height:auto;margin:12px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;'
        'max-height:65vh;overflow:auto}details{margin:10px 0}input{padding:10px;width:70%}</style>'
        f'<h1>Stage13 · {VERSION}</h1><p>Local OCR candidates from the declared frozen scope. '
        'Original PDF bytes unchanged; no API calls, database writes or answer activation. '
        'TXT/TSV preserved exactly. Low confidence and native token discrepancies are diagnostic only. '
        'Scientific accuracy, completeness, cells, unit/note linkage and plot values not evaluated.</p>'
        f'{details("Frozen input/code/engine manifest", manifest)}'
        '<label>Search all text and diagnostics <input id="q" type="search"></label>'
        '<table><thead><tr><th>Original source region</th><th>Raw OCR candidate text</th>'
        '<th>Native text comparison and diagnostics</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table>'
        '<script>document.getElementById("q").addEventListener("input",e=>{const q=e.target.value.toLowerCase();'
        'document.querySelectorAll("tr[data-region]").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});</script></html>')
    with (output / "review.html").open("x", encoding="utf-8") as stream:
        stream.write(html)
    parser = ReviewParser()
    parser.feed(html)
    if parser.rows != len(regions) or len(parser.links) != len(regions) or len(parser.images) != len(regions):
        raise ValueError("Region OCR static HTML scope coverage mismatch")
    if not all((output / image).is_file() for image in parser.images):
        raise ValueError("Region OCR HTML has a missing image")
    report = {"version": VERSION, "api_calls": 0, "scientific_accuracy": "not_evaluated", "automatic_promotion": False,
              "regions": results, "input_code_engine_pdf_hashes_unchanged": True,
              "html_qa": {"rows": parser.rows, "images": len(parser.images), "pdf_links": len(parser.links),
                          "visual_browser_check": "not_run"}}
    write(output / "report.json", report)
    print(json_dump({"version": VERSION, "api_calls": 0, "regions": [
        {"id": r["id"], "words": len(r["words"]), "characters": len(r["text"]), "diagnostics": r["diagnostics"]}
        for r in results], "html_qa": report["html_qa"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage12", required=True, type=Path)
    parser.add_argument("--scope", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="Fresh directory; existing outputs are never overwritten")
    parser.add_argument("--protocol", type=Path, default=Path("docs/records/region_ocr_protocol_v0.1.md"))
    parser.add_argument("--command", default="tesseract")
    parser.add_argument("--tessdata-dir", type=Path, default=Path("data/tessdata"))
    args = parser.parse_args()
    run(args.stage12, args.scope, args.output, args.protocol, command=args.command, tessdata_dir=args.tessdata_dir)


if __name__ == "__main__":
    main()
