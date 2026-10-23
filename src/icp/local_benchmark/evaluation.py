"""Narrow objective checks; subjective items require human assessment."""
from __future__ import annotations

import json


def score(item: dict, response: str | None) -> dict:
    rule = item["scoring"]
    kind = rule["kind"]
    if kind == "manual":
        return {"kind": "manual", "passed": None, "reason": "Awaiting human review", "rubric": rule["facts"]}
    if response is None:
        return {"kind": kind, "passed": False, "reason": "No response"}
    if kind == "exact":
        passed = response.strip() == rule["expected"]
        return {"kind": kind, "passed": passed, "reason": "Exact text after trimming outer whitespace"}
    if kind == "integer":
        text = response.strip()
        passed = text.isascii() and text.isdecimal() and int(text) == rule["expected"]
        return {"kind": kind, "passed": passed, "reason": "Only a nonnegative decimal integer is accepted"}
    if kind == "json_fields":
        try:
            parsed = json.loads(response)
        except (ValueError, TypeError):
            return {"kind": kind, "passed": False, "reason": "Invalid JSON"}
        expected = rule["expected"]
        passed = isinstance(parsed, dict) and all(
            key in parsed and type(parsed[key]) is type(value) and parsed[key] == value
            for key, value in expected.items()
        )
        return {"kind": kind, "passed": passed, "reason": "Expected fields and typed values; additional fields allowed"}
    raise ValueError(f"Unknown scorer: {kind}")
