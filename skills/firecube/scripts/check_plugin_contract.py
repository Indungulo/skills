#!/usr/bin/env python3
# Copyright (c) 2026 EUMETSAT
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

"""Static contract check for a Firecube plugin: core owns run/resume, no private names, no known traps.

The import boundary (only firecube.ingestor.api, firecube.core.api, firecube.ingestor.extensions) is a ruff rule in the
plugin's pyproject.toml, see plugin-development.md, not a check here.

Usage (no data, no install, seconds; stdlib only):
  python check_plugin_contract.py <plugin-project> [--json OUT] [--exclude GLOB ...] [--max-locations N]

Run it with the plugin project's interpreter so an installed firecube extends the private-name list;
`uv run check_plugin_contract.py <plugin-project>` also works standalone, with the static list only.

FAIL (exit 1):
  framework-overrides     a plugin class defines run, finalize_pipeline, or a private Firecube method
                          (_aggregate_metrics, _resolve_time_dim_name, _create_batches, ...); _process_batch is
                          allowed only on a direct BaseIngestor subclass
  private-core-access     self._name / super()._name that no plugin class defines (inherited from Firecube, or
                          missing like self._write_lock on core main); self._log is a WARN
  discovery-empty-return  discover_source_files returns [], (), None, or an empty iterator (hides items from core);
                          a final bare `return` that ends a generator is not flagged
  referenced-files        README, CONTRIBUTING, docs, or notebooks name a repository file that does not exist
WARN (review, exit 0):
  store-writes            attrs writes, zarr.open_group in a write mode, consolidate_metadata in plugin code
  tests-outside-repo      test fixtures resolved outside the repository
  firecube-pin            firecube requirement not pinned
  performance-claims      docs lines with timing numbers: each needs a benchmark record

Exit codes: 0 no FAIL, 1 at least one FAIL, 2 invalid arguments.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

# Public modules imported from their parent package, e.g. `from firecube.ingestor import api`.
PUBLIC_SUBMODULES = {"firecube.ingestor": {"api", "extensions"}, "firecube.core": {"api"}}
FORBIDDEN_PUBLIC_OVERRIDES = {"run", "finalize_pipeline"}
# Private names on Firecube's ingestor classes (0.1.5 and core main). Extended at runtime from an installed firecube.
CORE_PRIVATE = {
    "_aggregate_metrics", "_bind_index_at_startup", "_cached_zarr_schema",
    "_check_legacy_index_record_at_startup", "_compile_write_intents", "_create_batches",
    "_emit_index_ensured_event", "_ensure_index_identity_at_startup", "_ensure_index_record_at_startup",
    "_materialize", "_process_batch", "_resolve_index_binding_at_startup", "_resolve_time_dim_name",
    "_validate_context_hook_signatures", "_validate_duckdb_persistence_contract",
    "_verify_existing_cube_batch_groups", "_verify_per_group_identity_at_startup",
    "_verify_per_group_identity_at_store", "_verify_schema_at_pod_startup", "_write_lock", "_write_gate",
    "_chunk_manager", "_span_recorder", "_alignment", "_append_order", "_log",
}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", "build", "dist",
             ".claude", ".check_done"}
PATH_RE = re.compile(
    r"(?<![\w./-])((?:scripts|tools|bin|examples|docs|tests|notebooks|src)/[\w./-]+"
    r"\.(?:py|sh|md|ipynb|toml|ya?ml|json|txt))\b"
)
PLACEHOLDER_STEMS = {"path", "path_or_file", "file", "foo", "bar", "example", "my_plugin", "your_file"}
MD_LINK_RE = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")
EXTERNAL_LINK_RE = re.compile(r"^[a-z]+:|^/|^<|^\{")
CLAIM_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:ms|s|sec|seconds|min|minutes|h|hours)\b.*"
    r"\b(?:ingest|wall|faster|speedup|run|download|takes?|in about)\b|"
    r"\b(?:ingest|wall|faster|speedup|takes?|in about)\b.*"
    r"\b\d+(?:\.\d+)?\s*(?:ms|s|sec|seconds|min|minutes|h|hours)\b",
    re.I,
)
STORE_NAME_RE = re.compile(r"root|group|store|zarr|stored", re.I)
WRITE_MODES = {"a", "w", "w-", "r+"}
EMPTY_CALLS = {"iter(())", "iter([])", "list()", "tuple()", "[]"}

results: list[dict] = []


def format_locations(locations: list[str], limit: int) -> str:
    """Render up to `limit` locations after a separator, with a count of the ones left out."""
    if not locations:
        return ""
    more = f"; +{len(locations) - limit} more" if len(locations) > limit else ""
    return " | " + "; ".join(locations[:limit]) + more


def report(check: str, level: str, detail: str, locations: list[str] | None = None, limit: int = 8) -> None:
    """Record one result and print it as a single `[LEVEL] check: detail | locations` line."""
    locations = locations or []
    results.append({"check": check, "level": level, "detail": detail, "locations": locations})
    print(f"[{level}] {check}: {detail}{format_locations(locations, limit)}")


def report_rule(check: str, level: str, found: list[str], ok: str, bad: str, max_loc: int) -> None:
    """Report PASS with `ok` when nothing was found, otherwise `level` with `bad` and the locations."""
    report(check, level if found else "PASS", bad if found else ok, found, max_loc)


def git_ignored(root: Path, paths: list[Path]) -> set[Path]:
    """The subset of paths that git ignores under root (.gitignore, .git/info/exclude, global excludes).
    Empty when root is not a git checkout or git is not installed; the check then relies on SKIP_DIRS alone."""
    if not paths:
        return set()
    try:
        r = subprocess.run(["git", "-C", str(root), "check-ignore", "--stdin"], capture_output=True, text=True,
                           input="\n".join(str(p.relative_to(root)) for p in paths) + "\n", timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return set()
    if r.returncode not in (0, 1):
        return set()
    return {root / line for line in r.stdout.splitlines() if line}


def walk(root: Path, patterns: tuple[str, ...], excludes: list[str]) -> list[Path]:
    """Files under root matching any pattern, skipping tool directories, excluded globs and git-ignored files."""
    out = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts) or not path.is_file():
            continue
        if any(fnmatch.fnmatch(str(rel), ex) for ex in excludes):
            continue
        if any(fnmatch.fnmatch(path.name, p) for p in patterns):
            out.append(path)
    ignored = git_ignored(root, out)
    return sorted(p for p in out if p not in ignored)


def extend_private_names() -> str:
    """Add the private names of an installed firecube's ingestor classes to CORE_PRIVATE; say which source was used."""
    try:
        import firecube.ingestor.api as api
    except Exception:
        # any import failure means no installed firecube to read names from
        return "static list (firecube not importable)"
    for name in ("BaseIngestor", "GenericZarrIngestor", "DirectZarrIngestor", "GenericParquetIngestor"):
        cls = getattr(api, name, None)
        if cls is not None:
            CORE_PRIVATE.update(n for n in dir(cls) if n.startswith("_") and not n.startswith("__"))
    return "static list plus installed firecube"


def is_firecube_module(name: str) -> bool:
    """True only for the firecube package itself, never a plugin package like firecube_<name>."""
    return name == "firecube" or name.startswith("firecube.")


def assign_targets(node: ast.Assign | ast.AnnAssign | ast.AugAssign) -> list[ast.expr]:
    """The target expressions of an assignment, augmented assignment, or annotated assignment."""
    return node.targets if isinstance(node, ast.Assign) else [node.target]


class PluginIndex:
    """Collect class structure across the plugin's source files."""

    def __init__(self, trees: dict[Path, ast.Module]):
        """Index every parsed file."""
        self.trees = trees
        self.firecube_names: set[str] = set()
        self.firecube_module_aliases: set[str] = set()
        self.classes: dict[str, ast.ClassDef] = {}
        self.class_file: dict[str, Path] = {}
        self.defined_private: set[str] = set()
        for path, tree in trees.items():
            for node in ast.walk(tree):
                self._index_node(path, node)

    def _index_node(self, path: Path, node: ast.AST) -> None:
        """Record one node: firecube imports, plugin classes, and the private names the plugin assigns."""
        if isinstance(node, ast.ImportFrom) and node.module and is_firecube_module(node.module):
            self._index_import_from(node)
        elif isinstance(node, ast.Import):
            self._index_import(node)
        elif isinstance(node, ast.ClassDef):
            self._index_class(path, node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            self._index_self_assign(node)

    def _index_import_from(self, node: ast.ImportFrom) -> None:
        """Names imported from firecube; an imported public module (`api`) also becomes a module alias."""
        self.firecube_names.update(a.asname or a.name for a in node.names)
        public = PUBLIC_SUBMODULES.get(node.module, set())
        self.firecube_module_aliases.update(a.asname or a.name for a in node.names if a.name in public)

    def _index_import(self, node: ast.Import) -> None:
        """Aliases bound by `import firecube...` statements."""
        for a in node.names:
            if is_firecube_module(a.name):
                self.firecube_module_aliases.add(a.asname or a.name.split(".")[0])

    def _index_class(self, path: Path, node: ast.ClassDef) -> None:
        """Remember the class and the private methods and class attributes it defines itself."""
        self.classes[node.name] = node
        self.class_file[node.name] = path
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("_"):
                if item.name not in CORE_PRIVATE:
                    self.defined_private.add(item.name)
            elif isinstance(item, (ast.Assign, ast.AnnAssign)):
                names = (t.id for t in assign_targets(item) if isinstance(t, ast.Name))
                self.defined_private.update(n for n in names if n.startswith("_"))

    def _index_self_assign(self, node: ast.Assign | ast.AnnAssign | ast.AugAssign) -> None:
        """Private `self._x` attributes the plugin assigns anywhere."""
        for target in assign_targets(node):
            for sub in ast.walk(target):
                if (isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == "self"
                        and sub.attr.startswith("_")):
                    self.defined_private.add(sub.attr)

    def base_names(self, cls: ast.ClassDef) -> list[tuple[str, bool]]:
        """Return (name, via_firecube_module_alias) for each base, e.g. `api.GenericZarrIngestor`
        after `import firecube.ingestor.api as api` is tracked the same as a plain ImportFrom name."""
        names = []
        for b in cls.bases:
            if isinstance(b, ast.Name):
                names.append((b.id, False))
            elif isinstance(b, ast.Attribute):
                via_alias = isinstance(b.value, ast.Name) and b.value.id in self.firecube_module_aliases
                names.append((b.attr, via_alias))
        return names

    def is_ingestor(self, name: str, seen: set[str] | None = None) -> bool:
        """True when the class derives, directly or through plugin classes, from a Firecube ingestor or mixin."""
        seen = seen or set()
        if name in seen or name not in self.classes:
            return False
        seen.add(name)
        for base, via_alias in self.base_names(self.classes[name]):
            if (base in self.firecube_names or via_alias) and base.endswith(("Ingestor", "Mixin")):
                return True
            if self.is_ingestor(base, seen):
                return True
        return False


def loc(root: Path, path: Path, node: ast.AST) -> str:
    """`relative/path.py:line` for a node."""
    return f"{path.relative_to(root)}:{getattr(node, 'lineno', '?')}"


def call_name(func: ast.expr) -> str:
    """The called name: `x` for `x(...)` and `a.b.x(...)`, empty for anything else."""
    if isinstance(func, ast.Attribute):
        return func.attr
    return func.id if isinstance(func, ast.Name) else ""


def is_store_attrs_update(func: ast.expr, name: str) -> bool:
    """`<store-like>.attrs.update(...)`; in-memory dataset attrs do not count."""
    if name != "update" or not isinstance(func, ast.Attribute):
        return False
    owner = ast.unparse(func.value)
    return owner.endswith("attrs") and bool(STORE_NAME_RE.search(owner))


def open_group_write_mode(node: ast.Call, name: str) -> str | None:
    """The write mode of an `open_group(..., mode=...)` call, or None for a read or no call."""
    if name != "open_group":
        return None
    mode = next((kw.value for kw in node.keywords if kw.arg == "mode"), None)
    if isinstance(mode, ast.Constant) and mode.value in WRITE_MODES:
        return mode.value
    return None


def is_empty_value(v: ast.expr | None) -> bool:
    """A return value that hands core nothing: bare return, None, an empty literal, or an empty iterator call."""
    return (
        v is None
        or (isinstance(v, (ast.List, ast.Tuple, ast.Set)) and not v.elts)
        or (isinstance(v, ast.Constant) and v.value is None)
        or (isinstance(v, ast.Call) and ast.unparse(v) in EMPTY_CALLS)
    )


def is_generator(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True when the function itself yields; yields inside nested functions, lambdas, or classes do not count."""
    stack = list(func.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.Yield, ast.YieldFrom)):
            return True
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            stack.extend(ast.iter_child_nodes(node))
    return False


def is_framework_override(name: str, direct_base: bool) -> bool:
    """run/finalize_pipeline, or a private Firecube method other than _process_batch on a direct BaseIngestor."""
    if name in FORBIDDEN_PUBLIC_OVERRIDES:
        return True
    return name in CORE_PRIVATE and not (name == "_process_batch" and direct_base)


class CodeChecker:
    """Apply the per-node contract rules to the plugin sources and collect the locations for each rule."""

    def __init__(self, root: Path, index: PluginIndex):
        """Start with empty findings for the project at root."""
        self.root = root
        self.index = index
        self.path = root
        self.overrides: list[str] = []
        self.private_access: list[str] = []
        self.log_access: list[str] = []
        self.empty_returns: list[str] = []
        self.store_writes: list[str] = []

    def at(self, node: ast.AST) -> str:
        """Location of a node in the file being checked."""
        return loc(self.root, self.path, node)

    def check_file(self, path: Path, tree: ast.Module) -> None:
        """Run every rule over one parsed file."""
        self.path = path
        for node in ast.walk(tree):
            self.check_node(node)
        for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            if self.index.is_ingestor(cls.name):
                self.check_ingestor_class(cls)

    def check_node(self, node: ast.AST) -> None:
        """Dispatch one node to the rule for its kind."""
        if isinstance(node, ast.Attribute) and node.attr.startswith("_") and not node.attr.startswith("__"):
            self.check_private_attribute(node)
        elif isinstance(node, ast.Call):
            self.check_call(node)
        elif isinstance(node, (ast.Assign, ast.AugAssign)):
            self.check_attrs_assign(node)

    def check_private_attribute(self, node: ast.Attribute) -> None:
        """private-core-access: super()._core_name, or a self._name the plugin never defines."""
        owner = node.value
        is_self = isinstance(owner, ast.Name) and owner.id == "self"
        is_super = isinstance(owner, ast.Call) and isinstance(owner.func, ast.Name) and owner.func.id == "super"
        if is_super and node.attr in CORE_PRIVATE and node.attr != "_process_batch":
            self.private_access.append(f"{self.at(node)} super().{node.attr}")
        elif is_self and isinstance(node.ctx, ast.Load) and node.attr not in self.index.defined_private:
            if node.attr == "_log":
                self.log_access.append(self.at(node))
            elif node.attr != "_process_batch":
                self.private_access.append(f"{self.at(node)} self.{node.attr}")

    def check_call(self, node: ast.Call) -> None:
        """store-writes: the calls that write a store from plugin code."""
        name = call_name(node.func)
        if name == "consolidate_metadata":
            self.store_writes.append(f"{self.at(node)} consolidate_metadata")
        if is_store_attrs_update(node.func, name):
            self.store_writes.append(f"{self.at(node)} attrs.update")
        mode = open_group_write_mode(node, name)
        if mode:
            self.store_writes.append(f"{self.at(node)} open_group(mode={mode!r})")

    def check_attrs_assign(self, node: ast.Assign | ast.AugAssign) -> None:
        """store-writes: `<store-like>.attrs[...] = ...`; dataset.attrs on an in-memory xarray object is fine."""
        for target in assign_targets(node):
            if isinstance(target, ast.Subscript) and ast.unparse(target.value).endswith("attrs"):
                target_text = ast.unparse(target.value)
                if STORE_NAME_RE.search(target_text):
                    self.store_writes.append(f"{self.at(node)} {target_text}[...] =")

    def check_ingestor_class(self, cls: ast.ClassDef) -> None:
        """framework-overrides and discovery-empty-return for one ingestor class."""
        bases = self.index.base_names(cls)
        direct_base = any(name == "BaseIngestor" for name, _ in bases)
        for item in cls.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if is_framework_override(item.name, direct_base):
                self.overrides.append(f"{self.at(item)} {cls.name}.{item.name}")
            if item.name == "discover_source_files":
                self.check_discovery(item)

    def check_discovery(self, func: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """discovery-empty-return: every empty return, except a final bare return that ends a generator."""
        final = func.body[-1] if func.body and is_generator(func) else None
        for sub in ast.walk(func):
            if not isinstance(sub, ast.Return) or not is_empty_value(sub.value):
                continue
            if sub is final and (sub.value is None or isinstance(sub.value, ast.Constant)):
                continue
            self.empty_returns.append(f"{self.at(sub)} {ast.unparse(sub)}")

    def report(self, max_loc: int) -> None:
        """Print the code-rule results in their fixed order."""
        report_rule("framework-overrides", "FAIL", self.overrides,
                    "no run/finalize_pipeline/private Firecube method overridden",
                    "framework-owned methods overridden", max_loc)
        report_rule("private-core-access", "FAIL", self.private_access,
                    "no private Firecube attribute or method used",
                    "private names the plugin does not define", max_loc)
        if self.log_access:
            report("private-core-access", "WARN",
                   f"self._log used {len(self.log_access)}x; prefer logging.getLogger(__name__)", self.log_access, 3)
        report_rule("discovery-empty-return", "FAIL", self.empty_returns,
                    "discovery never returns an empty result to skip work",
                    "discover_source_files returns empty: core never sees the items", max_loc)
        report_rule("store-writes", "WARN", self.store_writes, "none found",
                    "plugin writes the store itself: group attrs are write-once; provenance belongs in arrays",
                    max_loc)


def parse_sources(root: Path, src_files: list[Path]) -> dict[Path, ast.Module]:
    """Parse every source file; a file that does not parse is reported as a FAIL and skipped."""
    trees: dict[Path, ast.Module] = {}
    for path in src_files:
        try:
            trees[path] = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
        except SyntaxError as exc:
            report("parse", "FAIL", f"{path.relative_to(root)}: {exc}")
    return trees


def check_code(root: Path, src_files: list[Path], max_loc: int) -> None:
    """Run the static code rules over the plugin's source files and report them."""
    trees = parse_sources(root, src_files)
    checker = CodeChecker(root, PluginIndex(trees))
    for path, tree in trees.items():
        checker.check_file(path, tree)
    checker.report(max_loc)


def notebook_text(path: Path) -> str:
    """The concatenated cell sources of a notebook; empty when it is not valid JSON."""
    try:
        nb = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return ""
    return "\n".join("".join(c.get("source", [])) for c in nb.get("cells", []))


def missing_paths(root: Path, path: Path, lineno: int, line: str) -> list[str]:
    """Repository paths (scripts/, docs/, tests/, ...) named in one docs line that do not exist."""
    out = []
    for m in PATH_RE.finditer(line):
        rel = m.group(1).rstrip(".")
        if Path(rel).stem in PLACEHOLDER_STEMS:
            continue
        if not (root / rel).exists() and not (path.parent / rel).exists():
            out.append(f"{path.relative_to(root)}:{lineno} {rel}")
    return out


def missing_links(root: Path, path: Path, lineno: int, line: str) -> list[str]:
    """Relative Markdown link targets in one line that do not exist next to the document."""
    out = []
    for m in MD_LINK_RE.finditer(line):
        target = m.group(1)
        if EXTERNAL_LINK_RE.match(target) or "{{" in target or Path(target).stem in PLACEHOLDER_STEMS:
            continue
        if not (path.parent / target).exists():
            out.append(f"{path.relative_to(root)}:{lineno} {target}")
    return out


def check_docs(root: Path, excludes: list[str], max_loc: int) -> None:
    """referenced-files and performance-claims over README, docs, and notebooks."""
    missing, claims = [], []
    for path in walk(root, ("*.md", "*.ipynb", "*.rst"), excludes):
        text = notebook_text(path) if path.suffix == ".ipynb" else path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), 1):
            missing += missing_paths(root, path, lineno, line)
            if path.suffix == ".md":
                missing += missing_links(root, path, lineno, line)
                if CLAIM_RE.search(line):
                    claims.append(f"{path.relative_to(root)}:{lineno}")
    report_rule("referenced-files", "FAIL", sorted(set(missing)), "every referenced repository file exists",
                "referenced files missing", max_loc)
    report_rule("performance-claims", "WARN", claims, "none found",
                f"{len(claims)} lines with timing numbers: each needs a full-scale benchmark record", max_loc)


def outside_references(root: Path, path: Path) -> list[str]:
    """Lines in one test file that resolve fixtures above the repository or through an absolute home path."""
    depth = len(path.relative_to(root).parts) - 1
    out = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        m = re.search(r"parents\[(\d+)\]", line)
        if m and "__file__" in line and int(m.group(1)) >= depth:
            out.append(f"{path.relative_to(root)}:{lineno}")
        if re.search(r"""["'](?:/home/|/Users/|[A-Z]:\\\\)""", line):
            out.append(f"{path.relative_to(root)}:{lineno} absolute path")
    return out


def check_tests_outside(root: Path, excludes: list[str], max_loc: int) -> None:
    """tests-outside-repo: a fresh checkout must skip missing fixtures, never error."""
    tests = walk(root / "tests", ("*.py",), excludes) if (root / "tests").exists() else []
    outside = [ref for path in tests for ref in outside_references(root, path)]
    report_rule("tests-outside-repo", "WARN", outside, "none found",
                "fixtures resolved outside the repository: a fresh checkout must skip, never error", max_loc)


def check_pin(root: Path) -> None:
    """firecube-pin: the firecube requirement in pyproject.toml has an upper bound or an exact pin."""
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return
    m = re.search(r"""["']firecube(\[[^\]]*\])?\s*([<>=!~][^"']*)?["']""", pyproject.read_text(encoding="utf-8"))
    spec = (m.group(2) or "").strip() if m else ""
    pinned = bool(re.search(r"==|<", spec))
    found = f"firecube{spec}" if m else "firecube requirement not found"
    report("firecube-pin", "PASS" if pinned else "WARN",
           found + ("" if pinned else ": pin the Firecube version the plugin is tested against"))


def main() -> int:
    """Run all checks on one plugin project; exit 1 when any check FAILs."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", type=Path, help="plugin project directory")
    ap.add_argument("--json", type=Path, help="write the full result list here")
    ap.add_argument("--exclude", action="append", default=[], help="glob relative to the project, repeatable")
    ap.add_argument("--max-locations", type=int, default=8)
    args = ap.parse_args()
    root = args.project.expanduser().resolve()
    if not root.is_dir():
        print(f"[FAIL] project: {root} is not a directory")
        return 1
    source = extend_private_names()
    src_root = root / "src" if (root / "src").is_dir() else root
    src_files = [p for p in walk(src_root, ("*.py",), args.exclude) if "tests" not in p.relative_to(root).parts]
    print(f"[info] project: {root.name}; {len(src_files)} source files; private names from {source}")
    if not src_files:
        where = src_root.relative_to(root) if src_root != root else "."
        report("no-source-files", "FAIL", f"no Python source files found under {where}")
    check_code(root, src_files, args.max_locations)
    check_docs(root, args.exclude, args.max_locations)
    check_tests_outside(root, args.exclude, args.max_locations)
    check_pin(root)
    fails = sum(r["level"] == "FAIL" for r in results)
    warns = sum(r["level"] == "WARN" for r in results)
    hint = "" if not fails else " -- see plugin-traps.md"
    print(f"CONTRACT {'FAIL' if fails else 'PASS'}: {fails} FAIL, {warns} WARN{hint}")
    if args.json:
        args.json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
