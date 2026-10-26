"""Performance evaluation (proposal 3.2.5): threshold metrics with bootstrap CIs, baseline models trained under
the same protocol, overfitting diagnostics (learning curve) and an exploratory survival check."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import data as D
from . import modeling as M

METRICS = ["accuracy", "balanced_accuracy", "precision", "recall", "specificity", "f1", "auc_roc", "pr_auc", "flag_rate"]


def threshold_metrics(y: np.ndarray, p: np.ndarray, thr) -> dict:
    flag = p >= thr
    tp = int(((y == 1) & flag).sum()); fn = int(((y == 1) & ~flag).sum())
    fp = int(((y == 0) & flag).sum()); tn = int(((y == 0) & ~flag).sum())
    div = lambda a, b: a / b if b else np.nan
    rec, spec, prec = div(tp, tp + fn), div(tn, tn + fp), div(tp, tp + fp)
    return dict(tp=tp, fn=fn, fp=fp, tn=tn, accuracy=(tp + tn) / len(y), balanced_accuracy=np.nanmean([rec, spec]),
                precision=prec, recall=rec, specificity=spec,
                f1=div(2 * prec * rec, prec + rec) if tp else 0.0, flag_rate=(tp + fp) / len(y),
                auc_roc=roc_auc_score(y, p) if len(np.unique(y)) > 1 else np.nan,
                pr_auc=average_precision_score(y, p) if len(np.unique(y)) > 1 else np.nan)


def bootstrap_metrics(y: np.ndarray, p: np.ndarray, thr, n_boot: int = 1000, seed: int = 0) -> pd.DataFrame:
    """Point estimate and percentile 95 % CI for every metric (the threshold is fixed: it was learned on training data only)."""
    rng = np.random.default_rng(seed)
    pt = threshold_metrics(y, p, thr)
    draws = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        if y[idx].min() == y[idx].max():
            continue
        draws.append(threshold_metrics(y[idx], p[idx], thr if np.isscalar(thr) else np.asarray(thr)[idx]))
    d = pd.DataFrame(draws)
    return pd.DataFrame([dict(metric=m, estimate=pt[m], lo=np.nanpercentile(d[m], 2.5), hi=np.nanpercentile(d[m], 97.5)) for m in METRICS])


# ---------------------------------------------------------------------------------------------
# Baselines under the same protocol (proposal 3.2.4: logistic regression, random forest, stage-only)
# ---------------------------------------------------------------------------------------------
def _pipe(kind: str, hp):
    imp = SimpleImputer(strategy="median", add_indicator=True)
    if kind == "lr":
        return make_pipeline(imp, StandardScaler(), LogisticRegression(C=hp, class_weight="balanced", max_iter=3000))
    return make_pipeline(imp, RandomForestClassifier(500, min_samples_leaf=hp, max_features="sqrt",
                                                     class_weight="balanced_subsample", random_state=0, n_jobs=-1))


BASELINES = {
    "Logistic regression": ("lr", None, [0.03, 0.1, 0.3, 1.0]),      # None = the model's full predictor list
    "Random forest": ("rf", None, [5, 10, 20]),
    "Stage-only (logistic)": ("lr", ["stage_group"], [0.1, 1.0]),
}


def fit_baselines(X: pd.DataFrame, y: np.ndarray, strata: np.ndarray, dev: np.ndarray, seed: int = 42,
                  target: float = M.TARGET_RECALL, full_cols: list[str] | None = None) -> dict:
    """Tune each baseline on the development set (repeated 5-fold CV), learn its recall-first threshold from
    out-of-fold scores, and score the hold-out set.  Returns {name: dict(p_test, thr, auc_cv, hp)}."""
    Xd, yd, sd = X[dev].reset_index(drop=True), y[dev], strata[dev]
    out = {}
    rskf = RepeatedStratifiedKFold(n_splits=5, n_repeats=2, random_state=seed)
    splits = list(rskf.split(np.zeros(len(yd)), sd))
    for name, (kind, cols, grid) in BASELINES.items():
        cols = cols or full_cols or D.PRIMARY
        best = None
        for hp in grid:
            oof = np.zeros((2, len(yd)))
            for i, (tr, va) in enumerate(splits):
                m = _pipe(kind, hp).fit(Xd.iloc[tr][cols], yd[tr])
                oof[i // 5, va] = m.predict_proba(Xd.iloc[va][cols])[:, 1]
            auc = np.mean([roc_auc_score(yd, o) for o in oof])
            if best is None or auc > best[0]:
                best = (auc, hp, oof.mean(0))
        auc, hp, oof = best
        thr = M.recall_threshold(yd, oof, target)
        m = _pipe(kind, hp).fit(Xd[cols], yd)
        out[name] = dict(p_test=m.predict_proba(X[~dev][cols])[:, 1], thr=thr, auc_cv=auc, hp=hp, oof_dev=oof)
    return out


# ---------------------------------------------------------------------------------------------
# Overfitting diagnostics: train vs cross-validated vs test AUC along the boosting path
# ---------------------------------------------------------------------------------------------
def learning_curve(X: pd.DataFrame, y: np.ndarray, strata: np.ndarray, dev: np.ndarray, params: dict, cols: list[str],
                   seed: int = 42, step: int = 10) -> pd.DataFrame:
    Xd, yd, sd = X[dev].reset_index(drop=True), y[dev], strata[dev]
    n = params["n_estimators"]
    ks = list(range(step, n + 1, step))
    if ks[-1] != n:
        ks.append(n)
    cv_auc = np.zeros((5, len(ks)))
    rskf = RepeatedStratifiedKFold(n_splits=5, n_repeats=1, random_state=seed)
    for f, (tr, va) in enumerate(rskf.split(np.zeros(len(yd)), sd)):
        m = M.make_model(params, seed, cols=cols, spw=M.class_weight(yd[tr])).fit(Xd.iloc[tr][cols], yd[tr])
        for j, k in enumerate(ks):
            cv_auc[f, j] = roc_auc_score(yd[va], m.predict_proba(Xd.iloc[va][cols], iteration_range=(0, k))[:, 1])
    m = M.make_model(params, seed, cols=cols, spw=M.class_weight(yd)).fit(Xd[cols], yd)
    Xt, yt = X[~dev], y[~dev]
    rows = []
    for j, k in enumerate(ks):
        rows.append(dict(trees=k, train=roc_auc_score(yd, m.predict_proba(Xd[cols], iteration_range=(0, k))[:, 1]),
                         cv=cv_auc[:, j].mean(), cv_sd=cv_auc[:, j].std(),
                         test=roc_auc_score(yt, m.predict_proba(Xt[cols], iteration_range=(0, k))[:, 1])))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# Exploratory: does the binary label throw away signal?  (proposal 3.2.11 leaves survival modelling to future work)
# ---------------------------------------------------------------------------------------------
def harrell_c(time: np.ndarray, event: np.ndarray, risk: np.ndarray) -> float:
    """Harrell's concordance index (ties in risk count 0.5)."""
    t, e, r = np.asarray(time), np.asarray(event).astype(bool), np.asarray(risk)
    comp = e[:, None] & (t[:, None] < t[None, :])           # i had an event before j's time
    conc = (r[:, None] > r[None, :]) & comp
    tie = (r[:, None] == r[None, :]) & comp
    return float((conc.sum() + 0.5 * tie.sum()) / comp.sum())


def survival_check(X: pd.DataFrame, c: pd.DataFrame, params: dict, cols: list[str], strata: np.ndarray, seed: int = 42,
                   n_repeats: int = 3) -> dict:
    import xgboost as xgb
    y, t = c[D.TARGET].to_numpy(), c["followup_months"].to_numpy()
    p = {k: v for k, v in {**M.DEFAULT_PARAMS, **params}.items()}
    mono = {k: 1 for k in cols if k in M.MONOTONE_COLS}
    rskf = RepeatedStratifiedKFold(n_splits=5, n_repeats=n_repeats, random_state=seed)
    cb, cs = [], []
    ob, os_ = np.zeros((n_repeats, len(y))), np.zeros((n_repeats, len(y)))
    for i, (tr, va) in enumerate(rskf.split(np.zeros(len(y)), strata)):
        mb = M.make_model(params, seed, cols=cols, spw=M.class_weight(y[tr])).fit(X.iloc[tr][cols], y[tr])
        ob[i // 5, va] = mb.predict_proba(X.iloc[va][cols])[:, 1]
        lab = np.where(y == 1, t, -t)                        # xgboost survival:cox: negative time = censored
        ms = xgb.XGBRegressor(objective="survival:cox", tree_method="hist", n_jobs=1, verbosity=0, random_state=seed,
                              monotone_constraints=mono or None, **p)
        ms.fit(X.iloc[tr][cols], lab[tr])
        os_[i // 5, va] = ms.predict(X.iloc[va][cols])
    return dict(c_index_binary=float(np.mean([harrell_c(t, y, o) for o in ob])),
                c_index_cox=float(np.mean([harrell_c(t, y, o) for o in os_])),
                auc_binary=float(np.mean([roc_auc_score(y, o) for o in ob])))
