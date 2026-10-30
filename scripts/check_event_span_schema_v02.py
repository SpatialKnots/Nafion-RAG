"""Check frozen unsent schemas using installed local jsonschema; no provider test."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from importlib.metadata import version
from pathlib import Path

from jsonschema import Draft202012Validator


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def no_network(event: str, args: tuple[object, ...]) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"}:
        raise AssertionError("Network forbidden during local JSON-schema check")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.addaudithook(no_network)
    manifest = json.loads((args.prepared / "manifest.json").read_bytes())
    actual = {p.relative_to(args.prepared).as_posix(): sha(p.read_bytes()) for p in args.prepared.rglob("*")
              if p.is_file() and p.name != "manifest.json"}
    if actual != manifest["outputs"]:
        raise ValueError("Prepared output manifest changed")
    report = json.loads((args.prepared / "report.json").read_bytes())
    rows = []
    validators = {}
    bindings = {str((args.prepared / "manifest.json").resolve()): sha((args.prepared / "manifest.json").read_bytes()),
                str(Path(__file__).resolve()): sha(Path(__file__).read_bytes())}
    for row in report["cases"]:
        case_id = row["case"]["id"]
        path = args.prepared / "requests" / (case_id + ".json")
        raw = path.read_bytes()
        if sha(raw) != row["request_sha256"]:
            raise ValueError("Native request identity differs")
        request = json.loads(raw)
        schema = request["response_format"]["schema"]
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        validator.validate(row["constructed_fixture"]["contract_fixture"])
        validators[case_id] = validator
        bindings[str(path.resolve())] = sha(raw)
        rows.append({"case_id": case_id, "schema_valid": True, "constructed_fixture_valid": True})
    controls = []
    first_id = report["cases"][0]["case"]["id"]
    for control in report["structural_controls"]:
        errors = list(validators[first_id].iter_errors(control["fixture"]))
        valid = not errors
        if valid != control["expected_schema_valid"]:
            raise ValueError("Native schema control differs from declared expectation: " + control["id"])
        controls.append({"id": control["id"], "schema_valid": valid, "local_valid": control["local_valid"],
                         "errors": [e.message for e in errors]})
    wrong_stage = report["wrong_stage_control"]
    validators[wrong_stage["case_id"]].validate(wrong_stage["fixture"])
    result = {"version": "event_span_jsonschema_preflight_v0.2", "bindings": bindings,
              "runtime": {"python": sys.version, "jsonschema": version("jsonschema")},
              "cases": rows, "controls": controls, "wrong_stage_fixture_schema_valid": True,
              "source_integrity_supplements_native_schema": True,
              "provider_schema_support": "not_tested", "model_quality": "not_tested", "new_api_oauth_calls": 0}
    args.output.mkdir(parents=True, exist_ok=False)
    data = (json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    with (args.output / "report.json").open("xb") as stream:
        stream.write(data)
    with (args.output / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump({"outputs": {"report.json": sha(data)}}, stream, indent=2)
    print(json.dumps({"schemas_and_positive_fixtures": len(rows), "negative_or_source_integrity_controls": len(controls),
                      "wrong_stage_fixture_schema_valid": True, "provider_schema_support": "not_tested", "new_api_oauth_calls": 0}))


if __name__ == "__main__":
    main()
