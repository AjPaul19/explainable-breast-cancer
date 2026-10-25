"""XGBoost training, recall-first thresholding and bias-mitigation strategies.

Recall-first design
-------------------
The operating point is not 0.5.  It is the *largest* score threshold whose recall (sensitivity for
death during follow-up) reaches ``TARGET_RECALL`` on out-of-fold training predictions.  Everything
the threshold depends on is therefore learned from training data only.

Bias mitigation
---------------
Three families are compared in :data:`STRATEGIES`:
  * pre-processing  - Kamiran & Calders *reweighing* of race x outcome cells,
  * unawareness     - dropping the race column,
  * post-processing - *group-specific thresholds* that give each group the same target recall
                      (the "equal opportunity" criterion of Hardt, Price & Srebro, 2016).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import xgboost as xgb
from joblib import Parallel, delayed
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import ParameterSampler, RepeatedStratifiedKFold, StratifiedKFold
from scipy.stats import loguniform, randint, uniform

from . import data as D

TARGET_RECALL = 0.80

DEFAULT_PARAMS = dict(max_depth=2, learning_rate=0.05, n_estimators=150, min_child_weight=2.0,
                      subsample=0.8, colsample_bytree=0.8, reg_lambda=2.0, reg_alpha=0.1, gamma=0.0)

# Clinical prior baked into every model: a larger tumour, more involved nodes or distant metastasis
# can never LOWER predicted risk.  This is a design decision (see Chapter 3), not a tuned parameter.
MONOTONE = {"t_stage": 1, "n_stage": 1, "m_stage": 1}


def make_model(params: dict | None = None, seed: int = 42, monotone: bool = True) -> xgb.XGBClassifier:
    p = {**DEFAULT_PARAMS, **(params or {})}
    if monotone:
        p["monotone_constraints"] = MONOTONE
    return xgb.XGBClassifier(objective="binary:logistic", eval_metric="logloss", tree_method="hist",
                             n_jobs=1, random_state=seed, verbosity=0, **p)


# --------------------------------------------------------------------------------------------
# Recall-first thresholds
# --------------------------------------------------------------------------------------------
def recall_threshold(y: np.ndarray, p: np.ndarray, target: float = TARGET_RECALL) -> float:
    """Largest threshold t such that recall(p >= t) >= target on (y, p)."""
    pos = np.sort(p[y == 1])[::-1]
    if len(pos) == 0:
        return 0.5
    k = int(np.ceil(target * len(pos)))
    return float(pos[k - 1])


def fpr_at_recall(y: np.ndarray, p: np.ndarray, target: float = TARGET_RECALL) -> float:
    """False-positive rate when the threshold is set to reach ``target`` recall (lower is better)."""
    fpr, tpr, _ = roc_curve(y, p)
    return float(fpr[np.searchsorted(tpr, target, side="left")])


# --------------------------------------------------------------------------------------------
# Reweighing (pre-processing)
# --------------------------------------------------------------------------------------------
def reweighing_weights(group: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Kamiran-Calders weights  w(g, y) = P(g) P(y) / P(g, y)  - makes race and outcome independent
    in the weighted training set, so a minority group's deaths are not drowned out."""
    group, y = np.asarray(group), np.asarray(y)
    w = np.ones(len(y))
    for g in np.unique(group):
        for lab in (0, 1):
            m = (group == g) & (y == lab)
            if m.any():
                w[m] = (group == g).mean() * (y == lab).mean() / m.mean()
    return w


# --------------------------------------------------------------------------------------------
# Strategies
# --------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Strategy:
    key: str
    label: str
    features: tuple          # model inputs
    reweigh: bool = False
    group_thresholds: bool = False
    family: str = "baseline"
    note: str = ""

    @property
    def uses_race_at_inference(self) -> bool:
        return self.group_thresholds or "race_black" in self.features


STRATEGIES = [
    Strategy("aware", "Baseline (race-aware, one threshold)", tuple(D.FEATURES_AWARE), family="baseline",
             note="Race is a model input; a single recall-first threshold for everyone."),
    Strategy("blind", "Race-blind (one threshold)", tuple(D.FEATURES_BLIND), family="unawareness",
             note="Fairness through unawareness: the race column is removed."),
    Strategy("reweigh", "Reweighing (race-blind, one threshold)", tuple(D.FEATURES_BLIND), reweigh=True,
             family="pre-processing", note="Training rows re-weighted so race and outcome are independent; no race needed at prediction time."),
    Strategy("gthr", "Group thresholds (race-blind scores)", tuple(D.FEATURES_BLIND), group_thresholds=True,
             family="post-processing", note="Each group gets its own threshold so that both reach the target recall."),
    Strategy("reweigh_gthr", "Reweighing + group thresholds", tuple(D.FEATURES_BLIND), reweigh=True,
             group_thresholds=True, family="combined", note="Pre- and post-processing together."),
]
STRATEGY_BY_KEY = {s.key: s for s in STRATEGIES}


def _fit(strategy: Strategy, X: pd.DataFrame, y: np.ndarray, group: np.ndarray, params: dict, seed: int):
    m = make_model(params, seed)
    w = reweighing_weights(group, y) if strategy.reweigh else None
    m.fit(X[list(strategy.features)], y, sample_weight=w)
    return m


def oof_scores(strategy: Strategy, X: pd.DataFrame, y: np.ndarray, group: np.ndarray, strata: np.ndarray,
               params: dict, seed: int = 0, n_splits: int = 5, n_repeats: int = 2) -> np.ndarray:
    """Out-of-fold probability for every row, averaged over ``n_repeats`` stratified CV repeats."""
    acc = np.zeros(len(y))
    cnt = np.zeros(len(y))
    rskf = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=seed)
    for tr, va in rskf.split(np.zeros(len(y)), strata):
        m = _fit(strategy, X.iloc[tr], y[tr], group[tr], params, seed)
        acc[va] += m.predict_proba(X.iloc[va][list(strategy.features)])[:, 1]
        cnt[va] += 1
    return acc / cnt


@dataclass
class Fitted:
    """A trained strategy: model + thresholds.  ``flag`` implements the recall-first decision."""
    strategy: Strategy
    model: xgb.XGBClassifier
    thresholds: dict = field(default_factory=dict)   # {"global": t, "White": t, "Black": t}

    def proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(X[list(self.strategy.features)])[:, 1]

    def threshold_for(self, group: np.ndarray) -> np.ndarray:
        if self.strategy.group_thresholds:
            return np.array([self.thresholds[g] for g in group])
        return np.full(len(group), self.thresholds["global"])

    def flag(self, X: pd.DataFrame, group: np.ndarray) -> np.ndarray:
        return (self.proba(X) >= self.threshold_for(group)).astype(int)


def fit_strategy(strategy: Strategy, X: pd.DataFrame, y: np.ndarray, group: np.ndarray, strata: np.ndarray,
                 params: dict, target: float = TARGET_RECALL, seed: int = 42, n_inner: int = 5,
                 n_repeats: int = 2) -> Fitted:
    """Fit the model on all given rows and learn its thresholds from inner out-of-fold scores."""
    oof = oof_scores(strategy, X, y, group, strata, params, seed=seed, n_splits=n_inner, n_repeats=n_repeats)
    thr = {"global": recall_threshold(y, oof, target)}
    for g in D.GROUPS:
        mask = group == g
        thr[g] = recall_threshold(y[mask], oof[mask], target)
    model = _fit(strategy, X, y, group, params, seed)
    return Fitted(strategy, model, thr)


# --------------------------------------------------------------------------------------------
# Hyper-parameter search (objective = lowest FPR at 80 % recall, i.e. most specificity for the recall target)
# --------------------------------------------------------------------------------------------
# A leaf must be able to hold ~4-15 patients at the base death rate (hessian p(1-p) ~ 0.13 each), otherwise
# rare but decisive groups (M1: 17 patients, 88 % mortality) can never be isolated.
SPACE = dict(max_depth=randint(1, 4), learning_rate=loguniform(0.01, 0.2), n_estimators=randint(60, 400),
             min_child_weight=uniform(0.1, 1.9), subsample=uniform(0.6, 0.4), colsample_bytree=uniform(0.5, 0.5),
             reg_lambda=loguniform(0.5, 10), reg_alpha=uniform(0, 1.0), gamma=uniform(0, 1.0))


def tune(X: pd.DataFrame, y: np.ndarray, strata: np.ndarray, n_iter: int = 60, n_splits: int = 5,
         n_repeats: int = 4, seed: int = 42, n_jobs: int = -1) -> tuple[dict, pd.DataFrame]:
    """Randomised search; each candidate is scored on pooled out-of-fold predictions per CV repeat."""
    cands = list(ParameterSampler(SPACE, n_iter=n_iter, random_state=seed))
    cands = [{**c, "max_depth": int(c["max_depth"]), "n_estimators": int(c["n_estimators"])} for c in cands]
    cands.append(dict(DEFAULT_PARAMS))
    rskf = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=seed)
    splits = list(rskf.split(np.zeros(len(y)), strata))

    def score(params):
        aucs, fprs = [], []
        for r in range(n_repeats):
            oof = np.zeros(len(y))
            for tr, va in splits[r * n_splits:(r + 1) * n_splits]:
                m = make_model(params, seed)
                m.fit(X.iloc[tr], y[tr])
                oof[va] = m.predict_proba(X.iloc[va])[:, 1]
            aucs.append(roc_auc_score(y, oof))
            fprs.append(fpr_at_recall(y, oof))
        return dict(params, auc=np.mean(aucs), fpr_at_80_recall=np.mean(fprs))

    res = Parallel(n_jobs=n_jobs)(delayed(score)(c) for c in cands)
    table = pd.DataFrame(res).sort_values(["fpr_at_80_recall", "auc"], ascending=[True, False]).reset_index(drop=True)
    best = {k: table.loc[0, k] for k in DEFAULT_PARAMS}
    best["max_depth"], best["n_estimators"] = int(best["max_depth"]), int(best["n_estimators"])
    return {k: (float(v) if not isinstance(v, int) else v) for k, v in best.items()}, table


def fit_all(strategies: list[Strategy], X: pd.DataFrame, y: np.ndarray, group: np.ndarray, strata: np.ndarray,
            params: dict, target: float = TARGET_RECALL, seed: int = 42, n_inner: int = 5,
            n_repeats: int = 2) -> dict[str, Fitted]:
    """Fit every strategy, sharing the underlying model between strategies that only differ in
    their thresholds (e.g. ``blind`` and ``gthr``)."""
    cache: dict[tuple, tuple] = {}
    out: dict[str, Fitted] = {}
    for s in strategies:
        key = (s.features, s.reweigh)
        if key not in cache:
            oof = oof_scores(s, X, y, group, strata, params, seed=seed, n_splits=n_inner, n_repeats=n_repeats)
            cache[key] = (_fit(s, X, y, group, params, seed), oof)
        model, oof = cache[key]
        thr = {"global": recall_threshold(y, oof, target)}
        for g in D.GROUPS:
            thr[g] = recall_threshold(y[group == g], oof[group == g], target)
        out[s.key] = Fitted(s, model, thr)
    return out
