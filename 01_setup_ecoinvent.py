"""Step 1 - create the Brightway project and import ecoinvent 3.12 cut-off.

Credentials are read from a .env file next to this script (copy
.env.example to .env and fill it in) or asked for interactively.
The import downloads ecoinvent through ecoinvent_interface and also installs
the matching biosphere database and LCIA methods (EF v3.1, IPCC 2021, CED...).
It takes 10-30 minutes the first time and is skipped on later runs.
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import getpass
import os

import bw2data as bd
import bw2io as bi

import config as C

if C.BACKGROUND != "ecoinvent":
    raise SystemExit('config.BACKGROUND is "bafu" - run 01b_setup_bafu.py instead '
                     '(or set BACKGROUND = "ecoinvent" in config.py once you have the licence).')

try:
    import ecoinvent_interface  # noqa: F401  (bw2io needs it for import_ecoinvent_release)
except ImportError:
    raise SystemExit(
        "ecoinvent_interface is not installed in this Python environment:\n  " + sys.executable +
        "\nInstall it from the Anaconda Prompt / terminal with:\n  \"" + sys.executable +
        "\" -m pip install ecoinvent_interface python-dotenv edges"
    )

try:
    from dotenv import load_dotenv
    load_dotenv(C.ROOT / ".env")
except ImportError:
    pass

bd.projects.set_current(C.PROJECT)
print("Project:", bd.projects.current)

if C.EI_DB in bd.databases and C.BIO_DB in bd.databases:
    print(f"{C.EI_DB} already present ({len(bd.Database(C.EI_DB)):,} activities) - nothing to do.")
else:
    user = os.environ.get("ECOINVENT_USERNAME") or input("ecoinvent username: ")
    pwd = os.environ.get("ECOINVENT_PASSWORD") or getpass.getpass("ecoinvent password: ")
    bi.import_ecoinvent_release(
        version=C.EI_VERSION,
        system_model=C.EI_SYSTEM_MODEL,
        username=user,
        password=pwd,
    )
    if C.EI_DB not in bd.databases:
        raise SystemExit(f"Import did not create {C.EI_DB}. Check the messages above "
                         "(login, licence or download errors).")

print("Databases:", sorted(bd.databases))
print("LCIA methods:", len(bd.methods))

# Quick check that the datasets the foreground links to exist
checks = [
    ("market for electricity, medium voltage", "electricity, medium voltage", "HK"),
    ("market for sulfuric acid", "sulfuric acid", "RoW"),
    ("market for water, deionised", "water, deionised", "RoW"),
] + list(C.ELECTRICITY_SCENARIOS.values()) + [C.HCN_DATASET]
db = bd.Database(C.EI_DB)
index = {(a["name"], a.get("reference product"), a.get("location")) for a in db}
for c in checks:
    print(("  ok      " if c in index else "  MISSING ") + " | ".join(c))
