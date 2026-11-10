"""Resolve update permissions once for every workflow entry point."""

from __future__ import annotations

import json
import os
from pathlib import Path

WEEKLY = "37 6 * * 1"
DAILY = "37 6 * * 0,2-6"


def input_flag(inputs: dict, name: str) -> bool:
    value = inputs.get(name, False)
    if value is True or value == "true":
        return True
    if value is False or value == "false":
        return False
    raise ValueError(f"Invalid boolean workflow input {name}: {value!r}")


def plan_update(event_name: str, ref: str, event: dict) -> dict[str, bool]:
    refresh = check_only = False
    if event_name == "schedule":
        schedule = event.get("schedule")
        if schedule not in (WEEKLY, DAILY):
            raise ValueError(f"Unrecognized update schedule: {schedule!r}")
        refresh, check_only = True, schedule == DAILY
    elif event_name == "workflow_dispatch":
        inputs = event.get("inputs") or {}
        check_only = input_flag(inputs, "source_check_only")
        refresh = input_flag(inputs, "refresh_data") or check_only
    elif event_name not in ("push", "pull_request"):
        raise ValueError(f"Unsupported update event: {event_name!r}")
    return {
        "refresh_data": refresh,
        "publish": ref == "refs/heads/master" and event_name != "pull_request" and not check_only,
    }


def main() -> None:
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    plan = plan_update(os.environ["GITHUB_EVENT_NAME"], os.environ["GITHUB_REF"], event)
    for key, value in plan.items():
        print(f"{key}={str(value).lower()}")


if __name__ == "__main__":
    main()
