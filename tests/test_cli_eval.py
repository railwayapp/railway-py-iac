"""Replicate the CLI's python3 -c eval wrapper against this package."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

CLI_EVAL = r"""
import importlib.util, inspect, json, os, sys
path = sys.argv[1]
payload = json.loads(os.environ.get("RAILWAY_IAC_CONTEXT") or "{}")
from railway_sdk import create_railway_context
ctx = create_railway_context(payload)
spec = importlib.util.spec_from_file_location("railway_sdk_user", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
partial = getattr(mod, "PARTIAL", None) or getattr(mod, "Partial", None) or getattr(mod, "partial", None)
candidate = getattr(mod, "main", None) or getattr(mod, "Railway", None) or getattr(mod, "default", None)
if callable(candidate):
    try:
        params = list(inspect.signature(candidate).parameters.values())
    except (TypeError, ValueError):
        params = [None]
    project = candidate() if not params else candidate(ctx)
else:
    project = candidate
if hasattr(project, "to_graph"):
    project = project.to_graph()
print(json.dumps({"partial": partial, "project": project}, default=str))
"""


def test_cli_eval_wrapper_loads_sdk(tmp_path: Path):
    source = tmp_path / "railway.py"
    source.write_text(
        textwrap.dedent(
            """
            from railway_sdk import define_railway, project, service

            PARTIAL = "api"

            @define_railway
            def main(ctx=None):
                web = service("api", start="echo api", tracing={"enabled": True, "autoInstrumentation": True})
                return project("app", resources=[web])
            """
        )
    )
    result = subprocess.run(
        [sys.executable, "-c", CLI_EVAL, str(source)],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["partial"] == "api"
    resources = payload["project"]["resources"]
    assert resources[0]["address"] == "service.api"
    assert resources[0]["deploy"]["startCommand"] == "echo api"
    assert resources[0]["tracing"] == {"enabled": True, "autoInstrumentation": True}


def test_cli_eval_payload_includes_policy_environments_and_branchless_github(tmp_path: Path):
    source = tmp_path / "railway.py"
    source.write_text(
        textwrap.dedent(
            """
            from railway_sdk import github, postgres, project, service

            def main():
                db = postgres("db", environments=["production"])
                web = service("web", source=github("org/app"), environments=["production", "staging"])
                return project(
                    "app",
                    resources=[db, web],
                    variables={"managed": True, "ignore": ["DOPPLER_*", "metabase/*"]},
                )
            """
        )
    )
    result = subprocess.run(
        [sys.executable, "-c", CLI_EVAL, str(source)],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)["project"]
    assert payload["variables"] == {"managed": True, "ignore": ["DOPPLER_*", "metabase/*"]}
    assert payload["resources"][0]["environments"] == ["production"]
    assert payload["resources"][1]["environments"] == ["production", "staging"]
    assert payload["resources"][1]["source"] == {"type": "github", "repo": "org/app"}
    assert "branch" not in payload["resources"][1]["source"]


def test_cli_eval_reads_pr_from_context(tmp_path: Path):
    source = tmp_path / "railway.py"
    source.write_text(
        textwrap.dedent(
            """
            from railway_sdk import project, service

            def main(ctx):
                name = f"pr-{ctx.pr.number}" if ctx.pr else "app"
                return project(name, resources=[service("web", start=ctx.pr.branch if ctx.pr else "noop")])
            """
        )
    )
    context = json.dumps({"pr": {"number": 12, "branch": "feat/login", "base": "main"}})
    result = subprocess.run(
        [sys.executable, "-c", CLI_EVAL, str(source)],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "RAILWAY_IAC_CONTEXT": context},
    )
    payload = json.loads(result.stdout)["project"]
    assert payload["name"] == "pr-12"
    assert payload["resources"][0]["deploy"]["startCommand"] == "feat/login"
