import pytest

from railway_sdk import (
    bucket,
    create_railway_context,
    database,
    define_railway,
    fn,
    github,
    group,
    image,
    mongo,
    mysql,
    postgres,
    preserve,
    project,
    redis,
    ref,
    service,
    volume,
)


def test_service_to_graph():
    web = service("web", build="pip install -r requirements.txt", start="gunicorn app:app")
    node = web.to_graph()
    assert node["type"] == "service"
    assert node["name"] == "web"
    assert node["address"] == "service.web"
    assert node["kind"] == "empty"
    assert node["build"] == {"buildCommand": "pip install -r requirements.txt"}
    assert node["deploy"] == {"startCommand": "gunicorn app:app"}


def test_github_source_and_env_refs():
    db = postgres("db")
    api = service(
        "api",
        source=github("org/api"),
        env={"DATABASE_URL": db.env.DATABASE_URL, "NAME": "api"},
        domains=["api.example.com"],
        replicas=2,
    )
    node = api.to_graph()
    assert node["kind"] == "github"
    assert node["source"] == {"type": "github", "repo": "org/api"}
    assert "branch" not in node["source"]
    assert node["variables"]["DATABASE_URL"] == {
        "type": "reference",
        "resource": "database.db",
        "output": "DATABASE_URL",
    }
    assert node["variables"]["NAME"] == {"type": "literal", "value": "api"}
    assert node["deploy"]["numReplicas"] == 2
    assert node["networking"]["customDomains"]["api.example.com"] == {"port": 8080}


def test_define_railway_project_graph():
    @define_railway
    def main(ctx=None):
        api = service("api", start="uvicorn app:app")
        return project("demo", resources=[api])

    graph = main().to_graph()
    assert graph["name"] == "demo"
    assert graph["resources"][0]["name"] == "api"


def test_group_flatten_and_volume_mount():
    data = volume("data")
    web = service("web", start="./app", volumeMounts={"/data": data})
    graph = project("demo", resources=group("app", [web, data])).to_graph()
    types = [item["type"] for item in graph["resources"]]
    assert types == ["group", "service", "volume"]
    assert graph["resources"][1]["groupId"] == "app"
    assert graph["resources"][1]["volumeAttachments"]["data"]["volume"] == "volume.data"


def test_context_helpers():
    ctx = create_railway_context(environment="prod")
    assert ctx.is_environment("prod")
    assert not ctx.is_environment("dev")
    assert ctx.shared.STRIPE_KEY == {"type": "sharedReference", "name": "STRIPE_KEY"}
    assert len(ctx.random_string("secret")) == 24
    assert ctx.pr is None


def test_context_pr_from_cli_json():
    ctx = create_railway_context(
        {
            "environment": "pr-12",
            "pr": {"number": 12, "branch": "feat/login", "base": "main"},
        }
    )
    assert ctx.pr.number == 12
    assert ctx.pr.branch == "feat/login"
    assert ctx.pr.base == "main"
    assert create_railway_context(pr=None).pr is None
    with pytest.raises(ValueError, match="number, branch, and base"):
        create_railway_context(pr={"number": 1})


def test_project_variable_policy_reaches_payload():
    policy = {"managed": True, "ignore": ["DOPPLER_*", "metabase/*"]}
    web = service("web", variables={"TOKEN": "secret"})
    graph = project("app", resources=[web], variables=policy).to_graph()
    assert graph["variables"] == policy
    assert graph["resources"][0]["variables"] == {"TOKEN": {"type": "literal", "value": "secret"}}
    assert "managed" not in graph["resources"][0]
    with pytest.raises(ValueError, match="managed must be a boolean"):
        project("app", variables={"managed": "yes"})


def test_github_omitted_branch_is_environment_owned():
    assert github("org/app") == {"type": "github", "repo": "org/app"}
    assert "branch" not in github("org/app", branch=None)
    assert github("org/app", branch="release")["branch"] == "release"
    assert service("web", source={"repo": "org/app"}).to_graph()["source"] == {
        "type": "github",
        "repo": "org/app",
    }


def test_environments_reach_payload():
    envs = ["production", "staging"]
    nodes = [
        service("web", environments=envs),
        fn("job", environments=envs),
        postgres("pg", environments=envs),
        mysql("sql", environments=envs),
        redis("cache", environments=envs),
        mongo("docs", environments=envs),
        database("custom", "private", image="custom:1", environments=envs),
        bucket("media", environments=envs),
        volume("data", environments=envs),
        group("app", environments=envs),
    ]
    for node in nodes:
        graph = node.to_graph()
        assert graph["environments"] == envs
        assert graph.get("config", {}).get("environments") is None
    grouped = group("app", [service("web")], environments=["production"])
    assert grouped[0].to_graph()["environments"] == ["production"]
    assert "environments" not in grouped[1].to_graph()
    assert "environments" not in service("web").to_graph()
    with pytest.raises(ValueError, match="environments must be a list"):
        service("web", environments="production")


def test_tracing_block_passes_through():
    both = service("web", start="./app", tracing={"enabled": True, "autoInstrumentation": True})
    assert both.to_graph()["tracing"] == {"enabled": True, "autoInstrumentation": True}

    enabled_only = service("web", start="./app", tracing={"enabled": True})
    assert enabled_only.to_graph()["tracing"] == {"enabled": True}

    # A false switch is authored as-is; the CLI treats it the same as absent.
    off = service("web", start="./app", tracing={"enabled": False})
    assert off.to_graph()["tracing"] == {"enabled": False}

    worker = fn("worker", start="./worker", tracing={"enabled": True})
    assert worker.to_graph()["tracing"] == {"enabled": True}
    assert worker.to_graph()["kind"] == "function"


def test_tracing_none_switches_are_pruned():
    node = service("web", start="./app", tracing={"enabled": True, "autoInstrumentation": None}).to_graph()
    assert node["tracing"] == {"enabled": True}

    assert "tracing" not in service("web", start="./app", tracing={"enabled": None}).to_graph()
    assert "tracing" not in service("web", start="./app", tracing={}).to_graph()
    assert "tracing" not in service("web", start="./app", tracing=None).to_graph()
    assert "tracing" not in service("web", start="./app").to_graph()


def test_tracing_rejects_bad_input():
    with pytest.raises(ValueError, match="Unknown tracing field"):
        service("web", tracing={"enabled": True, "sampleRate": 0.5})
    with pytest.raises(ValueError, match="tracing.enabled must be a boolean"):
        service("web", tracing={"enabled": "yes"})
    with pytest.raises(ValueError, match="tracing must be a mapping"):
        service("web", tracing=True)


def test_ref_and_preserve():
    db = postgres("db")
    assert ref(db, "DATABASE_URL") == db.env.DATABASE_URL
    assert preserve() == {"type": "preserve"}
    assert image("nginx:latest")["type"] == "image"
    assert bucket("assets").to_graph()["address"] == "bucket.assets"
