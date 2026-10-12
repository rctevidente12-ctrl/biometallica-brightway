"""Step 2 - import the BioMetallica foreground (biometallica_v1_1).

Mirrors the course pattern (D1-04 / D1-10): ExcelImporter -> strategies ->
link to ecoinvent 3.12 -> write with database parameters -> register the
formula exchanges so the scenario multipliers (m_u1_elec, ...) are live.
Re-running replaces the database.
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import bw2data as bd
import bw2io as bi
from bw2data import parameters
from bw2data.parameters import ActivityParameter, DatabaseParameter, Group, ParameterizedExchange

import config as C
from utils import open_project, get_fu

open_project()

imp = bi.ExcelImporter(str(C.FG_XLSX))
print("Workbook database:", imp.db_name, "| datasets:", len(imp.data))
imp.apply_strategies()
imp.match_database(C.EI_DB, fields=("name", "reference product", "location", "unit"))
imp.match_database(C.BIO_DB, fields=("name", "unit", "categories"), kind="biosphere")
imp.match_database(fields=("name", "reference product", "location", "unit"))  # internal links
imp.statistics()

unlinked = list(imp.unlinked)
if unlinked:
    imp.write_excel(only_unlinked=True)
    for exc in unlinked[:20]:
        print("  unlinked:", exc.get("name"), exc.get("location"), exc.get("categories"), exc.get("type"))
    raise SystemExit("Fix the unlinked exchanges above (an Excel list was written next to the bw2io output dir).")

# clean re-run
if C.FG_DB in bd.databases:
    del bd.databases[C.FG_DB]
ParameterizedExchange.delete().where(ParameterizedExchange.group == C.FORMULA_GROUP).execute()
ActivityParameter.delete().where(ActivityParameter.group == C.FORMULA_GROUP).execute()
Group.delete().where(Group.name == C.FORMULA_GROUP).execute()

imp.write_database(activate_parameters=True)

# register every activity that carries a formula exchange
n_formula = 0
for act in bd.Database(C.FG_DB):
    if any("formula" in exc for exc in act.exchanges()):
        parameters.add_exchanges_to_group(C.FORMULA_GROUP, act.key)
        n_formula += 1
ActivityParameter.recalculate(C.FORMULA_GROUP)
ActivityParameter.recalculate_exchanges(C.FORMULA_GROUP)
bd.Database(C.FG_DB).process()

print(f"Activities: {len(bd.Database(C.FG_DB))} | activities with formulas: {n_formula}")
print("Database parameters:",
      [(p.name, p.amount) for p in DatabaseParameter.select().where(DatabaseParameter.database == C.FG_DB)])
fu = get_fu()
print("Functional unit:", fu["name"], fu["location"], fu["unit"])
