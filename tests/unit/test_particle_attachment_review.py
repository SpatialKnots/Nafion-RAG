import json

from scripts import particle_attachment_audit as v7
from scripts.run_particle_attachment_review import PACKET, PREVIOUS, controls, real_records
from scripts.verify_particle_attachment_review import base_result


def test_predeclared_control_and_real_inventory():
    assert len(controls()) == 46
    rows = real_records(json.loads(PACKET.read_bytes()))
    assert len(rows) == 14
    assert len({r["source_case"]["provenance"]["article_id"] for r in rows}) == 6
    assert all(not r["analysis"]["particle_requirements_met"] for r in rows)


def test_all_193_older_decisions_reproduce_exactly():
    previous = json.loads((PREVIOUS / "report.json").read_bytes())
    rows = [*previous["older_control_replays"], *previous["chain_controls"]["records"]]
    assert len(rows) == 193
    for row in rows:
        result = v7.audit(row["question"], row["sources"], baseline_adequate=False)
        assert base_result(result) == row["analysis"]


def test_real_description_and_concentration_not_promoted_to_solvent_dependency():
    rows = {r["id"]: r for r in real_records(json.loads(PACKET.read_bytes()))}
    kim = rows["kim_concentration_null"]["analysis"]
    units = [u for s in kim["atomic_sources"] for u in s["units"]]
    assert any(u["status"] == "observed_null_shape_unverified" and u["role_links_complete"] for u in units)
    assert not kim["particle_requirements_met"]
    geometry = rows["kim_owned_geometry"]["analysis"]
    assert any(u["relation_kind"] == "shape_description" and u["role_links_complete"]
               for s in geometry["atomic_sources"] for u in s["units"])
    assert not geometry["particle_requirements_met"]
    welch = rows["welch_ratio_direction"]["analysis"]
    assert any(u["eligible_particle_relation"] and u["directions"] and not u["role_links_complete"]
               for s in welch["atomic_sources"] for u in s["units"])
