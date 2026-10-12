"""Step 1 (stand-in) - project with the free BAFU:2025 background.

Same steps as course notebook D1-04:
  1. install the prepared Brightway project 'ecoinvent-3.10-biosphere'
     (biosphere flows + LCIA methods incl. EF v3.1) under the name
     config.PROJECT;
  2. import data/lci-bafu.xlsx from the Barcelona course repository as
     database 'bafu'.
Takes ~5-15 minutes the first time; skipped on later runs.
Results with this background are PROVISIONAL (not for publication).
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import bw2data as bd
import bw2io as bi

import config as C

if C.BACKGROUND != "bafu":
    raise SystemExit('config.BACKGROUND is not "bafu" - use 01_setup_ecoinvent.py.')

if C.PROJECT not in bd.projects:
    print(f"Installing prepared project {C.BAFU_REMOTE_PROJECT!r} as {C.PROJECT!r} (download) ...")
    bi.remote.install_project(C.BAFU_REMOTE_PROJECT, C.PROJECT)
bd.projects.set_current(C.PROJECT)
print("Project:", bd.projects.current)
bi.create_core_migrations()

if C.EI_DB in bd.databases:
    print(f"{C.EI_DB} already present ({len(bd.Database(C.EI_DB)):,} activities) - nothing to import.")
else:
    if not C.BAFU_XLSX.exists():
        raise SystemExit(f"BAFU workbook not found at {C.BAFU_XLSX} - set BAFU_XLSX in config.py.")
    print("Reading", C.BAFU_XLSX, "(a few minutes) ...")
    imp = bi.ExcelImporter(str(C.BAFU_XLSX))
    imp.apply_strategies()
    imp.match_database(fields=("name", "reference product", "location"))
    imp.match_database(C.BIO_DB, fields=("name", "unit", "categories"))
    imp.statistics()
    imp.write_database()

print("Databases:", sorted(bd.databases))
print("LCIA methods:", len(bd.methods))
print("EF v3.1 GWP100 available:",
      any("EF v3.1" in m and "global warming potential (GWP100)" in m for m in bd.methods))

# check the datasets used by the BioMetallica scenarios
db = bd.Database(C.EI_DB)
index = {(a["name"], a.get("reference product"), a.get("location")) for a in db}
for c in list(C.ELECTRICITY_SCENARIOS.values()) + [C.HCN_DATASET]:
    print(("  ok      " if c in index else "  MISSING ") + " | ".join(c))
