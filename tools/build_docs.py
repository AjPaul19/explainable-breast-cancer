"""Generate the Markdown documents in docs/ from the artifacts (so numbers always match the results)."""
import common as C
from common import KEYS, SHORT, pct

P, H = C.load()
DOCS = C.ROOT / "docs"
DOCS.mkdir(exist_ok=True)
FL = P.FL


def md_table(df, floatfmt="{:.3f}"):
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(floatfmt.format(v) if isinstance(v, float) else str(v) for v in r) + " |")
    return "\n".join(out)


def spec_line(S):
    o, c = S.cv_overall, S
    return dict(auc=S.ov("aware", "auc_roc")[0], pr=S.ov("aware", "pr_auc")[0], rec=S.ov("aware", "recall")[0], prec=S.ov("aware", "precision")[0],
                flag=S.ov("aware", "flag_rate")[0])


ps, hs = spec_line(P), spec_line(H)
abl = P.ablation.set_index("variant")
lad = P.ladder
rt = P.missing = P.miss.set_index("column")
rad = rt.loc["RADIATION_THERAPY"]
race_rows = P.race_shap.set_index("patients")
unk = race_rows.loc["race NOT recorded"]
sv = P.meta["survival"]
top_prop, top_hard = P.align.iloc[0], H.align.iloc[0]
radiation_rank = int(P.imp.index.get_loc("radiation") + 1) if "radiation" in P.imp.index else None
gbase = P.cv("aware", "tpr_gap"); fbase = P.cv("aware", "fpr_gap")
hg, hf = H.cv("aware", "tpr_gap"), H.cv("aware", "fpr_gap")

# ------------------------------------------------------------------------------------------ PROPOSAL REVIEW
review = f"""# Review of the revised proposal and how the implementation responds

*Written from the standpoint of the data scientist who built the implementation; every number below is reproduced by `python run_pipeline.py`.*

## 1. What the revision changes (and why it is the right direction)
| Topic | Original proposal | Revised proposal | Verdict |
|---|---|---|---|
| Task | Diagnose benign vs malignant | **Prognosis**: death during follow-up (`OS_STATUS`), all {FL['n_records']:,} TCGA-BRCA patients, {FL['n_deaths']} deaths ({FL['prevalence']:.1%}) | Correct. TCGA-BRCA has no benign cases; the old target could not be built. |
| Leakage | Not addressed | Explicit variable-selection table (Table 3.2); outcome-related columns excluded | Strong improvement; the single most important methodological fix. |
| Imbalance | Not addressed | `scale_pos_weight`, no synthetic oversampling | Appropriate for 13.9 % prevalence. |
| Tuning / overfitting | Hold-out only | Repeated stratified 5-fold CV, Bayesian or grid search, early stopping, train/CV/test comparison | Implemented (Bayesian TPE; learning curve). |
| Threshold | Recall emphasised | Choose on CV predictions to maximise recall at an acceptable precision | Needs an operational definition of "acceptable" (see 3.3). |
| Evaluation | Accuracy, precision, recall, F1, AUC | + PR-AUC, confusion matrix, bootstrap CIs, baselines (LR, RF, stage-only), accuracy vs the 86 % no-skill baseline | Right. With {FL['test_deaths']} test deaths the CIs matter. |
| Explainability | SHAP plots | + fidelity, stability, clinical alignment, race check | Implemented; see Chapter 4. |
| User study | Qualitative or quantitative | Within-subject A (score) vs B (score + SHAP), Likert, Wilcoxon, thematic analysis | Kit built (`userstudy/`); not yet run. |
| Limitations | Generic | Variable follow-up, cause of death, ceiling, single cohort | Honest and accurate: median follow-up {FL['median_followup']:.0f} months and {FL['living_lt60']:.0%} of living patients under 60 months were confirmed in the data. |

## 2. Claims in the proposal that I verified against the data
Median follow-up 27 months (max 283), 79 % of living patients under 60 months, 1,084 patients / 38 variables, 151 deaths (13.9 %), sex 98.9 % female, subtype missing for 103
(9.5 %), ethnicity missing for 169, weight 100 % missing, about 30 test deaths at an 80/20 split: **all correct.**

## 3. Where I would push back (with evidence)
1. **Two retained predictors carry the outcome through their blanks.** *Radiation therapy* is blank for {int(rad.n_missing)} patients, **{rad.death_rate_missing:.0%} of whom died vs {rad.death_rate_recorded:.0%}**
   when recorded; XGBoost's native handling of missing values turns that documentation pattern into a feature. Removing it alone drops cross-validated AUC from
   {abl.loc['Proposal predictors (as specified)', 'auc']:.3f} to {abl.iloc[1].auc:.3f}. In the as-specified model it is the **#{radiation_rank if radiation_rank else '?'} feature by SHAP importance**,
   above nodal status.  Likewise "NX / MX set to missing" gives the model a flag for a code whose death rate is {pct(rt.loc['PATH_N_STAGE = NX', 'death_rate_missing'], 0)} (NX, n = {int(rt.loc['PATH_N_STAGE = NX', 'n_missing'])}).
   **Recommendation:** keep the specification as the primary analysis (it is the approved design) but report the audit-hardened specification next to it, and do not present the higher AUC as clinical signal.
2. **Race as a predictor interacts with missing race.** {FL['n_unknown_race']} patients have no recorded race and an {unk.death_rate:.0%} death rate; with native missing handling the model uses "race not recorded" as a
   low-risk flag: it carries {unk.share_of_total_attribution:.0%} of their total attribution. Race recorded: {race_rows.loc['race recorded'].share_of_total_attribution:.0%}. Asian patients (60, 3 deaths) also receive a
   learned "low risk" effect from three events. The proposal's *fairness check* of race SHAP is therefore essential, and its answer is not "race is unused".
3. **"Acceptable precision" must be defined.** Without a floor, "maximise recall" returns "flag everyone". I operationalised it as: catch >= 80 % of deaths, then require precision >= 1.25 x prevalence
   ({FL['precision_floor']:.2f}); alternative rules are compared in `threshold_rules.csv`: Youden and the default 0.5 catch only {pct(P.rules.recall.iloc[4], 0)} of hold-out deaths.
4. **Early stopping** with only {FL['n_dev']} development patients is noisy; the number of trees is tuned inside CV and checked with a train / CV / test learning curve.
5. **Hold-out intervals are very wide** ({FL['test_deaths']} deaths; {FL['test_black_deaths']} Black). I kept the proposal's hold-out protocol but base the headline numbers and all fairness statements on 5x5 repeated CV.
6. **Wording.** The title, Sections 1.1, 1.2, 1.5 and 2.x still speak of diagnosis, benign/malignant and "diagnostic accuracy", while Chapter 3 is prognostic. Table 2.2 is mostly diagnostic work (WBCD, imaging);
   add prognostic XGBoost / SHAP literature. "Significance of Study" lacks a section number (1.5), and the proposal's "4.0 Conclusion" becomes Chapter 5 of the thesis.
7. **Sample size of the user study** (15-30, paired Wilcoxon) detects only large effects (r about 0.6 at n = 20); state it as exploratory (done) and pre-register the primary outcome (trust, understandability).
8. **Fidelity** of TreeSHAP is guaranteed by construction (local accuracy); keep the check as a unit test but add a *faithfulness* test (deletion) and the stability checks, which I did.

## 4. What I added beyond the revision (flag for supervisors)
* **Black vs White fairness audit and mitigation** (race-blind, reweighing, group thresholds): the revised proposal only has the SHAP race check. It is reported as an *extension*; drop or promote it to an objective as supervisors prefer.
* **Audit-hardened specification** and artefact ablation (Section 3 above).
* **Exploratory survival check** (Cox objective, C-index {sv['c_index_cox']:.3f} vs {sv['c_index_binary']:.3f} for the binary score): the binary label loses little ranking information; the proposal leaves survival modelling to future work.

## 5. Headline results
| | As proposed | Audit-hardened |
|---|---|---|
| AUC-ROC (5x5 CV, all patients) | {ps['auc']:.3f} | {hs['auc']:.3f} |
| PR-AUC (no-skill {FL['prevalence']:.3f}) | {ps['pr']:.3f} | {hs['pr']:.3f} |
| Recall at the 80 % rule | {pct(ps['rec'])} | {pct(hs['rec'])} |
| Precision at that point | {pct(ps['prec'])} | {pct(hs['prec'])} |
| Share of patients flagged | {pct(ps['flag'], 0)} | {pct(hs['flag'], 0)} |
| Recall gap Black - White | {P.ci('aware', 'tpr_gap', True)} | {H.ci('aware', 'tpr_gap', True)} |
| False-alarm gap Black - White | {P.ci('aware', 'fpr_gap', True)} | {H.ci('aware', 'fpr_gap', True)} |
"""
(DOCS / "PROPOSAL_REVIEW.md").write_text(review, encoding="utf-8")

# ------------------------------------------------------------------------------------------ MODEL CARD
rows = []
for k in KEYS:
    rows.append({"Strategy": SHORT[k], "Recall White": pct(P.cv(k, "tpr_W")[0]), "Recall Black": pct(P.cv(k, "tpr_B")[0]),
                 "Recall gap": P.ci(k, "tpr_gap", True), "False-alarm gap": P.ci(k, "fpr_gap", True), "Flagged (W+B)": pct(P.cv(k, "flag_all")[0], 0)})
te = P.test_metrics.pivot(index="model", columns="metric", values="estimate")
card = f"""# Model card: recall-first prediction of death during follow-up (TCGA-BRCA)

*Research prototype for an MSc project (University of Jos, Dept. of Computer Science). Not a medical device. Not validated for clinical use.*

## Intended use
Demonstrate how an XGBoost classifier, explained with SHAP, can be built with a **recall-first** operating point, audited for leakage and informative missingness, and checked for
**racial fairness** (White vs Black / African American patients) on public TCGA-BRCA data. **Out of scope:** real patient-care decisions, triage, insurance or resource allocation.

## Task, label, cohort
* `died = 1` if `OS_STATUS = 1:DECEASED`. Follow-up is censored (median {FL['median_followup']:.0f} months), so the label is *death observed during follow-up*, not "death within N years".
* {FL['n_records']:,} patients, {FL['n_deaths']} deaths ({FL['prevalence']:.1%}). Fairness audit groups: {FL['n_white']} White ({FL['deaths_white']} deaths), {FL['n_black']} Black ({FL['deaths_black']} deaths); {FL['n_other']} Asian / race-not-recorded patients are used for training only.
* Split: stratified 80/20 ({FL['n_dev']} development / {FL['n_test']} hold-out).

## Inputs (revised proposal, Table 3.2)
Age, pathologic T / N / M (TX, NX, MX = missing), PAM50 subtype (not called = missing), histology group, prior diagnosis, neoadjuvant therapy, radiation therapy (blank = missing), race.
**Excluded:** follow-up time, other survival endpoints, tumour status and new-tumour events at follow-up, composite stage, days to birth, ancestry, ethnicity, administrative fields.
**Audit-hardened specification** (sensitivity): drops radiation and neoadjuvant therapy, sets NX / MX to N0 / M0. See `docs/DATA_AUDIT.md`.

## Model
XGBoost, depth {P.P['max_depth']}, {P.P['n_estimators']} trees, learning rate {P.P['learning_rate']:.3f}; `scale_pos_weight` = negatives / positives; monotone non-decreasing in T, N, M; Bayesian (TPE) search with repeated
5-fold CV minimising FPR at 80 % recall. Tree SHAP.

## Operating point (recall first)
Threshold = highest score that still catches **80 %** of deaths on out-of-fold training predictions (global: {P.meta['thresholds']['aware']['global']:.3f}). Precision floor 1.25 x prevalence = {FL['precision_floor']:.2f}.

## Performance
| | As proposed | Audit-hardened |
|---|---|---|
| AUC-ROC (5x5 CV) | {ps['auc']:.3f} | {hs['auc']:.3f} |
| PR-AUC | {ps['pr']:.3f} | {hs['pr']:.3f} |
| Recall / precision / flagged | {pct(ps['rec'])} / {pct(ps['prec'])} / {pct(ps['flag'], 0)} | {pct(hs['rec'])} / {pct(hs['prec'])} / {pct(hs['flag'], 0)} |

Hold-out ({FL['n_test']} patients, {FL['test_deaths']} deaths), as proposed: recall {te.loc['XGBoost (race-aware, primary)', 'recall']:.2f}, precision {te.loc['XGBoost (race-aware, primary)', 'precision']:.2f},
AUC {te.loc['XGBoost (race-aware, primary)', 'auc_roc']:.2f}, PR-AUC {te.loc['XGBoost (race-aware, primary)', 'pr_auc']:.2f}; accuracy {te.loc['XGBoost (race-aware, primary)', 'accuracy']:.2f} versus {1 - FL['test_deaths'] / FL['n_test']:.2f} for always predicting "living".
Intervals: `artifacts/proposal/test_metrics.csv`.

## Fairness audit (as proposed; Black minus White; 5x5 CV with bootstrap CI)
{md_table(__import__('pandas').DataFrame(rows))}

**Reading:** no gap is statistically distinguishable from zero, and with {FL['deaths_black']} Black deaths the recall-gap interval is about +-{100 * (P.cv('aware', 'tpr_gap')[2] - P.cv('aware', 'tpr_gap')[1]) / 2:.0f} points. Point estimates also depend on model selection:
across near-equivalent tuned configurations the baseline recall gap ranges from {100 * P.msens[(P.msens.strategy == 'aware') & (P.msens.metric == 'tpr_gap')].estimate.min():+.1f} to {100 * P.msens[(P.msens.strategy == 'aware') & (P.msens.metric == 'tpr_gap')].estimate.max():+.1f} points.
Stable across configurations: removing race lowers the recall gap (Black recall falls), and group thresholds hold it near zero. The baseline uses the Black indicator and, more heavily, *race not recorded*; see `docs/PROPOSAL_REVIEW.md`.

## Limitations
1. Small group: {FL['deaths_black']} Black deaths; the hold-out set holds {FL['test_black_deaths']}.
2. Censoring: survivors with short follow-up may still die; treatment other than radiation / neoadjuvant is absent.
3. Blank-field artefacts raise the as-proposed AUC; use the hardened model for any real use.
4. Single cohort (TCGA), no external validation. Race is a social label; ancestry analysis is small.
5. Group thresholds use race at prediction time, which may be unacceptable in some settings.
6. Clinician study (Objective 4) not yet run.

## Reproduce
`pip install -r requirements.txt && python run_pipeline.py && streamlit run app.py`
"""
(DOCS / "MODEL_CARD.md").write_text(card, encoding="utf-8")

# ------------------------------------------------------------------------------------------ DATA AUDIT
lad_t = lad[["rung", "note", "auc", "pr_auc", "precision_at_80_recall"]].copy()
lad_t.columns = ["Feature set", "Why", "AUC", "PR-AUC", "Precision at 80% recall"]
miss = P.miss.reset_index(drop=True).copy()
miss.columns = ["Column / code", "n", "% of cohort", "Death rate if missing", "Death rate if recorded"]
audit = f"""# Data audit

Source: `data/data_clinical_patient.csv` (cBioPortal, TCGA PanCancer Atlas BRCA clinical patient table, 1,084 rows x 38 columns) with `data/clinical_data_dictionary.xlsx`.

## Cohort
{FL['n_records']:,} patients; {FL['n_deaths']} deaths ({FL['prevalence']:.1%}); {FL['n_white']} White, {FL['n_black']} Black, {FL['n_asian']} Asian, {FL['n_unknown_race']} race not recorded (+1 Native American, counted as not recorded).
Development / hold-out: {FL['n_dev']} / {FL['n_test']} ({FL['test_black']} Black patients and {FL['test_black_deaths']} Black deaths in the hold-out).

## Column governance (revised proposal Table 3.2 plus audit notes)
{md_table(P.gov)}

## Evidence 1: blanks that carry the outcome
{md_table(miss)}

## Evidence 2: where the as-proposed AUC comes from
{md_table(P.ablation[['variant', 'auc', 'pr_auc']])}

## Evidence 3: the leakage ladder
{md_table(lad_t)}

## Evidence 4: specifications compared
{md_table(P.specs[['spec', 'n_features', 'auc', 'pr_auc', 'fpr_at_80_recall', 'precision_at_80_recall']])}

## Other checks
* IDs unique; T, N, M parsed to ordinals (`T1C -> 1`, `N1MI -> 1`, `N0 (I+) -> 0`, `cM0 (I+) -> 0`); stage group parsed from `AJCC_PATHOLOGIC_TUMOR_STAGE` for the stage-group sensitivity model.
* PAM50 missing for {int(rt.loc['SUBTYPE', 'n_missing'])} patients (death rate {pct(rt.loc['SUBTYPE', 'death_rate_missing'])} vs {pct(rt.loc['SUBTYPE', 'death_rate_recorded'])}); complete-case sensitivity analysis in the specs table.
* Race not recorded: {int(rt.loc['RACE', 'n_missing'])} patients, death rate {pct(rt.loc['RACE', 'death_rate_missing'])} vs {pct(rt.loc['RACE', 'death_rate_recorded'])}.
"""
(DOCS / "DATA_AUDIT.md").write_text(audit, encoding="utf-8")

# ------------------------------------------------------------------------------------------ EXPLAINER
expl = f"""# The project in plain language

## The question
*From what doctors know about a breast-cancer patient at diagnosis, can a model warn us who is likely to die during follow-up without missing many of them, can we see why it says so, and does it work equally well for Black and White patients?*

## Why "recall first"?
With 100 patients, about 14 die. **Recall** is how many of those 14 the model catches. A missed death is a disaster, an extra check-up a nuisance, so the alarm level is set to catch **80 %** of deaths,
not at the default 50 % (which would flag almost nobody). The price: about {pct(ps['flag'], 0)} of patients get flagged and only about {pct(ps['prec'], 0)} of those flagged die.

## What does the model look at?
Age, tumour size (T), lymph nodes (N), spread (M), molecular subtype (PAM50), histology, prior cancer, neoadjuvant therapy, radiation therapy and race (the revised proposal's list). It never sees follow-up time or anything recorded after diagnosis.

## A warning about blanks
Radiation therapy is blank for {int(rad.n_missing)} patients, and {pct(rad.death_rate_missing, 0)} of them died (against {pct(rad.death_rate_recorded, 0)} when it is recorded). A blank is not "no radiation": it is a registry gap that happens to
go with death. A model that learns "blank means danger" looks better ({ps['auc']:.2f} AUC) than one that cannot ({hs['auc']:.2f}), without knowing more about cancer. We report both and recommend the second for any real use.

## What is SHAP?
SHAP splits each prediction into contributions ("older age added this much; node-negative subtracted that much") that add up exactly to the model's output. We check it three ways: **fidelity** (the sums are exact), **stability**
(the same features rank on top when the data are resampled) and **clinical alignment** (the top features should be what oncologists expect). In the as-proposed model the top feature is **{top_prop.feature}**, which is *not* a clinical
factor; in the hardened model it is **{top_hard.feature}**.

## Bias
We measure, for Black versus White patients: **recall** (among those who die, how many are flagged), **false-alarm rate** (among survivors, how many are flagged), ranking quality (AUC) and calibration. With only {FL['deaths_black']} Black deaths every Black number is fuzzy, so
we use repeated cross-validation, bootstrap intervals and compare strategies on the same resamples. Strategies: baseline (race as input), race-blind, reweighing, group thresholds, reweighing + group thresholds.

**Finding (as proposed):** recall gap {P.ci('aware', 'tpr_gap', True)}; false-alarm gap {P.ci('aware', 'fpr_gap', True)}: neither is distinguishable from zero. Removing race or re-weighting the training data *lowers* Black recall in return for fewer false alarms; separate alarm levels per group keep both gaps near zero.

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
"""
(DOCS / "EXPLAINER.md").write_text(expl, encoding="utf-8")
print("docs written")
