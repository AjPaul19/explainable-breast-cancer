"""Helpers shared by the document builders: read artifacts, format numbers."""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"
FIG = ROOT / "reports" / "figures"
sys.path.insert(0, str(ROOT / "src"))

META = json.loads((ART / "meta.json").read_text())
SUMMARY = pd.read_csv(ART / "fairness_cv_summary.csv")
PAIRED = pd.read_csv(ART / "fairness_paired_vs_aware.csv")
HOLDOUT = pd.read_csv(ART / "holdout_by_group.csv")
LADDER = pd.read_csv(ART / "leakage_ladder.csv")
BENCH = pd.read_csv(ART / "model_benchmark.csv")
AUCG = pd.read_csv(ART / "auc_by_group.csv")
CAL = pd.read_csv(ART / "calibration_by_group.csv")
SWEEP = pd.read_csv(ART / "recall_target_sweep.csv")
SENS = pd.read_csv(ART / "sensitivity_settled_outcome.csv")
ANC = pd.read_csv(ART / "sensitivity_ancestry.csv")
IMP = pd.read_csv(ART / "importance_black_vs_white.csv", index_col=0)
GAP = pd.read_csv(ART / "risk_gap_decomposition.csv", index_col=0)
STAB = pd.read_csv(ART / "stability_black.csv", index_col=0)
DIRN = pd.read_csv(ART / "shap_direction_check.csv")
PROFILE = pd.read_csv(ART / "decision_profile.csv")
THR = pd.read_csv(ART / "cv_thresholds.csv")
TABLE1 = pd.read_csv(ART / "table1.csv")
GOV = pd.read_csv(ART / "column_governance.csv")
MISS = pd.read_csv(ART / "missingness_audit.csv")
IMPM = pd.read_csv(ART / "importance_by_model.csv", index_col=0)

LABEL = {k: v["label"] for k, v in META["strategies"].items()}
SHORT = {"aware": "Baseline (race-aware)", "blind": "Race-blind", "reweigh": "Reweighing",
         "gthr": "Group thresholds", "reweigh_gthr": "Reweighing + group thresholds"}
FL = META["flow"]


def cv(strategy, metric):
    r = SUMMARY[(SUMMARY.strategy == strategy) & (SUMMARY.metric == metric)].iloc[0]
    return float(r.estimate), float(r.lo), float(r.hi)


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def pp(x, d=1):
    return f"{100 * x:+.{d}f} points"


def ci(strategy, metric, signed=False, d=1):
    e, lo, hi = cv(strategy, metric)
    if signed:
        return f"{100 * e:+.{d}f} percentage points (95% CI {100 * lo:+.{d}f} to {100 * hi:+.{d}f})"
    return f"{100 * e:.{d}f}% (95% CI {100 * lo:.{d}f} to {100 * hi:.{d}f})"


def paired(strategy, metric):
    r = PAIRED[(PAIRED.strategy == strategy) & (PAIRED.metric == metric)].iloc[0]
    return float(r.diff_vs_aware), float(r.lo), float(r.hi), float(r.prob_smaller)


def ho(strategy, group):
    return HOLDOUT[(HOLDOUT.strategy == strategy) & (HOLDOUT.group == group)].iloc[0]


def auc_g(strategy, group):
    r = AUCG[(AUCG.strategy == strategy) & (AUCG.group == group)].iloc[0]
    return float(r.auc), float(r.lo), float(r.hi)


def sens(months, strategy, metric):
    key = f">= {months} mo"
    r = SENS[(SENS.analysis.str.contains(key, regex=False)) & (SENS.strategy == strategy) & (SENS.metric == metric)].iloc[0]
    return float(r.estimate), float(r.lo), float(r.hi)


def sens_n(months):
    a = SENS[SENS.analysis.str.contains(f">= {months} mo", regex=False)].analysis.iloc[0]
    return int(a.split("n=")[1])
