#!/usr/bin/env python3
"""Auto-generate project documentation from source code.

Produces 5 markdown files in docs/:
  - api-routes.md    (FastAPI router endpoints)
  - db-schema.md     (SQLAlchemy model definitions)
  - frontend-tree.md (component/page structure)
  - dependencies.md  (Python + JS dependencies)
  - env-vars.md      (environment variables)

Run: python scripts/generate_docs.py
CI:  called by .github/workflows/ci.yml on push to main
"""

import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
DOCS = ROOT / "docs"


def ensure_docs_dir():
    DOCS.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# 1. API Routes
# ---------------------------------------------------------------------------

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def extract_routes_from_file(filepath: Path) -> list[dict]:
    """Parse a FastAPI router file using AST to extract route decorators."""
    try:
        source = filepath.read_text()
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return []

    routes = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            method, path = _parse_route_decorator(decorator)
            if method is None:
                continue
            # Extract auth dependency from function args
            auth = _extract_auth_dep(node)
            # Extract status code from decorator kwargs
            status_code = _extract_kwarg(decorator, "status_code")
            # Extract response_model from decorator kwargs
            response_model = _extract_kwarg(decorator, "response_model")
            routes.append({
                "method": method.upper(),
                "path": path,
                "function": node.name,
                "auth": auth,
                "status_code": status_code,
                "response_model": response_model,
                "line": node.lineno,
            })
    return routes


def _parse_route_decorator(decorator) -> tuple:
    """Extract HTTP method and path from @router.get("/path") style decorators."""
    call = decorator if isinstance(decorator, ast.Call) else None
    if call is None:
        return None, None
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in HTTP_METHODS:
        method = func.attr
        if call.args and isinstance(call.args[0], ast.Constant):
            path = call.args[0].value
            return method, path
    return None, None


def _extract_auth_dep(node: ast.FunctionDef) -> str:
    """Look for ResearcherDep, AnnotatorDep, CurrentUser in function params."""
    for arg in node.args.args:
        ann = arg.annotation
        if ann is None:
            continue
        name = ""
        if isinstance(ann, ast.Name):
            name = ann.id
        elif isinstance(ann, ast.Attribute):
            name = ann.attr
        if name in ("ResearcherDep", "AnnotatorDep", "CurrentUser"):
            return name
    return "public"


def _extract_kwarg(decorator, key: str) -> str | None:
    if not isinstance(decorator, ast.Call):
        return None
    for kw in decorator.keywords:
        if kw.arg == key:
            if isinstance(kw.value, ast.Constant):
                return str(kw.value.value)
            return ast.dump(kw.value)
    return None


def extract_router_prefix(filepath: Path) -> str:
    """Extract the prefix from router = APIRouter(prefix=...)."""
    try:
        source = filepath.read_text()
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "router":
                    if isinstance(node.value, ast.Call):
                        for kw in node.value.keywords:
                            if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                                return kw.value.value
    return ""


def generate_api_routes():
    api_dir = BACKEND / "app" / "api" / "v1"
    lines = [
        "# API Routes",
        "",
        f"> Auto-generated on {_now()}. Do not edit manually.",
        "",
    ]

    router_files = sorted(api_dir.glob("*.py"))
    for rf in router_files:
        if rf.name in ("__init__.py", "router.py"):
            continue
        prefix = extract_router_prefix(rf)
        routes = extract_routes_from_file(rf)
        if not routes:
            continue
        lines.append(f"## {rf.stem} (`{prefix}`)")
        lines.append("")
        lines.append("| Method | Path | Function | Auth | Status |")
        lines.append("|--------|------|----------|------|--------|")
        for r in routes:
            full_path = f"{prefix}{r['path']}"
            status = r["status_code"] or "200"
            lines.append(
                f"| `{r['method']}` | `{full_path}` | `{r['function']}` | {r['auth']} | {status} |"
            )
        lines.append("")

    (DOCS / "api-routes.md").write_text("\n".join(lines))
    print(f"  Generated docs/api-routes.md ({len(lines)} lines)")


# ---------------------------------------------------------------------------
# 2. DB Schema
# ---------------------------------------------------------------------------

def generate_db_schema():
    models_dir = BACKEND / "app" / "models"
    lines = [
        "# Database Schema",
        "",
        f"> Auto-generated on {_now()}. Do not edit manually.",
        "",
    ]

    model_files = sorted(models_dir.glob("*.py"))
    for mf in model_files:
        if mf.name in ("__init__.py", "base.py"):
            continue
        try:
            source = mf.read_text()
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue

        # Extract enums
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = [_name(b) for b in node.bases]
                if "Enum" in bases or "str, Enum" in ", ".join(bases):
                    values = []
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            for t in item.targets:
                                if isinstance(t, ast.Name):
                                    values.append(t.id)
                    if values:
                        lines.append(f"### Enum: `{node.name}`")
                        lines.append(f"Values: {', '.join(f'`{v}`' for v in values)}")
                        lines.append("")

        # Extract SQLAlchemy models
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = [_name(b) for b in node.bases]
            if "Base" not in bases:
                continue

            tablename = _extract_tablename(node)
            lines.append(f"## `{node.name}` (table: `{tablename}`)")
            lines.append("")
            lines.append("| Column | Type | Constraints |")
            lines.append("|--------|------|-------------|")

            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    col_name = item.target.id
                    col_type = _unparse_safe(item.annotation)
                    constraints = _extract_column_constraints(item)
                    lines.append(f"| `{col_name}` | `{col_type}` | {constraints} |")

            # Extract relationships
            rels = []
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    type_str = _unparse_safe(item.annotation)
                    if "Mapped" in type_str and ("list[" in type_str.lower() or any(
                        base in type_str for base in ("User", "Task", "Annotation", "RewardSignal",
                                                       "TaskAssignment", "Dataset", "DatasetExport",
                                                       "FineTuningJob", "ModelVersion", "RefreshToken")
                    )):
                        if item.value and "relationship" in _unparse_safe(item.value):
                            rels.append(f"`{item.target.id}` -> `{type_str}`")

            if rels:
                lines.append("")
                lines.append("**Relationships:** " + " | ".join(rels))

            lines.append("")

    (DOCS / "db-schema.md").write_text("\n".join(lines))
    print(f"  Generated docs/db-schema.md ({len(lines)} lines)")


def _name(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _extract_tablename(cls_node: ast.ClassDef) -> str:
    for item in cls_node.body:
        if isinstance(item, ast.Assign):
            for t in item.targets:
                if isinstance(t, ast.Name) and t.id == "__tablename__":
                    if isinstance(item.value, ast.Constant):
                        return item.value.value
    return "?"


def _extract_column_constraints(item: ast.AnnAssign) -> str:
    parts = []
    ann_str = _unparse_safe(item.annotation)
    if "None" in ann_str:
        parts.append("nullable")
    # Check for mapped_column kwargs in the value
    if item.value and isinstance(item.value, ast.Call):
        val_str = _unparse_safe(item.value)
        if "primary_key=True" in val_str:
            parts.append("PK")
        if "unique=True" in val_str:
            parts.append("unique")
        if "index=True" in val_str:
            parts.append("indexed")
        if "ForeignKey" in val_str:
            fk_match = re.search(r'ForeignKey\(["\']([^"\']+)', val_str)
            if fk_match:
                parts.append(f"FK({fk_match.group(1)})")
        if "server_default" in val_str or "default=" in val_str:
            parts.append("has default")
    return ", ".join(parts) if parts else "-"


def _unparse_safe(node) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return "?"


# ---------------------------------------------------------------------------
# 3. Frontend Tree
# ---------------------------------------------------------------------------

def generate_frontend_tree():
    lines = [
        "# Frontend Structure",
        "",
        f"> Auto-generated on {_now()}. Do not edit manually.",
        "",
    ]

    src = FRONTEND / "src"
    if not src.exists():
        lines.append("Frontend src/ directory not found.")
        (DOCS / "frontend-tree.md").write_text("\n".join(lines))
        return

    # Pages
    lines.append("## Pages (App Router)")
    lines.append("")
    lines.append("| Route | File |")
    lines.append("|-------|------|")
    for page in sorted(src.rglob("page.tsx")):
        rel = page.relative_to(src / "app")
        route = "/" + str(rel.parent).replace("\\", "/")
        if route == "/.":
            route = "/"
        # Convert [param] to :param for readability
        route = re.sub(r'\[(\w+)\]', r':\1', route)
        lines.append(f"| `{route}` | `src/app/{rel}` |")
    lines.append("")

    # Layouts
    lines.append("## Layouts")
    lines.append("")
    for layout in sorted(src.rglob("layout.tsx")):
        rel = layout.relative_to(src)
        lines.append(f"- `src/{rel}`")
    lines.append("")

    # Components
    lines.append("## Components")
    lines.append("")
    components_dir = src / "components"
    if components_dir.exists():
        for category in sorted(components_dir.iterdir()):
            if category.is_dir():
                files = sorted(category.glob("*.tsx"))
                if files:
                    lines.append(f"### {category.name}/")
                    for f in files:
                        lines.append(f"- `{f.name}`")
                    lines.append("")

    # Lib
    lines.append("## Library (src/lib/)")
    lines.append("")
    lib_dir = src / "lib"
    if lib_dir.exists():
        for f in sorted(lib_dir.glob("*.ts")):
            lines.append(f"- `{f.name}`")
    lines.append("")

    (DOCS / "frontend-tree.md").write_text("\n".join(lines))
    print(f"  Generated docs/frontend-tree.md ({len(lines)} lines)")


# ---------------------------------------------------------------------------
# 4. Dependencies
# ---------------------------------------------------------------------------

def generate_dependencies():
    lines = [
        "# Dependencies",
        "",
        f"> Auto-generated on {_now()}. Do not edit manually.",
        "",
    ]

    # Python
    req_file = BACKEND / "requirements.txt"
    if req_file.exists():
        lines.append("## Backend (Python)")
        lines.append("")
        lines.append("| Package | Version |")
        lines.append("|---------|---------|")
        for line in req_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "==" in line:
                pkg, ver = line.split("==", 1)
                lines.append(f"| `{pkg}` | {ver} |")
            elif ">=" in line:
                pkg, ver = line.split(">=", 1)
                lines.append(f"| `{pkg}` | >={ver} |")
            else:
                lines.append(f"| `{line}` | - |")
        lines.append("")

    # JavaScript
    pkg_file = FRONTEND / "package.json"
    if pkg_file.exists():
        pkg = json.loads(pkg_file.read_text())

        lines.append("## Frontend (Node.js)")
        lines.append("")

        for section_name, section_key in [("Dependencies", "dependencies"), ("Dev Dependencies", "devDependencies")]:
            deps = pkg.get(section_key, {})
            if deps:
                lines.append(f"### {section_name}")
                lines.append("")
                lines.append("| Package | Version |")
                lines.append("|---------|---------|")
                for name, ver in sorted(deps.items()):
                    lines.append(f"| `{name}` | {ver} |")
                lines.append("")

    (DOCS / "dependencies.md").write_text("\n".join(lines))
    print(f"  Generated docs/dependencies.md ({len(lines)} lines)")


# ---------------------------------------------------------------------------
# 5. Environment Variables
# ---------------------------------------------------------------------------

def generate_env_vars():
    lines = [
        "# Environment Variables",
        "",
        f"> Auto-generated on {_now()}. Do not edit manually.",
        "",
    ]

    # Parse from .env.example
    env_example = ROOT / ".env.example"
    if env_example.exists():
        lines.append("## From `.env.example`")
        lines.append("")
        lines.append("| Variable | Example Value | Notes |")
        lines.append("|----------|---------------|-------|")

        current_section = ""
        for line in env_example.read_text().splitlines():
            line = line.strip()
            if line.startswith("# --") or (line.startswith("# ") and line.endswith("--")):
                # Section header
                current_section = line.strip("# -").strip()
                continue
            if line.startswith("#") and "=" not in line:
                # Comment line (note)
                continue
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                # Mask sensitive values
                display_val = val
                if any(s in key.lower() for s in ("password", "secret", "key")) and val not in ("", "change-me-in-production"):
                    display_val = "***"
                lines.append(f"| `{key}` | `{display_val}` | {current_section} |")

        lines.append("")

    # Parse from config.py Settings class
    config_file = BACKEND / "app" / "core" / "config.py"
    if config_file.exists():
        lines.append("## From `config.py` Settings class")
        lines.append("")
        lines.append("| Setting | Type | Default |")
        lines.append("|---------|------|---------|")

        try:
            source = config_file.read_text()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == "Settings":
                    for item in node.body:
                        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                            name = item.target.id
                            type_str = _unparse_safe(item.annotation)
                            default = _unparse_safe(item.value) if item.value else "required"
                            # Skip internal fields
                            if name.startswith("_") or name == "model_config":
                                continue
                            lines.append(f"| `{name}` | `{type_str}` | `{default}` |")
        except (SyntaxError, UnicodeDecodeError):
            pass

        lines.append("")

    (DOCS / "env-vars.md").write_text("\n".join(lines))
    print(f"  Generated docs/env-vars.md ({len(lines)} lines)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Generating project documentation...")
    ensure_docs_dir()
    generate_api_routes()
    generate_db_schema()
    generate_frontend_tree()
    generate_dependencies()
    generate_env_vars()
    print("Done! Files written to docs/")


if __name__ == "__main__":
    main()
