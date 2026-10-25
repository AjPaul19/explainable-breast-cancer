"""Evidence for the data-governance decisions and a simple model benchmark.

* :func:`leakage_ladder` - cross-validated AUC as columns are added that should NOT be model inputs.
  Each rung shows how much an unprotected pipeline would overstate performance.
* :func:`benchmark` - logistic regression / random forest / XGBoost on the same clean features.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import data as D
from . import modeling as M


def _oof(make, X, y, strata, n_splits=5, n_repeats=5, seed=11):
    rskf = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=seed)
    oof = np.zeros((n_repeats, len(y)))
    for i, (tr, va) in enumerate(rskf.split(np.zeros(len(y)), strata)):
        m = make()
        m.fit(X.iloc[tr], y[tr])
        oof[i // n_splits, va] = m.predict_proba(X.iloc[va])[:, 1]
    return oof


def _summ(oof, y):
    aucs = [roc_auc_score(y, p) for p in oof]
    fprs = [M.fpr_at_recall(y, p) for p in oof]
    return dict(auc=np.mean(aucs), auc_sd=np.std(aucs), fpr_at_80_recall=np.mean(fprs))


def leakage_ladder(c: pd.DataFrame, X: pd.DataFrame, params: dict, seed: int = 11) -> pd.DataFrame:
    y = c[D.TARGET].to_numpy()
    st = D.strata(c).to_numpy()
    base = X[D.FEATURES_BLIND].copy()

    naive = base.copy()
    naive["n_stage"] = D._ordinal(c["raw_path_n_stage"], "N")          # NX stays missing
    naive["m_stage"] = np.where(c["raw_path_m_stage"] == "MX", np.nan, base["m_stage"])
    yn = {"Yes": 1.0, "No": 0.0}
    inf = naive.copy()
    inf["radiation"] = c["raw_radiation_therapy"].map(yn)
    inf["hispanic"] = c["raw_ethnicity"].map({"Hispanic Or Latino": 1.0, "Not Hispanic Or Latino": 0.0})
    inf["primary_ln_assessed"] = c["raw_primary_lymph_node_presentation_assessment"].map(yn)
    post = inf.copy()
    post["tumour_status_at_followup"] = c["raw_person_neoplasm_cancer_status"].map({"With Tumor": 1.0, "Tumor Free": 0.0})
    post["new_tumour_event"] = c["raw_new_tumor_event_after_initial_treatment"].map(yn)
    fu = post.copy()
    fu["days_last_followup"] = pd.to_numeric(c["raw_days_last_followup"], errors="coerce")

    rungs = [
        ("0  Clean pre-treatment features (used)", base, "Age, T, N (NX->N0), M (MX->M0), PAM50, histology, prior diagnosis"),
        ("1  + NX / MX left as 'missing'", naive, "Registry 'not assessed' codes: NX has a 61 % death rate"),
        ("2  + radiation, ethnicity, node-assessment (informative missingness)", inf, "Their blanks track the outcome (56 % vs 12 % for radiation)"),
        ("3  + tumour status & new-tumour event at follow-up (post-baseline)", post, "Outcome proxies recorded after diagnosis"),
        ("4  + days to last follow-up", fu, "Blank for every patient who died"),
    ]
    rows = []
    for name, Xr, note in rungs:
        oof = _oof(lambda: M.make_model(params, seed), Xr, y, st, seed=seed)
        rows.append(dict(rung=name, n_features=Xr.shape[1], note=note, **_summ(oof, y)))
    return pd.DataFrame(rows)


def benchmark(c: pd.DataFrame, X: pd.DataFrame, params: dict, seed: int = 11) -> pd.DataFrame:
    y = c[D.TARGET].to_numpy()
    st = D.strata(c).to_numpy()
    g = c["race"].to_numpy()
    Xb = X[D.FEATURES_BLIND]
    models = {
        "Logistic regression": lambda: make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                                     LogisticRegression(C=1.0, max_iter=2000)),
        "Random forest": lambda: make_pipeline(SimpleImputer(strategy="median"),
                                               RandomForestClassifier(400, min_samples_leaf=8, random_state=seed, n_jobs=-1)),
        "XGBoost (defaults, monotone TNM)": lambda: M.make_model(None, seed),
        "XGBoost (tuned, no monotone constraint)": lambda: M.make_model(params, seed, monotone=False),
        "XGBoost (tuned, monotone TNM) - used": lambda: M.make_model(params, seed),
    }
    rows = []
    for name, mk in models.items():
        oof = _oof(mk, Xb, y, st, seed=seed)
        r = _summ(oof, y)
        for grp in D.GROUPS:
            m = g == grp
            r[f"auc_{grp}"] = np.mean([roc_auc_score(y[m], p[m]) for p in oof])
        rows.append(dict(model=name, **r))
    return pd.DataFrame(rows)
