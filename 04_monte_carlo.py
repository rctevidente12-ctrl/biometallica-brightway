"""Step 4 - Monte Carlo uncertainty (course D1-10 pattern).

Two runs, same seed:
  A  exchange uncertainty only: pedigree lognormals of the foreground plus
     the ecoinvent background distributions (use_distributions=True);
  B  A + the database parameters (m_u1_elec, m_u5_elec, m_u5_cn_yield, ...)
     sampled from their triangular ranges and pushed into the formula
     exchanges through a sequential bw_processing datapackage.
Several methods are scored from the same sampled inventory in each iteration.
Spearman rank correlations between the parameters and the headline score
give the contribution to variance of each design lever.

Outputs: mc_scores.csv, mc_summary.csv, mc_parameter_spearman.csv,
         mc_realised_parameters.csv, mc_histogram.png
Run A is reused from an earlier mc_scores.csv when the settings match.
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import bw2calc as bc
import bw2data as bd
import bw_processing as bwp
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from bw2data.parameters import DatabaseParameter
from bw2parameters import ParameterSet
from scipy.stats import spearmanr

import config as C
from utils import open_project, get_fu, headline_method, pick_methods, method_unit, short, save_table

open_project()
fu = get_fu()
head = headline_method()

# extra methods scored from the same inventory (first hit of each)
EXTRA = [
    ["EF v3.1", "energy resources: non-renewable"],
    ["EF v3.1", "water use"],
    ["EF v3.1", "ecotoxicity: freshwater"],
    ["EF v3.1", "material resources: metals/minerals"],
]
methods = [head] + [pick_methods(k)[0] for k in EXTRA if pick_methods(k)]
print("Methods:", *[short(m) for m in methods], sep="\n  ")

# ---------------------------------------------------- parameter samples ---
np.random.seed(C.MC_SEED)
param_defs = {p.name: {"amount": p.amount, **p.data}
              for p in DatabaseParameter.select().where(DatabaseParameter.database == C.FG_DB)}

formula_rows = []
for act in bd.Database(C.FG_DB):
    for exc in act.exchanges():
        if "formula" in exc:
            formula_rows.append(dict(col=f"exchange_{exc._document.id}", formula=exc["formula"],
                                     amount=float(exc["amount"]), type=exc["type"],
                                     input_id=exc.input.id, output_id=act.id,
                                     matrix="biosphere_matrix" if exc["type"] == "biosphere"
                                     else "technosphere_matrix",
                                     label=f"{act['name'].split(' ')[0]}: {exc.input['name']}"))
formula_rows = pd.DataFrame(formula_rows)
print(f"Database parameters: {len(param_defs)} | formula exchanges: {len(formula_rows)}")

sampler = ParameterSet({**param_defs,
                        **{r.col: {"amount": r.amount, "formula": r.formula}
                           for r in formula_rows.itertuples()}})
samples = sampler.evaluate_monte_carlo(iterations=C.MC_ITERATIONS)

dp = bwp.create_datapackage(sequential=True)
for matrix, sub in formula_rows.groupby("matrix"):
    kw = dict(matrix=matrix,
              indices_array=np.array(list(zip(sub.input_id.astype(int), sub.output_id.astype(int))),
                                     dtype=bwp.INDICES_DTYPE),
              data_array=np.vstack([samples[c] for c in sub.col]),
              name=f"{matrix}-database-parameter-overrides")
    if matrix == "technosphere_matrix":
        # inputs are stored negative in A; production exchanges are not flipped
        kw["flip_array"] = (sub["type"] != "production").to_numpy()
    dp.add_persistent_array(**kw)


# ------------------------------------------------------------ MC runner ---
def cf_vector(lca, method):
    """Characterisation factors aligned with lca's biosphere rows."""
    v = np.zeros(len(lca.dicts.biosphere))
    for flow, cf in bd.Method(method).load():
        fid = flow if isinstance(flow, int) else bd.get_id(flow)
        if fid in lca.dicts.biosphere:
            v[lca.dicts.biosphere[fid]] += cf["amount"] if isinstance(cf, dict) else cf
    return v


def run(with_parameters: bool):
    """Return (scores, realised multipliers). The multipliers are read back from
    the sampled technosphere matrix in every iteration (value / central amount),
    so the sensitivity analysis does not depend on how bw2calc indexes the
    sequential parameter arrays."""
    demand, data_objs, remapping = bd.prepare_lca_inputs(demand={fu: 1}, method=head)
    if with_parameters:
        data_objs = data_objs + [dp]
    lca = bc.LCA(demand, data_objs=data_objs, remapping_dicts=remapping,
                 use_distributions=True, use_arrays=with_parameters, seed_override=C.MC_SEED)
    lca.lci()
    lca.lcia()
    cfs = [cf_vector(lca, m) for m in methods]
    tech = formula_rows[formula_rows.matrix == "technosphere_matrix"]
    cells = [(lca.dicts.product[r.input_id], lca.dicts.activity[r.output_id], r.amount, r.formula.split("*")[-1].strip())
             for r in tech.itertuples()]
    out, realised = [], []
    for it in range(C.MC_ITERATIONS):
        if it:
            next(lca)
        inv = np.asarray(lca.inventory.sum(axis=1)).ravel()
        out.append([float(c @ inv) for c in cfs])
        realised.append({p: abs(lca.technosphere_matrix[i, j]) / abs(a) for i, j, a, p in cells})
        if (it + 1) % 100 == 0:
            print(f"    {it + 1}/{C.MC_ITERATIONS}")
    return pd.DataFrame(out, columns=[short(m) for m in methods]), pd.DataFrame(realised)


prev = C.RESULTS / "mc_scores.csv"
A = None
if prev.exists():  # reuse run A from an earlier run with the same settings
    old_scores = pd.read_csv(prev)
    a_old = old_scores[old_scores.run == "A exchange uncertainty"].drop(columns="run")
    if len(a_old) == C.MC_ITERATIONS and list(a_old.columns) == [short(m) for m in methods]:
        A = a_old.reset_index(drop=True)
        print("Run A reused from results/mc_scores.csv")
if A is None:
    print("Run A - exchange uncertainty only")
    A, _ = run(False)
print("Run B - exchange uncertainty + database parameters")
B, realised = run(True)
save_table(realised, "mc_realised_parameters")

scores = pd.concat([A.assign(run="A exchange uncertainty"),
                    B.assign(run="B + database parameters")], ignore_index=True)
save_table(scores, "mc_scores")

summ = (scores.melt(id_vars="run", var_name="method", value_name="score")
        .groupby(["method", "run"])["score"]
        .describe(percentiles=[0.025, 0.05, 0.5, 0.95, 0.975]).reset_index())
summ["unit"] = summ["method"].map({short(m): method_unit(m) for m in methods})
summ["CV"] = summ["std"] / summ["mean"]
save_table(summ, "mc_summary")

# Spearman: realised parameter values vs each score in run B
rho = []
for p in realised.columns:
    row = dict(parameter=p, realised_min=realised[p].min(), realised_max=realised[p].max())
    for col in B.columns:
        row[f"rho | {col.split('|')[1].strip()}"] = float(spearmanr(realised[p], B[col])[0])
    rho.append(row)
rho = pd.DataFrame(rho)
hc = f"rho | {short(head).split('|')[1].strip()}"
rho = rho.sort_values(hc, key=abs, ascending=False)
rho["share of explained rank variance (headline)"] = rho[hc] ** 2 / (rho[hc] ** 2).sum()
save_table(rho, "mc_parameter_spearman")
print(rho[["parameter", "realised_min", "realised_max", hc]].to_string(index=False))

h = short(head)
fig, ax = plt.subplots(figsize=(8, 4.5))
for name, df in [("A exchange uncertainty", A), ("B + database parameters", B)]:
    ax.hist(df[h], bins=50, alpha=0.55, label=name)
ax.set_xlabel(f"{method_unit(head)} per kg doré")
ax.set_ylabel("Frequency")
ax.set_title(f"Monte Carlo, {C.MC_ITERATIONS} iterations - {h}")
ax.legend()
plt.tight_layout()
plt.savefig(C.RESULTS / "mc_histogram.png", dpi=200)
print("  -> results/mc_histogram.png")
