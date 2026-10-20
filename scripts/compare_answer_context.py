"""Offline stage07 compaction/block-window audit; never calls a model or database.

Run from the repository root: python -m scripts.compare_answer_context --help
Private input/output artifacts are intentionally excluded from Git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from html import escape
from html.parser import HTMLParser
from pathlib import Path

import fitz

from app.evaluation.answer_trace import TraceResponsesProvider, encode
from app.evaluation.context_compaction import (
    VERSION,
    SourcePage,
    compact_source_pages,
    complete_pages_in_request,
    require_no_complete_pages,
)
from app.evaluation.context_windows import VERSION as WINDOW_VERSION
from app.evaluation.context_windows import read_registered_blocks, select_block_windows
from app.evaluation.layout_groups import VERSION as LAYOUT_VERSION
from app.evaluation.layout_groups import propose_layout_groups
from app.evaluation.ruled_tables import VERSION as TABLE_VERSION
from app.evaluation.ruled_tables import propose_ruled_tables, read_registered_rules
from app.evaluation.source_gaps import VERSION as GAPS_VERSION
from app.evaluation.source_gaps import bind_source_gaps, read_source_gaps
from app.generation.evidence_adequacy import assess_evidence_adequacy
from app.generation.providers import Evidence
from app.retrieval.cross_lingual import glossary_terms_for_concepts


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("xb") as stream:
        stream.write(encode(value))


def details(title, value):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return f"<details><summary>{escape(title)}</summary><pre>{escape(text)}</pre></details>"


def write_source_gap_review(output, report, input_manifest):
    rows = []
    unique_pages = set()
    counts = {"raster_occurrences": 0, "vector_entries": 0, "rasters_without_overlapping_registered_lines": 0,
              "pages_with_unproven_text_geometry": 0}
    for case in report["cases"]:
        for entry in case["source_gaps"]:
            source = entry["source"]
            unique_pages.add((source["article_id"], source["page"], source["layer_id"]))
            images = [a for a in source["assets"] if a["kind"] == "raster_image"]
            drawings = [a for a in source["assets"] if a["kind"] == "vector_drawing"]
            absent = sum(a["text_overlap"] == "none" for a in images)
            counts["raster_occurrences"] += len(images)
            counts["vector_entries"] += len(drawings)
            counts["rasters_without_overlapping_registered_lines"] += absent
            counts["pages_with_unproven_text_geometry"] += not source["text_geometry_proven"]
            title = next(s["title"] for s in case["source_registry"] if s["article_id"] == source["article_id"])
            link = Path(source["original_pdf_path"]).as_uri() + "#page=" + str(source["page"])
            rows.append(f'<tr data-case="{escape(case["id"], quote=True)}"><td>{escape(case["question"])}</td>'
                f'<td><a href="{escape(link, quote=True)}">{escape(title)} · p. {source["page"]}</a>'
                f'{details("Original and selected PDF identity", {k: v for k, v in source.items() if "pdf" in k})}</td>'
                f'<td>{len(images)} raster occurrences; {len(drawings)} vector entries; '
                f'{absent} rasters without overlapping registered lines. Scientific role unknown.'
                f'{details("Every source asset and exact text line", source)}</td>'
                f'<td>{details("Selected citations, proposed caption relations and uncertainties", entry["selection"])}</td></tr>')
    html = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>ARIADNE source graphics review</title>'
        '<style>body{font:15px system-ui;margin:24px}table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #bbb;padding:10px;vertical-align:top}td{max-width:35vw}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:55vh;overflow:auto}input{width:70%;padding:10px}</style>'
        f'<h1>Stage12 · {GAPS_VERSION}</h1><p>All declared pages from four frozen stage07 cases. '
        'Occurrence counts include repeats across questions; no size filtering or figure reconstruction. '
        'Pixels/vector paths are absent from text-only messages. Text overlap does not prove complete OCR. '
        'Scientific relevance and information loss not evaluated; unchanged stage11 selection, zero API calls.</p>'
        f'{details("Frozen input/code manifest", input_manifest)}{details("Per-case registration counts", counts)}'
        '<label>Search all source/diagnostic text <input id="q" type="search"></label>'
        '<table><thead><tr><th>Question</th><th>Source/page</th><th>Unserialized graphics</th>'
        '<th>Exact selected text binding</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table>'
        '<script>document.getElementById("q").addEventListener("input",e=>{const q=e.target.value.toLowerCase();'
        'document.querySelectorAll("tr[data-case]").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});</script></html>')
    (output / "source_gap_review.html").write_text(html, encoding="utf-8")
    parser = ReviewParser()
    parser.feed(html)
    if parser.rows != len(rows) or len(parser.links) != len(rows):
        raise ValueError("Source-gap static HTML page/link coverage check failed")
    return {**counts, "page_registrations": len(rows), "unique_pages": len(unique_pages),
            "html_rows": parser.rows, "existing_pdf_links": len(parser.links), "visual_browser_check": "not_run"}


class ReviewParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = 0
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr" and attrs.get("data-case"):
            self.rows += 1
        if tag == "a":
            self.links.append(attrs.get("href", ""))


def run(baseline, output, protocol, *, block_windows=False, layout_groups=False, ruled_tables=False, source_gaps=False):
    if layout_groups and not block_windows:
        raise ValueError("Layout grouping requires the registered block-window path")
    if ruled_tables and not layout_groups:
        raise ValueError("Ruled tables require the registered layout-group path")
    if source_gaps and not ruled_tables:
        raise ValueError("Source-gap audit requires the unchanged stage11 selection path")
    version = (GAPS_VERSION if source_gaps else TABLE_VERSION if ruled_tables
               else LAYOUT_VERSION if layout_groups else WINDOW_VERSION if block_windows else VERSION)
    stage = ("stage12" if source_gaps else "stage11" if ruled_tables else "stage10" if layout_groups
             else "stage09" if block_windows else "stage08")
    manifest_path = baseline / "pre_inference_manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    questions = json.loads((baseline / "questions.json").read_bytes())
    if len(questions) != 4 or len(manifest["cases"]) != 4:
        raise ValueError("This declared audit requires exactly four stage07 cases")
    inputs = {str(manifest_path.resolve()): sha(manifest_path), str(protocol.resolve()): sha(protocol)}
    for name in ("questions", "protocol"):
        path = baseline / ("questions.json" if name == "questions" else "protocol.md")
        if sha(path) != manifest[name + "_sha256"]:
            raise ValueError("Baseline hash mismatch: " + str(path))
        inputs[str(path.resolve())] = sha(path)
    for entry in manifest["cases"]:
        for name in ("trace", "sources", "request"):
            expected = entry[name + "_sha256"]
            if expected is not None:
                path = baseline / entry["id"] / (name + ".json")
                if sha(path) != expected:
                    raise ValueError("Baseline hash mismatch: " + str(path))
                inputs[str(path.resolve())] = expected
    selected_pdfs = {}
    if block_windows:
        snapshot_path = baseline / "corpus_snapshot.json"
        snapshot = json.loads(snapshot_path.read_bytes())
        fingerprint = hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
        if fingerprint != manifest["corpus_sha256"]:
            raise ValueError("Frozen corpus snapshot fingerprint mismatch")
        inputs[str(snapshot_path.resolve())] = sha(snapshot_path)
        frozen_pdfs = {str(Path(path).resolve()): checksum for path, checksum in snapshot["pdfs"].items()}
        for entry in manifest["cases"]:
            for source in json.loads((baseline / entry["id"] / "sources.json").read_bytes()):
                for layer in source["layer_pages"]:
                    path = Path(layer["source_pdf_path"]).resolve()
                    checksum = frozen_pdfs[str(path)]
                    if sha(path) != checksum:
                        raise ValueError("Selected-layer PDF changed since stage07")
                    selected_pdfs[str(path)] = checksum
                    inputs[str(path)] = checksum
    code = {str(path.resolve()): sha(path) for path in (
        Path(__file__), Path("app/evaluation/context_compaction.py"), Path("app/evaluation/answer_trace.py"),
        Path("app/generation/providers.py"), Path("app/generation/evidence_adequacy.py"),
        Path("app/generation/required_concepts.py"), Path("app/retrieval/cross_lingual.py"),
        Path("app/retrieval/cross_lingual_glossary.yaml"))}
    if block_windows:
        path = Path("app/evaluation/context_windows.py")
        code[str(path.resolve())] = sha(path)
    if layout_groups:
        path = Path("app/evaluation/layout_groups.py")
        code[str(path.resolve())] = sha(path)
    if ruled_tables:
        path = Path("app/evaluation/ruled_tables.py")
        code[str(path.resolve())] = sha(path)
    if source_gaps:
        path = Path("app/evaluation/source_gaps.py")
        code[str(path.resolve())] = sha(path)
    output.mkdir(parents=True, exist_ok=False)
    input_manifest = {"version": version, "inputs": inputs, "code": code,
                      "baseline_corpus_sha256": manifest["corpus_sha256"], "mode": "offline_no_inference"}
    if block_windows:
        input_manifest.update(selected_pdf_hashes=selected_pdfs, pymupdf_version=fitz.VersionBind)
    write(output / "input_manifest.json", input_manifest)
    report = {"version": version, "api_calls": 0, "scientific_accuracy": "not_evaluated", "cases": []}
    rows = []
    pdf_hashes = {}
    for question, entry in zip(questions, manifest["cases"], strict=True):
        if question["id"] != entry["id"]:
            raise ValueError("Question/manifest order differs")
        folder = baseline / question["id"]
        trace = json.loads((folder / "trace.json").read_bytes())
        sources = json.loads((folder / "sources.json").read_bytes())
        pages = []
        by_chunk = {source["chunk_id"]: source for source in sources}
        for source in sources:
            pdf = Path(source["pdf_path"])
            pdf_hashes.setdefault(str(pdf), sha(pdf))
            if pdf_hashes[str(pdf)] != source["pdf_sha256"]:
                raise ValueError("Original PDF checksum mismatch")
            if hashlib.sha256(source["chunk_text"].encode()).hexdigest() != source["chunk_text_sha256"]:
                raise ValueError("Chunk checksum mismatch")
            for layer in source["layer_pages"]:
                if hashlib.sha256(layer["text"].encode()).hexdigest() != layer["text_sha256"]:
                    raise ValueError("Layer checksum mismatch")
                pages.append(SourcePage(source["article_id"], source["chunk_id"], layer["page"],
                    layer["layer_type"], layer["layer_id"], layer["text"], source["pdf_path"], source["pdf_sha256"]))
        before = [Evidence(**item) for item in trace["evidence"]]
        for item in before:
            if item.source_type != "table_derived" and item.text != by_chunk[item.chunk_id]["chunk_text"]:
                raise ValueError("Baseline evidence is not its registered chunk")
        compacted = compact_source_pages(before, pages)
        prepass = compacted
        case_folder = output / question["id"]
        case_folder.mkdir()
        block_registry = []
        layout_registry = []
        rule_registry = []
        table_registry = []
        gap_registry = []
        groups_by_key = {}
        block_baseline = None
        layout_baseline = None
        anchor_terms = trace["metadata"]["answer_evidence_selection"]["distinctive_terms"]
        if block_windows:
            unique_maps = {}
            for source in sources:
                for layer in source["layer_pages"]:
                    page = next(p for p in pages if p.chunk_id == source["chunk_id"] and p.layer_id == layer["layer_id"])
                    key = (page.article_id, page.page, page.layer_id)
                    if key not in unique_maps:
                        path = Path(layer["source_pdf_path"]).resolve()
                        unique_maps[key] = read_registered_blocks(page, path, selected_pdfs[str(path)])
            block_registry = [asdict(mapping) for mapping in unique_maps.values()]
            write(case_folder / "geometry_registry.json", block_registry)
            protected = None
            if layout_groups:
                protected = {}
                for key, mapping in unique_maps.items():
                    page = next(p for p in pages if (p.article_id, p.page, p.layer_id) == key)
                    protection = propose_layout_groups(page, mapping)
                    groups_by_key[key] = list(protection.groups)
                    layout_registry.append({"article_id": page.article_id, "page": page.page,
                                            "layer_id": page.layer_id, **asdict(protection)})
                    protected[key] = [pair for group in protection.groups for pair in group.page_ranges]
                write(case_folder / "layout_registry.json", layout_registry)
                block_baseline = select_block_windows(prepass, pages, list(unique_maps.values()), anchor_terms)
            if ruled_tables:
                layout_baseline = select_block_windows(prepass, pages, list(unique_maps.values()), anchor_terms, protected_ranges=protected)
                for key, mapping in unique_maps.items():
                    page = next(p for p in pages if (p.article_id, p.page, p.layer_id) == key)
                    rules = read_registered_rules(page, mapping)
                    rule_registry.append(asdict(rules))
                    protection = propose_ruled_tables(page, mapping, rules)
                    groups_by_key[key].extend(protection.groups)
                    table_registry.append({"article_id": page.article_id, "page": page.page,
                                           "layer_id": page.layer_id, **asdict(protection)})
                    protected[key].extend(pair for group in protection.groups for pair in group.page_ranges)
                write(case_folder / "vector_rules_registry.json", rule_registry)
                write(case_folder / "table_registry.json", table_registry)
            compacted = select_block_windows(prepass, pages, list(unique_maps.values()), anchor_terms, protected_ranges=protected)
            if source_gaps:
                for key, mapping in unique_maps.items():
                    page = next(p for p in pages if (p.article_id, p.page, p.layer_id) == key)
                    gaps = read_source_gaps(page, mapping)
                    gap_registry.append({"source": asdict(gaps), "selection": bind_source_gaps(
                        gaps, page, compacted.slices, groups_by_key[key])})
                write(case_folder / "source_gap_registry.json", gap_registry)
        for fragment in compacted.slices:
            emitted = next(item for item in compacted.evidence if item.citation_id == fragment.citation_id)
            stored = by_chunk[fragment.chunk_id]
            layer = next(layer for layer in stored["layer_pages"] if layer["layer_id"] == fragment.layer_id)
            if not (emitted.text == stored["chunk_text"][fragment.chunk_start:fragment.chunk_end]
                    == layer["text"][fragment.page_start:fragment.page_end]):
                raise ValueError("Exact source slice comparison failed")
        provider = TraceResponsesProvider(model=manifest["model"], api_key="offline-no-credential")
        # request() only constructs bytes; generate()/transport are never called.
        candidate = provider.request(question["query"], compacted.evidence) if compacted.evidence else None
        user_text = "" if candidate is None else candidate["input"][1]["content"]
        full_pages = complete_pages_in_request(user_text, pages)
        scope_error = None
        try:
            require_no_complete_pages(user_text, pages)
        except ValueError as exc:
            scope_error = str(exc)
        concepts = trace["metadata"]["retrieval"].get("cross_lingual", {}).get("matched_concepts", [])
        adequacy = assess_evidence_adequacy(question["query"], compacted.evidence,
                                           concept_terms=glossary_terms_for_concepts(concepts))
        case = {"id": question["id"], "question": question["query"], "before_evidence": len(before),
                "after_evidence": len(compacted.evidence), "before_characters": sum(len(item.text) for item in before),
                "after_characters": sum(len(item.text) for item in compacted.evidence),
                "baseline_request_bytes": None if entry["request_sha256"] is None else (folder / "request.json").stat().st_size,
                "candidate_request_bytes": None if candidate is None else len(encode(candidate)),
                "baseline_adequacy": trace["metadata"]["evidence_adequacy"], "candidate_adequacy": asdict(adequacy),
                "complete_pages_in_candidate": full_pages, "scope_guard_error": scope_error,
                "api_calls": 0, "new_answer": None, "token_savings": "not_measured",
                "source_registry": sources,
                "result": asdict(compacted)}
        if block_windows:
            case.update(prepass_result=asdict(prepass), block_registry=block_registry, anchor_terms=anchor_terms,
                        geometry_sha256=sha(case_folder / "geometry_registry.json"),
                        prepass_characters=sum(len(item.text) for item in prepass.evidence))
        if layout_groups:
            case.update(layout_protection=layout_registry, layout_sha256=sha(case_folder / "layout_registry.json"),
                        block_baseline_result=asdict(block_baseline),
                        block_baseline_characters=sum(len(item.text) for item in block_baseline.evidence))
        if ruled_tables:
            case.update(vector_rules=rule_registry, table_protection=table_registry,
                        rules_sha256=sha(case_folder / "vector_rules_registry.json"),
                        tables_sha256=sha(case_folder / "table_registry.json"), layout_baseline_result=asdict(layout_baseline),
                        layout_baseline_characters=sum(len(item.text) for item in layout_baseline.evidence))
        if source_gaps:
            case.update(source_gaps=gap_registry, source_gaps_sha256=sha(case_folder / "source_gap_registry.json"))
        write(case_folder / "comparison.json", case)
        if candidate is not None:
            write(case_folder / "candidate_request_not_sent.json", candidate)
        report["cases"].append(case)
        before_details = "".join(details(item.citation_id + " / " + item.title, item.text) for item in before)
        after_details = "".join(details(item.citation_id + " / " + item.title, item.text) for item in compacted.evidence)
        if block_windows:
            after_details += details("Prepass text and diagnostics", asdict(prepass))
            after_details += details("Verified PDF block registry and query terms", {"blocks": block_registry, "terms": anchor_terms})
        if layout_groups:
            after_details += details("Protected layout proposals and unresolved boundaries", layout_registry)
            after_details += details("Stage09 block-only baseline", asdict(block_baseline))
        if ruled_tables:
            after_details += details("Closed table proposals, notes, reference paragraphs and rule registry",
                                     {"proposals": table_registry, "rules": rule_registry})
            after_details += details("Stage10 layout-only baseline", asdict(layout_baseline))
        if source_gaps:
            after_details += details("Source graphics absent from text-only messages; relevance/completeness not evaluated", gap_registry)
        links = "".join(f'<p><a href="{escape(Path(source["pdf_path"]).as_uri(), quote=True)}">'
                        f'{escape(source["title"])} · pp. {source["page_start"]}–{source["page_end"]}</a></p>' for source in sources)
        rows.append(f'<tr data-case="{escape(question["id"], quote=True)}"><td>{escape(question["query"])}</td>'
                    f'<td>{case["before_characters"]} → {case["after_characters"]} characters'
                    f'{before_details}</td><td>{after_details}{details("Exact slices", asdict(compacted)["slices"])}</td>'
                    f'<td>{details("All omissions and uncertainties", compacted.diagnostics)}'
                    f'{details("Original source registry and full page layers", sources)}'
                    f'{details("Adequacy", case["candidate_adequacy"])}'
                    f'{escape(scope_error or "Scope guard accepted; no inference in this stage")}'
                    f'{details("Remaining full pages", full_pages)}{links}</td></tr>')
    report["pdf_hashes"] = pdf_hashes
    report["input_files_unchanged"] = all(sha(Path(path)) == checksum for path, checksum in inputs.items())
    report["code_unchanged"] = all(sha(Path(path)) == checksum for path, checksum in code.items())
    report["pdf_files_unchanged"] = all(sha(Path(path)) == checksum for path, checksum in pdf_hashes.items())
    if not all(report[key] for key in ("input_files_unchanged", "code_unchanged", "pdf_files_unchanged")):
        raise ValueError("Inputs/code/PDFs changed during replay")
    html = (f'<!doctype html><html lang="en"><meta charset="utf-8"><title>ARIADNE {stage} context review</title>'
        '<style>body{font:15px system-ui;margin:24px}table{border-collapse:collapse;width:100%}'
        'td,th{border:1px solid #bbb;padding:10px;vertical-align:top}td{max-width:35vw}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:55vh;overflow:auto}'
        'details{margin:8px 0}input{width:70%;padding:10px}</style>'
        f'<h1>ARIADNE {stage} · {version}</h1><p>Frozen stage07 input; offline replay. '
        'Reference exclusions are algorithm proposals. Zero API calls; no new answers or scientific accuracy score. '
        'Complete-page guard remains separate from adequacy. Original damaged source text is preserved.</p>'
        f'{details("Input and code manifest", json.loads((output / "input_manifest.json").read_bytes()))}'
        '<label>Search all source/diagnostic text <input id="q" type="search"></label>'
        '<table><thead><tr><th>Question</th><th>Before</th><th>After: exact text</th>'
        '<th>Diagnostics and original files</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table>'
        '<script>document.getElementById("q").addEventListener("input",e=>{const q=e.target.value.toLowerCase();'
        'document.querySelectorAll("tr[data-case]").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});</script></html>')
    (output / "review.html").write_text(html, encoding="utf-8")
    parser = ReviewParser()
    parser.feed(html)
    if parser.rows != 4 or len(parser.links) != sum(len(json.loads((baseline / q["id"] / "sources.json").read_bytes()))
                                                 for q in questions):
        raise ValueError("Static HTML row/link check failed")
    report["html_qa"] = {"rows": parser.rows, "existing_pdf_links": len(parser.links), "visual_browser_check": "not_run"}
    if source_gaps:
        report["source_gap_qa"] = write_source_gap_review(output, report, input_manifest)
    write(output / "report.json", report)
    print(json.dumps({"version": version, "api_calls": 0, "html_qa": report["html_qa"], "cases": [
        {key: case[key] for key in ("id", "before_characters", "after_characters", "scope_guard_error")}
        for case in report["cases"]]}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="Fresh output directory; existing output is never overwritten")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--block-windows", action="store_true", help="Opt into source_block_windows_v0.1 (stage09)")
    mode.add_argument("--layout-groups", action="store_true", help="Opt into source_layout_groups_v0.1 (stage10)")
    mode.add_argument("--ruled-tables", action="store_true", help="Opt into source_ruled_tables_v0.2 (stage11)")
    mode.add_argument("--source-gaps", action="store_true", help="Opt into source_visual_gaps_v0.1 diagnostics (stage12)")
    parser.add_argument("--protocol", type=Path)
    args = parser.parse_args()
    protocol = args.protocol or Path("docs/records/source_gaps_protocol_v0.1.md" if args.source_gaps
        else "docs/records/ruled_tables_protocol_v0.2.md" if args.ruled_tables
        else "docs/records/layout_groups_protocol_v0.1.md" if args.layout_groups
        else "docs/records/context_windows_protocol_v0.1.md" if args.block_windows
        else "docs/records/context_compaction_protocol_v0.1.md")
    run(args.baseline, args.output, protocol,
        block_windows=args.block_windows or args.layout_groups or args.ruled_tables or args.source_gaps,
        layout_groups=args.layout_groups or args.ruled_tables or args.source_gaps,
        ruled_tables=args.ruled_tables or args.source_gaps, source_gaps=args.source_gaps)


if __name__ == "__main__":
    main()
