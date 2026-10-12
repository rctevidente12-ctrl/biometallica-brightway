"""Run steps 2-6 in order (step 1 is run once, by itself, because it may ask
for ecoinvent credentials). Use: python run_all.py  [or Run file in Spyder]."""
import runpy
import time
from pathlib import Path

here = Path(__file__).resolve().parent
for step in ["02_import_biometallica.py", "03_lcia_contribution.py",
             "05_regionalised_edges.py", "06_scenarios.py", "04_monte_carlo.py"]:
    t0 = time.time()
    print(f"\n######## {step}")
    runpy.run_path(str(here / step), run_name="__main__")
    print(f"######## {step} done in {time.time() - t0:,.0f} s")
