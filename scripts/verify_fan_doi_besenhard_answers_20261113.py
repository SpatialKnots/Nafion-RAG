"""Final attempt closure, byte identity and local report/source-link verification."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

from scripts import run_fan_doi_besenhard_answers_20261113 as run

f = run.f


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        if tag in {"a", "img"}:
            self.paths += [value for key, value in attrs if key in {"href", "src"}]


def main():
    approved = run.authorization()
    closed = run.read(run.BASE / "scope_closed_v01.json")
    expected_ids = [r["id"] for r in approved["cases"]]
    run.require([r["id"] for r in closed["cases"]] == expected_ids, "Closure cases differ")
    run.require(closed["remaining_model_allowance"] == closed["remaining_oauth_allowance"] == 0, "Unclosed scope")
    expected_slots = {r["request_sha256"] for r in approved["cases"]}
    run.require({p.name for p in run.LEDGER.iterdir() if p.is_dir()} == expected_slots, "Unexpected attempt slots")
    paths, source_comparisons = [], 0
    for row in approved["cases"]:
        live, prepared = run.BASE / "live" / row["id"], Path(row["prepared_folder"])
        f.verify_manifest(live)
        f.verify_manifest(prepared)
        for name in ("trace.json", "sources.json", "articles.json", "request.json"):
            run.require((live / name).read_bytes() == (prepared / name).read_bytes(), "Live/preparation drift: " + row["id"])
            source_comparisons += 1
        result = run.read(live / "result.json")
        run.require(result["model_attempts"] == result["oauth_attempts"] == 1
            and result["allowance_closed"] and not result["resend_authorized"]
            and not result["network_denials"] and not result["reference_read_denials"], "Invalid attempt state")
        slot = run.LEDGER / row["request_sha256"]
        run.require(run.read(slot / "result.json") == result and run.read(slot / "closed.json")["allowance_closed"], "Ledger drift")
        paths += list(p for p in slot.iterdir() if p.is_file()) + [live / "manifest.json", prepared / "manifest.json"]
    f.verify_manifest(run.BASE / "offline_replay_v01")
    replay = run.read(run.BASE / "offline_replay_v01/report.json")
    run.require(replay["finished_all"] and len(replay["cases"]) == 26, "Incomplete offline replay")
    source = run.BASE / "source_review_v01"
    f.write(source / "visual_notes.json", {"reviewer": "implementation_assistant_exposed_posthoc",
        "pages_viewed": ["besenhard_pdf3.png", "doi-05.png", "doi-06.png", "doi-07.png", "fan-06.png", "doi_raman-04.png"],
        "B6": {"printed": "1.3–1.0 V range", "raw_and_native": "1.3 ± 1.0 V",
               "runtime_glyph_repair": False, "scope": "one observed glyph mismatch; no general replacement"},
        "D5": "Table1 six percentages verified", "D6": "Table2 fractions verified",
        "D8_D9": "different HFE/TFEE frames and 186/93.4 after50cycles verified",
        "F9": "four DFT energies in Figure6 verified", "D4": "Raman bands/context verified",
        "mupdf_diagnostics": "Doi content-stream/colorspace warnings remain; Poppler rendered four Doi pages successfully"})
    f.manifest(source)
    total_links = 0
    for folder in (run.BASE / "review_v01", run.BASE / "assessment_v01"):
        f.verify_manifest(folder)
        parser = Links()
        parser.feed((folder / "review.html").read_text(encoding="utf-8"))
        for link in parser.paths:
            parsed = urlparse(link)
            path = unquote(parsed.path)
            if re.match(r"^/[A-Za-z]:/", path):
                path = path[1:]
            run.require(parsed.scheme == "file" and Path(path).is_file(), "Broken review media/source link")
        total_links += len(parser.paths)
        paths += [folder / "manifest.json"]
    paths += [Path(__file__), run.BASE / "authorized_inputs_v01/manifest.json", run.BASE / "scope_closed_v01.json",
        run.BASE / "offline_replay_v01/manifest.json", source / "manifest.json", run.SCOPE]
    report = {"actual_answer_attempt_slots": 26, "model_attempts": 26, "oauth_attempts": 26,
        "all_allowances_closed": True, "remaining_model_allowance": 0, "remaining_oauth_allowance": 0,
        "live_vs_frozen_byte_comparisons": source_comparisons, "full_api_saved_response_replays": 26,
        "local_links_and_images_verified": total_links, "visual_source_pages": 6,
        "new_model_or_oauth_calls_in_verification": 0, "browser_layout_checked": False}
    target = run.BASE / "final_verification_v01"
    target.mkdir(exist_ok=False)
    f.write(target / "report.json", report)
    f.write(target / "bindings.json", f.bindings(paths))
    f.save(target / "executed_script.py", Path(__file__).read_bytes())
    f.manifest(target)
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
