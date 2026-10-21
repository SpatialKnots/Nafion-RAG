"""Local multi-record smoke results, including stopped cases and exact sources."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from app.records.review import observations_for_review
from app.records.schema import CandidateBundle


def details(label: str, value: object) -> str:
    return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(
        value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)) + '</pre></details>'


def render_smoke(report: dict[str, Any], output_dir: Path, prepared: Path) -> str:
    rows = []
    for row in report["cases"]:
        context = CandidateBundle.model_validate_json((prepared / row["input"]).read_bytes())
        source = "".join('<p><a href="' + html.escape(Path(r.original_pdf_path).resolve().as_uri(), quote=True)
                         + f'#page={r.page_number}">Original PDF p.{r.page_number}</a></p>'
                         + details(f"Exact context · {r.text_layer} · page offsets {r.start}:{r.end}", r.quote)
                         for r in context.regions)
        case_dir = output_dir / row["case_id"]
        records = []
        candidate_path = case_dir / "candidates.json"
        if candidate_path.exists():
            bundle = CandidateBundle.model_validate_json(candidate_path.read_bytes())
            for record in bundle.records:
                observations = "".join('<tr><td>' + html.escape(name) + '</td><td>' + html.escape(obs.status)
                                       + '</td><td>' + html.escape(obs.raw_text or "") + '</td><td>'
                                       + details("Exact evidence", [s.model_dump(mode="json") for s in obs.evidence])
                                       + '</td></tr>' for name, obs in observations_for_review(record))
                records.append('<article><h3>Proposed record ' + str(record.record_id) + '</h3>'
                               '<table><thead><tr><th>Field</th><th>Status</th><th>Raw text</th><th>Evidence</th></tr></thead>'
                               '<tbody>' + observations + '</tbody></table>'
                               + details("Full candidate / linkage proposals", record.model_dump(mode="json")) + '</article>')
        artifacts = []
        for name in ("reply.json", "unresolved.json", "checks.json", "response.json"):
            path = case_dir / name
            if path.exists():
                artifacts.append(details(name, json.loads(path.read_bytes())))
        rows.append('<tr class="case"><td>' + html.escape(row["case_id"]) + '<p>' + html.escape(row["status"])
                    + '</p><p>Coverage claim: ' + html.escape(row.get("coverage", "unavailable")) + '</p>'
                    + details("Attempt / usage / errors / missingness", row) + '</td><td>' + source + '</td><td>'
                    + "".join(records) + "".join(artifacts) + '</td></tr>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>ARIADNE multi-record smoke</title><style>body{font:15px system-ui;margin:24px;color:#19332d}'
            'table{border-collapse:collapse;width:100%}td,th{border:1px solid #bbc9c2;padding:10px;vertical-align:top}'
            'td{max-width:65ch}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:60vh;overflow:auto}'
            'input{padding:8px;width:60%}[hidden]{display:none!important}</style>'
            '<h1>Multi-record development smoke</h1><p>Proposals and model coverage claims only. '
            'No independent scientific accuracy, admission or article-wide recall established.</p><pre>'
            + html.escape(json.dumps(report["summary"], ensure_ascii=False, indent=2)) + '</pre>'
            + details("Version and final source integrity", {"version": report["version"],
                                                           "source_integrity": report["final_source_integrity"]})
            + '<label>Search <input id="search" type="search"></label><p id="count"></p><table>'
            '<thead><tr><th>Case / state</th><th>Source</th><th>All records and raw diagnostics</th></tr></thead><tbody>'
            + "".join(rows) + '</tbody></table><script>const rows=[...document.querySelectorAll("tr.case")];'
            'function filter(){const q=document.getElementById("search").value.toLocaleLowerCase();let n=0;'
            'for(const r of rows){r.hidden=!r.textContent.toLocaleLowerCase().includes(q);if(!r.hidden)n++;}'
            'document.getElementById("count").textContent=n+" / "+rows.length;}'
            'document.getElementById("search").addEventListener("input",filter);filter();</script></html>\n')
