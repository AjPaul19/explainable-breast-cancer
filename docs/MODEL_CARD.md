# Model card: recall-first prediction of death during follow-up (TCGA-BRCA)

*Research prototype for an MSc project (University of Jos, Dept. of Computer Science). Not a medical device. Not validated for clinical use.*

## Intended use
Demonstrate how an XGBoost classifier, explained with SHAP, can be built with a **recall-first** operating point and audited
for **racial fairness** (White vs Black / African American patients) on public TCGA-BRCA data.
**Out of scope:** any real patient-care decision, triage, insurance or resource-allocation use.

## Task and label
* Binary: `died = 1` if `OS_STATUS = 1:DECEASED` (death at any time during follow-up). Follow-up is censored and varies (median
  30 months), so the label is *death observed during follow-up*, not "death within N years".
* Cohort: 933 patients with self-reported White (751) or Black (182) race; 141 deaths
  (111 White, 30 Black). 90 patients with missing race and 61 Asian / other were
  excluded from the fairness cohort.

## Inputs (all known at diagnosis)
Age, pathologic T, N, M category, PAM50 subtype (unknown allowed), histology (ductal / lobular / other), prior malignancy.
The baseline model also receives a Black-race indicator; it ended up with a mean |SHAP| of
0.000 (the model never uses it).
**Deliberately excluded:** follow-up time, disease-specific / disease-free / progression endpoints, tumour status and new-tumour events at
follow-up, radiation, ethnicity and node-assessment fields (blank patterns that track the outcome). See `docs/DATA_AUDIT.md`.

## Model
XGBoost (`max_depth=1`, `n_estimators=377`, `learning_rate=0.019`), monotone
non-decreasing in T, N and M (clinical prior), hyper-parameters chosen on a development set by 4x5-fold CV to minimise the
false-positive rate at 80 % recall. Tree SHAP explanations.

## Operating point (recall first)
Threshold = highest risk score that still catches **80 %** of deaths on out-of-fold training predictions.
Race-blind model: 11.9% global; 11.9% (White) and 13.1% (Black) when thresholds are set per group.

## Performance (5 x 5-fold repeated CV over the cohort; bootstrap 95 % CI)
* AUC 0.66 (White 0.66, Black 0.65; Black interval 0.54-0.75).
* Recall 79.1% (95% CI 72.8 to 85.3); false-positive rate 63.0% (95% CI 60.3 to 65.7). The model flags roughly two in three patients to catch four in five deaths.
* Discrimination is modest; this is a limit of the information in clinical covariates, not of the algorithm (logistic regression and random forest do no better).

## Fairness audit
| Strategy | Recall White | Recall Black | Recall gap | False-alarm gap | Flagged overall |
|---|---|---|---|---|---|
| Baseline (race-aware) | 79.5% | 80.0% | +0.5 percentage points (95% CI -14.1 to +15.6) | +5.0 percentage points (95% CI -2.2 to +12.0) | 65.2% |
| Race-blind | 78.9% | 80.0% | +1.1 percentage points (95% CI -13.4 to +16.3) | +4.2 percentage points (95% CI -3.0 to +11.4) | 65.5% |
| Reweighing | 79.1% | 80.0% | +0.9 percentage points (95% CI -13.5 to +16.1) | +3.7 percentage points (95% CI -3.5 to +10.9) | 65.7% |
| Group thresholds | 79.6% | 82.0% | +2.4 percentage points (95% CI -11.3 to +16.4) | +4.2 percentage points (95% CI -2.3 to +11.0) | 66.7% |
| Reweighing + group thresholds | 80.2% | 81.3% | +1.2 percentage points (95% CI -13.1 to +15.6) | +2.9 percentage points (95% CI -3.7 to +9.6) | 67.4% |

Gap = Black minus White. Recall gap near zero means equal opportunity; a positive false-alarm gap means Black survivors are flagged more often.
**Reading:** no measurable recall gap, but with 30 Black deaths the CI spans about ±14 points, so a real gap cannot be excluded. The
false-alarm gap is positive in every strategy; it widens when evaluation is limited to patients with settled outcomes. Reweighing gave the only
paired-bootstrap-supported improvement (false-alarm gap -0.013, CI -0.024 to -0.001).
Group-specific thresholds did **not** help: the Black threshold is estimated from ~30 deaths and is noisy.

## Limitations
1. Small group: 30 Black deaths. Hold-out test set holds 6 Black deaths, so single-split numbers are anecdotes.
2. Censoring: survivors with short follow-up may still die; "false alarms" are partly future deaths. Treatment (surgery, chemotherapy, endocrine therapy) is absent from the data.
3. TCGA is not population-representative; no external validation.
4. Race is a social construct used here only to *audit* disparities; genetic-ancestry sensitivity analysis is in `artifacts/sensitivity_ancestry.csv` (also small).
5. Group-specific thresholds use race at prediction time, which may be legally or ethically unacceptable in some settings.

## Reproduce
`pip install -r requirements.txt && python run_pipeline.py && streamlit run app.py`
