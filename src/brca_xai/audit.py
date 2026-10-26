"""Evidence for the data-governance decisions, the sensitivity specifications and a model benchmark.

* :func:`leakage_ladder`   - cross-validated AUC as columns are added that should NOT be model inputs.
* :func:`ablation_ladder`  - where the extra AUC of the proposal's predictor list comes from (informative blanks).
* :func:`spec_comparison`  - the proposal's primary specification against the sensitivity specifications.
* :func:`benchmark`        - logistic regression / random forest / XGBoost on identical features.
"""
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


def _oof(fitpred, X, y, strata, n_splits=5, n_repeats=5, seed=11):
    rskf = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=seed)
    oof = np.zeros((n_repeats, len(y)))
    for i, (tr, va) in enumerate(rskf.split(np.zeros(len(y)), strata)):
        oof[i // n_splits, va] = fitpred(X.iloc[tr], y[tr], X.iloc[va])
    return oof


def xgb_fitpred(params, cols, seed=11, monotone=True):
    def f(Xtr, ytr, Xva):
        m = M.make_model(params, seed, cols=list(cols), spw=M.class_weight(ytr), monotone=monotone)
        m.fit(Xtr[list(cols)], ytr)
        return m.predict_proba(Xva[list(cols)])[:, 1]
    return f


def _summ(oof, y, target=M.TARGET_RECALL):
    aucs = [roc_auc_score(y, p) for p in oof]
    out = dict(auc=np.mean(aucs), auc_sd=np.std(aucs), pr_auc=np.mean([average_precision_score(y, p) for p in oof]),
               fpr_at_80_recall=np.mean([M.fpr_at_recall(y, p, target) for p in oof]))
    # precision when the recall target is hit (is the 'acceptable precision' floor cleared?)
    prec = []
    for p in oof:
        thr = M.recall_threshold(y, p, target)
        prec.append(y[p >= thr].mean())
    out["precision_at_80_recall"] = float(np.mean(prec))
    return out


# ---------------------------------------------------------------------------------------------
def leakage_ladder(c: pd.DataFrame, X: pd.DataFrame, params: dict, seed: int = 11) -> pd.DataFrame:
    y, st = c[D.TARGET].to_numpy(), D.strata(c).to_numpy()
    yn = {"Yes": 1.0, "No": 0.0}
    base = X[D.SPECS["hardened"]].copy()
    prop = X[D.SPECS["proposal"]].copy()
    inf = prop.copy()
    inf["hispanic"] = c["raw_ethnicity"].map({"Hispanic Or Latino": 1.0, "Not Hispanic Or Latino": 0.0})
    inf["primary_ln_assessed"] = c["raw_primary_lymph_node_presentation_assessment"].map(yn)
    post = inf.copy()
    post["tumour_status_at_followup"] = c["raw_person_neoplasm_cancer_status"].map({"With Tumor": 1.0, "Tumor Free": 0.0})
    post["new_tumour_event"] = c["raw_new_tumor_event_after_initial_treatment"].map(yn)
    fu = post.copy()
    fu["days_last_followup"] = pd.to_numeric(c["raw_days_last_followup"], errors="coerce")
    rungs = [
        ("0  Audit-hardened features", base, "Age, T, N (NX->N0), M (MX->M0), PAM50, histology, prior dx, race"),
        ("1  Proposal Table 3.2 predictors (as specified)", prop, "Adds radiation therapy, neoadjuvant; NX / MX / TX left missing"),
        ("2  + ethnicity and node-assessment", inf, "Excluded by the proposal: blanks track the outcome"),
        ("3  + tumour status & new tumour event at follow-up", post, "Outcome proxies recorded after diagnosis"),
        ("4  + days to last follow-up", fu, "Blank for every patient who died"),
    ]
    rows = []
    for name, Xr, note in rungs:
        oof = _oof(xgb_fitpred(params, list(Xr.columns), seed), Xr, y, st, seed=seed)
        rows.append(dict(rung=name, n_features=Xr.shape[1], note=note, **_summ(oof, y)))
    return pd.DataFrame(rows)


def ablation_ladder(c: pd.DataFrame, X: pd.DataFrame, params: dict, seed: int = 11) -> pd.DataFrame:
    """Start from the proposal's predictor list and remove one documentation artefact at a time."""
    y, st = c[D.TARGET].to_numpy(), D.strata(c).to_numpy()
    Xa = X.copy()
    Xa["race_black_ref"] = Xa["race_black"].fillna(0.0)
    Xa["race_asian_ref"] = Xa["race_asian"].fillna(0.0)
    P = list(D.SPECS["proposal"])
    sw = lambda cols, m: [m.get(f, f) for f in cols]
    no_rt = [f for f in P if f != "radiation"]
    race_ref = {"race_black": "race_black_ref", "race_asian": "race_asian_ref"}
    nxmx = {"n_stage": "n_stage_h", "m_stage": "m_stage_h"}
    variants = [
        ("Proposal predictors (as specified)", P),
        ("minus radiation therapy (blank = 42 % death)", no_rt),
        ("minus race recorded / not recorded signal (unknown -> White)", sw(P, race_ref)),
        ("minus NX / MX codes (NX -> N0, MX -> M0)", sw(P, nxmx)),
        ("minus all three artefacts", sw(no_rt, {**race_ref, **nxmx})),
        ("minus all three and neoadjuvant (= audit-hardened)", [f for f in sw(no_rt, {**race_ref, **nxmx}) if f != "neoadjuvant"]),
        ("race-blind proposal predictors", [f for f in P if f not in D.RACE_FEATURES]),
    ]
    rows = []
    for name, cols in variants:
        oof = _oof(xgb_fitpred(params, cols, seed), Xa, y, st, seed=seed)
        rows.append(dict(variant=name, **_summ(oof, y)))
    return pd.DataFrame(rows)


def spec_comparison(c: pd.DataFrame, X: pd.DataFrame, params: dict, seed: int = 11) -> pd.DataFrame:
    y, st = c[D.TARGET].to_numpy(), D.strata(c).to_numpy()
    rows = []
    for name, cols in D.SPECS.items():
        oof = _oof(xgb_fitpred(params, cols, seed), X, y, st, seed=seed)
        rows.append(dict(spec=name, n_features=len(cols), **_summ(oof, y)))
    cc = X["sub_luma"].notna().to_numpy()                         # complete-case subtype sensitivity (proposal 3.2.3)
    Xc, yc, sc = X[cc].reset_index(drop=True), y[cc], st[cc]
    oof = _oof(xgb_fitpred(params, D.SPECS["proposal"], seed), Xc, yc, sc, seed=seed)
    rows.append(dict(spec="complete_case_subtype", n_features=len(D.SPECS["proposal"]), **_summ(oof, yc)))
    return pd.DataFrame(rows)


def benchmark(c: pd.DataFrame, X: pd.DataFrame, params: dict, cols: list[str], seed: int = 11) -> pd.DataFrame:
    y, st, g = c[D.TARGET].to_numpy(), D.strata(c).to_numpy(), c["race"].to_numpy()
    lr = lambda cl: (lambda Xt, yt, Xv: make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(),
                                                      LogisticRegression(C=0.3, class_weight="balanced", max_iter=3000))
                     .fit(Xt[cl], yt).predict_proba(Xv[cl])[:, 1])
    rf = lambda cl: (lambda Xt, yt, Xv: make_pipeline(SimpleImputer(strategy="median", add_indicator=True),
                                                      RandomForestClassifier(300, min_samples_leaf=10, class_weight="balanced_subsample", random_state=seed, n_jobs=-1))
                     .fit(Xt[cl], yt).predict_proba(Xv[cl])[:, 1])
    models = {
        "Stage-only (logistic)": lr(["stage_group"]),
        "Logistic regression": lr(cols),
        "Random forest": rf(cols),
        "XGBoost (defaults)": xgb_fitpred(None, cols, seed),
        "XGBoost (tuned, no monotone constraint)": xgb_fitpred(params, cols, seed, monotone=False),
        "XGBoost (tuned, monotone) - used": xgb_fitpred(params, cols, seed),
    }
    rows = []
    for name, fp in models.items():
        oof = _oof(fp, X, y, st, seed=seed)
        r = _summ(oof, y)
        for grp in D.GROUPS:
            m = g == grp
            r[f"auc_{grp}"] = np.mean([roc_auc_score(y[m], p[m]) for p in oof])
        rows.append(dict(model=name, **r))
    return pd.DataFrame(rows)
