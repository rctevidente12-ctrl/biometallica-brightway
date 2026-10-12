"""Shared settings for the BioMetallica Brightway / edges workflow.

Edit the values here (not in the numbered scripts) if your project or
database names differ.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

# --- Background choice --------------------------------------------------
# "bafu"      : free BAFU:2025 database from the Barcelona course (stand-in,
#               provisional numbers - NOT for publication)
# "ecoinvent" : ecoinvent 3.12 cut-off (needs an ecoinvent licence that
#               allows ecoSpold2 / API download)
BACKGROUND = "bafu"

if BACKGROUND == "ecoinvent":
    PROJECT = "biometallica"
    EI_DB = "ecoinvent-3.12-cutoff"
    BIO_DB = "ecoinvent-3.12-biosphere"
    FG_XLSX = DATA / "BioMetallica_LCI_brightway_v1.1.xlsx"
    FG_DB = "biometallica_v1_1"
else:
    PROJECT = "biometallica-bafu"
    EI_DB = "bafu"                                # background database name
    BIO_DB = "ecoinvent-3.10-biosphere"
    FG_XLSX = DATA / "BioMetallica_LCI_brightway_v1.1_BAFU.xlsx"
    FG_DB = "biometallica_v1_1_bafu"
    # course workbook (Barcelona repository, data/lci-bafu.xlsx)
    BAFU_XLSX = Path.home() / "Desktop" / "barcelona-regionalized-lcia-main" / "data" / "lci-bafu.xlsx"
    BAFU_REMOTE_PROJECT = "ecoinvent-3.10-biosphere"   # prepared project with biosphere + LCIA methods

EI_VERSION = "3.12"
EI_SYSTEM_MODEL = "cutoff"
FORMULA_GROUP = f"{FG_DB}_formulas"

# Functional unit: 1 kg metal dore leaving U12
FU_NAME = "U12 electrowinning and doré smelting"
FU_LOCATION = "HK"

# --- LCIA method selection (matched by keywords, see utils.pick_methods) ---
# Every method whose tuple contains all keywords (case-insensitive) is run.
# The first match of HEADLINE is used for Monte Carlo and the Sankey diagram.
HEADLINE = ["EF v3.1", "climate change", "global warming potential (GWP100)"]
METHOD_FAMILIES = {
    "EF v3.1": ["EF v3.1"],                                  # every EF 3.1 indicator
    "IPCC 2021": ["IPCC 2021", "climate change", "GWP100"],
    "CED": ["cumulative energy demand"],                     # all CED sub-indicators
}

# --- Monte Carlo ------------------------------------------------------------
MC_ITERATIONS = 1000
MC_SEED = 2026

# --- Regionalised LCIA with edges ------------------------------------------
# Matched against edges.get_available_methods(); tuples are built from the
# JSON file names shipped with edges (e.g. 'AWARE 2.0_Country_all_yearly').
EDGES_METHODS = [
    ("AWARE 2.0", "Country", "all", "yearly"),
    ("IBIF", "biodiversity", "all pressures", "overall"),
    ("IBIF", "biodiversity", "CO2", "overall"),
    ("IBIF", "biodiversity", "LU", "overall"),
    ("IBIF", "biodiversity", "NOx", "overall"),
    ("GeoPolRisk", "paired", "2024"),
]
EDGES_IMPACTWORLD_DAMAGE = True                # also run all ImpactWorld+ 2.1 damage indicators
# Hong Kong has no country entry in AWARE 2.0 or IBIF, so edges falls back to
# a weighted global average for HK consumers. As a sensitivity, the foreground
# is re-run with location CN-GD (Guangdong; ~70-80 % of HK's fresh water is
# imported from the Dongjiang river in Guangdong).
PROXY_LOCATION = "CN-GD"

# --- Electricity scenarios (first entry = base case of the inventory) ------
if BACKGROUND == "ecoinvent":
    ELECTRICITY_SCENARIOS = {
        "HK grid (base)": ("market for electricity, medium voltage", "electricity, medium voltage", "HK"),
        "China Southern Grid": ("market for electricity, medium voltage", "electricity, medium voltage", "CN-S-Grid"),
        "PV 570 kWp, Guangdong": ("electricity production, photovoltaic, 570kWp open ground installation, multi-Si",
                                   "electricity, low voltage", "CN-GD"),
        "Wind onshore >3 MW, Guangdong": ("electricity production, wind, >3MW turbine, onshore",
                                          "electricity, high voltage", "CN-GD"),
    }
    # Purchased-cyanide benchmark: fossil HCN replaces bio/photo-cyanide (CN basis)
    HCN_DATASET = ("market for hydrogen cyanide", "hydrogen cyanide", "RoW")
else:  # BAFU names: reference product = activity name
    _e = lambda n, l: (n, n, l)
    ELECTRICITY_SCENARIOS = {
        "China grid (base, HK proxy)": _e("Electricity, medium voltage, at grid", "CN"),
        "Asia & Pacific grid (RAS)": _e("Electricity, medium voltage, at grid", "RAS"),
        "PV production mix, China": _e("Electricity, production mix photovoltaic, at plant", "CN"),
        "Wind onshore 4.5 MW, Europe": _e("Electricity, at 100MW wind farm, onshore, 4.5 MW turbines", "RER"),
    }
    HCN_DATASET = _e("Hydrogen cyanide, at plant", "RER")
    # GeoPolRisk matches ecoinvent 3 supplier names, so it is not meaningful on BAFU
    EDGES_METHODS = [m for m in EDGES_METHODS if m[0] != "GeoPolRisk"]

HCN_PER_CN = 27.025 / 26.017      # kg HCN per kg CN
