# Model card: recall-first prediction of death during follow-up (TCGA-BRCA)

*Research prototype for an MSc project (University of Jos, Dept. of Computer Science). Not a medical device. Not validated for clinical use.*

## Intended use
Demonstrate how an XGBoost classifier, explained with SHAP, can be built with a **recall-first** operating point, audited for leakage and informative missingness, and checked for
**racial fairness** (White vs Black / African American patients) on public TCGA-BRCA data. **Out of scope:** real patient-care decisions, triage, insurance or resource allocation.

## Task, label, cohort
* `died = 1` if `OS_STATUS = 1:DECEASED`. Follow-up is censored (median 27 months), so the label is *death observed during follow-up*, not "death within N years".
* 1,084 patients, 151 deaths (13.9%). Fairness audit groups: 751 White (111 deaths), 182 Black (30 deaths); 151 Asian / race-not-recorded patients are used for training only.
* Split: stratified 80/20 (867 development / 217 hold-out).

## Inputs (revised proposal, Table 3.2)
Age, pathologic T / N / M (TX, NX, MX = missing), PAM50 subtype (not called = missing), histology group, prior diagnosis, neoadjuvant therapy, radiation therapy (blank = missing), race.
**Excluded:** follow-up time, other survival endpoints, tumour status and new-tumour events at follow-up, composite stage, days to birth, ancestry, ethnicity, administrative fields.
**Audit-hardened specification** (sensitivity): drops radiation and neoadjuvant therapy, sets NX / MX to N0 / M0. See `docs/DATA_AUDIT.md`.

## Model
XGBoost, depth 2, 299 trees, learning rate 0.023; `scale_pos_weight` = negatives / positives; monotone non-decreasing in T, N, M; Bayesian (TPE) search with repeated
5-fold CV minimising FPR at 80 % recall. Tree SHAP.

## Operating point (recall first)
Threshold = highest score that still catches **80 %** of deaths on out-of-fold training predictions (global: 0.356). Precision floor 1.25 x prevalence = 0.17.

## Performance
| | As proposed | Audit-hardened |
|---|---|---|
| AUC-ROC (5x5 CV) | 0.747 | 0.662 |
| PR-AUC | 0.457 | 0.307 |
| Recall / precision / flagged | 79.2% / 20.2% / 55% | 81.2% / 17.5% / 64% |

Hold-out (217 patients, 30 deaths), as proposed: recall 0.70, precision 0.23,
AUC 0.77, PR-AUC 0.47; accuracy 0.64 versus 0.86 for always predicting "living".
Intervals: `artifacts/proposal/test_metrics.csv`.

## Fairness audit (as proposed; Black minus White; 5x5 CV with bootstrap CI)
| Strategy | Recall White | Recall Black | Recall gap | False-alarm gap | Flagged (W+B) |
|---|---|---|---|---|---|
| Baseline (race-aware) | 80.2% | 87.3% | +7.2 percentage points (95% CI -4.2 to +17.0) | +1.4 percentage points (95% CI -6.6 to +8.9) | 58% |
| Race-blind | 80.4% | 72.7% | -7.7 percentage points (95% CI -22.5 to +6.5) | -7.2 percentage points (95% CI -15.4 to +0.7) | 56% |
| Reweighing | 80.9% | 70.0% | -10.9 percentage points (95% CI -26.4 to +4.8) | -9.6 percentage points (95% CI -17.8 to -1.6) | 57% |
| Group thresholds | 79.8% | 78.0% | -1.8 percentage points (95% CI -15.3 to +10.8) | -3.9 percentage points (95% CI -12.4 to +3.8) | 57% |
| Reweighing + group thresholds | 80.2% | 78.7% | -1.5 percentage points (95% CI -14.0 to +11.7) | -2.2 percentage points (95% CI -10.3 to +5.6) | 57% |

**Reading:** no gap is statistically distinguishable from zero, and with 30 Black deaths the recall-gap interval is about +-11 points. Point estimates also depend on model selection:
across near-equivalent tuned configurations the baseline recall gap ranges from -2.8 to +5.3 points.
Stable across configurations: removing race lowers the recall gap (Black recall falls), and group thresholds hold it near zero. The baseline uses the Black indicator and, more heavily, *race not recorded*; see `docs/PROPOSAL_REVIEW.md`.

## Limitations
1. Small group: 30 Black deaths; the hold-out set holds 6.
2. Censoring: survivors with short follow-up may still die; treatment other than radiation / neoadjuvant is absent.
3. Blank-field artefacts raise the as-proposed AUC; use the hardened model for any real use.
4. Single cohort (TCGA), no external validation. Race is a social label; ancestry analysis is small.
5. Group thresholds use race at prediction time, which may be unacceptable in some settings.
6. Clinician study (Objective 4) not yet run.

## Reproduce
`pip install -r requirements.txt && python run_pipeline.py && streamlit run app.py`
