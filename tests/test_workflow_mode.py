import json
from pathlib import Path
import re

import pytest

from scripts import workflow_mode


def test_configured_schedules_have_explicit_routes():
    workflow = (Path(__file__).parents[1] / ".github/workflows/update-site.yml").read_text()
    schedules = re.findall(r'cron: "([^"]+)"', workflow)
    assert set(schedules) == {workflow_mode.WEEKLY, workflow_mode.DAILY}
    for schedule in schedules:
        plan = workflow_mode.plan_update("schedule", "refs/heads/master", {"schedule": schedule})
        assert plan["refresh_data"]


@pytest.mark.parametrize(("event_name", "ref", "event", "expected"), [
    ("push", "refs/heads/master", {}, (False, True)),
    ("push", "refs/heads/repair", {}, (False, False)),
    ("pull_request", "refs/pull/42/merge", {}, (False, False)),
    ("pull_request", "refs/heads/master", {}, (False, False)),
    ("schedule", "refs/heads/master", {"schedule": workflow_mode.WEEKLY}, (True, True)),
    ("schedule", "refs/heads/master", {"schedule": workflow_mode.DAILY}, (True, False)),
])
def test_automatic_routes(event_name, ref, event, expected):
    plan = workflow_mode.plan_update(event_name, ref, event)
    assert (plan["refresh_data"], plan["publish"]) == expected


@pytest.mark.parametrize("ref", ["refs/heads/master", "refs/heads/repair"])
@pytest.mark.parametrize("refresh", [True, False])
@pytest.mark.parametrize("check_only", [True, False])
@pytest.mark.parametrize("serialized", [True, False])
def test_manual_routes_honor_inputs_without_publishing_branch_or_check_runs(
    ref, refresh, check_only, serialized,
):
    inputs = {"refresh_data": refresh, "source_check_only": check_only}
    if serialized:
        inputs = {key: str(value).lower() for key, value in inputs.items()}
    plan = workflow_mode.plan_update("workflow_dispatch", ref, {"inputs": inputs})
    assert plan["refresh_data"] is (refresh or check_only)
    assert plan["publish"] is (ref == "refs/heads/master" and not check_only)


@pytest.mark.parametrize("inputs", [None, {}, {"refresh_data": "false"}])
def test_dispatch_with_default_inputs_publishes_saved_figures(inputs):
    assert workflow_mode.plan_update(
        "workflow_dispatch", "refs/heads/master", {"inputs": inputs},
    ) == {"refresh_data": False, "publish": True}


@pytest.mark.parametrize(("event_name", "event"), [
    ("schedule", {"schedule": "0 0 * * *"}),
    ("schedule", {}),
    ("repository_dispatch", {}),
    ("workflow_dispatch", {"inputs": {"source_check_only": "yes"}}),
    ("workflow_dispatch", {"inputs": {"refresh_data": None}}),
])
def test_unknown_routes_or_malformed_inputs_fail_closed(event_name, event):
    with pytest.raises(ValueError):
        workflow_mode.plan_update(event_name, "refs/heads/master", event)


def test_runner_event_file_produces_real_step_outputs(monkeypatch, tmp_path, capsys):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"inputs": {"source_check_only": "true", "refresh_data": "false"}}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/repair")
    workflow_mode.main()
    assert capsys.readouterr().out.splitlines() == ["refresh_data=true", "publish=false"]
