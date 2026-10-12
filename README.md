# BioMetallica – Brightway and edges LCA simulation

This repository runs the impact assessment of the BioMetallica bio-opto leaching process. It covers precious-metal recovery from e-waste ash: roasting, acid digestion, formic-acid reduction, biocyanide and photocyanide leaching, resin recovery and electrowinning.

- **Functional unit:** 1 kg metal doré leaving U12.
- **Location:** Hong Kong.
- **Background:** ecoinvent 3.12 cut-off.
- **Foreground:** the life cycle inventory v1.1 in `data/BioMetallica_LCI_brightway_v1.1.xlsx`, database `biometallica_v1_1`. It has 14 units, pedigree uncertainty and six database parameters.

The workflow follows the *Regionalised LCIA with Brightway and edges* course (Barcelona, 2026), modules D1-04, D1-08, D1-10, D2-03, D2-05 and D2-07.

## Two backgrounds (switch in `config.py` → `BACKGROUND`)

| `BACKGROUND` | Background database | Foreground | Status |
|---|---|---|---|
| `"bafu"` (current) | BAFU:2025, the free Swiss LCI database from the course, plus the ecoinvent 3.10 biosphere | `BioMetallica_LCI_brightway_v1.1_BAFU.xlsx`, database `biometallica_v1_1_bafu` | **Stand-in.** Provisional numbers, not for publication |
| `"ecoinvent"` | ecoinvent 3.12 cut-off | `BioMetallica_LCI_brightway_v1.1.xlsx`, database `biometallica_v1_1` | Final. Needs an ecoinvent licence that allows ecoSpold2 or API download |

In the BAFU version, the 30 ecoinvent 3.12 background links are re-mapped to BAFU datasets.
- **Proxies.** Where BAFU has no equivalent, the closest dataset is used and the comment column marks it `BAFU: PROXY`:
  - Hong Kong grid → China grid
  - glucose → maize starch
  - glycine → organic chemicals
  - yeast extract → whey yeast paste
  - titanium anode → TiO2
  - ferrocyanide → NaCN
- **Waste treatment** is entered as a positive service input, following the ecoinvent v2 convention BAFU uses.
- **No GeoPolRisk.** It is dropped in BAFU mode, because it matches ecoinvent 3 supplier names.

## Requirements

- The course conda environment `bw`: Python 3.11, bw2data ≥ 4.3, bw2calc ≥ 2.0.1, bw2io ≥ 0.9.4, edges, matplotlib and python-dotenv.
- An ecoinvent account with a 3.12 licence.

## Run order (Spyder or terminal, from this folder, in the `bw` environment)

| Step | Script | What it does | Time |
|---|---|---|---|
| 1 (BAFU) | `01b_setup_bafu.py` | Installs the course's prepared project (biosphere and LCIA methods) as `biometallica-bafu`, then imports `lci-bafu.xlsx`. Run it once on its own. | 5–15 min |
| 1 (ecoinvent) | `01_setup_ecoinvent.py` | Creates project `biometallica`, then imports ecoinvent 3.12 cut-off, the biosphere and the LCIA methods. Run it once on its own. | 10–30 min |
| 2 | `02_import_biometallica.py` | Imports and links the foreground, then activates the database parameters and formulas. | 1 min |
| 3 | `03_lcia_contribution.py` | Runs every EF v3.1, IPCC 2021 and CED indicator. Splits each score into units and input groups. | 5 min |
| 4 | `04_monte_carlo.py` | Runs 1,000 Monte Carlo iterations. Run A uses exchange uncertainty only. Run B adds the database parameters and reports Spearman ranks. | 20–60 min |
| 5 | `05_regionalised_edges.py` | Runs regionalised LCIA with edges: AWARE 2.0, IBIF, GeoPolRisk and the ImpactWorld+ 2.1 damage indicators. Includes an HK-to-CN-GD proxy sensitivity and Sankey diagrams. | 10–30 min |
| 6 | `06_scenarios.py` | Runs the scenarios: electricity grid and renewables, design levers and a purchased-HCN benchmark. | 5 min |

`run_all.py` runs steps 2 to 6. Every output is written to `results/`, as CSV, PNG and HTML.

Before step 1, copy `.env.example` to `.env` and enter your ecoinvent credentials. You can also leave `.env` empty and type the credentials when the script asks. All names (project, databases, methods and scenarios) are set in `config.py`.

## Methods notes

- **Contribution analysis (`utils.foreground_contributions`).**
  - Each foreground unit gets two parts:
    - its direct emissions;
    - the cradle-to-gate burden of each background input. The unit score of every product comes from one transposed solve, Aᵀx = (CB)ᵀ.
  - The rows add up exactly to the LCA score. Inputs between foreground units are counted only once, at the supplying unit.
- **Monte Carlo** follows the database-parameter pattern from D1-10.
  - Parameter samples come from `bw2parameters.ParameterSet`.
  - They are pushed into the formula exchanges through a sequential `bw_processing` datapackage, together with `use_distributions=True`.
  - All indicators are scored from the same sampled inventory in each iteration.
- **Regionalisation.** Hong Kong is not a country entry in AWARE 2.0 or IBIF, so edges gives HK consumers a weighted global CF.
  - Most of Hong Kong's fresh water is imported from the Dongjiang river in Guangdong (about 70–80 %, Development Bureau, HKSAR, LCQ20 "Fresh water supply": https://devb.gov.hk/en/sdev/press/index_id_7698.html).
  - The foreground is therefore re-assessed with CN-GD as a proxy location.
  - In the base inventory, AWARE impacts arise mainly in the background: the water and electricity supply chains. The foreground water flows are evaporation to air, and AWARE 2.0 does not characterise those.
- **Purchased-cyanide benchmark (S3).** U5 and U6 are replaced by the ecoinvent `market for hydrogen cyanide` (RoW), at 27.025/26.017 kg HCN per kg CN.

## References

- Sacchi, R. et al. (2025). *edges: exchange-based, regionalised LCIA in Brightway.* Int J Life Cycle Assess. https://doi.org/10.1007/s11367-025-02551-7
- Mutel, C. (2017). Brightway: an open source framework for Life Cycle Assessment. *JOSS* 2(12), 236. https://doi.org/10.21105/joss.00236
- Boulay, A.-M. et al. (2018). The WULCA consensus characterization model for water scarcity footprints (AWARE). Int J Life Cycle Assess 23, 368–378. https://doi.org/10.1007/s11367-017-1333-8
- Schipper, A. M. et al. (2025). Intactness-based biodiversity impact factors (IBIF). *Scientific Data*. https://doi.org/10.1038/s41597-025-05946-1
- Ciroth, A. et al. (2016). Empirically based uncertainty factors for the pedigree matrix in ecoinvent. Int J Life Cycle Assess 21, 1338–1348. https://doi.org/10.1007/s11367-013-0670-5
- FOEN/BAFU (2025). *BAFU:2025 LCI database.* Swiss Federal Office for the Environment. https://www.bafu.admin.ch/en/life-cycle-assessment (terms of use: https://www.bafu.admin.ch/dam/en/sd-web/-9ZObeMCZy8A/BAFU_2025_TermOfUse_EN_Webpage.pdf)
- Wernet, G. et al. (2016). The ecoinvent database version 3 (part I). Int J Life Cycle Assess 21, 1218–1230. https://doi.org/10.1007/s11367-016-1087-8

Author: Ralph Carlo Evidente, 2026.
