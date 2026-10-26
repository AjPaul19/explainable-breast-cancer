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
        if f not in sv.columns:
            continue
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
                   features: list[str], n_boot: int = 100, seed: int = 0, weights_fn=None) -> tuple[pd.DataFrame, float]:
    """Bootstrap the training set, refit, re-explain, and record each feature's importance rank among Black patients
    (the sub-group with only 30 deaths) and overall.  Returns (table, mean pairwise Spearman of the overall importance
    vectors across bootstraps).  Low stability = do not over-interpret the ranking."""
    rng = np.random.default_rng(seed)
    r_black, r_all, vecs = [], [], []
    for b in range(n_boot):
        idx = np.concatenate([rng.choice(np.where(strata == s)[0], size=(strata == s).sum(), replace=True)
                              for s in np.unique(strata)])
        m = M.make_model(params, seed + b, cols=features, spw=M.class_weight(y[idx]))
        w = M.reweighing_weights(group[idx], y[idx]) if weights_fn else None
        m.fit(X.iloc[idx][features], y[idx], sample_weight=w)
        sv, _ = shap_matrix(m, X, features)
        r_black.append(sv[group == D.UNPRIVILEGED].abs().mean().rank(ascending=False))
        imp = sv.abs().mean(); vecs.append(imp.to_numpy()); r_all.append(imp.rank(ascending=False))
    R, A = pd.DataFrame(r_black), pd.DataFrame(r_all)
    out = pd.DataFrame({"mean_rank": R.mean(), "rank_sd": R.std(), "top3_freq": (R <= 3).mean(),
                        "rank_lo": R.quantile(0.025), "rank_hi": R.quantile(0.975),
                        "mean_rank_all": A.mean(), "top3_freq_all": (A <= 3).mean()})
    out["label"] = [D.LABELS[f] for f in out.index]
    V = np.array(vecs)
    pair = [spearmanr(V[i], V[j])[0] for i in range(0, len(V), 2) for j in range(i + 1, len(V), 7)]
    return out.sort_values("mean_rank"), float(np.nanmean(pair))


# --------------------------------------------------------------------------------------------
# Explanation quality (proposal 3.2.6): fidelity, stability, clinical alignment, race check, faithfulness
# --------------------------------------------------------------------------------------------
def fidelity(model, X: pd.DataFrame, features: list[str]) -> dict:
    """Local accuracy: base value + sum of SHAP values must equal the model's margin for every patient."""
    sv, base = shap_matrix(model, X, features)
    margin = model.predict(X[features], output_margin=True)
    err = np.abs(sv.sum(1).to_numpy() + base - margin)
    return dict(max_abs_error=float(err.max()), mean_abs_error=float(err.mean()), n=len(X))


def builtin_agreement(model, sv: pd.DataFrame) -> pd.DataFrame:
    """Rank correlation between mean |SHAP| and XGBoost's built-in importances."""
    shap_imp = sv.abs().mean()
    rows = []
    booster = model.get_booster()
    for kind in ["gain", "total_gain", "weight", "cover"]:
        sc = booster.get_score(importance_type=kind)
        v = pd.Series({f: sc.get(f, 0.0) for f in sv.columns})
        rows.append(dict(importance_type=kind, spearman_with_shap=float(spearmanr(shap_imp, v)[0])))
    return pd.DataFrame(rows)


def fold_stability(X: pd.DataFrame, y: np.ndarray, strata: np.ndarray, params: dict, features: list[str], seed: int = 0) -> dict:
    """Rank correlation of global importance between models trained on different CV folds (5 x 2)."""
    from sklearn.model_selection import RepeatedStratifiedKFold
    vecs = []
    for tr, _ in RepeatedStratifiedKFold(n_splits=5, n_repeats=2, random_state=seed).split(np.zeros(len(y)), strata):
        m = M.make_model(params, seed, cols=features, spw=M.class_weight(y[tr])).fit(X.iloc[tr][features], y[tr])
        vecs.append(shap_matrix(m, X, features)[0].abs().mean().to_numpy())
    pair = [spearmanr(vecs[i], vecs[j])[0] for i in range(len(vecs)) for j in range(i + 1, len(vecs))]
    return dict(mean_spearman=float(np.nanmean(pair)), min_spearman=float(np.nanmin(pair)), n_models=len(vecs))


def clinical_alignment(sv: pd.DataFrame, top: int = 5) -> pd.DataFrame:
    imp = global_importance(sv)
    rows = []
    for r, (f, v) in enumerate(imp.head(top).items(), 1):
        rows.append(dict(rank=r, feature=D.LABELS[f], mean_abs_shap=float(v),
                         established_prognostic_factor=D.ESTABLISHED_FACTORS.get(f, "no (administrative / treatment-documentation field)")))
    return pd.DataFrame(rows)


def race_check(sv: pd.DataFrame, X: pd.DataFrame, c: pd.DataFrame) -> pd.DataFrame:
    """Does the model lean on race?  Mean |SHAP| of the race columns, split by whether race was recorded."""
    rows = []
    cols = [f for f in D.RACE_FEATURES if f in sv.columns]
    if not cols:
        return pd.DataFrame()
    total = sv.abs().sum(1)
    for lab, m in [("race recorded", c["race_detail"] != "Unknown"), ("race NOT recorded", c["race_detail"] == "Unknown")]:
        rs = sv.loc[m.to_numpy(), cols].sum(1)
        rows.append(dict(patients=lab, n=int(m.sum()), mean_race_shap=float(rs.mean()), mean_abs_race_shap=float(rs.abs().mean()),
                         share_of_total_attribution=float(rs.abs().sum() / total[m.to_numpy()].sum()),
                         death_rate=float(c.loc[m, D.TARGET].mean())))
    return pd.DataFrame(rows)


def deletion_test(model, X: pd.DataFrame, y: np.ndarray, sv: pd.DataFrame, features: list[str], ks=(1, 2, 3, 4), seed: int = 0) -> pd.DataFrame:
    """Faithfulness: blank the k most-attributed features of every patient (set to missing) and compare the AUC drop with
    blanking k random features.  A faithful explanation should hurt more than chance."""
    from sklearn.metrics import roc_auc_score
    rng = np.random.default_rng(seed)
    base = roc_auc_score(y, model.predict_proba(X[features])[:, 1])
    absv = sv.abs().to_numpy()
    order = np.argsort(-absv, axis=1)
    rows = [dict(k=0, auc_top_shap=base, auc_random=base)]
    for k in ks:
        Xt = X[features].to_numpy().copy(); Xr = X[features].to_numpy().copy()
        for i in range(len(Xt)):
            Xt[i, order[i, :k]] = np.nan
            Xr[i, rng.choice(len(features), k, replace=False)] = np.nan
        rows.append(dict(k=k, auc_top_shap=roc_auc_score(y, model.predict_proba(pd.DataFrame(Xt, columns=features))[:, 1]),
                         auc_random=roc_auc_score(y, model.predict_proba(pd.DataFrame(Xr, columns=features))[:, 1])))
    return pd.DataFrame(rows)
