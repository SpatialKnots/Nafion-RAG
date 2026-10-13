"""Portable snapshot/ledger backup and read-only graph/table rendering."""
from __future__ import annotations

import html
import json
import re
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from app.terms.review_projection import project_review
from app.terms.review_store import DB_NAME, canonical, connection, history, latest, load_snapshot, sha


def graph_view(root: Path, sid: str, mode: str = "effective", cutoff: int | None = None,
               online: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    _, snapshot = load_snapshot(root, sid)
    events = history(root, sid, cutoff)
    revision_cutoff = max((e["event_id"] for e in events), default=0)
    graph = project_review(snapshot["graph"], latest(root, sid, revision_cutoff), sid, revision_cutoff, mode)
    if online:
        for article in graph["articles"]:
            article["original_href"] = asset_url(sid, sha(article["original_pdf_path"].encode()))
            for key in ("contexts", "mentions"):
                for row in article[key]:
                    source = row["source"]
                    source["original_href"] = asset_url(sid, sha(source["original_pdf_path"].encode())) + f'#page={source["page_number"]}'
                    source["layer_href"] = asset_url(sid, sha(source["layer_pdf_path"].encode())) + f'#page={source["page_number"]}'
    return snapshot, graph


def asset_url(sid: str, asset: str) -> str:
    return "/ui/terms-review/asset?" + urlencode({"snapshot": sid, "asset": asset})


def render_graph(snapshot: dict[str, Any], graph: dict[str, Any], table_href: str, live_script: str = "") -> str:
    assets = snapshot["viewer_assets"]
    payload = json.dumps(graph, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    payload = payload.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    replacements = {"@@STYLE@@": assets["graph.css"], "@@SCRIPT@@": assets["graph.js"], "@@DATA@@": payload,
                    "@@REVIEW@@": f'<a href="{html.escape(table_href, quote=True)}" target="_blank" rel="noopener">Таблица TAC ↗</a>'}
    result = re.sub(r"@@(?:STYLE|SCRIPT|DATA|REVIEW)@@", lambda m: replacements[m.group()], assets["template.html"])
    if live_script:
        result = result.replace("</body>", f"<script>{live_script}</script></body>")
    return result


def render_table(snapshot: dict[str, Any], sid: str, decisions: dict[str, dict[str, Any]], cutoff: int,
                 online: bool = False) -> str:
    result: str = snapshot["table_html"]
    summary = (f'<p class="identity">Terms review v0.1 · Snapshot {sid} · event cutoff {cutoff}. '
               'Заявленные локальные решения; независимая научная приёмка не установлена.</p>')
    for event in decisions.values():
        text = (f'Review rev {event["revision"]}: {event["action"]}; categories {", ".join(event["categories"]) or "—"}; '
                f'{event["reviewer_kind"]}:{event["reviewer"]}; {event["reason"]}')
        badge = '<p class="review-event">' + html.escape(text) + '</p>'
        if event["target_kind"] == "classification":
            pattern = r'(<details class="classification" data-assignment-id="' + event["target_id"] + r'"[^>]*><summary>.*?</summary>)'
        else:
            pattern = r'(<details class="term"[^>]*data-candidate-id="' + event["target_id"] + r'"[^>]*><summary>.*?</summary>)'
        def add_badge(match: re.Match[str], text: str = badge) -> str:
            return match.group() + text
        result, count = re.subn(pattern, add_badge, result, flags=re.S)
        if count != 1:
            raise ValueError("Terms review table target missing or duplicated")
    result = result.replace('<div class="toolbar">', summary + '<div class="toolbar">', 1)
    if online:
        for asset_id, asset in snapshot["assets"].items():
            uri = (Path(snapshot["source_root"]) / asset["path"]).resolve().as_uri()
            result = result.replace(html.escape(uri, quote=True), html.escape(asset_url(sid, asset_id), quote=True))
    return result


def backup(root: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(destination)
    # SQLite backup produces one consistent DB image, independent of a live writer.
    temporary = destination.with_suffix(destination.suffix + ".sqlite.tmp")
    if temporary.exists():
        raise FileExistsError(temporary)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with connection(root) as source, closing(sqlite3.connect(temporary)) as target:
        source.backup(target)
    with closing(sqlite3.connect(temporary)) as conn:
        sids = {r[0] for r in conn.execute("SELECT DISTINCT snapshot FROM events")}
        row = conn.execute("SELECT value FROM meta WHERE key='current_snapshot'").fetchone()
        if row:
            sids.add(row[0])
    files = {DB_NAME: temporary.read_bytes()}
    for sid in sorted(sids):
        load_snapshot(root, sid)
        files[f"snapshots/{sid}.json"] = (root / "snapshots" / f"{sid}.json").read_bytes()
    manifest = {"schema": "tac_terms_review_backup_v0.1", "files": {name: sha(raw) for name, raw in files.items()},
                "includes": "SQLite ledger, frozen sources/policy/graph/table; original PDF/PNG files remain external"}
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
        archive.writestr("manifest.json", canonical(manifest))
    temporary.unlink()


def restore(archive_path: Path, root: Path) -> None:
    if root.exists() and any(root.iterdir()):
        raise FileExistsError("Terms restore requires an empty directory")
    with zipfile.ZipFile(archive_path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("schema") != "tac_terms_review_backup_v0.1":
            raise ValueError("Unknown Terms backup schema")
        if set(archive.namelist()) != set(manifest["files"]) | {"manifest.json"} or len(archive.namelist()) != len(set(archive.namelist())):
            raise ValueError("Terms backup inventory mismatch")
        files = {}
        for name, expected in manifest["files"].items():
            if name != DB_NAME and not re.fullmatch(r"snapshots/[0-9a-f]{64}\.json", name):
                raise ValueError("Unsafe Terms backup member")
            raw = archive.read(name)
            if sha(raw) != expected or (name.startswith("snapshots/") and sha(raw) != Path(name).stem):
                raise ValueError("Terms backup checksum mismatch")
            files[name] = raw
        if DB_NAME not in files:
            raise ValueError("Terms backup ledger missing")
    root.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)
    with connection(root) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Terms restored SQLite integrity failure")
    # Every restored event must reference an intact target and exact source binding.
    from app.terms.review_store import target_info
    cache = {}
    for event in history(root):
        sid = event["snapshot_id"]
        if sid not in cache:
            cache[sid] = load_snapshot(root, sid)[1]
        target = target_info(cache[sid], event["target_kind"], event["target_id"])
        if target["evidence_sha256"] != event["evidence_sha256"]:
            raise ValueError("Restored Terms event source binding mismatch")
    load_snapshot(root)
