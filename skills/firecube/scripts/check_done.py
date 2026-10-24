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

"""Definition-of-done check for a Firecube plugin: one command, PASS/FAIL lines, details on disk.

Usage (from anywhere; run with the plugin project's interpreter so xarray and zarr are available):
  uv run --project <plugin-project> python check_done.py --plugin-id <id> --project <plugin-project> \
      --input-dir <dir with real products> [--ref-var VARIABLE] [--min-variables N] [--group-regex RE] \
      [--fixture-env VAR ...] [--scratch DIR] [--keep]
      [--ingest-option key=value ...] [--workers N] [--skip-lifecycle] [--quick [--quick-glob PATTERN]]
      [--regridded] [--json OUT]

Checks, in order: the static contract check (check_plugin_contract.py beside this file); the entry point and no
developer paths; tests run against real fixtures with none skipped, and again without the fixture variables (a fresh
checkout) with no errors or failures; lint; the plugin is registered; one ingestion that processed at least one item,
with the found/processed/product counts recorded (a bundling plugin reports items, not files); groups written,
with a 1-D monotonic ordering coordinate; a second ingestion with
pipeline_batch_size=1 producing the same groups, sizes, values and attributes; one variable's finite count and sum
equal to the decoded source; then the lifecycle (Zarr, skip with --skip-lifecycle): on core main a pipeline_workers>1
run equal to the one-worker store (skipped on firecube 0.1.5, a documented version limit), a rerun without a flag
refused, a rerun with resume_existing over the same window (0.1.5: expects the documented refusal; core main: leaves
the store equal), an extension (first half of the input, then all of it with resume_existing) equal to the one-shot
store, and a force_reingest run equal as well. Prints a block to paste into
the plan's Log. --quick runs the split-batch and lifecycle checks on one product of the input (the first by name, or
--quick-glob) against a one-product reference store, instead of re-ingesting the whole input four or five times:
the full input is still ingested once for the processed count and the store checks; the extension check is skipped,
since one product is one time unit. --regridded says the store is on a different grid than the source (a binner or a
resampler), so the source-equivalence figures cannot match by construction: the source is not decoded and that
check is skipped without counting against completion. --json also writes every result to a file.
Writes only a fresh subdirectory it creates for itself
inside --scratch (default: <project>/.check_done; removed after the run unless --keep); it never creates or removes
--scratch itself beyond that subdirectory. Running tests or an editable install inside the plugin project also
writes uv's own .venv/ and uv.lock there, not under --scratch.

Exit codes: 0 every check passed, 1 at least one check failed or was skipped, 2 invalid arguments.
"""

from __future__ import annotations

import argparse
import fnmatch
import functools
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inspect_product import group_paths  # noqa: E402  (the sibling script owns the NetCDF group walk)

DATA_SUFFIXES = (".nc", ".nc4", ".h5", ".hdf", ".hdf5")
IGNORED = (".xml", ".jpg", ".jpeg", ".png", ".txt", ".md", ".json", ".py", ".pyc")
# Relative tolerance for comparing float sums of the same values read through different paths.
SUM_RTOL = 1e-6
ENVIRON_RE = re.compile(r"""environ(?:\.get)?\(\s*["']([A-Z][A-Z0-9_]+)["']""")
GETENV_RE = re.compile(r"""getenv\(\s*["']([A-Z][A-Z0-9_]+)["']""")
results: list[tuple[str, bool, str]] = []
infos: list[tuple[str, str]] = []


def check(name: str, ok, detail="") -> None:
    """Record a PASS or FAIL result and print it."""
    results.append((name, bool(ok), str(detail)[:300]))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {str(detail)[:160]}")


def skip(name: str, detail="", counted: bool = True) -> None:
    """counted=True records a not-passed result (missing evidence); counted=False is only for a documented,
    version-specific gate that is not a plugin defect and should not by itself block completion."""
    if counted:
        results.append((name, False, str(detail)[:300]))
    print(f"[SKIP] {name}: {str(detail)[:160]}")


def info(name: str, detail) -> None:
    """Record and print a figure that is evidence but not a pass/fail result."""
    infos.append((name, str(detail)[:300]))
    print(f"[info] {name}: {str(detail)[:160]}")


def run_cmd(cmd, cwd=None, env=None, timeout=3600):
    """Run cmd; a missing executable or a timeout is reported as a failed run (non-zero rc, message in stderr),
    never a traceback. The default timeout of one hour bounds a full ingestion of the operator's input."""
    try:
        r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        return 127, "", f"executable not found: {exc.filename or cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s: {' '.join(str(c) for c in cmd)}"
    return r.returncode, r.stdout, r.stderr


def last_line(text: str) -> str:
    """The last non-blank line of a command's output, or an empty string."""
    return text.strip().splitlines()[-1] if text.strip() else ""


def close(value: float, reference: float) -> bool:
    """True when value equals reference within SUM_RTOL (absolute for references below 1)."""
    return abs(value - reference) <= SUM_RTOL * max(1.0, abs(reference))


def products_in(input_dir: Path) -> set[str]:
    """Product names in the input directory: data files and archives, an archive counted once without .zip."""
    names = set()
    for p in input_dir.iterdir():
        if p.name.startswith(".") or p.suffix.lower() in IGNORED:
            continue
        stem = p.name[:-4] if p.name.endswith(".zip") else p.name
        names.add(stem)
    return names


def source_files(input_dir: Path, extract_root: Path) -> list[Path]:
    """Every data file in the input, extracting archive members that have no extracted twin into extract_root
    (a directory the caller creates and removes; this function never creates or removes it)."""
    files = {p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() in DATA_SUFFIXES}
    for zp in sorted(p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() not in DATA_SUFFIXES):
        if not zipfile.is_zipfile(zp):
            continue
        base = zp.name[:-4] if zp.name.endswith(".zip") else zp.name
        if any(base in str(f) for f in files):
            continue
        with zipfile.ZipFile(zp) as zf:
            for m in zf.namelist():
                if m.lower().endswith(DATA_SUFFIXES):
                    files.add(Path(zf.extract(m, extract_root)))
    return sorted(files)


def first_float_variable(np, ds) -> str | None:
    """The first floating data variable with two or more dimensions."""
    return next((name for name in ds.data_vars if ds[name].ndim >= 2 and np.issubdtype(ds[name].dtype, np.floating)),
                None)


def source_figures(files: list[Path], var: str | None) -> dict:
    """Finite count and nansum of one variable over every source file (first group that has it), plus sizes."""
    import numpy as np
    import xarray as xr

    tot, fin, n, size, chosen = 0.0, 0, 0, 0, var
    for f in files:
        size += f.stat().st_size
        for group in group_paths(f):
            try:
                with xr.open_dataset(f, group=group or None) as ds:
                    if chosen is None:
                        chosen = first_float_variable(np, ds)
                    if chosen and chosen in ds:
                        a = ds[chosen].values
                        tot += float(np.nansum(a))
                        fin += int(np.isfinite(a).sum())
                        n += 1
                        break
            except Exception:
                # the variable is not readable in this group: try the next group
                continue
    return {"var": chosen, "files": n, "sum": tot, "finite": fin, "bytes": size}


def inspect_store(path: Path, var: str | None) -> dict:
    """Per-group sizes, variable count, monotonic 1-D coordinates, attributes, and one variable's figures."""
    import numpy as np
    import xarray as xr
    import zarr

    out: dict = {}
    root = zarr.open_group(str(path), mode="r")

    def walk(g, prefix=""):
        for k, _ in g.groups():
            gp = f"{prefix}{k}"
            try:
                ds = xr.open_zarr(str(path), group=gp, consolidated=False)
                if len(ds.data_vars) == 0:
                    walk(g[k], gp + "/")
                    continue
                rec = {"sizes": {d: int(s) for d, s in ds.sizes.items()}, "nvars": len(ds.data_vars), "mono": [],
                       "coord_warnings": [], "attrs": {a: str(v) for a, v in ds.attrs.items()}}
                for c in ds.coords:
                    v = ds[c].values
                    if v.ndim == 1 and v.size >= 1:  # one time step is trivially ordered
                        try:
                            if bool(np.all(np.diff(v.astype("int64")) > 0)):
                                rec["mono"].append(c)
                        except (TypeError, ValueError, OverflowError) as exc:
                            rec["coord_warnings"].append(
                                f"{c}: cannot check monotonic int64 ordering ({type(exc).__name__}: {str(exc)[:80]})"
                            )
                if var and var in ds:
                    a = ds[var].values
                    rec["sum"] = float(np.nansum(a))
                    rec["finite"] = int(np.isfinite(a).sum())
                out[gp] = rec
            except Exception as exc:
                # record the group's error and keep inspecting the others
                out[gp] = {"error": f"{type(exc).__name__}: {str(exc)[:100]}"}
            walk(g[k], gp + "/")

    walk(root)
    return out


def parse_args() -> argparse.Namespace:
    """The command line; --help prints the module docstring."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plugin-id", required=True)
    ap.add_argument("--project", type=Path, required=True, help="plugin project directory (pyproject.toml)")
    ap.add_argument("--input-dir", type=Path, required=True, help="directory of real products")
    ap.add_argument("--ref-var",
                    help="variable for the source-equivalence figures (default: first floating 2-D+ variable)")
    ap.add_argument("--min-variables", type=int, default=0, help="minimum data variables per group (0 = report only)")
    ap.add_argument("--group-regex", help="every group name must match, e.g. the platform identifier")
    ap.add_argument("--fixture-env", action="append", default=[],
                    help="environment variable the tests read for the fixture directory "
                         "(auto-detected from the tests when omitted)")
    ap.add_argument("--scratch", type=Path, help="where the check writes its stores (default: <project>/.check_done)")
    ap.add_argument("--keep", action="store_true", help="keep the scratch stores")
    ap.add_argument("--ingest-option", action="append", default=[],
                    help="extra --option key=value for every ingestion (plugin options)")
    ap.add_argument("--workers", type=int, default=4, help="pipeline_workers for the parallel run (default 4)")
    ap.add_argument("--first-part-glob",
                    help="products for the first run of the extension check "
                         "(default: the earlier half of the dates in the file names)")
    ap.add_argument("--skip-lifecycle", action="store_true",
                    help="skip the workers/rerun/resume/extension/force runs (Parquet plugins)")
    ap.add_argument("--quick", action="store_true",
                    help="run the split-batch and lifecycle checks on one product of the input instead of all of it")
    ap.add_argument("--quick-glob", help="product name pattern for --quick (default: the first product by name)")
    ap.add_argument("--regridded", action="store_true",
                    help="the store is on a different grid than the source: skip the source-equivalence figures")
    ap.add_argument("--json", type=Path, help="also write every result and figure to this JSON file")
    return ap.parse_args()


def read_py_tree(directory: Path) -> str:
    """The concatenated text of every .py file under a directory."""
    paths = glob.glob(str(directory / "**" / "*.py"), recursive=True)
    return "\n".join(Path(p).read_text(encoding="utf-8", errors="ignore") for p in paths)


def check_contract(proj: Path) -> None:
    """Run check_plugin_contract.py beside this file and record its verdict with the FAIL lines."""
    contract = Path(__file__).with_name("check_plugin_contract.py")
    if not contract.exists():
        return
    rc, out, err = run_cmd([sys.executable, str(contract), str(proj)])
    summary = next((line for line in out.splitlines() if line.startswith("CONTRACT")), (out + err).strip()[-160:])
    fails = [line for line in out.splitlines() if line.startswith("[FAIL]")]
    check("contract: public Firecube API only, no framework overrides, no empty discovery", rc == 0,
          "; ".join(f[7:90] for f in fails) or summary)


def check_metadata(args: argparse.Namespace, proj: Path, pyproject: Path) -> str:
    """Entry point and developer paths; returns the tests' text for fixture detection."""
    text = pyproject.read_text(encoding="utf-8")
    check("entry point registered under the plugin id", re.search(rf"^\s*{re.escape(args.plugin_id)}\s*=", text, re.M),
          args.plugin_id)
    src_text = read_py_tree(proj / "src")
    test_text = read_py_tree(proj / "tests")
    home = str(Path.home())
    check("no absolute developer paths in code or tests", home not in src_text + test_text, "")
    return test_text


def check_tests_and_lint(args: argparse.Namespace, proj: Path, input_dir: Path, test_text: str) -> None:
    """Tests against real fixtures with none skipped, a fresh-checkout run without fixture variables, and ruff."""
    env = dict(os.environ)
    fixture_vars = set(args.fixture_env) | set(ENVIRON_RE.findall(test_text)) | set(GETENV_RE.findall(test_text))
    for var in fixture_vars:
        env[var] = str(input_dir)
    info("fixture env vars set to the input dir", sorted(fixture_vars) or "none found in tests")
    rc, out, err = run_cmd(["uv", "run", "pytest", "-q"], cwd=proj, env=env)
    tail = last_line(out + err)
    check("tests pass", rc == 0, tail)
    skipped = re.search(r"(\d+) skipped", tail)
    check("no test skipped", not skipped or int(skipped.group(1)) == 0, tail)
    fresh_env = {k: v for k, v in os.environ.items() if k not in fixture_vars}
    rc, out, err = run_cmd(["uv", "run", "pytest", "-q"], cwd=proj, env=fresh_env)
    tail = last_line(out + err)
    bad = re.search(r"(\d+) (?:failed|errors?)\b", tail)
    check("fresh checkout (fixture variables unset): no errors or failures, skips allowed", not bad and rc in (0, 5),
          tail)
    rc, out, err = run_cmd(["uv", "run", "ruff", "check"], cwd=proj, env=env)
    check("ruff clean", rc == 0, last_line(out + err))


def firecube_version() -> str | None:
    """The installed firecube version, or None (recorded as a FAIL) when `firecube --version` does not run."""
    rc, out, err = run_cmd(["firecube", "--version"])
    if rc != 0:
        check("firecube is on PATH (firecube --version)", False, err.strip() or out.strip() or f"exit {rc}")
        return None
    m = re.search(r"\d+\.\d+\.\d+", out + err)
    version = m.group(0) if m else (out + err).strip()
    info("firecube version", version)
    return version


def plugin_registered(plugin_id: str) -> bool:
    """Whether `firecube plugins list` names the plugin id; recorded as a check."""
    _, out, _ = run_cmd(["firecube", "plugins", "list"])
    registered = bool(re.search(rf"\b{re.escape(plugin_id)}\b", out))
    check("plugin registered (firecube plugins list)", registered, out.strip()[:100])
    return registered


def ingest_detail(rc: int, err: str) -> str:
    """'ok' for a successful run; otherwise the last error-looking stderr line, else the last stderr line."""
    if rc == 0:
        return "ok"
    errors = [line for line in err.splitlines()
              if re.search(r"error|traceback|failed", line, re.I) and not line.startswith("{")]
    return errors[-1] if errors else last_line(err)


def ingest(args: argparse.Namespace, input_dir: Path, work: Path, name: str, *extra: str,
           source: Path | None = None, target: Path | None = None):
    """One `firecube ingest` into target (default: <work>/<name>.zarr); returns
    (rc, target, files found, files processed, detail)."""
    target = target or work / f"{name}.zarr"
    cmd = ["firecube", "ingest", args.plugin_id, "--input-data", str(source or input_dir),
           "--target", f"file://{target}", "--product-name", args.plugin_id, "--storage-type", "local",
           "--storage-driver", "fsspec", "--output-format", "zarr", "--write-mode", "direct",
           "--option", "no_progress=true", *[x for o in args.ingest_option for x in ("--option", o)], *extra]
    rc, out, err = run_cmd(cmd)
    found = re.search(r"Found (\d+) files", err)
    processed = re.search(r'"files_processed":\s*(\d+)', out)
    return (rc, target, int(found.group(1)) if found else None, int(processed.group(1)) if processed else None,
            ingest_detail(rc, err)[:200])


def check_source_equivalence(groups: dict, ref: str | None, src: dict, regridded: bool = False) -> None:
    """The reference variable's finite count and sum over every group equal the decoded source."""
    if regridded:
        skip("source-equivalence check", "--regridded: the store is on another grid than the source, so finite "
             "count and sum cannot match; compare against an independent regrid instead", counted=False)
        return
    if not ref:
        skip("source-equivalence check", "no reference variable found in the store or source; pass --ref-var",
             counted=True)
        return
    cube_sum = sum(v.get("sum", 0.0) for v in groups.values())
    cube_fin = sum(v.get("finite", 0) for v in groups.values())
    same = cube_fin == src["finite"] and close(cube_sum, src["sum"])
    check(f"{ref}: finite count and sum equal the decoded source", same,
          f"cube finite={cube_fin} sum={cube_sum:.6g} | source finite={src['finite']} sum={src['sum']:.6g} "
          f"over {src['files']} files")


def check_groups(args: argparse.Namespace, groups: dict, ref: str | None, src: dict, native: Path) -> None:
    """Group names, ordering coordinates, variable counts, source equivalence, and store size of the first run."""
    if args.group_regex:
        check("group names match the identity regex", all(re.search(args.group_regex, g) for g in groups),
              list(groups)[:6])
    check("1-D monotonic ordering coordinate in every group", all(v["mono"] for v in groups.values()),
          {g: v["mono"] for g, v in groups.items()})
    nvars = {g: v["nvars"] for g, v in groups.items()}
    if args.min_variables:
        check(f"at least {args.min_variables} variables per group",
              all(c >= args.min_variables for c in nvars.values()), nvars)
    else:
        info("variables per group", nvars)
    info("groups", {g: v["sizes"] for g, v in groups.items()})
    coord_warnings = {g: v["coord_warnings"] for g, v in groups.items() if v.get("coord_warnings")}
    if coord_warnings:
        info("coordinate conversion warnings", coord_warnings)
    check_source_equivalence(groups, ref, src, args.regridded)
    size = sum(p.stat().st_size for p in native.rglob("*") if p.is_file())
    info("store bytes / source bytes", f"{size} / {src['bytes']} = {size / max(1, src['bytes']):.2f}x")


def check_native_store(args: argparse.Namespace, input_dir: Path, work: Path, native: Path) -> tuple[str | None, dict]:
    """Decode the source figures and inspect the first store; returns the reference variable and the groups."""
    if args.regridded:
        size = sum(p.stat().st_size for p in input_dir.rglob("*") if p.is_file())
        src = {"var": args.ref_var, "files": 0, "sum": 0.0, "finite": 0, "bytes": size}
    else:
        extract_tmp = Path(tempfile.mkdtemp(dir=work, prefix="extract_"))
        try:
            files = source_files(input_dir, extract_tmp)
            src = source_figures(files, args.ref_var)
        finally:
            shutil.rmtree(extract_tmp, ignore_errors=True)
    ref = src["var"]
    n = inspect_store(native, ref)
    groups = {k: v for k, v in n.items() if "error" not in v}
    check("at least one group written", bool(groups), [k for k in n][:6])
    if groups:
        check_groups(args, groups, ref, src, native)
    return ref, groups


def same_values(a: dict, b: dict) -> bool:
    """Two group summaries hold the same finite count and, within tolerance, the same sum."""
    return a.get("finite") == b.get("finite") and close(b.get("sum", 0), a.get("sum", 0))


def check_split_batch(run, groups: dict, ref: str | None) -> None:
    """A pipeline_batch_size=1 ingestion gives the same groups, sizes, values, and attributes as the first run."""
    rc2, split, _, _, last2 = run("split", "--option", "pipeline_batch_size=1")
    check("split-batch ingestion (pipeline_batch_size=1) succeeds", rc2 == 0, last2)
    if rc2 != 0 or not groups:
        return
    s = {k: v for k, v in inspect_store(split, ref).items() if "error" not in v}
    same_groups = set(groups) == set(s)
    check("split-batch: same groups", same_groups, sorted(set(groups) ^ set(s))[:6])
    if not same_groups:
        return
    check("split-batch: same sizes", all(groups[g]["sizes"] == s[g]["sizes"] for g in groups), "")
    if ref:
        check("split-batch: same values", all(same_values(groups[g], s[g]) for g in groups), "")
    check("split-batch: same group attributes", all(groups[g]["attrs"] == s[g]["attrs"] for g in groups),
          {g: "differs" for g in groups if groups[g]["attrs"] != s[g]["attrs"]})


def main() -> int:
    """Run every check in order and print the summary; exit 0 only when all of them passed."""
    args = parse_args()
    proj = args.project.expanduser().resolve()
    input_dir = args.input_dir.expanduser().resolve()
    scratch = (args.scratch or proj / ".check_done").expanduser().resolve()
    pyproject = proj / "pyproject.toml"
    if not pyproject.exists():
        check("plugin project", False, f"no pyproject.toml in {proj}")
        return finish(json_out=args.json)
    check_contract(proj)
    test_text = check_metadata(args, proj, pyproject)
    check_tests_and_lint(args, proj, input_dir, test_text)
    version = firecube_version()
    if version is None or not plugin_registered(args.plugin_id):
        return finish(json_out=args.json)

    # the user-named base directory; never removed by this script
    scratch.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(dir=scratch, prefix="check_done_"))
    products = products_in(input_dir)
    info("products in input", f"{len(products)}")
    run = functools.partial(ingest, args, input_dir, work)

    rc, native, found, processed, last = run("native")
    check("first ingestion succeeds", rc == 0, last)
    check("first ingestion processed at least one item", (processed or 0) >= 1,
          f"found={found} processed={processed} products={len(products)}")
    if processed is not None and processed != len(products):
        info("files processed differ from products in the input",
             f"found={found} processed={processed} products={len(products)}: a plugin that bundles files into "
             "items (a pass, a day) reports items; anything else dropped must be explained in the plugin's log")
    if rc != 0:
        return finish(work, args.keep, args.json)

    ref, groups = check_native_store(args, input_dir, work, native)
    if args.quick:
        quick_checks(args, input_dir, work, ref, version)
    else:
        check_split_batch(run, groups, ref)
        if not args.skip_lifecycle and groups:
            lifecycle(run, native, input_dir, work, args.workers, version, args.first_part_glob)
    return finish(work, args.keep, args.json)


def quick_input(input_dir: Path, work: Path, pattern: str | None) -> tuple[Path, list[str]]:
    """A directory of symlinks to the --quick products: those matching the pattern, else the first by name."""
    entries = sorted(p for p in input_dir.iterdir() if not p.name.startswith(".") and p.suffix.lower() not in IGNORED)
    chosen = [p for p in entries if fnmatch.fnmatch(p.name, pattern)] if pattern else entries[:1]
    qdir = work / "input_quick"
    qdir.mkdir()
    for p in chosen:
        (qdir / p.name).symlink_to(p)
    return qdir, [p.name for p in chosen]


def quick_checks(args: argparse.Namespace, input_dir: Path, work: Path, ref: str | None, version: str) -> None:
    """Split-batch and lifecycle checks on a one-product subset with its own reference store (--quick)."""
    qdir, names = quick_input(input_dir, work, args.quick_glob)
    info("quick", f"split-batch and lifecycle on {len(names)} product(s): {', '.join(names)}")
    if not names:
        check("quick: a product matches --quick-glob", False, args.quick_glob or "empty input")
        return
    run = functools.partial(ingest, args, qdir, work)
    rc, native, _, _, last = run("quick-native")
    check("quick: reference ingestion of the subset succeeds", rc == 0, last)
    if rc != 0:
        return
    groups = {k: v for k, v in inspect_store(native, ref).items() if "error" not in v}
    check_split_batch(run, groups, ref)
    if not args.skip_lifecycle and groups:
        lifecycle(run, native, qdir, work, args.workers, version, args.first_part_glob)


def same_store(a: Path, b: Path) -> tuple[bool, str]:
    """`firecube zarr compare` on two local stores: (exit code 0, last output line)."""
    rc, out, err = run_cmd(["firecube", "zarr", "compare", f"file://{a}", f"file://{b}", "--storage-type", "local",
                       "--storage-driver", "fsspec"])
    lines = (out + err).strip().splitlines()
    return rc == 0, (lines[-1] if lines else f"exit {rc}")[:160]


def first_part(entries: list[Path], glob_pattern: str | None) -> list[Path]:
    """Products for the first extension run, split on a whole time unit (a date), never inside one."""
    if glob_pattern:
        return [p for p in entries if fnmatch.fnmatch(p.name, glob_pattern)]
    dates = {p: m.group(1) for p in entries if (m := re.search(r"(?<!\d)((?:19|20)\d{6})(?:T\d{4,6})?", p.name))}
    ordered = sorted(set(dates.values()))
    if len(ordered) < 2 or len(dates) != len(entries):
        return []
    keep = set(ordered[: len(ordered) // 2])
    return [p for p in entries if dates[p] in keep]


def lifecycle_workers(ingest, native: Path, workers: int, is_015: bool) -> None:
    """A pipeline_workers>1 run succeeds and, on core main, equals the one-worker store."""
    rc, par, _, _, last = ingest("workers", "--option", f"pipeline_workers={workers}")
    check(f"pipeline_workers={workers} ingestion succeeds", rc == 0, last)
    if rc != 0:
        return
    name = f"pipeline_workers={workers} store equals the one-worker store (zarr compare)"
    if is_015:
        skip(name, "0.1.5: keep pipeline_workers=1 for order-dependent append plugins; equality comparison skipped "
                   "(plugin-traps.md)", counted=False)
    else:
        ok, detail = same_store(native, par)
        check(name, ok, detail)


def lifecycle_rerun(ingest, native: Path, scratch: Path, is_015: bool) -> None:
    """A rerun without a flag is refused; a rerun with resume_existing is refused on 0.1.5 and a no-op on core main."""
    rerun = scratch / "rerun.zarr"
    shutil.copytree(native, rerun)
    rc, _, _, _, last = ingest("rerun", target=rerun)
    check("rerun without a flag is refused (ResumeConflictError)",
          rc != 0 and re.search(r"existing entries|resume_existing|ResumeConflict", last, re.I), last)
    rc, _, _, _, last = ingest("rerun", "--option", "resume_existing=true", target=rerun)
    if is_015:
        refused = rc != 0 and bool(re.search(r"Refusing overlapping resume append", last, re.I))
        check("rerun with resume_existing=true over the same window (expected refusal on 0.1.5)", refused, last)
        return
    check("rerun with resume_existing=true succeeds", rc == 0, last)
    if rc == 0:
        ok, detail = same_store(native, rerun)
        check("rerun with resume_existing=true leaves the store equal", ok, detail)


def lifecycle_extension(ingest, native: Path, input_dir: Path, scratch: Path, glob_pattern: str | None) -> None:
    """The first part of the input, then all of it with resume_existing, equals the one-shot store."""
    entries = sorted(p for p in input_dir.iterdir() if not p.name.startswith(".") and p.suffix.lower() not in IGNORED)
    head = first_part(entries, glob_pattern)
    if not head or len(head) >= len(entries):
        info("extension", "skipped: no whole-time-unit split found; pass --first-part-glob")
        return
    part = scratch / "input_first_part"
    part.mkdir()
    for p in head:
        (part / p.name).symlink_to(p)
    ext = scratch / "extend.zarr"
    rc, _, _, _, last = ingest("extend", source=part, target=ext)
    check("extension: first half of the input ingests", rc == 0, last)
    if rc != 0:
        return
    rc, _, _, _, last = ingest("extend", "--option", "resume_existing=true", target=ext)
    check("extension: full input with resume_existing=true succeeds", rc == 0, last)
    if rc == 0:
        ok, detail = same_store(native, ext)
        check("extension store equals the one-shot store", ok, detail)


def lifecycle_force(ingest, native: Path, scratch: Path) -> None:
    """A force_reingest run over a copy of the store succeeds and equals the one-shot store."""
    forced = scratch / "force.zarr"
    shutil.copytree(native, forced)
    rc, _, _, _, last = ingest("force", "--option", "force_reingest=true", target=forced)
    check("force_reingest=true succeeds", rc == 0, last)
    if rc == 0:
        ok, detail = same_store(native, forced)
        check("force_reingest store equals the one-shot store", ok, detail)


def lifecycle(ingest, native: Path, input_dir: Path, scratch: Path, workers: int, version: str = "",
              glob_pattern: str | None = None) -> None:
    """Parallel run, reruns, extension and force against the one-shot store (core's resume contract).
    firecube 0.1.5 has two documented limits (plugin-traps.md) this function gates on: order-dependent append
    plugins should stay at pipeline_workers=1, and resume_existing=true over a fully overlapping window is
    refused rather than a silent no-change; both are treated as the expected 0.1.5 outcome, not a plugin defect."""
    is_015 = version.startswith("0.1.5")
    lifecycle_workers(ingest, native, workers, is_015)
    lifecycle_rerun(ingest, native, scratch, is_015)
    lifecycle_extension(ingest, native, input_dir, scratch, glob_pattern)
    lifecycle_force(ingest, native, scratch)


def write_json(path: Path, passed: int) -> None:
    """Every result and figure, for tools that read the outcome instead of the printed lines."""
    doc = {"passed": passed, "total": len(results), "done": passed == len(results),
           "results": [{"check": n, "passed": ok, "detail": d} for n, ok, d in results],
           "info": [{"name": n, "detail": d} for n, d in infos]}
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")


def finish(scratch: Path | None = None, keep: bool = False, json_out: Path | None = None) -> int:
    """Print the summary, write --json, remove the run's scratch subdirectory unless kept, and pick the exit code."""
    passed = sum(1 for _, ok, _ in results if ok)
    hint = "" if passed == len(results) else " -- not done: fix the FAIL lines, then rerun"
    print(f"DONE {passed}/{len(results)} checks passed{hint}")
    print("paste the lines above into the plan's Log with the command that produced them")
    if json_out:
        write_json(json_out, passed)
    if scratch and not keep:
        shutil.rmtree(scratch, ignore_errors=True)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
