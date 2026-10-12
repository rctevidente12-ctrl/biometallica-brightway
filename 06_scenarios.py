"""Step 6 - scenario analysis per kg dore (headline + selected EF 3.1 methods).

  S0  base case (v1.1, HK grid)
  S1  electricity supply swaps (config.ELECTRICITY_SCENARIOS)
  S2  design scenarios through the database parameters (same levers as the
      model workbook): continuous sterilisation with heat recovery,
      low-agitation reactor, acid/formic reuse, higher cyanide productivity,
      and a combined 'optimistic' case
  S3  purchased-cyanide benchmark: U7 takes fossil HCN (Andrussow/BMA market)
      instead of the bio/photo-cyanide units U5 + U6

Electricity and cyanide swaps are done on a temporary copy of the foreground
(<FG_DB>_scenario), so the imported database is never modified.
Outputs: scenarios.csv, scenarios_headline.png
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import bw2calc as bc
import bw2data as bd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from bw2data import parameters
from bw2data.parameters import DatabaseParameter

import config as C
from utils import open_project, get_fu, get_ei, headline_method, pick_methods, method_unit, short, save_table

open_project()
head = headline_method()
methods = [head] + [pick_methods(k)[0] for k in (
    ["EF v3.1", "energy resources: non-renewable"],
    ["EF v3.1", "water use"],
    ["EF v3.1", "acidification"],
    ["EF v3.1", "ecotoxicity: freshwater"],
) if pick_methods(k)]

SCN_DB = f"{C.FG_DB}_scenario"
rows = []


def score_all(fu, scenario, note=""):
    for name in (C.FG_DB, SCN_DB):  # make sure edited databases are re-processed
        if name in bd.databases:
            bd.Database(name).process()
    lca = bc.LCA({fu: 1}, methods[0])
    lca.lci()
    for m in methods:
        lca.switch_method(m)
        lca.lcia()
        rows.append(dict(scenario=scenario, method=short(m), unit=method_unit(m),
                         score=lca.score, note=note))
    print(f"  {scenario:45s} {rows[-len(methods)]['score']:10.2f} {method_unit(methods[0])}")


def fresh_copy():
    if SCN_DB in bd.databases:
        del bd.databases[SCN_DB]
    bd.Database(C.FG_DB).copy(SCN_DB)
    return bd.Database(SCN_DB)


# ---------------------------------------------------------------- S0 + S1
base_label, base_spec = next(iter(C.ELECTRICITY_SCENARIOS.items()))
base_elec = get_ei(*base_spec)
for label, spec in C.ELECTRICITY_SCENARIOS.items():
    if label == base_label:
        score_all(get_fu(), f"S0 base ({label})")
        continue
    try:
        new = get_ei(*spec)
    except ValueError as err:
        print("  ! skipped", label, "-", err)
        continue
    db = fresh_copy()
    for act in db:
        for exc in act.technosphere():
            if exc.input.key == base_elec.key:
                exc["input"] = new.key
                exc.save()
    score_all(get_fu(SCN_DB), f"S1 electricity: {label}", " | ".join(spec))


# ---------------------------------------------------------------- S2
DESIGN = {
    "S2a continuous sterilisation + heat recovery": {"m_u5_elec": 0.5},
    "S2b low-agitation bioreactor (100 W/m3)": {"m_u5_elec": 0.895},  # model tornado: -80 kWh of 761.6
    "S2c acid + formic liquor reuse": {"m_u2_acid": 0.25, "m_u4_formic": 0.4},
    "S2d 2x cyanide productivity": {"m_u5_cn_yield": 2.0},
    "S2e optimistic (a + c + d, efficient kiln)": {"m_u5_elec": 0.5, "m_u2_acid": 0.25,
                                                  "m_u4_formic": 0.4, "m_u5_cn_yield": 2.0,
                                                  "m_u1_elec": 0.8},
}


def set_params(values: dict):
    for p in DatabaseParameter.select().where(DatabaseParameter.database == C.FG_DB):
        p.amount = values.get(p.name, 1.0)
        p.save()
    parameters.recalculate()


try:
    for label, values in DESIGN.items():
        set_params(values)
        score_all(get_fu(), label, ", ".join(f"{k}={v}" for k, v in values.items()))
finally:
    set_params({})  # always restore the base case
    print("  database parameters restored to 1.0")


# ---------------------------------------------------------------- S3
try:
    hcn = get_ei(*C.HCN_DATASET)
    db = fresh_copy()
    u7 = [a for a in db if a["name"].startswith("U7 ")][0]
    cn_kg = 0.0
    for exc in list(u7.technosphere()):
        if exc.input["database"] == SCN_DB and exc.input["name"].startswith(("U5 ", "U6 ")):
            cn_kg += exc["amount"]
            exc.delete()
    u7.new_exchange(input=hcn.key, amount=cn_kg * C.HCN_PER_CN, type="technosphere",
                    comment="Benchmark: purchased HCN replaces bio/photo-cyanide (CN basis x 27.025/26.017).").save()
    score_all(get_fu(SCN_DB), "S3 purchased fossil HCN (no U5/U6)", f"{cn_kg:.4g} kg CN -> HCN market RoW")
except ValueError as err:
    print("  ! S3 skipped -", err)

if SCN_DB in bd.databases:
    del bd.databases[SCN_DB]

df = pd.DataFrame(rows)
base = df[df.scenario.str.startswith("S0")].set_index("method")["score"]
df["change vs base"] = df["score"] / df["method"].map(base) - 1
save_table(df, "scenarios")

h = df[df.method == short(head)].set_index("scenario")["score"]
ax = h.iloc[::-1].plot(kind="barh", figsize=(10, 5.5), color="#1C5739")
ax.axvline(h.iloc[0], color="grey", ls="--", lw=1)
ax.set_xlabel(f"{method_unit(head)} per kg doré")
ax.set_ylabel("")
ax.set_title(f"Scenarios - {short(head)}")
plt.tight_layout()
plt.savefig(C.RESULTS / "scenarios_headline.png", dpi=200)
print("  -> results/scenarios_headline.png")
