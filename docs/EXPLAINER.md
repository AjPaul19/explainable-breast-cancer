# The project in plain language

## What question are we asking?
*Given what doctors know about a breast-cancer patient at diagnosis, can a model warn us who is likely to die during follow-up, without
missing many of them, and does it do this equally well for Black and White patients?*

## Why "recall first"?
Imagine 100 patients, 15 of whom will die. **Recall** is how many of those 15 the model catches. A missed death (false negative) is a
disaster; an unnecessary extra check-up (false positive) is a nuisance. So we do not use the default "flag if risk > 50 %" rule (that would
flag almost nobody, because most patients survive). We pick the threshold that catches **80 %** of deaths and accept the price: about two
thirds of patients get flagged (63.0% (95% CI 60.3 to 65.7) of survivors).

## What does the model look at?
Age, tumour size (T), lymph-node involvement (N), distant spread (M), the PAM50 molecular subtype, tumour histology, and whether the
patient had a previous cancer. It does **not** see follow-up time or anything recorded after diagnosis; including those would make the
model look brilliant (AUC about 0.9) while predicting nothing (`docs/DATA_AUDIT.md`).

## What is SHAP?
SHAP splits each prediction into contributions: "starting from the average patient's risk, being 74 years old added this much, being
node-negative subtracted that much ...". The contributions add up exactly to the model output, so a doctor can check whether the reasoning
matches clinical sense. In this study older age, larger tumours, more positive nodes and metastasis push risk up, as medicine expects.

## What is "bias" here, and how do we measure it?
* **Equal opportunity**: among patients who die, does the model flag Black and White patients equally often? (recall gap)
* **Burden of false alarms**: among survivors, is one group flagged more? (false-alarm gap)
* **Ranking quality**: does the score separate dying from surviving patients equally well in both groups? (AUC by race)
* **Calibration**: when the model says 20 %, does 20 % die, in each group?

Because only 30 Black patients died, every Black number is fuzzy. We therefore (a) repeat 5-fold cross-validation 5 times over the whole
cohort, (b) bootstrap confidence intervals, and (c) compare strategies *on the same resamples* so we can tell real change from noise.

## The five strategies
1. **Baseline**: race is an input; one threshold.
2. **Race-blind**: delete the race column ("fairness through unawareness").
3. **Reweighing**: give rare race x outcome combinations (e.g. Black patients who died) more weight while training.
4. **Group thresholds**: a separate alarm level per race so each group's recall hits 80 %.
5. **Reweighing + group thresholds**.

## What did we find?
* No measurable recall gap (+0.5 percentage points (95% CI -14.1 to +15.6) baseline), but the interval is wide: we **cannot** rule out a gap of about 14 points either way.
* Black survivors are flagged more often (+5.0 percentage points (95% CI -2.2 to +12.0) baseline), and the gap grows when we evaluate only patients whose outcome is
  settled (+13.6% at >= 36 months of follow-up).
* Removing race changes almost nothing, because the baseline model already ignored it. Reweighing shaved the false-alarm gap slightly and is the cheapest
  mitigation that does not need race at prediction time. Group thresholds were noisy and did not help.
* SHAP explanations are essentially the same for both groups; only the top of the importance ranking (age, nodal status) is stable in the Black group.

## Honest bottom line
The data show *no evidence of a recall disparity* and *some evidence of extra false alarms for Black patients*, and they are too small to settle
either. The right next step is more data (and treatment variables), not more clever mitigation.

## Where things are
| What | Where |
|---|---|
| Run everything | `python run_pipeline.py` |
| Narrated analysis | `breast_cancer_death_fairness.ipynb` |
| Dashboard | `streamlit run app.py` |
| Thesis chapters 3-5 | `Chapters_3_4_5.docx` |
| Model card / data audit | `docs/MODEL_CARD.md`, `docs/DATA_AUDIT.md` |
| Figures and tables | `reports/figures/`, `artifacts/` |
