"""Generate breast_cancer_death_fairness.ipynb (execute it afterwards with nbconvert; see README)."""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
nb = nbf.v4.new_notebook()
cells = []
md = lambda t: cells.append(nbf.v4.new_markdown_cell(t))
code = lambda t: cells.append(nbf.v4.new_code_cell(t))

md("""# Recall-first prediction of death during follow-up in TCGA-BRCA: SHAP explanations and a Black-vs-White fairness audit

**MSc project, Dept. of Computer Science, University of Jos** - *Utilizing SHAP to explain XGBoost for breast cancer* (revised proposal).

This notebook runs the **primary specification** (the revised proposal's Table 3.2 predictors) with the same `brca_xai` package that
`run_pipeline.py` and the dashboard use, and ends by comparing it with the **audit-hardened** specification. Interpretation sentences are *generated from the
results*. Runtime: about 6-7 minutes.

| Section | Proposal item | Question |
|---|---|---|
| 1 | 3.2.1 | Who is in the cohort? |
| 2 | 3.2.2-3.2.3 | Which columns may a model use? What do blanks do? |
| 3 | 3.2.4 | Model, tuning, class imbalance, overfitting control, recall-first threshold |
| 4 | 3.2.5 | Hold-out performance with confidence intervals; baselines |
| 5 | 3.2.6 | SHAP: global, local, fidelity, stability, clinical alignment, race check |
| 6 | extension | Fairness audit and mitigation (Black vs White) |
| 7 | 3.2.11 | Robustness; survival check |
| 8 | - | As-proposed vs audit-hardened specification |""")

code("""import sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "src"))
import numpy as np, pandas as pd, joblib
from IPython.display import display, Image, Markdown
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30); pd.set_option("display.max_colwidth", 90)
from brca_xai import data as D, modeling as M, fairness as F, plots
from brca_xai.pipeline import Study, ART_ROOT
s = Study("proposal")
s.fig = ROOT / "reports" / "notebook_figures" / "proposal"      # the notebook never overwrites the thesis figures or artifacts
def show(name, w=800): display(Image(filename=str(s.fig / name), width=w))
def say(t): display(Markdown(t))""")

md("## 1. Cohort (proposal 3.2.1)")
code("""s.load()
f = s.res["flow"]
say(f"**{f['n_records']:,}** patients, **{f['n_deaths']}** deaths ({f['prevalence']:.1%}). Median follow-up {f['median_followup']:.0f} months (max {f['max_followup']:.0f}); "
    f"{f['living_lt60']:.0%} of living patients have under 60 months of follow-up. Fairness audit groups: {f['n_white']} White ({f['deaths_white']} deaths), "
    f"{f['n_black']} Black ({f['deaths_black']} deaths); {f['n_other']} Asian / race not recorded are used for training only. "
    f"80/20 split: {f['n_dev']} development / **{f['n_test']}** hold-out ({f['test_deaths']} deaths, only {f['test_black_deaths']} of them Black).")
display(s.table1)""")

md("""## 2. Variable selection, leakage control and preprocessing (proposal 3.2.2-3.2.3)

All 38 columns get an explicit decision. The audit then asks whether the *blanks* of the retained columns carry the outcome.""")
code("""display(s.governance.groupby("decision").size().to_frame("columns"))
display(s.governance)""")
code("""display(s.missingness.round(3))
r = s.missingness.set_index("column").loc["RADIATION_THERAPY"]
say(f"*Radiation therapy is blank for {int(r.n_missing)} patients, {r.death_rate_missing:.0%} of whom died, against {r.death_rate_recorded:.0%} when it is recorded. "
    "XGBoost handles blanks natively, so it will learn this: a documentation pattern, not biology.*")""")

md("## 3. Model development (proposal 3.2.4)")
code("""s.tune()
say(f"Bayesian (TPE) search, {s.n_trials} trials, repeated stratified 5-fold CV on the development set. Chosen: depth {s.params['max_depth']}, "
    f"{s.params['n_estimators']} trees, learning rate {s.params['learning_rate']:.3f}. Class weight scale_pos_weight = {s.res['flow']['spw']:.1f} (no oversampling).")
display(s.tuning.head(6)[["max_depth", "n_estimators", "learning_rate", "auc", "fpr_at_80_recall"]].round(3))""")
code("""s.audit_models()
display(s.ladder[["rung", "note", "auc", "pr_auc", "precision_at_80_recall"]].round(3))
plots.fig_leakage(s, s.fig); show("02_leakage_ladder.png", 800)""")
code("""display(s.ablation[["variant", "auc", "pr_auc"]].round(3)); plots.fig_ablation(s, s.fig); show("24_artefact_ablation.png", 800)
display(s.spec_table[["spec", "n_features", "auc", "pr_auc", "fpr_at_80_recall"]].round(3))
say("*Part of the proposal specification's discrimination is documentation, not biology. Sections 4-6 therefore report the specification as proposed and the audit-hardened one side by side.*")""")
code("""display(s.bench.round(3)); plots.fig_benchmark(s, s.fig); show("03_model_benchmark.png", 900)""")

md("## 4. Hold-out performance, baselines, recall-first threshold, overfitting (proposal 3.2.4-3.2.5)")
code("""s.holdout()
tm = s.test_metrics
pv = tm.assign(v=tm.apply(lambda r: f"{r.estimate:.3f}" + ("" if pd.isna(r.lo) else f" [{r.lo:.3f}, {r.hi:.3f}]"), axis=1)).pivot(index="model", columns="metric", values="v")
display(pv[["recall", "precision", "f1", "accuracy", "balanced_accuracy", "auc_roc", "pr_auc", "flag_rate"]])
say(f"Always predicting 'living' scores {1 - s.y[~s.dev].mean():.1%} accuracy - so accuracy is read against that; PR-AUC against the no-skill value {s.y[~s.dev].mean():.2f}.")
display(s.test_confusion)""")
code("""display(s.rule_table.round(3))
plots.fig_pr(s, s.fig); show("22_precision_recall.png", 520)
say("*The proposal asks to 'maximise recall at an acceptable precision'. Here that is operationalised as: catch >= 80 % of deaths, then check the precision floor (1.25 x prevalence). "
    "Any rule that ignores recall (Youden, F2, 0.5) gives up most deaths.*")""")
code("""display(s.curve.iloc[::6].round(3)); plots.fig_learning_curve(s, s.fig); show("21_learning_curve.png", 520)
plots.fig_test_forest(s, s.fig); show("23_test_forest.png", 950)""")

md("""## 5. SHAP explanations and their quality (proposal 3.2.6)""")
code("""s.fairness(); s.sweep(); s.sensitivity(); s.final_models(); s.explain(); s.headline()
eq = s.res["explain_quality"]
say(f"**Fidelity**: max |base + sum(SHAP) - model margin| = {eq['fidelity']['max_abs_error']:.1e} over {eq['fidelity']['n']} patients. "
    f"**Stability**: mean Spearman across 10 CV-fold models {eq['fold_stability']['mean_spearman']:.2f} (min {eq['fold_stability']['min_spearman']:.2f}); across bootstraps {eq['bootstrap_stability']:.2f}. "
    f"**Agreement with XGBoost gain importance**: {eq['builtin']['gain']:.2f}.")
display(s.alignment); display(s.direction.round(3))""")
code("""plots.fig_shap_global(s, s.fig); show("12_shap_beeswarm.png", 700)
plots.fig_dependence(s, s.fig); show("14_dependence.png", 1000)
plots.fig_deletion(s, s.fig); show("26_deletion_test.png", 450)""")
code("""plots.fig_waterfalls(s, s.fig)
for n in ["true_positive_black", "false_negative_black", "true_negative_white"]:
    show(f"15_waterfall_{n}.png", 520)""")
code("""say("**Race check (proposal 3.2.6 'fairness check').** Mean attribution of the race columns, by whether race was recorded:")
display(s.race_shap.round(3)); plots.fig_race_missing(s, s.fig); show("25_race_missing_signal.png", 700)""")

md("""## 6. Fairness audit and mitigation (extension)

5 strategies x 5 repeats x 5-fold CV on all patients; fairness metrics on the White and Black patients. Gap = Black minus White.
Recall gap = equal opportunity (0 is fair); false-alarm gap > 0 means Black survivors are flagged more often.""")
code("""t = s.summary[s.summary.metric.isin(["tpr_W", "tpr_B", "tpr_gap", "fpr_W", "fpr_B", "fpr_gap", "eod", "flag_all"])]
t = t.assign(v=t.apply(lambda r: f"{r.estimate:.3f} [{r.lo:.3f}, {r.hi:.3f}]", axis=1)).pivot(index="strategy", columns="metric", values="v")
display(t.loc[[x.key for x in s.strategies]])
plots.fig_group_rates(s, s.fig); show("05_rates_by_race.png", 1000); plots.fig_gaps(s, s.fig); show("06_gap_forest.png", 1000)""")
code("""display(s.paired.round(3))
r = s.res["cv"]["aware"]
say(f"**Baseline:** recall gap {r['tpr_gap']:+.3f} (95% CI {r['tpr_gap_ci'][0]:+.3f} to {r['tpr_gap_ci'][1]:+.3f}); false-alarm gap {r['fpr_gap']:+.3f} (CI {r['fpr_gap_ci'][0]:+.3f} to {r['fpr_gap_ci'][1]:+.3f}). "
    f"With {s.res['flow']['deaths_black']} Black deaths the recall CI is about +-{(r['tpr_gap_ci'][1]-r['tpr_gap_ci'][0])/2:.2f}: a gap of that size cannot be excluded.")
display(s.auc_group.round(3)); display(s.calibration.round(3)); display(s.cv_thresholds.round(3))
plots.fig_roc(s, s.fig); show("04_roc_by_group.png", 450); plots.fig_tradeoff(s, s.fig); show("07_tradeoff.png", 550)""")
code("""display(s.imp_group.round(3)); plots.fig_importance_group(s, s.fig); show("13_importance_by_race.png", 650)
display(s.gap_decomp.round(3)); plots.fig_gap_decomp(s, s.fig); show("16_risk_gap_decomposition.png", 650)
plots.fig_profile(s, s.fig); show("17_missed_deaths_profile.png", 950)
plots.fig_stability(s, s.fig); show("18_shap_stability_black.png", 650)
plots.fig_mitigation_explanations(s, s.fig); show("19_explanations_under_mitigation.png", 650); print(s.agreement)""")

md("## 7. Robustness (proposal 3.2.11 and sensitivity analyses)")
code("""display(s.sweep_table[s.sweep_table.metric.isin(["tpr_gap", "fpr_gap"])].pivot_table(index=["metric", "strategy"], columns="target", values="estimate").round(3))
plots.fig_sweep(s, s.fig); show("08_recall_target_sweep.png", 950)""")
code("""display(s.sensitivity_table[s.sensitivity_table.metric.isin(["tpr_gap", "fpr_gap"]) & s.sensitivity_table.strategy.isin(["aware", "blind", "reweigh"])].round(3))
display(s.ancestry_table.round(3)); plots.fig_sensitivity(s, s.fig); show("11_sensitivity_settled.png", 950)
sv = s.res["survival"]
say(f"**Survival check (beyond the proposal's scope).** Harrell C-index, 3x5-fold CV: binary XGBoost score {sv['c_index_binary']:.3f}; XGBoost Cox survival objective {sv['c_index_cox']:.3f}. "
    "The binary label gives away little ranking information at this sample size.")""")

md("## 8. Compare with the audit-hardened specification (read from the saved run; this notebook does not overwrite any artifact)")
code("""h = joblib.load(ART_ROOT / "hardened" / "_study.joblib")
rows = []
for name, st_ in [("As proposed (Table 3.2)", s), ("Audit-hardened", h)]:
    o = st_.res["cv_overall"]["aware"]; c = st_.res["cv"]["aware"]
    rows.append({"specification": name, "AUC-ROC": o["auc_roc"][0], "PR-AUC": o["pr_auc"][0], "recall": o["recall"][0], "precision": o["precision"][0],
                 "flagged": o["flag_rate"][0], "recall gap B-W": c["tpr_gap"], "false-alarm gap B-W": c["fpr_gap"], "top SHAP feature": st_.alignment.feature.iloc[0]})
display(pd.DataFrame(rows).round(3))""")
code("""say("### Findings (generated)\\n"
    f"* As proposed: AUC {s.res['cv_overall']['aware']['auc_roc'][0]:.2f}, PR-AUC {s.res['cv_overall']['aware']['pr_auc'][0]:.2f} (no-skill {s.res['flow']['prevalence']:.2f}); audit-hardened: AUC {h.res['cv_overall']['aware']['auc_roc'][0]:.2f}.\\n"
    f"* Top SHAP feature as proposed: **{s.alignment.feature.iloc[0]}**; hardened: **{h.alignment.feature.iloc[0]}**.\\n"
    f"* Recall gap (as proposed) {s.res['cv']['aware']['tpr_gap']:+.3f}, CI {s.res['cv']['aware']['tpr_gap_ci'][0]:+.3f} to {s.res['cv']['aware']['tpr_gap_ci'][1]:+.3f}; false-alarm gap {s.res['cv']['aware']['fpr_gap']:+.3f}.")""")

nb.cells = cells
nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
out = ROOT / "breast_cancer_death_fairness.ipynb"
nbf.write(nb, out)
print("wrote", out)
