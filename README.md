# Recall-first, explainable and fairness-audited prediction of death during follow-up (TCGA-BRCA)

MSc implementation project, Dept. of Computer Science, University of Jos — *Utilizing SHAP to explain XGBoost for breast cancer*.
**Version 3** implements the **revised proposal** (prognostic target, Table 3.2 predictor list, class weighting, Bayesian tuning, PR-AUC and bootstrap CIs, baselines,
SHAP fidelity / stability / clinical-alignment checks, physician user study). It keeps the **recall-first** design and adds a **Black-vs-White fairness audit** as an extension.
Earlier versions: `archive/v1_race_equity_shap/` (and git history, commit `7d78218` = version 2).

## What is in the box
| File | Purpose |
|---|---|
| `run_pipeline.py` | One command: audit → tuning → baselines → hold-out → fairness CV → SHAP → `artifacts/<spec>/` and `reports/figures/<spec>/` for both specifications (~15 min) |
| `breast_cancer_death_fairness.ipynb` | Narrated, executed analysis of the primary specification (does not overwrite artifacts) |
| `app.py` | Streamlit dashboard (11 tabs): patient explainer, performance, fairness lab, threshold explorer, explanations, data audit, user study, framework |
| `Chapters_3_4_5.docx` | Thesis Chapters 3 (Methodology), 4 (Implementation and Results), 5 (Conclusions) |
| `docs/PROPOSAL_REVIEW.md` | Review of the revised proposal: what improved, what to challenge (with evidence), what was added |
| `docs/EXPLAINER.md`, `docs/MODEL_CARD.md`, `docs/DATA_AUDIT.md` | Plain-language guide, model card, column-by-column data audit |
| `userstudy/` | Physician study kit: 12 case cards x 2 conditions, counterbalanced design, questionnaire, analysis script (no data collected yet) |
| `src/brca_xai/` | `data`, `audit`, `modeling`, `evaluate`, `fairness`, `explain`, `plots`, `pipeline` |
| `tools/` | Builders for the chapters, docs, notebook and user-study kit (all read `artifacts/`, with assertions that stop the build if the prose is no longer true) |

## Two specifications
* `proposal` — predictors exactly as in the revised proposal's Table 3.2 (**primary**).
* `hardened` — the same without three documentation artefacts the audit found (radiation / neoadjuvant blanks, NX / MX codes; race-not-recorded is quantified separately).
  The proposal's list reaches AUC 0.75; the hardened list 0.66. The difference is registry documentation, not biology (`docs/DATA_AUDIT.md`).

## Run
```bash
pip install -r requirements.txt
python run_pipeline.py                      # regenerate every number, figure and model (deterministic, seed 42)
streamlit run app.py                        # dashboard
python tools/build_userstudy.py             # case cards and design for the physician study
python tools/build_docs.py                  # docs/*.md
python tools/build_chapters.py              # Chapters_3_4_5.docx
python tools/build_notebook.py && jupyter nbconvert --to notebook --execute --inplace breast_cancer_death_fairness.ipynb
python tools/analyze_user_study.py --self-test   # tests the study analysis on synthetic data
```

## Things to know before citing a number
* **Blank fields carry the outcome.** Radiation therapy is blank for 101 patients, 42 % of whom died (11 % when recorded); it is the top SHAP feature of the as-specified model. Quote both specifications.
* **Small group.** 182 Black patients, 30 deaths; the hold-out set has 6. No fairness gap is statistically distinguishable from zero, and point estimates move with model selection (`model_selection_sensitivity.csv`).
* **Raw scores are not probabilities** (class weighting); use the recalibrated risk shown in the dashboard.
* **Hold-out recall** (0.70, CI 0.53-0.85) is below the 80 % target met in cross-validation; with 30 test deaths this is within noise.
* **Censoring.** The binary label ignores follow-up length; sensitivity analyses and an exploratory Cox model are included.
* **Objective 4 (clinician study)** is an instrument, not a result.
* Research prototype — not for clinical use.
