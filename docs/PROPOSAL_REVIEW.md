# Review of the revised proposal and how the implementation responds

*Written from the standpoint of the data scientist who built the implementation; every number below is reproduced by `python run_pipeline.py`.*

## 1. What the revision changes (and why it is the right direction)
| Topic | Original proposal | Revised proposal | Verdict |
|---|---|---|---|
| Task | Diagnose benign vs malignant | **Prognosis**: death during follow-up (`OS_STATUS`), all 1,084 TCGA-BRCA patients, 151 deaths (13.9%) | Correct. TCGA-BRCA has no benign cases; the old target could not be built. |
| Leakage | Not addressed | Explicit variable-selection table (Table 3.2); outcome-related columns excluded | Strong improvement; the single most important methodological fix. |
| Imbalance | Not addressed | `scale_pos_weight`, no synthetic oversampling | Appropriate for 13.9 % prevalence. |
| Tuning / overfitting | Hold-out only | Repeated stratified 5-fold CV, Bayesian or grid search, early stopping, train/CV/test comparison | Implemented (Bayesian TPE; learning curve). |
| Threshold | Recall emphasised | Choose on CV predictions to maximise recall at an acceptable precision | Needs an operational definition of "acceptable" (see 3.3). |
| Evaluation | Accuracy, precision, recall, F1, AUC | + PR-AUC, confusion matrix, bootstrap CIs, baselines (LR, RF, stage-only), accuracy vs the 86 % no-skill baseline | Right. With 30 test deaths the CIs matter. |
| Explainability | SHAP plots | + fidelity, stability, clinical alignment, race check | Implemented; see Chapter 4. |
| User study | Qualitative or quantitative | Within-subject A (score) vs B (score + SHAP), Likert, Wilcoxon, thematic analysis | Kit built (`userstudy/`); not yet run. |
| Limitations | Generic | Variable follow-up, cause of death, ceiling, single cohort | Honest and accurate: median follow-up 27 months and 79% of living patients under 60 months were confirmed in the data. |

## 2. Claims in the proposal that I verified against the data
Median follow-up 27 months (max 283), 79 % of living patients under 60 months, 1,084 patients / 38 variables, 151 deaths (13.9 %), sex 98.9 % female, subtype missing for 103
(9.5 %), ethnicity missing for 169, weight 100 % missing, about 30 test deaths at an 80/20 split: **all correct.**

## 3. Where I would push back (with evidence)
1. **Two retained predictors carry the outcome through their blanks.** *Radiation therapy* is blank for 101 patients, **42% of whom died vs 11%**
   when recorded; XGBoost's native handling of missing values turns that documentation pattern into a feature. Removing it alone drops cross-validated AUC from
   0.758 to 0.699. In the as-specified model it is the **#1 feature by SHAP importance**,
   above nodal status.  Likewise "NX / MX set to missing" gives the model a flag for a code whose death rate is 55% (NX, n = 20).
   **Recommendation:** keep the specification as the primary analysis (it is the approved design) but report the audit-hardened specification next to it, and do not present the higher AUC as clinical signal.
2. **Race as a predictor interacts with missing race.** 91 patients have no recorded race and an 8% death rate; with native missing handling the model uses "race not recorded" as a
   low-risk flag: it carries 39% of their total attribution. Race recorded: 8%. Asian patients (60, 3 deaths) also receive a
   learned "low risk" effect from three events. The proposal's *fairness check* of race SHAP is therefore essential, and its answer is not "race is unused".
3. **"Acceptable precision" must be defined.** Without a floor, "maximise recall" returns "flag everyone". I operationalised it as: catch >= 80 % of deaths, then require precision >= 1.25 x prevalence
   (0.17); alternative rules are compared in `threshold_rules.csv`: Youden and the default 0.5 catch only 60% of hold-out deaths.
4. **Early stopping** with only 867 development patients is noisy; the number of trees is tuned inside CV and checked with a train / CV / test learning curve.
5. **Hold-out intervals are very wide** (30 deaths; 6 Black). I kept the proposal's hold-out protocol but base the headline numbers and all fairness statements on 5x5 repeated CV.
6. **Wording.** The title, Sections 1.1, 1.2, 1.5 and 2.x still speak of diagnosis, benign/malignant and "diagnostic accuracy", while Chapter 3 is prognostic. Table 2.2 is mostly diagnostic work (WBCD, imaging);
   add prognostic XGBoost / SHAP literature. "Significance of Study" lacks a section number (1.5), and the proposal's "4.0 Conclusion" becomes Chapter 5 of the thesis.
7. **Sample size of the user study** (15-30, paired Wilcoxon) detects only large effects (r about 0.6 at n = 20); state it as exploratory (done) and pre-register the primary outcome (trust, understandability).
8. **Fidelity** of TreeSHAP is guaranteed by construction (local accuracy); keep the check as a unit test but add a *faithfulness* test (deletion) and the stability checks, which I did.

## 4. What I added beyond the revision (flag for supervisors)
* **Black vs White fairness audit and mitigation** (race-blind, reweighing, group thresholds): the revised proposal only has the SHAP race check. It is reported as an *extension*; drop or promote it to an objective as supervisors prefer.
* **Audit-hardened specification** and artefact ablation (Section 3 above).
* **Exploratory survival check** (Cox objective, C-index 0.742 vs 0.717 for the binary score): the binary label loses little ranking information; the proposal leaves survival modelling to future work.

## 5. Headline results
| | As proposed | Audit-hardened |
|---|---|---|
| AUC-ROC (5x5 CV, all patients) | 0.747 | 0.662 |
| PR-AUC (no-skill 0.139) | 0.457 | 0.307 |
| Recall at the 80 % rule | 79.2% | 81.2% |
| Precision at that point | 20.2% | 17.5% |
| Share of patients flagged | 55% | 64% |
| Recall gap Black - White | +7.2 percentage points (95% CI -4.2 to +17.0) | +2.0 percentage points (95% CI -10.3 to +14.4) |
| False-alarm gap Black - White | +1.4 percentage points (95% CI -6.6 to +8.9) | +5.0 percentage points (95% CI -1.5 to +11.4) |
