import json

from scripts import source_reference_chains as v5
from scripts.run_source_reference_review import CONTROLS, PACKET, PREVIOUS, controls, real_records
from scripts.verify_source_reference_review import base_result, check_chains


def test_frozen_controls_and_real_packet_execute_without_source_labels_in_analyzer():
    data = json.loads(CONTROLS.read_bytes())
    packet = json.loads(PACKET.read_bytes())
    result = controls()
    assert len(result["records"]) == 48
    real = real_records(packet, data["question"])
    assert len(real) == 14
    for row in real:
        check_chains(row["question"], row["analysis"], row["sources"])
    positive_parents = {c["parent_sha256"] for c in packet["context_cases"] if c["annotation"]["binding"]}
    for row in real:
        if row["kind"] == "full_parent":
            assert bool(row["analysis"]["source_chains"]) == (row["parent_sha256"] in positive_parents)
            assert not row["analysis"]["chain_textual_requirements_met"]


def test_all_139_older_control_decisions_reproduce_exactly():
    previous = json.loads((PREVIOUS / "report.json").read_bytes())
    rows = [r for r in previous["controls"]["records"] if r["kind"] != "real_development"]
    assert len(rows) == 139
    for row in rows:
        result = v5.audit(row["question"], row["sources"], baseline_adequate=False)
        assert base_result(result) == row["arms"]["v4"]


def test_hop_limit_has_explicit_diagnostic():
    data = json.loads(CONTROLS.read_bytes())
    control = next(c for c in data["controls"] if c["id"] == "hop_limit")
    result = v5.audit(data["question"], [{"text": control["text"]}], baseline_adequate=False)
    assert result["chain_sources"][0]["declarations"][0]["path_diagnostics"] == ["reference_hop_limit_reached"]
