"""Generate the Markdown documents in docs/ from the artifacts (so numbers always match the results)."""
import common as C
from common import ci, cv, pct, paired, ho, auc_g, FL, META

DOCS = C.ROOT / "docs"
DOCS.mkdir(exist_ok=True)
P = META["params"]
MED = C.pd.read_csv(C.ART / "cohort.csv").followup_months.median()
tw, tb = META["thresholds"]["blind"]["White"], META["thresholds"]["blind"]["Black"]
tg = META["thresholds"]["blind"]["global"]


def md_table(df, floatfmt="{:.3f}"):
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(floatfmt.format(v) if isinstance(v, float) else str(v) for v in r) + " |")
    return "\n".join(out)


# ------------------------------------------------------------------------------------------ MODEL CARD
rows = []
for k in ["aware", "blind", "reweigh", "gthr", "reweigh_gthr"]:
    rows.append({"Strategy": C.SHORT[k], "Recall White": pct(cv(k, "tpr_W")[0]), "Recall Black": pct(cv(k, "tpr_B")[0]),
                 "Recall gap": ci(k, "tpr_gap", True), "False-alarm gap": ci(k, "fpr_gap", True),
                 "Flagged overall": pct(cv(k, "flag_all")[0])})
card = f"""# Model card: recall-first prediction of death during follow-up (TCGA-BRCA)

*Research prototype for an MSc project (University of Jos, Dept. of Computer Science). Not a medical device. Not validated for clinical use.*

## Intended use
Demonstrate how an XGBoost classifier, explained with SHAP, can be built with a **recall-first** operating point and audited
for **racial fairness** (White vs Black / African American patients) on public TCGA-BRCA data.
**Out of scope:** any real patient-care decision, triage, insurance or resource-allocation use.

## Task and label
* Binary: `died = 1` if `OS_STATUS = 1:DECEASED` (death at any time during follow-up). Follow-up is censored and varies (median
  {MED:.0f} months), so the label is *death observed during follow-up*, not "death within N years".
* Cohort: {FL['n_cohort']} patients with self-reported White ({FL['n_white']}) or Black ({FL['n_black']}) race; {FL['deaths']} deaths
  ({FL['deaths_white']} White, {FL['deaths_black']} Black). {FL['n_missing_race']} patients with missing race and {FL['n_other_race']} Asian / other were
  excluded from the fairness cohort.

## Inputs (all known at diagnosis)
Age, pathologic T, N, M category, PAM50 subtype (unknown allowed), histology (ductal / lobular / other), prior malignancy.
The baseline model also receives a Black-race indicator; it ended up with a mean |SHAP| of
{C.IMPM.loc['race_black', 'aware']:.3f} (the model never uses it).
**Deliberately excluded:** follow-up time, disease-specific / disease-free / progression endpoints, tumour status and new-tumour events at
follow-up, radiation, ethnicity and node-assessment fields (blank patterns that track the outcome). See `docs/DATA_AUDIT.md`.

## Model
XGBoost (`max_depth={P['max_depth']}`, `n_estimators={P['n_estimators']}`, `learning_rate={P['learning_rate']:.3f}`), monotone
non-decreasing in T, N and M (clinical prior), hyper-parameters chosen on a development set by 4x5-fold CV to minimise the
false-positive rate at 80 % recall. Tree SHAP explanations.

## Operating point (recall first)
Threshold = highest risk score that still catches **80 %** of deaths on out-of-fold training predictions.
Race-blind model: {pct(tg)} global; {pct(tw)} (White) and {pct(tb)} (Black) when thresholds are set per group.

## Performance (5 x 5-fold repeated CV over the cohort; bootstrap 95 % CI)
* AUC {auc_g('blind', 'All')[0]:.2f} (White {auc_g('blind', 'White')[0]:.2f}, Black {auc_g('blind', 'Black')[0]:.2f}; Black interval {auc_g('blind', 'Black')[1]:.2f}-{auc_g('blind', 'Black')[2]:.2f}).
* Recall {ci('blind', 'tpr_all')}; false-positive rate {ci('blind', 'fpr_all')}. The model flags roughly two in three patients to catch four in five deaths.
* Discrimination is modest; this is a limit of the information in clinical covariates, not of the algorithm (logistic regression and random forest do no better).

## Fairness audit
{md_table(pd_rows := __import__('pandas').DataFrame(rows))}

Gap = Black minus White. Recall gap near zero means equal opportunity; a positive false-alarm gap means Black survivors are flagged more often.
**Reading:** no measurable recall gap, but with {FL['deaths_black']} Black deaths the CI spans about ±14 points, so a real gap cannot be excluded. The
false-alarm gap is positive in every strategy; it widens when evaluation is limited to patients with settled outcomes. Reweighing gave the only
paired-bootstrap-supported improvement (false-alarm gap {paired('reweigh', 'fpr_gap')[0]:+.3f}, CI {paired('reweigh', 'fpr_gap')[1]:+.3f} to {paired('reweigh', 'fpr_gap')[2]:+.3f}).
Group-specific thresholds did **not** help: the Black threshold is estimated from ~30 deaths and is noisy.

## Limitations
1. Small group: 30 Black deaths. Hold-out test set holds {FL['test_black_deaths']} Black deaths, so single-split numbers are anecdotes.
2. Censoring: survivors with short follow-up may still die; "false alarms" are partly future deaths. Treatment (surgery, chemotherapy, endocrine therapy) is absent from the data.
3. TCGA is not population-representative; no external validation.
4. Race is a social construct used here only to *audit* disparities; genetic-ancestry sensitivity analysis is in `artifacts/sensitivity_ancestry.csv` (also small).
5. Group-specific thresholds use race at prediction time, which may be legally or ethically unacceptable in some settings.

## Reproduce
`pip install -r requirements.txt && python run_pipeline.py && streamlit run app.py`
"""
(DOCS / "MODEL_CARD.md").write_text(card, encoding="utf-8")

# ------------------------------------------------------------------------------------------ DATA AUDIT
lad = C.LADDER[["rung", "note", "auc", "fpr_at_80_recall"]].copy()
lad.columns = ["Feature set", "Why", "AUC", "FPR @ 80% recall"]
miss = C.MISS.copy()
miss.columns = ["Column / code", "n", "% of cohort", "Death rate if missing", "Death rate if recorded"]
audit = f"""# Data audit

Source: `data/data_clinical_patient.csv` (cBioPortal, TCGA PanCancer Atlas BRCA clinical patient table, 1,084 rows x 38 columns) with the
definitions in `data/clinical_data_dictionary.xlsx`.

## Cohort flow
| Step | n |
|---|---|
| Records in file | {FL['n_records']} |
| Race not recorded | -{FL['n_missing_race']} |
| Asian / American Indian | -{FL['n_other_race']} |
| **Study cohort (White or Black)** | **{FL['n_cohort']}** ({FL['n_white']} White, {FL['n_black']} Black) |
| Deaths | {FL['deaths']} ({FL['deaths_white']} White, {FL['deaths_black']} Black) |
| Development / hold-out | {FL['n_dev']} / {FL['n_test']} (hold-out: {FL['test_black']} Black patients, {FL['test_black_deaths']} deaths) |

## What each column is allowed to do
{md_table(C.GOV[['column', 'decision', 'reason']])}

## Evidence 1: informative missingness
A blank is not neutral if it predicts the outcome. Death rates inside the White + Black cohort:

{md_table(miss)}

Consequences: radiation, ethnicity and the node-presentation field are dropped; `NX` is treated as N0 and `MX` as M0 (AJCC convention),
so the model cannot reward "not assessed".

## Evidence 2: the leakage ladder
Cross-validated AUC of the same XGBoost as columns that should not be inputs are added back:

{md_table(lad)}

An unprotected analysis would report AUC around 0.9 and look excellent; none of that is prediction (follow-up time is blank for every patient who died).

## Other checks
* Patient IDs unique (0 duplicates); T, N, M parsed to ordinal categories (`T1C -> 1`, `N1MI -> 1`, `N0 (I+) -> 0`, `CM0 (I+) -> M0`); TX (3 patients) stays missing.
* PAM50 subtype is missing for {int(C.MISS.set_index('column').loc['SUBTYPE', 'n_missing'])} patients; XGBoost treats unknown natively. The missing group's death rate is {pct(C.MISS.set_index('column').loc['SUBTYPE', 'death_rate_missing'])} vs {pct(C.MISS.set_index('column').loc['SUBTYPE', 'death_rate_recorded'])}: a mild shift, kept as `unknown`.
* `WEIGHT` is 100 % empty. `SEX`: 12 male patients, not modelled.
* Follow-up is similar across races (median {C.TABLE1.set_index('characteristic').loc['Follow-up months, median (IQR)', 'White']} months White vs {C.TABLE1.set_index('characteristic').loc['Follow-up months, median (IQR)', 'Black']} Black).
"""
(DOCS / "DATA_AUDIT.md").write_text(audit, encoding="utf-8")

# ------------------------------------------------------------------------------------------ EXPLAINER
expl = f"""# The project in plain language

## What question are we asking?
*Given what doctors know about a breast-cancer patient at diagnosis, can a model warn us who is likely to die during follow-up, without
missing many of them, and does it do this equally well for Black and White patients?*

## Why "recall first"?
Imagine 100 patients, 15 of whom will die. **Recall** is how many of those 15 the model catches. A missed death (false negative) is a
disaster; an unnecessary extra check-up (false positive) is a nuisance. So we do not use the default "flag if risk > 50 %" rule (that would
flag almost nobody, because most patients survive). We pick the threshold that catches **80 %** of deaths and accept the price: about two
thirds of patients get flagged ({ci('blind', 'fpr_all')} of survivors).

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

Because only {FL['deaths_black']} Black patients died, every Black number is fuzzy. We therefore (a) repeat 5-fold cross-validation 5 times over the whole
cohort, (b) bootstrap confidence intervals, and (c) compare strategies *on the same resamples* so we can tell real change from noise.

## The five strategies
1. **Baseline**: race is an input; one threshold.
2. **Race-blind**: delete the race column ("fairness through unawareness").
3. **Reweighing**: give rare race x outcome combinations (e.g. Black patients who died) more weight while training.
4. **Group thresholds**: a separate alarm level per race so each group's recall hits 80 %.
5. **Reweighing + group thresholds**.

## What did we find?
* No measurable recall gap ({ci('aware', 'tpr_gap', True)} baseline), but the interval is wide: we **cannot** rule out a gap of about 14 points either way.
* Black survivors are flagged more often ({ci('aware', 'fpr_gap', True)} baseline), and the gap grows when we evaluate only patients whose outcome is
  settled ({C.sens(36, 'aware', 'fpr_gap')[0]:+.1%} at >= 36 months of follow-up).
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
"""
(DOCS / "EXPLAINER.md").write_text(expl, encoding="utf-8")
print("docs written")
