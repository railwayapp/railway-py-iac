# Railway Infrastructure as Code (IaC) authoring helpers for Python.

Install: `pip install -e .` then author `.railway/railway.py`. Prefer **one
file per project** that owns the whole environment. Named partials are a last
resort for split repos that cannot share a file.

```python
from railway_iac import define_railway, github, postgres, project, service

@define_railway
def main(ctx=None):
    db = postgres("db")
    web = service(
        "web",
        source=github("org/app"),
        start="gunicorn app:app",
        env={"DATABASE_URL": db.env.DATABASE_URL},
    )
    return project("my-app", resources=[db, web])
```

The CLI evaluates this file and diffs against the linked environment.
Config as Code migration lives in the CLI (`railway config migrate --lang py`).

Last resort only: set module-level `PARTIAL = "api"` (same role as
`export const partial` in TypeScript). Do not rename a partial after apply.

See https://docs.railway.com/infrastructure-as-code
