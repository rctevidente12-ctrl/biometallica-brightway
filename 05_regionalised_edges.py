"""Step 5 - regionalised LCIA with edges (course Day 2: D2-03, D2-05, D2-07).

For each method in config.EDGES_METHODS (plus every ImpactWorld+ 2.1 damage
indicator if enabled) this runs the edges pipeline
    lci -> apply_strategies (exchange mapping + geographic fallbacks)
        -> evaluate_cfs -> lcia
on 1 kg dore, then writes the characterised-exchange table, split by
consumer country (split_aggregate_consumers=True) and by BioMetallica unit.

Hong Kong is not a country entry in AWARE 2.0 or IBIF, so HK consumers fall
back to a weighted global CF. As a sensitivity the foreground is copied to
<FG_DB>_<PROXY_LOCATION> with every foreground location set to CN-GD and
re-assessed.

Outputs: edges_scores.csv, edges_by_country.csv, edges_by_unit.csv,
         edges_cf_<method>.csv, edges_statistics.txt, sankey_<method>.html
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import contextlib
import io

import bw2data as bd
import edges
import pandas as pd
from edges import EdgeLCIA

import config as C
from utils import open_project, get_fu, save_table

open_project()

available = set(edges.get_available_methods())
methods = [m for m in C.EDGES_METHODS if m in available]
for m in C.EDGES_METHODS:
    if m not in available:
        print("  ! not in this edges version:", m)
if C.EDGES_IMPACTWORLD_DAMAGE:
    methods += sorted(m for m in available if m[0].startswith("ImpactWorld+") and m[-1] == "damage")
print(f"edges {edges.__version__} | methods: {len(methods)}")


def proxy_copy() -> str:
    """Copy the foreground with every location set to PROXY_LOCATION."""
    name = f"{C.FG_DB}_{C.PROXY_LOCATION}"
    if name in bd.databases:
        del bd.databases[name]
    bd.Database(C.FG_DB).copy(name)
    for act in bd.Database(name):
        act["location"] = C.PROXY_LOCATION
        act.save()
        for exc in act.production():
            exc["location"] = C.PROXY_LOCATION
            exc.save()
    return name


cases = {"HK (base)": get_fu(C.FG_DB)}
proxy_db = proxy_copy()
fu_proxy = [a for a in bd.Database(proxy_db) if a["name"] == C.FU_NAME][0]
cases[f"{C.PROXY_LOCATION} proxy"] = fu_proxy
fg_names = {a["name"] for a in bd.Database(C.FG_DB)}

scores, by_country, by_unit = [], [], []
stats_log = io.StringIO()

for method in methods:
    label = " | ".join(method)
    for case, fu in cases.items():
        print(f"  {label}  [{case}]")
        lca = EdgeLCIA(demand={fu: 1}, method=method)
        lca.lci()
        lca.apply_strategies()
        lca.evaluate_cfs()
        lca.lcia()
        meta = lca.method_metadata if hasattr(lca, "method_metadata") else {}
        unit = (meta or {}).get("unit", "")
        scores.append(dict(method=label, case=case, unit=unit, score=float(lca.score)))

        if case == "HK (base)":
            with contextlib.redirect_stdout(stats_log):
                print(f"\n===== {label}")
                lca.statistics()

        cf = lca.generate_cf_table(split_aggregate_consumers=True)
        if cf.empty:
            continue
        cf.insert(0, "case", case)
        cf.insert(0, "method", label)
        if case == "HK (base)":
            stem = "edges_cf_" + "_".join(method).replace(" ", "-").replace("+", "plus").replace("/", "-")
            save_table(cf, stem)
        cf["consumer location"] = cf["consumer location"].fillna("unknown")
        by_country.append(cf.groupby(["method", "case", "consumer location"], as_index=False)["impact"].sum())
        cf["unit id"] = cf["consumer name"].where(cf["consumer name"].isin(fg_names), "background")
        cf["unit id"] = cf["unit id"].str.split(" ").str[0].replace({"background": "background (supply chain)"})
        by_unit.append(cf.groupby(["method", "case", "unit id"], as_index=False)["impact"].sum())

save_table(pd.DataFrame(scores), "edges_scores")
if by_country:
    bc_df = pd.concat(by_country, ignore_index=True)
    bc_df["share"] = bc_df["impact"] / bc_df.groupby(["method", "case"])["impact"].transform("sum")
    save_table(bc_df.sort_values(["method", "case", "impact"], ascending=[True, True, False]), "edges_by_country")
if by_unit:
    save_table(pd.concat(by_unit, ignore_index=True), "edges_by_unit")
(C.RESULTS / "edges_statistics.txt").write_text(stats_log.getvalue(), encoding="utf-8")
print("  -> results/edges_statistics.txt")

# Supply-chain Sankey for water scarcity and biodiversity (interactive HTML)
from edges.supply_chain import SupplyChain
for method in [m for m in methods if m[0] in ("AWARE 2.0", "IBIF")][:2]:
    try:
        sc = SupplyChain(activity=cases["HK (base)"], method=method, amount=1,
                         level=4, cutoff=0.01, cutoff_basis="total")
        sc.bootstrap()
        df, total, _ = sc.calculate()
        path = C.RESULTS / ("sankey_" + "_".join(method).replace(" ", "-") + ".html")
        sc.save_html(df, str(path))
        print(f"  -> {path.name} (total {total:.4g})")
    except Exception as err:  # Sankey is a nice-to-have; never block the run
        print(f"  ! Sankey failed for {method}: {err}")
