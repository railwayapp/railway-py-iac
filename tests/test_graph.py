import pytest

from railway_sdk import (
    bucket,
    create_railway_context,
    define_railway,
    fn,
    github,
    group,
    image,
    postgres,
    preserve,
    project,
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
    assert node["source"] == {"type": "github", "repo": "org/api", "branch": "main"}
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
