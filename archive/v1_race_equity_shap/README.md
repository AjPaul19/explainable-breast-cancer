# Utilizing SHAP to explain XGBoost for breast-cancer risk — implementation

Implementation phase of the University of Jos research proposal (TCGA-BRCA, XGBoost + SHAP), with an
explicit **race-equity analysis** of how features drive predictions for Black patients.

| File | Purpose |
|---|---|
| `breast_cancer_shap_implementation.ipynb` | Full study: data audit → model → evaluation → SHAP (global/local/interaction) → race-equity analysis → stability → exports. Already executed; re-run to reproduce. |
| `app.py` | Streamlit dashboard (patient explainer + what-if, global SHAP, Black-patient equity view, cohort explorer, threshold explorer). |
| `src/brca_xai/data.py` | Data download, cleaning and the feature encoding shared by notebook and dashboard. |
| `artifacts/` | Model, cohort with per-patient SHAP values and audit tables written by the notebook. |
| `reports/figures/` | Figures for the thesis (PNG). |

## Run
```bash
pip install -r requirements-notebook.txt
jupyter nbconvert --to notebook --execute --inplace breast_cancer_shap_implementation.ipynb   # ~2 min, downloads TCGA tables on first run
streamlit run app.py
```

## Things to know before you cite any number
* **Target:** TCGA-BRCA has no benign cases, so "benign vs malignant" is replaced by *death during follow-up* (recall-first).
* **Informative missingness** (HER2, N, M, menopause "not recorded") inflated naive AUC from ~0.65 to ~0.77; it is neutralised.
* **Small subgroup:** 179 Black patients, 29 deaths. Subgroup SHAP rankings are only partly stable (see notebook §9, §10).
* Research prototype — not for clinical use.
