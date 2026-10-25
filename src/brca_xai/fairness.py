"""Group-fairness evaluation for a recall-first classifier (White = reference, Black = focus group).

Primary criterion: **equal opportunity** - the share of patients who die that the model flags
(recall / TPR) should not depend on race.  Because the clinical cost of a missed death is far larger
than that of a false alarm, we also report the false-positive rate (burden of over-flagging) and
the equalised-odds difference max(|dTPR|, |dFPR|).

Evaluation is a repeated, stratified K-fold cross-validation over the whole cohort (the Black
sub-group has only 30 deaths, so a single hold-out split gives uselessly wide intervals) with
patient-level bootstrap confidence intervals.  Paired bootstrap differences between strategies use
the same resamples, so "did mitigation help?" gets its own interval.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold

from . import data as D
from . import modeling as M

W, B = D.PRIVILEGED, D.UNPRIVILEGED


# --------------------------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------------------------
def wilson(k: float, n: float, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def _counts(y, flag):
    tp = int(((y == 1) & (flag == 1)).sum()); fn = int(((y == 1) & (flag == 0)).sum())
    fp = int(((y == 0) & (flag == 1)).sum()); tn = int(((y == 0) & (flag == 0)).sum())
    return tp, fn, fp, tn


def rates(y: np.ndarray, flag: np.ndarray) -> dict:
    tp, fn, fp, tn = _counts(y, flag)
    div = lambda a, b: a / b if b else np.nan
    return dict(n=len(y), deaths=tp + fn, tp=tp, fn=fn, fp=fp, tn=tn, recall=div(tp, tp + fn),
                specificity=div(tn, tn + fp), fpr=div(fp, fp + tn), ppv=div(tp, tp + fp),
                flag_rate=div(tp + fp, len(y)), miss_rate=div(fn, tp + fn))


def group_table(y: np.ndarray, flag: np.ndarray, group: np.ndarray) -> pd.DataFrame:
    """One decision vector -> overall / White / Black rates with Wilson CI on recall."""
    rows = []
    for name, m in [("All", np.ones(len(y), bool)), (W, group == W), (B, group == B)]:
        r = rates(y[m], flag[m])
        lo, hi = wilson(r["tp"], r["deaths"])
        r.update(group=name, recall_lo=lo, recall_hi=hi)
        rows.append(r)
    return pd.DataFrame(rows).set_index("group")


def _fast(y, g, flags, idx):
    """Metric dict for a bootstrap resample ``idx``; ``flags`` is (R, N) - metrics averaged over R."""
    yy, gg, ff = y[idx], g[idx], flags[:, idx]
    out = {}
    for name, m in [("all", np.ones(len(yy), bool)), ("W", gg == W), ("B", gg == B)]:
        pos, neg = (yy == 1) & m, (yy == 0) & m
        out[f"tpr_{name}"] = ff[:, pos].mean() if pos.any() else np.nan
        out[f"fpr_{name}"] = ff[:, neg].mean() if neg.any() else np.nan
        out[f"flag_{name}"] = ff[:, m].mean()
    out["tpr_gap"] = out["tpr_B"] - out["tpr_W"]
    out["fpr_gap"] = out["fpr_B"] - out["fpr_W"]
    out["eod"] = max(abs(out["tpr_gap"]), abs(out["fpr_gap"]))
    out["abs_tpr_gap"] = abs(out["tpr_gap"])
    return out


def bootstrap(y: np.ndarray, group: np.ndarray, flags: dict[str, np.ndarray], n_boot: int = 1000,
              seed: int = 0) -> tuple[pd.DataFrame, dict]:
    """Point estimates + percentile CIs for every strategy.  Resampling is stratified by group.
    Returns (summary table, raw bootstrap draws) - the draws feed :func:`paired_difference`."""
    rng = np.random.default_rng(seed)
    ig = {g: np.where(group == g)[0] for g in D.GROUPS}
    draws = {k: [] for k in flags}
    for _ in range(n_boot):
        idx = np.concatenate([rng.choice(ig[g], size=len(ig[g]), replace=True) for g in D.GROUPS])
        for k, f in flags.items():
            draws[k].append(_fast(y, group, f, idx))
    draws = {k: pd.DataFrame(v) for k, v in draws.items()}
    allidx = np.arange(len(y))
    rows = []
    for k, f in flags.items():
        pt = _fast(y, group, f, allidx)
        for metric, val in pt.items():
            lo, hi = np.nanpercentile(draws[k][metric], [2.5, 97.5])
            rows.append(dict(strategy=k, metric=metric, estimate=val, lo=lo, hi=hi))
    return pd.DataFrame(rows), draws


def paired_difference(draws: dict, a: str, b: str, metric: str) -> tuple[float, float, float, float]:
    """metric(a) - metric(b): mean, paired-bootstrap 95 % CI, and the share of draws with a < b."""
    d = draws[a][metric].to_numpy() - draws[b][metric].to_numpy()
    return float(np.nanmean(d)), float(np.nanpercentile(d, 2.5)), float(np.nanpercentile(d, 97.5)), float(np.mean(d < 0))


def auc_by_group(y: np.ndarray, group: np.ndarray, prob: np.ndarray, n_boot: int = 500, seed: int = 0) -> pd.DataFrame:
    """Threshold-free ranking quality per group (prob is (R, N) or (N,))."""
    prob = np.atleast_2d(prob)
    rng = np.random.default_rng(seed)
    rows = []
    for name, m in [("All", np.ones(len(y), bool)), (W, group == W), (B, group == B)]:
        idx = np.where(m)[0]
        point = np.mean([roc_auc_score(y[idx], p[idx]) for p in prob])
        bs = []
        for _ in range(n_boot):
            ii = rng.choice(idx, size=len(idx), replace=True)
            if y[ii].min() == y[ii].max():
                continue
            bs.append(np.mean([roc_auc_score(y[ii], p[ii]) for p in prob]))
        rows.append(dict(group=name, auc=point, lo=np.percentile(bs, 2.5), hi=np.percentile(bs, 97.5)))
    return pd.DataFrame(rows).set_index("group")


# --------------------------------------------------------------------------------------------
# Repeated cross-validation of all strategies
# --------------------------------------------------------------------------------------------
def _one_fold(r, f, tr, va, X, y, group, strata, params, target, strategies, seed):
    fitted = M.fit_all(strategies, X.iloc[tr], y[tr], group[tr], strata[tr], params, target=target,
                       seed=seed + 1000 * r + f)
    out = {}
    for s in strategies:
        fit = fitted[s.key]
        p = fit.proba(X.iloc[va])
        out[s.key] = (p, (p >= fit.threshold_for(group[va])).astype(int), fit.thresholds)
    return r, va, out


def cv_evaluate(X: pd.DataFrame, y: np.ndarray, group: np.ndarray, strata: np.ndarray, params: dict,
                strategies: list[M.Strategy] | None = None, target: float = M.TARGET_RECALL,
                n_splits: int = 5, n_repeats: int = 5, seed: int = 7, n_jobs: int = -1):
    """Out-of-fold probabilities and recall-first decisions for every strategy.
    Returns (probs, flags, thresholds) with probs/flags[key] of shape (n_repeats, N)."""
    strategies = strategies or M.STRATEGIES
    rskf = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=seed)
    tasks = [(i // n_splits, i % n_splits, tr, va)
             for i, (tr, va) in enumerate(rskf.split(np.zeros(len(y)), strata))]
    res = Parallel(n_jobs=n_jobs)(delayed(_one_fold)(r, f, tr, va, X, y, group, strata, params, target, strategies, seed)
                                  for r, f, tr, va in tasks)
    probs = {s.key: np.zeros((n_repeats, len(y))) for s in strategies}
    flags = {s.key: np.zeros((n_repeats, len(y)), dtype=int) for s in strategies}
    thr = {s.key: [] for s in strategies}
    for r, va, out in res:
        for k, (p, fl, th) in out.items():
            probs[k][r, va], flags[k][r, va] = p, fl
            thr[k].append(th)
    return probs, flags, thr


def summarise_thresholds(thr: dict) -> pd.DataFrame:
    rows = []
    for k, lst in thr.items():
        for name in ["global", W, B]:
            v = np.array([t[name] for t in lst])
            rows.append(dict(strategy=k, threshold=name, mean=v.mean(), sd=v.std(), min=v.min(), max=v.max()))
    return pd.DataFrame(rows)
