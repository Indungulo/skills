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
# dependencies = [
#   "numpy==2.5.2",
#   "xarray==2026.7.0",
#   "netCDF4==1.7.4",
# ]
# ///

"""Inspect one Earth Observation product file; print a short summary, write the full tables to a sidecar.

Usage:
  uv run inspect_product.py <file.nc|file.h5|archive.zip|product-dir> [--member NAME] [--var VARIABLE]
      [--out table.json]

Prints about twenty lines: dimensions, coordinate variables, global attributes, variable counts per group,
every time-like variable with its dimensionality and monotonicity, and the valid fraction of one reference
variable. The complete per-variable table (dims, shape, dtype, fill, scale, offset, units, long name) and
all attributes for every group go to the sidecar JSON, which the plan file can reference.

Not read-only: it writes the sidecar JSON next to the product by default (--out to change the path), and it
extracts an archive member to a temporary directory that it removes before exiting. It never modifies the
product file itself.

`uv run` installs the pinned dependencies declared at the top of this file. It also runs with any interpreter
that has xarray and a NetCDF/HDF5 engine (a Firecube plugin's `uv run python` qualifies).

Exit codes: 0 inspected and sidecar written, 1 no readable data file or missing libraries, 2 invalid arguments.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

DATA_SUFFIXES = (".nc", ".nc4", ".h5", ".hdf", ".hdf5", ".he5")
MAX_SUMMARY_ATTRS = 12


def resolve_dir(path: Path, member: str | None) -> Path:
    """The first data file under a product directory, or the first whose name contains `member`."""
    candidates = sorted(p for p in path.rglob("*") if p.suffix.lower() in DATA_SUFFIXES)
    if not candidates:
        sys.exit(f"no data file under {path}")
    if member:
        candidates = [p for p in candidates if member in p.name] or candidates
    if len(candidates) > 1:
        print(f"note: {len(candidates)} data files in the directory; inspecting {candidates[0].name} "
              "(use --member to pick another)")
    return candidates[0]


def resolve_zip(path: Path, member: str | None) -> tuple[Path, Path]:
    """Extract the first data member of an archive (or the first matching `member`) to a new temporary directory."""
    with zipfile.ZipFile(path) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(DATA_SUFFIXES)]
        if not names:
            sys.exit(f"no data member in {path}: {zf.namelist()[:8]}")
        if member:
            names = [n for n in names if member in n] or names
        if len(names) > 1:
            print(f"note: {len(names)} data members in the archive; inspecting {names[0]} "
                  "(use --member to pick another)")
        tmp = Path(tempfile.mkdtemp(prefix="inspect_"))
        return Path(zf.extract(names[0], tmp)), tmp


def resolve(path: Path, member: str | None) -> tuple[Path, Path | None]:
    """Return a readable data file for a file, an archive, or a product directory, and the temporary
    extraction directory to remove when done (None when nothing was extracted)."""
    if path.is_dir():
        return resolve_dir(path, member), None
    if zipfile.is_zipfile(path):
        return resolve_zip(path, member)
    return path, None


def group_paths(path: Path) -> list[str]:
    """Every group path in the file, root ("") first, walked with netCDF4 or h5netcdf's own h5py dependency,
    whichever is importable. Falls back to root only when neither library or the walk itself is available."""
    groups = [""]

    def walk(grp, prefix, children):
        for name, sub in children(grp):
            gp = f"{prefix}{name}"
            groups.append(gp)
            walk(sub, gp + "/", children)

    try:
        import netCDF4

        with netCDF4.Dataset(path) as root:
            walk(root, "", lambda g: g.groups.items())
        return groups
    except Exception:
        # netCDF4 missing or unable to read the file: fall back to h5py below
        pass
    try:
        import h5py

        with h5py.File(path, "r") as root:
            walk(root, "", lambda g: ((n, s) for n, s in g.items() if isinstance(s, h5py.Group)))
        return groups
    except Exception:
        # neither engine available; report root only
        return [""]


def short(value, width: int = 60) -> str:
    """One-line text of a value, cut to `width` characters with an ellipsis."""
    s = str(value).replace("\n", " ")
    return s if len(s) <= width else s[: width - 3] + "..."


def variable_row(ds, name) -> dict:
    """The sidecar table row for one variable: dims, shape, dtype, encoding attributes, and all attributes."""
    v = ds[name]
    a = v.attrs
    return {
        "name": name, "dims": list(v.dims), "shape": [int(s) for s in v.shape], "dtype": str(v.dtype),
        "fill": short(a.get("_FillValue", v.encoding.get("_FillValue", ""))),
        "scale_factor": short(a.get("scale_factor", "")), "add_offset": short(a.get("add_offset", "")),
        "units": short(a.get("units", "")), "long_name": short(a.get("long_name", ""), 80),
        "attrs": {k: short(val, 200) for k, val in a.items()},
    }


def variable_table(ds) -> list[dict]:
    """Rows for every variable of a dataset, coordinates included."""
    return [variable_row(ds, name) for name in ds.variables]


def read_groups(xr, data: Path) -> tuple[dict[str, list[dict]], dict[str, dict]]:
    """Variable tables and dims/coords/attributes for every group that opens; a bad group is noted and skipped."""
    group_tables: dict[str, list[dict]] = {}
    group_meta: dict[str, dict] = {}
    for g in group_paths(data):
        try:
            with xr.open_dataset(data, group=g or None, decode_times=False, mask_and_scale=False) as gds:
                group_tables[g] = variable_table(gds)
                group_meta[g] = {"dims": {k: int(s) for k, s in gds.sizes.items()}, "coords": list(gds.coords),
                                 "global_attrs": {k: short(v, 400) for k, v in gds.attrs.items()}}
        except Exception as exc:
            # one bad group must not stop the inspection
            print(f"note: could not open group {g or '/'!r} ({type(exc).__name__}: {short(exc, 80)})")
    return group_tables, group_meta


def build_sidecar(data: Path, primary: str, group_tables: dict[str, list[dict]], group_meta: dict[str, dict]) -> dict:
    """The sidecar document: the primary group's tables at the top level, every group under `groups`."""
    meta = group_meta.get(primary, {})
    return {"file": str(data), "size_bytes": os.path.getsize(data), "primary_group": primary or "/",
            "dims": meta.get("dims", {}), "coords": meta.get("coords", []),
            "global_attrs": meta.get("global_attrs", {}), "variables": group_tables.get(primary, []),
            "groups": {(g or "/"): t for g, t in group_tables.items()}}


def print_variable_counts(table: list[dict]) -> None:
    """Variable counts by dimensionality and dtype, and the shapes of the 2-D variables."""
    by_ndim: dict[int, int] = {}
    dtypes: dict[str, int] = {}
    for row in table:
        by_ndim[len(row["dims"])] = by_ndim.get(len(row["dims"]), 0) + 1
        dtypes[row["dtype"]] = dtypes.get(row["dtype"], 0) + 1
    print(f"variables (primary group): {len(table)} | by ndim {dict(sorted(by_ndim.items()))} | dtypes {dtypes}")
    twod = [r for r in table if len(r["dims"]) == 2]
    if twod:
        shapes = {tuple(r["shape"]) for r in twod}
        print(f"2-D variables: {len(twod)} on dims {sorted({tuple(r['dims']) for r in twod})} shapes {sorted(shapes)}")


def print_summary(data: Path, ds, sidecar: dict, group_tables: dict[str, list[dict]], primary: str) -> None:
    """File size, groups, dims, coordinates, global attributes, and variable counts of the primary group."""
    print(f"file: {data.name}  ({os.path.getsize(data) / 1e6:.2f} MB)")
    per_group = {(g or "/"): len(t) for g, t in group_tables.items()}
    print(f"groups: {len(group_tables)} | variables per group: {per_group}")
    if primary:
        print(f"primary group (most variables; use --member or open a specific group otherwise): {primary}")
    print(f"dims: {dict(sidecar['dims'])}")
    print("coords: " + (", ".join(f"{c}{tuple(ds[c].dims)} {ds[c].dtype}" for c in ds.coords) or "none declared"))
    attrs = list(ds.attrs.items())
    shown = "; ".join(f"{k}={short(v, 40)}" for k, v in attrs[:MAX_SUMMARY_ATTRS])
    print(f"global attrs ({len(attrs)}): " + shown + (" ..." if len(attrs) > MAX_SUMMARY_ATTRS else ""))
    print_variable_counts(sidecar["variables"])


def monotonic_suffix(np, vals, valid) -> str:
    """Strict monotonicity of the valid values: along the axis for 1-D, of the per-row means for 2-D and more."""
    if vals.ndim == 1:
        d = np.diff(vals[valid].astype("float64"))
        return f" | 1-D monotonic={bool(np.all(d > 0)) if d.size else 'n/a'}"
    masked = np.where(valid, vals.astype("float64"), np.nan)
    row_mean = np.nanmean(masked, axis=1)
    d = np.diff(row_mean[~np.isnan(row_mean)])
    spread = np.nanmax(np.nanmax(masked, axis=1) - np.nanmin(masked, axis=1))
    monotonic = bool(np.all(d > 0)) if d.size else "n/a"
    return f" | per-row mean monotonic={monotonic} | max spread within a row={spread:g}"


def time_like_line(np, name, v) -> str:
    """The summary line for one time-like variable; a non-numeric variable is reported without the ordering check."""
    line = f"time-like {name}{tuple(v.dims)} {v.dtype} units={short(v.attrs.get('units', ''), 40)}"
    if v.dtype.kind not in "iuf":
        return line + " | non-numeric: monotonicity not checked"
    vals = np.asarray(v.values)
    fill = v.attrs.get("_FillValue", v.encoding.get("_FillValue"))
    valid = np.ones(vals.shape, bool) if fill is None else vals != fill
    line += f" fill={short(fill, 20)}"
    if vals.ndim >= 1 and vals.size > 1:
        line += monotonic_suffix(np, vals, valid)
    return line


def print_time_like(np, ds) -> None:
    """Every variable named like time or with `since` units; one bad variable never aborts the sidecar write."""
    timeish = [n for n in ds.variables if "time" in n.lower() or "since" in str(ds[n].attrs.get("units", "")).lower()]
    for n in timeish:
        try:
            print(time_like_line(np, n, ds[n]))
        except Exception as exc:
            # report and move on; one variable must not abort the sidecar write
            print(f"time-like {n}: could not inspect ({type(exc).__name__}: {short(exc, 80)})")
    if not timeish:
        print("time-like variables: none found by name or units")


def pick_reference(table: list[dict], var: str | None) -> str | None:
    """The requested variable, else the first 2-D+ floating or scaled variable of the primary group."""
    if var:
        return var
    for row in table:
        if len(row["dims"]) >= 2 and (row["dtype"].startswith("float") or row["scale_factor"]):
            return row["name"]
    return None


def reference_line(np, ref, v) -> str:
    """The valid-fraction line for the reference variable: not fill and finite."""
    if v.dtype.kind not in "iuf":
        return f"reference {ref}{tuple(v.dims)} {v.dtype}: non-numeric, valid fraction not computed"
    vals = np.asarray(v.values)
    fill = v.attrs.get("_FillValue", v.encoding.get("_FillValue"))
    finite = np.isfinite(vals.astype("float64"))
    valid = finite if fill is None else (vals != fill) & finite
    return (f"reference {ref}{tuple(v.dims)} {v.dtype} fill={short(fill, 20)} "
            f"scale={short(v.attrs.get('scale_factor', ''), 12)} valid fraction={valid.mean():.3f}")


def print_reference(np, ds, ref: str | None, primary: str) -> None:
    """The reference variable's valid fraction, or why it could not be computed."""
    if ref and ref in ds:
        try:
            print(reference_line(np, ref, ds[ref]))
        except Exception as exc:
            # report and move on; must not abort the sidecar write
            print(f"reference {ref}: could not compute valid fraction ({type(exc).__name__}: {short(exc, 80)})")
    elif ref:
        print(f"reference {ref}: not found in the primary group ({primary or '/'})")


def inspect(np, xr, args, data: Path) -> int:
    """Read every group, print the summary of the primary group, and write the sidecar."""
    out = args.out or (args.path.expanduser().resolve().with_suffix("").parent / f"{args.path.name}.inspect.json")
    group_tables, group_meta = read_groups(xr, data)
    # the primary group drives the summary below: the first (root-first) group that has variables
    primary = next((g for g in group_tables if group_tables[g]), next(iter(group_tables), ""))
    sidecar = build_sidecar(data, primary, group_tables, group_meta)
    with xr.open_dataset(data, group=primary or None, decode_times=False, mask_and_scale=False) as ds:
        print_summary(data, ds, sidecar, group_tables, primary)
        print_time_like(np, ds)
        print_reference(np, ds, pick_reference(sidecar["variables"], args.var), primary)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sidecar, indent=1), encoding="utf-8")
    total_vars = sum(len(t) for t in group_tables.values())
    print(f"full tables ({total_vars} variables across {len(group_tables)} groups, all attributes): {out}")
    return 0


def main() -> int:
    """Parse the arguments, resolve the data file, inspect it, and remove any extraction directory."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path)
    ap.add_argument("--member", help="substring selecting the data file inside an archive or directory")
    ap.add_argument("--var", help="reference variable for the valid-fraction check "
                                  "(default: first floating or scaled 2-D+ variable)")
    ap.add_argument("--out", type=Path, help="sidecar JSON path (default: next to the product, <name>.inspect.json)")
    args = ap.parse_args()

    try:
        import numpy as np
        import xarray as xr
    except ImportError as exc:
        # environment guard: the interpreter lacks the inspection libraries
        sys.exit(f"needs xarray and numpy in this interpreter ({exc}); run with the plugin's `uv run python`")

    data, extract_tmp = resolve(args.path.expanduser().resolve(), args.member)
    try:
        return inspect(np, xr, args, data)
    finally:
        if extract_tmp is not None:
            shutil.rmtree(extract_tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
