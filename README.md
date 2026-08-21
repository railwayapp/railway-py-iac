# Thin Railway Infrastructure as Code authoring helpers for Python.
#
# Install: `pip install -e .` then author `.railway/railway.py`:
#
#   from railway_iac import define_railway, project, service
#
#   PARTIAL = "api"
#
#   @define_railway
#   def main(ctx=None):
#       web = service("web", build="pip install -r requirements.txt", start="gunicorn app:app")
#       return project("my-app", resources=[web])
#
# The CLI evaluates this file and diffs against the linked environment.
# Config as Code migration lives in the CLI (`railway config migrate --lang py`).
# Multi-repo: set module-level `PARTIAL = "api"` (same role as `export const partial` in TypeScript).
#
# See https://docs.railway.com/infrastructure-as-code
