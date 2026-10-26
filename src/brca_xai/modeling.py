"""XGBoost training, recall-first thresholding and bias-mitigation strategies.

Recall-first design
-------------------
The operating point is not 0.5.  It is the *largest* score threshold whose recall (sensitivity for death
during follow-up) reaches ``TARGET_RECALL`` on out-of-fold training predictions, so everything the
threshold depends on is learned from training data only.  "Acceptable precision" (proposal 3.2.4) is
operationalised as a floor of 1.25 x the training prevalence that the chosen threshold must clear
(``precision_floor``); other rules are available for comparison (:func:`threshold_rules`).

Class imbalance is handled with ``scale_pos_weight`` (negatives / positives), not oversampling.

Bias mitigation
---------------
Compared in :func:`make_strategies`:
  * unawareness     - dropping the race columns,
  * pre-processing  - Kamiran & Calders *reweighing* of race x outcome cells,
  * post-processing - *group-specific thresholds* that give each group the same target recall
                      (the "equal opportunity" criterion of Hardt, Price & Srebro, 2016).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import optuna
import pandas as pd
import xgboost as xgb
from joblib import Parallel, delayed
from sklearn.metrics import precision_recall_curve, roc_auc_score, roc_curve
from sklearn.model_selection import RepeatedStratifiedKFold

from . import data as D

optuna.logging.set_verbosity(optuna.logging.WARNING)

TARGET_RECALL = 0.80
PRECISION_FLOOR_MULT = 1.25      # acceptable precision = 1.25 x prevalence (flagging beats random by 25 %)

DEFAULT_PARAMS = dict(max_depth=2, learning_rate=0.05, n_estimators=150, min_child_weight=1.0,
                      subsample=0.8, colsample_bytree=0.8, reg_lambda=2.0, reg_alpha=0.1, gamma=0.0)

# Clinical prior baked into every model: a larger tumour, more involved nodes, distant metastasis or a higher stage
# group can never LOWER predicted risk.  A design decision (Chapter 3), not a tuned parameter.
MONOTONE_COLS = D.MONOTONE_COLS


def make_model(params: dict | None = None, seed: int = 42, monotone: bool = True, cols: list[str] | None = None,
               spw: float | None = None) -> xgb.XGBClassifier:
    p = {**DEFAULT_PARAMS, **(params or {})}
    if monotone and cols is not None:
        mono = {c: 1 for c in cols if c in MONOTONE_COLS}
        if mono:
            p["monotone_constraints"] = mono
    if spw is not None:
        p["scale_pos_weight"] = float(spw)
    return xgb.XGBClassifier(objective="binary:logistic", eval_metric="logloss", tree_method="hist",
                             n_jobs=1, random_state=seed, verbosity=0, **p)


def class_weight(y: np.ndarray) -> float:
    """scale_pos_weight = negatives / positives of the training data."""
    return float((y == 0).sum() / max(int((y == 1).sum()), 1))


# --------------------------------------------------------------------------------------------
# Thresholds
# --------------------------------------------------------------------------------------------
def recall_threshold(y: np.ndarray, p: np.ndarray, target: float = TARGET_RECALL) -> float:
    """Largest threshold t such that recall(p >= t) >= target on (y, p)."""
    pos = np.sort(p[y == 1])[::-1]
    if len(pos) == 0:
        return 0.5
    k = int(np.ceil(target * len(pos)))
    return float(pos[k - 1])


def precision_floor_threshold(y: np.ndarray, p: np.ndarray, floor: float) -> float:
    """Lowest threshold whose precision still clears ``floor`` (= highest recall at acceptable precision)."""
    pr, rc, th = precision_recall_curve(y, p)
    ok = np.where(pr[:-1] >= floor)[0]
    return float(th[ok[0]]) if len(ok) else float(p.max())


def fpr_at_recall(y: np.ndarray, p: np.ndarray, target: float = TARGET_RECALL) -> float:
    fpr, tpr, _ = roc_curve(y, p)
    return float(fpr[np.searchsorted(tpr, target, side="left")])


def threshold_rules(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    """Candidate decision rules on (out-of-fold) scores - used to document why recall-at-target is the primary rule."""
    floor = PRECISION_FLOOR_MULT * y.mean()
    out = {"recall >= 80 % (primary)": recall_threshold(y, p, 0.80), "recall >= 90 %": recall_threshold(y, p, 0.90),
           f"max recall s.t. precision >= {floor:.2f}": precision_floor_threshold(y, p, floor)}
    pr, rc, th = precision_recall_curve(y, p)
    f2 = 5 * pr[:-1] * rc[:-1] / np.maximum(4 * pr[:-1] + rc[:-1], 1e-12)
    out["max F2"] = float(th[np.argmax(f2)])
    fpr, tpr, thr = roc_curve(y, p)
    out["Youden J"] = float(thr[np.argmax(tpr - fpr)])
    out["0.5 (default)"] = 0.5
    return out


# --------------------------------------------------------------------------------------------
# Reweighing (pre-processing)
# --------------------------------------------------------------------------------------------
def reweighing_weights(group: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Kamiran-Calders weights w(g, y) = P(g) P(y) / P(g, y): race and outcome become independent in the weighted data."""
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
    features: tuple
    reweigh: bool = False
    group_thresholds: bool = False
    family: str = "baseline"
    note: str = ""

    @property
    def uses_race_at_inference(self) -> bool:
        return self.group_thresholds or any(f in self.features for f in D.RACE_FEATURES)


def make_strategies(spec: str = "proposal") -> list[Strategy]:
    aware = tuple(D.SPECS[spec])
    blind = tuple(f for f in aware if f not in D.RACE_FEATURES)
    return [
        Strategy("aware", "Baseline (race-aware, one threshold)", aware, family="baseline",
                 note="Race is a model input, as in the proposal's predictor list; a single recall-first threshold."),
        Strategy("blind", "Race-blind (one threshold)", blind, family="unawareness",
                 note="Fairness through unawareness: the race columns are removed."),
        Strategy("reweigh", "Reweighing (race-blind, one threshold)", blind, reweigh=True, family="pre-processing",
                 note="Training rows re-weighted so race and outcome are independent; no race needed at prediction time."),
        Strategy("gthr", "Group thresholds (race-blind scores)", blind, group_thresholds=True, family="post-processing",
                 note="Black and White patients get their own threshold so that both reach the target recall."),
        Strategy("reweigh_gthr", "Reweighing + group thresholds", blind, reweigh=True, group_thresholds=True,
                 family="combined", note="Pre- and post-processing together."),
    ]


STRATEGIES = make_strategies("proposal")
STRATEGY_BY_KEY = {s.key: s for s in STRATEGIES}


def _fit(strategy: Strategy, X: pd.DataFrame, y: np.ndarray, group: np.ndarray, params: dict, seed: int):
    cols = list(strategy.features)
    m = make_model(params, seed, cols=cols, spw=class_weight(y))
    w = reweighing_weights(group, y) if strategy.reweigh else None
    m.fit(X[cols], y, sample_weight=w)
    return m


def oof_scores(strategy: Strategy, X: pd.DataFrame, y: np.ndarray, group: np.ndarray, strata: np.ndarray,
               params: dict, seed: int = 0, n_splits: int = 5, n_repeats: int = 2) -> np.ndarray:
    """Out-of-fold probability for every row, averaged over ``n_repeats`` stratified CV repeats."""
    acc, cnt = np.zeros(len(y)), np.zeros(len(y))
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
            return np.array([self.thresholds.get(g, self.thresholds["global"]) for g in group])
        return np.full(len(group), self.thresholds["global"])

    def flag(self, X: pd.DataFrame, group: np.ndarray) -> np.ndarray:
        return (self.proba(X) >= self.threshold_for(group)).astype(int)


def fit_all(strategies: list[Strategy], X: pd.DataFrame, y: np.ndarray, group: np.ndarray, strata: np.ndarray,
            params: dict, target: float = TARGET_RECALL, seed: int = 42, n_inner: int = 5,
            n_repeats: int = 2) -> dict[str, Fitted]:
    """Fit every strategy, sharing the underlying model between strategies that only differ in their thresholds.
    Thresholds come from inner out-of-fold scores; group thresholds are learned within White / Black patients."""
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


# --------------------------------------------------------------------------------------------
# Bayesian hyper-parameter search (objective = lowest FPR at 80 % recall, i.e. most specificity at the recall target)
# --------------------------------------------------------------------------------------------
def _suggest(trial) -> dict:
    return dict(max_depth=trial.suggest_int("max_depth", 1, 3),
                learning_rate=trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
                n_estimators=trial.suggest_int("n_estimators", 60, 500),
                # a leaf must hold ~4-15 patients at the base rate (hessian ~ p(1-p)) or rare, decisive groups (M1) are unreachable
                min_child_weight=trial.suggest_float("min_child_weight", 0.1, 2.0),
                subsample=trial.suggest_float("subsample", 0.6, 1.0), colsample_bytree=trial.suggest_float("colsample_bytree", 0.5, 1.0),
                reg_lambda=trial.suggest_float("reg_lambda", 0.5, 10, log=True), reg_alpha=trial.suggest_float("reg_alpha", 0, 1),
                gamma=trial.suggest_float("gamma", 0, 1))


def _fit_fold(params, X, y, tr, va, cols, seed):
    m = make_model(params, seed, cols=cols, spw=class_weight(y[tr]))
    m.fit(X.iloc[tr][cols], y[tr])
    return va, m.predict_proba(X.iloc[va][cols])[:, 1]


def cv_score(params: dict, X: pd.DataFrame, y: np.ndarray, splits: list, n_splits: int, n_repeats: int, cols: list[str],
             seed: int = 42) -> tuple[float, float]:
    """(mean AUC, mean FPR@80 % recall) over repeats of pooled out-of-fold predictions.  The folds run in parallel but
    the search itself is sequential, so a given seed always returns the same model."""
    res = Parallel(n_jobs=-1)(delayed(_fit_fold)(params, X, y, tr, va, cols, seed) for tr, va in splits)
    aucs, fprs = [], []
    for r in range(n_repeats):
        oof = np.zeros(len(y))
        for va, p in res[r * n_splits:(r + 1) * n_splits]:
            oof[va] = p
        aucs.append(roc_auc_score(y, oof)); fprs.append(fpr_at_recall(y, oof))
    return float(np.mean(aucs)), float(np.mean(fprs))


def tune(X: pd.DataFrame, y: np.ndarray, strata: np.ndarray, cols: list[str], n_trials: int = 60, n_splits: int = 5,
         n_repeats: int = 4, seed: int = 42) -> tuple[dict, pd.DataFrame]:
    """Bayesian (TPE) search with repeated stratified 5-fold CV on the development set (proposal 3.2.4)."""
    rskf = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=seed)
    splits = list(rskf.split(np.zeros(len(y)), strata))

    def objective(trial):
        params = _suggest(trial)
        auc, fpr = cv_score(params, X, y, splits, n_splits, n_repeats, cols, seed)
        trial.set_user_attr("auc", auc)
        return fpr

    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=seed, n_startup_trials=15))
    study.enqueue_trial({**{k: v for k, v in DEFAULT_PARAMS.items()}})
    study.optimize(objective, n_trials=n_trials, n_jobs=1)
    rows = [dict(t.params, auc=t.user_attrs["auc"], fpr_at_80_recall=t.value) for t in study.trials if t.value is not None]
    table = pd.DataFrame(rows).sort_values(["fpr_at_80_recall", "auc"], ascending=[True, False]).reset_index(drop=True)
    best = {k: table.loc[0, k] for k in DEFAULT_PARAMS}
    best["max_depth"], best["n_estimators"] = int(best["max_depth"]), int(best["n_estimators"])
    return {k: (float(v) if not isinstance(v, int) else v) for k, v in best.items()}, table
