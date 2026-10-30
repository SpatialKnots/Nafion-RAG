"""Offline correction candidate; does not send requests or alter v0.1 replies."""

from __future__ import annotations

from copy import deepcopy
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints

VERSION = "gigachat_event_diagnostic_schema_v0.2_offline"
INSTRUCTION = " diagnostic must contain a non-whitespace explanation, even when no uncertainty is found."


class DiagnosticConstraint(BaseModel):
    model_config = ConfigDict(strict=True)
    diagnostic: Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]


def corrected_request(original: dict[str, Any]) -> dict[str, Any]:
    candidate = deepcopy(original)
    candidate["response_format"]["schema"]["properties"]["diagnostic"] = (
        DiagnosticConstraint.model_json_schema()["properties"]["diagnostic"])
    candidate["messages"][0]["content"] += INSTRUCTION
    return candidate
