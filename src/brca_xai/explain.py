"""SHAP explanations and the group-level analyses built on them.

Everything is expressed in log-odds (the model's margin): SHAP values add up to
``margin - base_value`` for every patient, so contributions can be compared across patients and groups.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import shap
from scipy.stats import kendalltau, spearmanr

from . import data as D
from . import modeling as M


def explainer(model) -> shap.TreeExplainer:
    return shap.TreeExplainer(model)


def shap_matrix(model, X: pd.DataFrame, features: list[str]) -> tuple[pd.DataFrame, float]:
    ex = explainer(model)
    sv = ex.shap_values(X[features])
    base = float(np.ravel(ex.expected_value)[0])
    return pd.DataFrame(sv, columns=features, index=X.index), base


def global_importance(sv: pd.DataFrame) -> pd.Series:
    return sv.abs().mean().sort_values(ascending=False)


def importance_by_group(sv: pd.DataFrame, group: np.ndarray) -> pd.DataFrame:
    """Mean |SHAP| per feature for White and Black patients, ranks, and the ratio Black / White."""
    out = pd.DataFrame({g: sv[group == g].abs().mean() for g in D.GROUPS})
    out["ratio_B_over_W"] = out[D.UNPRIVILEGED] / out[D.PRIVILEGED]
    for g in D.GROUPS:
        out[f"rank_{g}"] = out[g].rank(ascending=False).astype(int)
    out["label"] = [D.LABELS[f] for f in out.index]
    return out.sort_values(D.PRIVILEGED, ascending=False)


def risk_gap_decomposition(sv: pd.DataFrame, group: np.ndarray, margin: np.ndarray) -> pd.DataFrame:
    """Why does the model assign Black patients a different average risk than White patients?
    gap(log-odds) = sum over features of [mean phi_f(Black) - mean phi_f(White)]  (exact, additive)."""
    mb, mw = sv[group == D.UNPRIVILEGED].mean(), sv[group == D.PRIVILEGED].mean()
    d = pd.DataFrame({"mean_shap_White": mw, "mean_shap_Black": mb, "contribution_to_gap": mb - mw})
    d["label"] = [D.LABELS[f] for f in d.index]
    d.attrs["total_gap"] = float(margin[group == D.UNPRIVILEGED].mean() - margin[group == D.PRIVILEGED].mean())
    return d.sort_values("contribution_to_gap", key=np.abs, ascending=False)


def direction_check(X: pd.DataFrame, sv: pd.DataFrame) -> pd.DataFrame:
    """Does SHAP agree with textbook oncology?  Spearman(feature value, SHAP) against the expected sign."""
    rows = []
    for f, sign in D.CLINICAL_PRIOR.items():
        ok = X[f].notna()
        constant = sv.loc[ok, f].nunique() <= 1          # the model never split on it
        rho = np.nan if (X.loc[ok, f].nunique() < 2 or constant) else spearmanr(X.loc[ok, f], sv.loc[ok, f])[0]
        rows.append(dict(feature=D.LABELS[f], expected="higher -> more risk" if sign > 0 else "higher -> less risk",
                         spearman=rho, agrees=(None if np.isnan(rho) else bool(np.sign(rho) == sign)),
                         mean_abs_shap=float(sv[f].abs().mean())))
    return pd.DataFrame(rows)


def decision_profile(sv: pd.DataFrame, y: np.ndarray, flag: np.ndarray, group: np.ndarray) -> pd.DataFrame:
    """Mean SHAP of missed deaths (FN) vs caught deaths (TP), per group - what pushed a missed
    death below the threshold?"""
    rows = []
    for g in D.GROUPS:
        for name, m in [("TP (caught death)", (y == 1) & (flag == 1)), ("FN (missed death)", (y == 1) & (flag == 0)),
                        ("FP (false alarm)", (y == 0) & (flag == 1)), ("TN", (y == 0) & (flag == 0))]:
            mm = m & (group == g)
            if mm.sum() == 0:
                continue
            r = sv[mm].mean().to_dict()
            r.update(group=g, outcome=name, n=int(mm.sum()))
            rows.append(r)
    return pd.DataFrame(rows)


def explanation_agreement(sv_a: pd.DataFrame, sv_b: pd.DataFrame) -> dict:
    """How much does mitigation change the explanations?  (shared features only)"""
    cols = [c for c in sv_a.columns if c in sv_b.columns]
    ia, ib = sv_a[cols].abs().mean(), sv_b[cols].abs().mean()
    per_patient = [spearmanr(sv_a.iloc[i][cols], sv_b.iloc[i][cols])[0] for i in range(0, len(sv_a), 5)]
    return dict(rank_corr=float(spearmanr(ia, ib)[0]), per_patient_rank_corr=float(np.nanmean(per_patient)))


def shap_stability(X: pd.DataFrame, y: np.ndarray, group: np.ndarray, strata: np.ndarray, params: dict,
                   features: list[str], n_boot: int = 100, seed: int = 0, weights_fn=None) -> pd.DataFrame:
    """Bootstrap the training set, refit, re-explain, and record each feature's rank among Black patients
    (the sub-group with only 30 deaths).  Low stability = do not over-interpret the ranking."""
    rng = np.random.default_rng(seed)
    ranks = []
    for b in range(n_boot):
        idx = np.concatenate([rng.choice(np.where(strata == s)[0], size=(strata == s).sum(), replace=True)
                              for s in np.unique(strata)])
        m = M.make_model(params, seed + b)
        w = M.reweighing_weights(group[idx], y[idx]) if weights_fn else None
        m.fit(X.iloc[idx][features], y[idx], sample_weight=w)
        sv, _ = shap_matrix(m, X, features)
        imp = sv[group == D.UNPRIVILEGED].abs().mean()
        ranks.append(imp.rank(ascending=False))
    R = pd.DataFrame(ranks)
    out = pd.DataFrame({"mean_rank": R.mean(), "rank_sd": R.std(), "top3_freq": (R <= 3).mean(),
                        "rank_lo": R.quantile(0.025), "rank_hi": R.quantile(0.975)})
    out["label"] = [D.LABELS[f] for f in out.index]
    return out.sort_values("mean_rank")
