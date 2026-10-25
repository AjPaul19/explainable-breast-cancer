"""Generate breast_cancer_death_fairness.ipynb (then execute it with nbconvert; see README)."""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
nb = nbf.v4.new_notebook()
cells = []
md = lambda t: cells.append(nbf.v4.new_markdown_cell(t))
code = lambda t: cells.append(nbf.v4.new_code_cell(t))

md("""# Recall-first prediction of death during follow-up in TCGA-BRCA, with a Black-vs-White fairness audit

**MSc project, Dept. of Computer Science, University of Jos** - *Utilizing SHAP to explain XGBoost for breast cancer*.
Implementation phase, version 2: new target (death during follow-up), data from `data/data_clinical_patient.csv`, recall-first operating point, and a bias-mitigation study.

The notebook calls the same `brca_xai` package that `run_pipeline.py` and the dashboard use, so numbers here equal the thesis numbers.
Runtime: about 4-5 minutes. Interpretation sentences below are *generated from the results*, never typed in.

| Section | Question |
|---|---|
| 1 | Who is in the cohort? |
| 2 | Which columns may a model use? (leakage and informative missingness) |
| 3 | How good is the model and what does recall-first cost? |
| 4 | Does it treat Black and White patients equally? Does mitigation help? |
| 5 | Are the conclusions robust? |
| 6 | What does the model look at (SHAP), and does it differ by race? |
| 7 | Save artifacts and figures |""")

code("""import sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "src"))
import numpy as np, pandas as pd
from IPython.display import display, Image, Markdown
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30); pd.set_option("display.max_colwidth", 80)
from brca_xai import data as D, modeling as M, fairness as F, plots
from brca_xai.pipeline import Study, FIG
s = Study()
def show(name, w=800): display(Image(filename=str(FIG / name), width=w))
def say(t): display(Markdown(t))""")

md("## 1. Cohort")
code("""s.load()
say(f"**{s.res['flow']['n_records']}** records -> remove {s.res['flow']['n_missing_race']} without race and {s.res['flow']['n_other_race']} Asian / other -> "
    f"**{s.res['flow']['n_cohort']}** White ({s.res['flow']['n_white']}) and Black ({s.res['flow']['n_black']}) patients, "
    f"**{s.res['flow']['deaths']}** deaths ({s.res['flow']['deaths_white']} White, {s.res['flow']['deaths_black']} Black). "
    f"Hold-out test set: {s.res['flow']['n_test']} patients, only **{s.res['flow']['test_black_deaths']}** Black deaths.")
display(s.table1)""")
code("""plots.fig_followup(s, FIG); show("01_survival_followup.png", 900)""")

md("""## 2. Data governance: which columns may a model use?

Every one of the 38 source columns gets an explicit decision. Two traps in this table:
* **Leakage** - follow-up time, other survival endpoints, tumour status at follow-up.
* **Informative missingness** - a blank that predicts death (registry artefact, not biology).""")
code("""display(s.governance.groupby("decision").size().to_frame("columns"))
display(s.governance)""")
code("""display(s.missingness.round(3))""")

md("## 3. Model development")
code("""s.tune()
say(f"Selected hyper-parameters: max_depth={s.params['max_depth']}, n_estimators={s.params['n_estimators']}, learning_rate={s.params['learning_rate']:.3f}")
display(s.tuning.head(8)[["max_depth", "n_estimators", "learning_rate", "auc", "fpr_at_80_recall"]].round(3))""")
code("""s.audit_models()
display(s.ladder[["rung", "note", "auc", "fpr_at_80_recall"]].round(3))
plots.fig_leakage(s, FIG); show("02_leakage_ladder.png", 800)""")
code("""display(s.bench.round(3))
plots.fig_benchmark(s, FIG); show("03_model_benchmark.png", 900)
say("*Logistic regression, random forest and XGBoost reach similar AUC: the ceiling is set by the information in clinical covariates, not by the algorithm.*")""")

md("## 4. Recall-first evaluation on the untouched hold-out set")
code("""s.holdout()
display(s.holdout_table[["strategy", "group", "n", "deaths", "recall", "recall_lo", "recall_hi", "fpr", "flag_rate", "auc"]].round(3))
plots.fig_holdout(s, FIG); show("09_holdout_recall.png", 700)
say(f"*Only {s.res['flow']['test_black_deaths']} Black deaths are in this split - its group-level recall is an anecdote. The fairness conclusions come from the repeated cross-validation below.*")""")

md("""## 5. Fairness audit: 5 strategies x 5 repeats x 5-fold CV, bootstrap intervals

Gap = Black minus White. **Recall gap** is equal opportunity (0 is fair). **False-alarm gap** > 0 means Black survivors are flagged more often.""")
code("""s.fairness(); s.headline()
t = s.summary[s.summary.metric.isin(["tpr_W", "tpr_B", "tpr_gap", "fpr_W", "fpr_B", "fpr_gap", "eod", "flag_all"])]
t = t.assign(v=t.apply(lambda r: f"{r.estimate:.3f} [{r.lo:.3f}, {r.hi:.3f}]", axis=1)).pivot(index="strategy", columns="metric", values="v")
display(t.loc[[x.key for x in M.STRATEGIES]])""")
code("""plots.fig_group_rates(s, FIG); show("05_rates_by_race.png", 1000)
plots.fig_gaps(s, FIG); show("06_gap_forest.png", 1000)""")
code("""display(s.paired.round(3))
r = s.res["cv"]["aware"]
say(f"**Baseline:** recall gap {r['tpr_gap']:+.3f} (95% CI {r['tpr_gap_ci'][0]:+.3f} to {r['tpr_gap_ci'][1]:+.3f}); "
    f"false-alarm gap {r['fpr_gap']:+.3f} (CI {r['fpr_gap_ci'][0]:+.3f} to {r['fpr_gap_ci'][1]:+.3f}). "
    f"The recall CI is about +-{(r['tpr_gap_ci'][1]-r['tpr_gap_ci'][0])/2:.2f}: with {s.res['flow']['deaths_black']} Black deaths a gap of that size cannot be excluded.")""")
code("""display(s.auc_group.round(3)); display(s.calibration.round(3))
display(s.cv_thresholds.round(3))
plots.fig_roc(s, FIG); show("04_roc_by_group.png", 450)
plots.fig_tradeoff(s, FIG); show("07_tradeoff.png", 550)""")

md("## 6. Robustness: recall target, settled outcomes, group definition")
code("""s.sweep()
display(s.sweep_table[s.sweep_table.metric.isin(["tpr_gap", "fpr_gap"])].pivot_table(index=["metric", "strategy"], columns="target", values="estimate").round(3))
plots.fig_sweep(s, FIG); show("08_recall_target_sweep.png", 950)""")
code("""s.sensitivity()
display(s.sensitivity_table[s.sensitivity_table.metric.isin(["tpr_gap", "fpr_gap"]) & s.sensitivity_table.strategy.isin(["aware", "blind", "reweigh"])].round(3))
display(s.ancestry_table.round(3))
plots.fig_sensitivity(s, FIG); show("11_sensitivity_settled.png", 950)""")

md("""## 7. SHAP: what does the model look at, and is it the same for both groups?

SHAP values are in log-odds and add up exactly to each patient's score.""")
code("""s.final_models(); s.explain()
display(s.direction.round(3))
plots.fig_shap_global(s, FIG); show("12_shap_beeswarm.png", 700)
plots.fig_dependence(s, FIG); show("14_dependence.png", 1000)""")
code("""plots.fig_waterfalls(s, FIG)
for n in ["true_positive_black", "false_negative_black", "true_negative_white"]:
    show(f"15_waterfall_{n}.png", 520)""")
code("""display(s.imp_group.round(3))
plots.fig_importance_group(s, FIG); show("13_importance_by_race.png", 650)
display(s.gap_decomp.round(3)); print("total gap in mean log-odds:", round(s.gap_decomp.attrs["total_gap"], 3))
plots.fig_gap_decomp(s, FIG); show("16_risk_gap_decomposition.png", 650)""")
code("""plots.fig_profile(s, FIG); show("17_missed_deaths_profile.png", 950)
plots.fig_stability(s, FIG); show("18_shap_stability_black.png", 650)
plots.fig_mitigation_explanations(s, FIG); show("19_explanations_under_mitigation.png", 650)
print(s.agreement)""")

md("## 8. Save artifacts, figures and the cache the dashboard needs")
code("""import joblib
s.save(); plots.make_all(s); joblib.dump(s, ROOT / "artifacts" / "_study.joblib")
print(sorted(p.name for p in (ROOT / "artifacts").iterdir())[:40])""")
code("""h = s.res["cv"]
say("### Findings (generated)\\n"
    f"* Race-blind model, recall target {h['target_recall']:.0%}: recall {h['blind']['tpr_all']:.1%}, false-positive rate {h['blind']['fpr_all']:.1%}, "
    f"{h['blind']['flag_all']:.0%} of patients flagged.\\n"
    f"* Equal-opportunity gap (baseline): {h['aware']['tpr_gap']:+.3f}, CI {h['aware']['tpr_gap_ci'][0]:+.3f} to {h['aware']['tpr_gap_ci'][1]:+.3f}.\\n"
    f"* False-alarm gap: baseline {h['aware']['fpr_gap']:+.3f}; reweighing {h['reweigh']['fpr_gap']:+.3f}; group thresholds {h['gthr']['fpr_gap']:+.3f}.\\n"
    f"* Black-patient AUC {s.auc_group.query('strategy==\\"blind\\" and group==\\"Black\\"').auc.iloc[0]:.2f} vs White {s.auc_group.query('strategy==\\"blind\\" and group==\\"White\\"').auc.iloc[0]:.2f}.")""")

nb.cells = cells
nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
out = ROOT / "breast_cancer_death_fairness.ipynb"
nbf.write(nb, out)
print("wrote", out)
