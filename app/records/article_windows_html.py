"""Searchable offline context-plan report with source and denominator diagnostics."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def _details(label: str, value: object) -> str:
    return '<details><summary>' + html.escape(label) + '</summary><pre>' + html.escape(
        value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)) + '</pre></details>'


def render_plan(report: dict[str, Any]) -> str:
    rows = []
    for page in report["pages"]:
        uri = (Path(page["original_pdf_path"]).resolve().as_uri() + f'#page={page["page_number"]}'
               if page.get("original_pdf_path") else None)
        source = (f'<a href="{html.escape(uri, quote=True)}">Original PDF p.{page["page_number"]}</a>'
                  if uri else f'PDF p.{page["page_number"]}; source link unavailable')
        contexts = []
        for context in page["contexts"]:
            contexts.append('<section><p>' + html.escape(context["state"]) + ' · offsets '
                            + f'{context["start"]}:{context["end"]}' + '</p><pre>' + html.escape(context["quote"])
                            + '</pre>' + _details("Context diagnostics, core units and lexical cues", context) + '</section>')
        rows.append('<tr class="page"><td>' + html.escape(page["article_id"]) + '<p>' + source + '</p></td><td>'
                    + html.escape(page["planning_state"]) + _details("Diagnostics", page["diagnostics"])
                    + _details("Complete source page", page["page_text"])
                    + _details("Mapping, protected groups, all blocks and graphics", {k: v for k, v in page.items()
                                                                                    if k not in {"contexts", "page_text"}})
                    + '</td><td>' + "".join(contexts) + '</td></tr>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>ARIADNE whole-article bounded contexts</title><style>body{font:15px system-ui;margin:24px;color:#19332d}'
            'table{border-collapse:collapse;width:100%}td,th{border:1px solid #bccbc4;padding:10px;vertical-align:top}'
            'td{max-width:65ch}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:60vh;overflow:auto}'
            'section{border-top:1px solid #bbc8c1;padding:10px}input{padding:8px;width:60%}[hidden]{display:none!important}</style>'
            '<h1>Whole-article bounded context plan</h1><p>Offline proposals. No inference or scientific acceptance. '
            'All pages retained; unresolved pages/contexts remain in denominators.</p>'
            + _details("Version, source snapshot and policy", {k: report[k] for k in ("version", "source_fingerprint", "policy")})
            + '<pre>' + html.escape(json.dumps(report["summary"], ensure_ascii=False, indent=2)) + '</pre>'
            + _details("Limitations", report["limitations"])
            + '<label>Search all source text and diagnostics <input id="search" type="search"></label><p id="count"></p>'
            '<table><thead><tr><th>Source</th><th>Page state and full source</th><th>All context proposals</th></tr></thead><tbody>'
            + "".join(rows) + '</tbody></table><script>const rows=[...document.querySelectorAll("tr.page")];'
            'function filter(){const q=document.getElementById("search").value.toLocaleLowerCase();let n=0;'
            'for(const r of rows){r.hidden=!r.textContent.toLocaleLowerCase().includes(q);if(!r.hidden)n++;}'
            'document.getElementById("count").textContent=n+" / "+rows.length;}'
            'document.getElementById("search").addEventListener("input",filter);filter();</script></html>\n')
