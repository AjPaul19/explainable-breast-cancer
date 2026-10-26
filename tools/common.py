"""Helpers shared by the document builders: read artifacts for both specifications, format numbers."""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
KEYS = ["aware", "blind", "reweigh", "gthr", "reweigh_gthr"]
SHORT = {"aware": "Baseline (race-aware)", "blind": "Race-blind", "reweigh": "Reweighing",
         "gthr": "Group thresholds", "reweigh_gthr": "Reweighing + group thresholds"}


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


class Spec:
    """All artifacts of one specification, with small accessors."""

    def __init__(self, name):
        self.name = name
        self.art = ROOT / "artifacts" / name
        self.fig = ROOT / "reports" / "figures" / name
        self.meta = json.loads((self.art / "meta.json").read_text())
        rd = lambda f, **kw: pd.read_csv(self.art / f, **kw)
        self.summary, self.paired = rd("fairness_cv_summary.csv"), rd("fairness_paired_vs_main.csv")
        self.holdout, self.test_metrics = rd("holdout_by_group.csv"), rd("test_metrics.csv")
        self.confusion, self.rules, self.curve = rd("test_confusion.csv"), rd("threshold_rules.csv"), rd("learning_curve.csv")
        self.bench, self.auc_g, self.cal = rd("model_benchmark.csv"), rd("auc_by_group.csv"), rd("calibration_by_group.csv")
        self.sweep, self.sens, self.anc = rd("recall_target_sweep.csv"), rd("sensitivity_settled_outcome.csv"), rd("sensitivity_ancestry.csv")
        self.imp = rd("importance_by_group.csv", index_col=0)
        self.gap = rd("risk_gap_decomposition.csv", index_col=0)
        self.stab = rd("stability_black.csv", index_col=0)
        self.impm = rd("importance_by_model.csv", index_col=0)
        self.direction, self.profile, self.thr = rd("shap_direction_check.csv"), rd("decision_profile.csv"), rd("cv_thresholds.csv")
        self.table1, self.gov, self.miss = rd("table1.csv"), rd("column_governance.csv"), rd("missingness_audit.csv")
        self.cv_overall, self.align, self.race_shap = rd("cv_overall.csv"), rd("clinical_alignment.csv"), rd("race_shap_check.csv")
        self.deletion, self.builtin = rd("deletion_test.csv"), rd("shap_builtin_agreement.csv")
        self.tuning = rd("tuning_results.csv")
        self.msens = rd("model_selection_sensitivity.csv") if (self.art / "model_selection_sensitivity.csv").exists() else None
        self.cohort = rd("cohort.csv")
        if name == "proposal":
            self.ladder, self.ablation, self.specs = rd("leakage_ladder.csv"), rd("artefact_ablation.csv"), rd("spec_comparison.csv")
        self.FL = self.meta["flow"]
        self.P = self.meta["params"]
        self.label = {k: v["label"] for k, v in self.meta["strategies"].items()}

    # fairness cross-validation summary (White / Black rows only)
    def cv(self, strategy, metric):
        r = self.summary[(self.summary.strategy == strategy) & (self.summary.metric == metric)].iloc[0]
        return float(r.estimate), float(r.lo), float(r.hi)

    def ci(self, strategy, metric, signed=False, d=1):
        e, lo, hi = self.cv(strategy, metric)
        if signed:
            return f"{100 * e:+.{d}f} percentage points (95% CI {100 * lo:+.{d}f} to {100 * hi:+.{d}f})"
        return f"{100 * e:.{d}f}% (95% CI {100 * lo:.{d}f} to {100 * hi:.{d}f})"

    def paired_(self, strategy, metric):
        r = self.paired[(self.paired.strategy == strategy) & (self.paired.metric == metric)].iloc[0]
        return float(r.diff_vs_aware), float(r.lo), float(r.hi), float(r.prob_smaller)

    def ho(self, strategy, group):
        return self.holdout[(self.holdout.strategy == strategy) & (self.holdout.group == group)].iloc[0]

    def auc(self, strategy, group):
        r = self.auc_g[(self.auc_g.strategy == strategy) & (self.auc_g.group == group)].iloc[0]
        return float(r.auc), float(r.lo), float(r.hi)

    def ov(self, strategy, metric):
        r = self.cv_overall[(self.cv_overall.strategy == strategy) & (self.cv_overall.metric == metric)].iloc[0]
        return float(r.estimate), float(r.lo), float(r.hi)

    def tm(self, model, metric):
        r = self.test_metrics[(self.test_metrics.model == model) & (self.test_metrics.metric == metric)].iloc[0]
        return float(r.estimate), float(r.lo), float(r.hi)

    def sens_(self, months, strategy, metric):
        r = self.sens[(self.sens.analysis.str.contains(f">= {months} mo", regex=False)) & (self.sens.strategy == strategy) & (self.sens.metric == metric)].iloc[0]
        return float(r.estimate), float(r.lo), float(r.hi)

    def sens_n(self, months):
        return int(self.sens[self.sens.analysis.str.contains(f">= {months} mo", regex=False)].analysis.iloc[0].split("n=")[1])


def load():
    return Spec("proposal"), Spec("hardened")
