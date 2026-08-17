"""Statically validate etl/ingest_osm.py before running it.

Catches paste corruption (dropped characters) without touching the database:
  * keyword arguments that the callee does not accept  -> iex= vs index=
  * dict keys written to a table that are not columns   -> ight_m vs height_m
  * syntax errors and undefined names

Usage:  python3 validate_etl.py [path]
"""
from __future__ import annotations

import ast
import difflib
import re
import sys
from pathlib import Path

PATH = Path(sys.argv[1] if len(sys.argv) > 1 else "etl/ingest_osm.py")

# Signatures we can verify without importing heavy optional deps.
KNOWN_KWARGS = {
    "to_postgis": {"name", "con", "schema", "if_exists", "index",
                   "index_label", "chunksize", "dtype"},
    "to_sql": {"name", "con", "schema", "if_exists", "index", "index_label",
               "chunksize", "dtype", "method"},
    "to_crs": {"crs", "epsg", "inplace"},
    "set_crs": {"crs", "epsg", "inplace", "allow_override"},
    "astype": {"dtype", "copy", "errors"},
    "clip": {"lower", "upper", "axis", "inplace"},
    "fillna": {"value", "method", "axis", "inplace", "limit", "downcast"},
    "drop_duplicates": {"subset", "keep", "inplace", "ignore_index"},
    "reset_index": {"level", "drop", "inplace", "col_level", "col_fill",
                    "allow_duplicates", "names"},
}

# Column names are parsed from db/schema.sql at runtime - hardcoding them
# once produced false alarms (elevation_m is real; my copy was stale).
def load_schema(path: Path) -> dict[str, set[str]]:
    if not path.is_file():
        return {}
    sql = path.read_text()
    out: dict[str, set[str]] = {}
    for m in re.finditer(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\((.*?)\n\);",
                         sql, re.S):
        tbl, body = m.group(1), m.group(2)
        cols: set[str] = set()
        for line in body.splitlines():
            line = line.strip().rstrip(",")
            if not line or line.upper().startswith(
                    ("PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CONSTRAINT", "CHECK")):
                continue
            first = line.split()[0]
            if first.isidentifier():
                cols.add(first)
        if cols:
            out[tbl] = cols
    return out


SCHEMA_PATH = Path("db/schema.sql")
TABLE_COLUMNS = load_schema(SCHEMA_PATH)

problems: list[str] = []


def near(name: str, pool) -> str:
    m = difflib.get_close_matches(name, pool, n=1, cutoff=0.55)
    return f'  -> did you mean "{m[0]}" ?' if m else ""


def main() -> int:
    if not PATH.is_file():
        print(f"FAIL  {PATH} not found")
        return 2
    src = PATH.read_text()

    try:
        tree = ast.parse(src, filename=str(PATH))
    except SyntaxError as e:
        print(f"FAIL  syntax error at line {e.lineno}: {e.msg}")
        return 2

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        fname = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
        if fname not in KNOWN_KWARGS:
            continue
        allowed = KNOWN_KWARGS[fname]
        for kw in node.keywords:
            if kw.arg is None:
                continue
            if kw.arg not in allowed:
                problems.append(
                    f"line {node.lineno}: {fname}() got unexpected keyword "
                    f'"{kw.arg}"{near(kw.arg, allowed)}')

    # Dict literals written into a known table, scoped to the ENCLOSING
    # function so a dict in ingest_roads is never checked against buildings.
    for fnode in ast.walk(tree):
        if not isinstance(fnode, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        tables = [c.args[0].value
                  for c in ast.walk(fnode)
                  if isinstance(c, ast.Call)
                  and isinstance(c.func, ast.Attribute)
                  and c.func.attr in ("to_postgis", "to_sql")
                  and c.args and isinstance(c.args[0], ast.Constant)
                  and isinstance(c.args[0].value, str)]
        tables = [t for t in tables if t in TABLE_COLUMNS]
        if len(set(tables)) != 1:
            continue                      # ambiguous: skip rather than guess
        table = tables[0]
        cols = TABLE_COLUMNS[table]
        for anc in ast.walk(fnode):
            if not isinstance(anc, ast.Dict):
                continue
            keys = [k.value for k in anc.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)]
            if "geometry" not in keys:
                continue
            if len(set(keys) & cols) < 3:
                continue                  # not the table-shaped dict
            for b in [k for k in keys if k not in cols]:
                problems.append(
                    f'line {anc.lineno}: dict written to "{table}" has '
                    f'key "{b}" which is not a column{near(b, cols)}')

    # Undefined names. compile() does NOT catch these - it only checks
    # syntax - so a dropped character inside an identifier (roof_col ->
    # of_col) survives all the way to runtime. Resolve each function's
    # loads against its own assignments plus module and builtin scope.
    import builtins

    # Implicit module globals that never appear as assignments.
    module_names = set(dir(builtins)) | {
        "__file__", "__name__", "__doc__", "__package__", "__spec__",
        "__loader__", "__builtins__", "__debug__", "__path__",
    }
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                module_names.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            module_names.add(n.name)
        elif isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.For,
                            ast.withitem, ast.NamedExpr)):
            # Covers  a = ...,  a, b = ...,  [a, b] = ...,  for a, b in ...
            targets = []
            if isinstance(n, ast.Assign):
                targets = n.targets
            elif isinstance(n, (ast.AugAssign, ast.AnnAssign)):
                targets = [n.target]
            elif isinstance(n, ast.For):
                targets = [n.target]
            elif isinstance(n, ast.withitem):
                targets = [n.optional_vars] if n.optional_vars else []
            elif isinstance(n, ast.NamedExpr):
                targets = [n.target]
            for t in targets:
                for sub in ast.walk(t) if t is not None else []:
                    if isinstance(sub, ast.Name):
                        module_names.add(sub.id)

    def check_fn(fn: ast.AST, outer: set[str]) -> None:
        local = set(outer)
        for a in ast.walk(fn):
            if isinstance(a, ast.arg):
                local.add(a.arg)
            elif isinstance(a, ast.Name) and isinstance(a.ctx, (ast.Store, ast.Del)):
                local.add(a.id)
            elif isinstance(a, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                local.add(a.name)
            elif isinstance(a, (ast.Import, ast.ImportFrom)):
                for al in a.names:
                    local.add((al.asname or al.name).split(".")[0])
            elif isinstance(a, ast.ExceptHandler) and a.name:
                local.add(a.name)
            elif isinstance(a, (ast.Global, ast.Nonlocal)):
                local.update(a.names)
        for a in ast.walk(fn):
            if isinstance(a, ast.Name) and isinstance(a.ctx, ast.Load):
                if a.id not in local:
                    problems.append(
                        f"line {a.lineno}: undefined name \"{a.id}\""
                        f"{near(a.id, sorted(local))}")

    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            check_fn(n, module_names)

    seen = set()
    uniq = [p for p in problems if not (p in seen or seen.add(p))]
    if uniq:
        print(f"FAIL  {len(uniq)} problem(s) in {PATH}\n")
        for p in uniq:
            print("  " + p)
        print("\nThe file is corrupted. Re-paste it from the fix document.")
        return 1
    print(f"OK    {PATH} passes static validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
