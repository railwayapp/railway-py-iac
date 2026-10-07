# Railway Infrastructure as Code (IaC) authoring helpers for Python.

Install: `pip install railway-sdk` (or `pip install -e .` from this repo) then
author `.railway/railway.py`. Prefer **one file per project** that owns the
whole environment. Named partials are a last resort for split repos that cannot
share a file.

```python
from railway_sdk import define_railway, github, postgres, project, service

@define_railway
def main(ctx=None):
    db = postgres("db")
    web = service(
        "web",
        source=github("org/app"),
        start="gunicorn app:app",
        env={"DATABASE_URL": db.env.DATABASE_URL},
        tracing={"enabled": True},
    )
    return project("my-app", resources=[db, web])
```

Variable ownership is project-wide. `variables` is only a policy on `project`
(`service` still uses `variables` / `env` for values, not this policy):

```python
return project(
    "my-app",
    resources=[db, web],
    variables={"managed": True, "ignore": ["DOPPLER_*", "metabase/*"]},
)
```

`managed` marks variables as IaC-owned. `ignore` lists patterns left untouched.

`github(repo)` with no `branch` leaves the branch environment-owned. Pass
`branch=` only to pin one:

```python
service("web", source=github("org/app"))  # environment owns the branch
service("web", source=github("org/app", branch="main"))
```

Limit a resource to named environments with `environments` on `service`, `fn`,
database helpers (`postgres`, `mysql`, `redis`, `mongo`, `database`), `bucket`,
`volume`, or `group`:

```python
service("web", environments=["production", "staging"])
```

The CLI context JSON may include `pr` as
`{"number": 12, "branch": "feat", "base": "main"}`. `ctx.pr` is that object,
or `None` when the key is absent.

The CLI evaluates this file and diffs against the linked environment.
Config as Code migration lives in the CLI (`railway config migrate --lang py`).

Last resort only: set module-level `PARTIAL = "api"` (same role as
`export const partial` in TypeScript). Do not rename a partial after apply.

See https://docs.railway.com/infrastructure-as-code
