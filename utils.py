"""Helper functions shared by the numbered scripts."""
from __future__ import annotations

import numpy as np
import pandas as pd
import bw2data as bd
from functools import lru_cache
from scipy.sparse.linalg import splu

import config as C


# ---------------------------------------------------------------- project ---
def open_project():
    if C.PROJECT not in bd.projects:
        raise SystemExit(f"Project {C.PROJECT!r} not found - run 01_setup_ecoinvent.py (ecoinvent) or 01b_setup_bafu.py (BAFU) first.")
    bd.projects.set_current(C.PROJECT)
    return bd.projects.current


def get_fu(db_name: str = C.FG_DB):
    hits = [a for a in bd.Database(db_name)
            if a["name"] == C.FU_NAME and a.get("location") == C.FU_LOCATION]
    if len(hits) != 1:
        raise ValueError(f"Expected one functional-unit activity in {db_name}, found {len(hits)}")
    return hits[0]


def get_ei(name: str, product: str, location: str, db_name: str = C.EI_DB):
    hits = [a for a in bd.Database(db_name).search(name, limit=200)
            if a["name"] == name and a.get("reference product") == product
            and a.get("location") == location]
    if not hits:  # search() can miss long names - fall back to a full scan
        hits = [a for a in bd.Database(db_name)
                if a["name"] == name and a.get("reference product") == product
                and a.get("location") == location]
    if len(hits) != 1:
        raise ValueError(f"Expected one '{name}' [{product}, {location}] in {db_name}, found {len(hits)}")
    return hits[0]


# ---------------------------------------------------------------- methods ---
def _match(method: tuple, keywords: list[str]) -> bool:
    text = " | ".join(method).lower()
    return all(k.lower() in text for k in keywords)


def pick_methods(keywords: list[str]) -> list[tuple]:
    return sorted(m for m in bd.methods if _match(m, keywords))


def headline_method() -> tuple:
    hits = pick_methods(C.HEADLINE)
    if not hits:
        raise ValueError(f"No method matches {C.HEADLINE}. Check names with: [m for m in bd.methods if 'climate' in str(m)]")
    return hits[0]


def all_methods() -> dict[tuple, str]:
    """{method tuple: family label} for every configured family."""
    out = {}
    for family, kw in C.METHOD_FAMILIES.items():
        hits = pick_methods(kw)
        if not hits:
            print(f"  ! no method matched family {family!r} ({kw}) - skipped")
        for m in hits:
            out.setdefault(m, family)
    return out


def method_unit(method: tuple) -> str:
    return bd.Method(method).metadata.get("unit", "")


def short(method: tuple) -> str:
    """Readable label: drop the leading 'ecoinvent-3.12' element if present."""
    parts = [p for p in method if not p.lower().startswith("ecoinvent-")]
    return " | ".join(parts)


# ------------------------------------------------- foreground attribution ---
def _input_group(act) -> str:
    """Group a background input (works for ecoinvent 3 and BAFU/ecoinvent v2 names)."""
    name = act["name"].lower()
    prod = (act.get("reference product") or "").lower()
    if "electricity" in name or "electricity" in prod:
        return "electricity"
    if (name.startswith(("disposal", "treatment")) or "waste" in name or "wastewater" in prod):
        return "waste treatment"
    if name.startswith(("tap water", "water, deionised", "market for tap water", "market for water")):
        return "water"
    if "transport" in name:
        return "transport"
    if act.get("unit") == "unit":            # plants, factories (infrastructure)
        return "infrastructure"
    return "chemicals and materials"


@lru_cache(maxsize=None)
def _node(node_id: int):
    return bd.get_node(id=node_id)


def foreground_contributions(lca, fg_db: str = C.FG_DB) -> pd.DataFrame:
    """Attribute the current LCA score to each foreground unit.

    For every foreground activity j the score is split into
      * direct emissions of j (characterised biosphere column of j), and
      * each background input i of j: amount_ij * supply_j * unit_score_i,
    where unit_score_i is the cradle-to-gate score of one unit of product i,
    obtained for all products at once from A^T x = (C B)^T (one solve).
    Inputs from other foreground units are not counted here - they appear
    under their own unit - so the rows sum exactly to lca.score.
    """
    A = lca.technosphere_matrix.tocsc()
    s = np.asarray(lca.supply_array).ravel()
    cb = np.asarray((lca.characterization_matrix @ lca.biosphere_matrix).sum(axis=0)).ravel()
    # One LU factorisation of A^T per LCA object, reused for every method
    # (scipy SuperLU; avoids repeated PARDISO factorisations and their memory).
    lu = getattr(lca, "_bm_lu_T", None)
    if lu is None:
        lu = splu(A.T.tocsc())
        lca._bm_lu_T = lu
    unit_scores = lu.solve(cb)

    col_of = lca.dicts.activity          # activity id -> column
    row_of = lca.dicts.product           # product id  -> row
    rev_row = {v: k for k, v in row_of.items()}
    fg_ids = {a.id for a in bd.Database(fg_db)}

    rows = []
    for act in bd.Database(fg_db):
        if act.id not in col_of:
            continue
        j = col_of[act.id]
        if s[j] == 0:
            continue
        rows.append(dict(unit=act["name"], input="direct emissions", group="direct emissions",
                         score=cb[j] * s[j]))
        col = A.getcol(j)
        for i, a_ij in zip(col.indices, col.data):
            pid = rev_row[i]
            if pid in fg_ids:
                continue
            inp = _node(pid)
            rows.append(dict(unit=act["name"],
                             input=f"{inp['name']} [{inp.get('location')}]",
                             group=_input_group(inp),
                             score=-a_ij * s[j] * unit_scores[i]))
    df = pd.DataFrame(rows)
    gap = df["score"].sum() - lca.score
    if abs(gap) > 1e-6 * max(1.0, abs(lca.score)):
        print(f"  ! attribution closes with a gap of {gap:.3g} ({gap / lca.score:.2%})")
    return df


def unit_label(name: str) -> str:
    """'U5 biocyanide generation, ...' -> 'U5'."""
    return name.split(" ")[0]


def save_table(df: pd.DataFrame, stem: str, index=False):
    path_csv = C.RESULTS / f"{stem}.csv"
    df.to_csv(path_csv, index=index)
    print(f"  -> {path_csv.relative_to(C.ROOT)}")
    return path_csv
