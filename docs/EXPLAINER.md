# The project in plain language

## The question
*From what doctors know about a breast-cancer patient at diagnosis, can a model warn us who is likely to die during follow-up without missing many of them, can we see why it says so, and does it work equally well for Black and White patients?*

## Why "recall first"?
With 100 patients, about 14 die. **Recall** is how many of those 14 the model catches. A missed death is a disaster, an extra check-up a nuisance, so the alarm level is set to catch **80 %** of deaths,
not at the default 50 % (which would flag almost nobody). The price: about 55% of patients get flagged and only about 20% of those flagged die.

## What does the model look at?
Age, tumour size (T), lymph nodes (N), spread (M), molecular subtype (PAM50), histology, prior cancer, neoadjuvant therapy, radiation therapy and race (the revised proposal's list). It never sees follow-up time or anything recorded after diagnosis.

## A warning about blanks
Radiation therapy is blank for 101 patients, and 42% of them died (against 11% when it is recorded). A blank is not "no radiation": it is a registry gap that happens to
go with death. A model that learns "blank means danger" looks better (0.75 AUC) than one that cannot (0.66), without knowing more about cancer. We report both and recommend the second for any real use.

## What is SHAP?
SHAP splits each prediction into contributions ("older age added this much; node-negative subtracted that much") that add up exactly to the model's output. We check it three ways: **fidelity** (the sums are exact), **stability**
(the same features rank on top when the data are resampled) and **clinical alignment** (the top features should be what oncologists expect). In the as-proposed model the top feature is **Radiation therapy**, which is *not* a clinical
factor; in the hardened model it is **Age at diagnosis**.

## Bias
We measure, for Black versus White patients: **recall** (among those who die, how many are flagged), **false-alarm rate** (among survivors, how many are flagged), ranking quality (AUC) and calibration. With only 30 Black deaths every Black number is fuzzy, so
we use repeated cross-validation, bootstrap intervals and compare strategies on the same resamples. Strategies: baseline (race as input), race-blind, reweighing, group thresholds, reweighing + group thresholds.

**Finding (as proposed):** recall gap +7.2 percentage points (95% CI -4.2 to +17.0); false-alarm gap +1.4 percentage points (95% CI -6.6 to +8.9): neither is distinguishable from zero. Removing race or re-weighting the training data *lowers* Black recall in return for fewer false alarms; separate alarm levels per group keep both gaps near zero.

## Honest bottom line
Use the model to learn, not to decide. The clinically honest model has modest accuracy; the sample is too small to prove fairness; the physician study is still to be run.

## Where things are
| What | Where |
|---|---|
| Run everything | `python run_pipeline.py` |
| Narrated analysis | `breast_cancer_death_fairness.ipynb` |
| Dashboard | `streamlit run app.py` |
| Thesis chapters 3-5 | `Chapters_3_4_5.docx` |
| Review of the revised proposal | `docs/PROPOSAL_REVIEW.md` |
| Model card / data audit | `docs/MODEL_CARD.md`, `docs/DATA_AUDIT.md` |
| User-study kit | `userstudy/` |
