"""Step 3 - deterministic LCIA and contribution analysis per kg dore.

Outputs (results/):
  lcia_scores.csv                 score of every configured method
  contribution_by_unit.csv        method x unit (U1...U13b), incl. background
  contribution_by_unit_group.csv  method x unit x input group (electricity, ...)
  contribution_detail.csv         every unit x input row (all methods)
  contribution_headline.png       stacked bar of the headline method
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import bw2calc as bc
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import config as C
from utils import (open_project, get_fu, all_methods, headline_method, method_unit,
                   short, foreground_contributions, unit_label, save_table)

open_project()
fu = get_fu()
methods = all_methods()
head = headline_method()
print(f"Functional unit: 1 kg {fu['reference product']} | methods: {len(methods)}")

lca = bc.LCA({fu: 1}, head)
lca.lci()

scores, detail = [], []
for m, family in methods.items():
    lca.switch_method(m)
    lca.lcia()
    scores.append(dict(family=family, method=short(m), unit=method_unit(m), score=lca.score))
    df = foreground_contributions(lca)
    df.insert(0, "method", short(m))
    df.insert(1, "method unit", method_unit(m))
    detail.append(df)
    print(f"  {short(m):95s} {lca.score:12.4g} {method_unit(m)}")

scores = pd.DataFrame(scores)
detail = pd.concat(detail, ignore_index=True)
detail["unit id"] = detail["unit"].map(unit_label)
save_table(scores, "lcia_scores")
save_table(detail, "contribution_detail")

by_unit = detail.pivot_table(index=["method", "method unit"], columns="unit id",
                             values="score", aggfunc="sum", fill_value=0.0)
by_unit["total"] = by_unit.sum(axis=1)
save_table(by_unit.reset_index(), "contribution_by_unit")

by_group = detail.groupby(["method", "unit id", "group"], as_index=False)["score"].sum()
save_table(by_group, "contribution_by_unit_group")

# electricity share for every method (key thesis number)
elec = detail[detail["group"] == "electricity"].groupby("method")["score"].sum()
tot = detail.groupby("method")["score"].sum()
share = (elec / tot).rename("electricity share").reset_index()
save_table(share, "electricity_share")

# headline plot: units stacked by input group
h = short(head)
sub = by_group[by_group["method"] == h].pivot_table(index="unit id", columns="group",
                                                    values="score", aggfunc="sum", fill_value=0)
order = sorted(sub.index, key=lambda u: (len(u), u))
sub = sub.loc[order]
ax = sub.plot(kind="bar", stacked=True, figsize=(10, 5), width=0.75)
ax.set_ylabel(f"{method_unit(head)} per kg doré")
ax.set_xlabel("")
ax.set_title(f"Contribution by unit - {h}\nTotal {tot[h]:,.1f} {method_unit(head)} per kg doré")
ax.axhline(0, color="black", lw=0.6)
plt.tight_layout()
plt.savefig(C.RESULTS / "contribution_headline.png", dpi=200)
print("  -> results/contribution_headline.png")
