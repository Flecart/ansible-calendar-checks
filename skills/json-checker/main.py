#!/usr/bin/env python3
"""Validate a batch-send JSON file. Outputs structured JSON — designed for LLM agent consumption."""

import json
import re
import sys
from pathlib import Path

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def validate(path: str) -> dict:
    errors   = []
    warnings = []

    p = Path(path)
    if not p.exists():
        return _result(False, errors=[f"File not found: {path}"], warnings=[])

    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        return _result(False, errors=[f"JSON syntax error at line {exc.lineno}, col {exc.colno}: {exc.msg}"], warnings=[])

    if not isinstance(data, dict):
        return _result(False, errors=[f"Top-level must be an object, got {type(data).__name__}."], warnings=[])

    if not data:
        warnings.append("Object is empty — no events to process.")

    total_recipients = 0

    for event, recipients in data.items():
        if not isinstance(event, str) or not event.strip():
            errors.append(f"Key {event!r}: event name must be a non-empty string.")
            continue

        if isinstance(recipients, str):
            recipients = [recipients]
        elif not isinstance(recipients, list):
            errors.append(
                f"Event {event!r}: value must be a string or list of strings, "
                f"got {type(recipients).__name__}."
            )
            continue

        if not recipients:
            errors.append(f"Event {event!r}: recipient list is empty.")
            continue

        for i, addr in enumerate(recipients):
            loc = f"Event {event!r}, recipient[{i}]"
            if not isinstance(addr, str):
                errors.append(f"{loc}: expected string, got {type(addr).__name__}.")
            elif not addr.strip():
                errors.append(f"{loc}: address is an empty string.")
            elif not _EMAIL_RE.match(addr.strip()):
                warnings.append(f"{loc}: {addr!r} does not look like a valid email address.")
            else:
                total_recipients += 1

    valid = not errors
    summary = (
        f"Valid. {len(data)} event(s), {total_recipients} recipient(s) total."
        if valid else
        f"Invalid. {len(errors)} error(s), {len(warnings)} warning(s)."
    )
    return _result(valid, errors=errors, warnings=warnings, summary=summary,
                   stats={"events": len(data), "recipients": total_recipients} if valid else None)


def _result(valid: bool, *, errors: list, warnings: list,
            summary: str = "", stats: dict | None = None) -> dict:
    out = {"valid": valid, "summary": summary or ("Invalid." if not valid else "Valid."),
           "errors": errors, "warnings": warnings}
    if stats is not None:
        out["stats"] = stats
    return out


def main() -> None:
    if len(sys.argv) != 2:
        print(json.dumps(_result(
            False,
            errors=["Wrong number of arguments. Usage: python main.py <path/to/batch.json>"],
            warnings=[],
        ), indent=2))
        sys.exit(1)

    result = validate(sys.argv[1])
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


if __name__ == '__main__':
    main()
