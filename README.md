# Recall-first, explainable and fairness-audited prediction of death during follow-up (TCGA-BRCA)

MSc implementation project, Dept. of Computer Science, University of Jos — *Utilizing SHAP to explain XGBoost for breast cancer*.
**Version 2:** new target (death during follow-up), new data table (`data/data_clinical_patient.csv`), recall-first operating point,
and a Black-vs-White bias-mitigation study. Version 1 (race-equity SHAP study) is kept in `archive/v1_race_equity_shap/`.

## What is in the box
| File | Purpose |
|---|---|
| `run_pipeline.py` | One command: audit → tuning → hold-out → fairness CV → SHAP → `artifacts/` and `reports/figures/` (~4 min) |
| `breast_cancer_death_fairness.ipynb` | Narrated, executed analysis (same code as the pipeline) |
| `app.py` | Streamlit dashboard: patient explainer, fairness lab, threshold explorer, global SHAP, data audit, cohort, model card |
| `Chapters_3_4_5.docx` | Thesis Chapters 3 (Methodology), 4 (Implementation and Results), 5 (Conclusions) |
| `docs/EXPLAINER.md` | The project in plain language |
| `docs/MODEL_CARD.md` | Intended use, performance, fairness audit, limitations |
| `docs/DATA_AUDIT.md` | Column-by-column governance, leakage ladder, missingness evidence |
| `src/brca_xai/` | `data`, `audit`, `modeling`, `fairness`, `explain`, `plots`, `pipeline` |
| `tools/` | Builders for the Word chapters, the docs and the notebook (all read `artifacts/`, so numbers never drift) |
| `data/` | Input table and data dictionary (public, de-identified TCGA clinical data via cBioPortal) |

## Run
```bash
pip install -r requirements.txt
python run_pipeline.py                      # regenerate every number, figure and model
streamlit run app.py                        # dashboard
python tools/build_docs.py                  # docs/*.md
python tools/build_chapters.py              # Chapters_3_4_5.docx
python tools/build_notebook.py && jupyter nbconvert --to notebook --execute --inplace breast_cancer_death_fairness.ipynb
```

## Design in one paragraph
Target `died` = TCGA overall-survival event. Inputs are limited to what is known at diagnosis (age, T/N/M, PAM50, histology, prior cancer);
follow-up time, other survival endpoints, tumour status at follow-up and fields whose *blanks* predict death are excluded (they would lift AUC from
0.66 to 0.91). XGBoost with monotone T/N/M constraints; the alarm threshold is the highest score that still catches **80 % of deaths** (learned in-fold).
Five strategies (race-aware baseline, race-blind, reweighing, group thresholds, reweighing + group thresholds) are compared with 5×5-fold CV and paired
bootstrap intervals; SHAP explains the model globally, locally and by race.

## Things to know before citing a number
* **Small group:** 182 Black patients, 30 deaths. The recall gap CI is about ±14 points, so "no measurable gap" is not "no gap". The hold-out set has 6 Black deaths.
* **Censoring:** the label ignores follow-up length; sensitivity analyses restrict evaluation to patients with settled outcomes.
* **Modest discrimination** (AUC ≈ 0.66) is a property of the data, not the algorithm (logistic regression and random forest do no better).
* **Clinician study (Objective 4)** is designed (Chapter 3.12) but not run.
* Research prototype — not for clinical use.
