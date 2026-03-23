# docs/

This directory is **auto-generated** by CI on every push to `main`.

**Do not edit these files manually** -- your changes will be overwritten.

## How it works

The GitHub Action at `.github/workflows/ci.yml` runs `scripts/generate_docs.py`
which uses Python AST parsing to extract information from the actual source code
and generates the following files:

| File | What it documents |
|------|-------------------|
| `api-routes.md` | All FastAPI endpoints with methods, paths, auth, and status codes |
| `db-schema.md` | SQLAlchemy model definitions with columns, types, and constraints |
| `frontend-tree.md` | Next.js pages, layouts, components, and library files |
| `dependencies.md` | Python (requirements.txt) and Node.js (package.json) dependencies |
| `env-vars.md` | Environment variables from .env.example and config.py |

## Running locally

```bash
python scripts/generate_docs.py
```
