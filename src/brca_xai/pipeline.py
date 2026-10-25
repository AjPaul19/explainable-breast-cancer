"""End-to-end study orchestration.  The notebook and ``run_pipeline.py`` both drive this class, so
the thesis numbers, the notebook output and the dashboard can never drift apart.

    s = Study(); s.run_all(); s.save()
"""
from __future__ import annotations

import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve, brier_score_loss

from . import audit, explain
from . import data as D
from . import fairness as F
from . import modeling as M

warnings.filterwarnings("ignore")
ROOT = D.ROOT
ART = ROOT / "artifacts"
FIG = ROOT / "reports" / "figures"
W, B = D.PRIVILEGED, D.UNPRIVILEGED
SWEEP_TARGETS = [0.70, 0.75, 0.80, 0.85, 0.90, 0.95]


def _log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Study:
    def __init__(self, seed: int = 42, target: float = M.TARGET_RECALL, n_repeats: int = 5, n_boot: int = 1000,
                 n_stability: int = 100, tune_iter: int = 60):
        self.seed, self.target, self.n_repeats, self.n_boot = seed, target, n_repeats, n_boot
        self.n_stability, self.tune_iter = n_stability, tune_iter
        self.res: dict = {}      # everything that ends up in artifacts

    # ------------------------------------------------------------------ data
    def load(self):
        self.raw = D.load_raw()
        self.c = D.clean(self.raw)
        self.X = D.encode(self.c)
        self.y = self.c[D.TARGET].to_numpy()
        self.g = self.c["race"].to_numpy()
        self.st = D.strata(self.c).to_numpy()
        self.split = D.split_labels(self.c, self.seed)
        self.dev = (self.split == "dev").to_numpy()
        self.res["flow"] = dict(
            n_records=len(self.raw), n_missing_race=int(self.raw["RACE"].isna().sum()),
            n_other_race=int((self.raw["RACE"].notna() & ~self.raw["RACE"].isin(D.RACE_MAP)).sum()),
            n_cohort=len(self.c), n_white=int((self.g == W).sum()), n_black=int((self.g == B).sum()),
            deaths=int(self.y.sum()), deaths_white=int(self.y[self.g == W].sum()), deaths_black=int(self.y[self.g == B].sum()),
            n_dev=int(self.dev.sum()), n_test=int((~self.dev).sum()),
            test_black=int(((~self.dev) & (self.g == B)).sum()), test_black_deaths=int(((~self.dev) & (self.g == B) & (self.y == 1)).sum()),
            test_deaths=int(self.y[~self.dev].sum()), dev_deaths=int(self.y[self.dev].sum()))
        self.table1 = D.table1(self.c)
        self.governance = D.column_governance()
        self.missingness = D.missingness_audit(self.raw)
        return self

    # ------------------------------------------------------------------ model selection
    def tune(self):
        _log("tuning hyper-parameters on the development set ...")
        Xd = self.X[self.dev].reset_index(drop=True)
        self.params, self.tuning = M.tune(Xd, self.y[self.dev], self.st[self.dev], n_iter=self.tune_iter, seed=self.seed)
        self.res["params"] = self.params
        return self

    def audit_models(self):
        _log("leakage ladder and model benchmark ...")
        self.ladder = audit.leakage_ladder(self.c, self.X, self.params)
        self.bench = audit.benchmark(self.c, self.X, self.params)
        return self

    # ------------------------------------------------------------------ hold-out test
    def holdout(self):
        _log("hold-out evaluation ...")
        dev, te = self.dev, ~self.dev
        fits = M.fit_all(M.STRATEGIES, self.X[dev], self.y[dev], self.g[dev], self.st[dev], self.params,
                         target=self.target, seed=self.seed)
        rows, probs = [], {}
        for s in M.STRATEGIES:
            f = fits[s.key]
            p = f.proba(self.X[te])
            flag = (p >= f.threshold_for(self.g[te])).astype(int)
            probs[s.key] = p
            t = F.group_table(self.y[te], flag, self.g[te]).reset_index()
            t.insert(0, "strategy", s.key)
            t["auc"] = [roc_auc_score(self.y[te][m], p[m]) if len(np.unique(self.y[te][m])) > 1 else np.nan
                        for m in [np.ones(te.sum(), bool), self.g[te] == W, self.g[te] == B]]
            rows.append(t)
        self.holdout_table = pd.concat(rows, ignore_index=True)
        self.holdout_thresholds = {k: v.thresholds for k, v in fits.items()}
        self.holdout_probs = probs
        return self

    # ------------------------------------------------------------------ repeated CV fairness study (main result)
    def fairness(self):
        _log(f"repeated {self.n_repeats}x5-fold CV of all strategies ...")
        self.probs, self.flags, thr = F.cv_evaluate(self.X, self.y, self.g, self.st, self.params,
                                                    target=self.target, n_repeats=self.n_repeats, seed=self.seed)
        self.cv_thresholds = F.summarise_thresholds(thr)
        _log("bootstrap ...")
        self.summary, self.draws = F.bootstrap(self.y, self.g, self.flags, n_boot=self.n_boot, seed=self.seed)
        rows = []
        for k in self.flags:
            if k == "aware":
                continue
            for metric in ["tpr_gap", "fpr_gap", "abs_tpr_gap", "eod"]:
                d, lo, hi, p_better = F.paired_difference(self.draws, k, "aware", metric)
                rows.append(dict(strategy=k, metric=metric, diff_vs_aware=d, lo=lo, hi=hi, prob_smaller=p_better))
        self.paired = pd.DataFrame(rows)
        self.oof_mean = {k: v.mean(0) for k, v in self.probs.items()}
        self.auc_group = {}
        for k in ["aware", "blind", "reweigh"]:
            t = F.auc_by_group(self.y, self.g, self.probs[k], n_boot=300, seed=self.seed)
            t.insert(0, "strategy", k)
            self.auc_group[k] = t
        self.auc_group = pd.concat(self.auc_group.values()).reset_index()
        # ROC data (blind model, patient-level mean OOF risk)
        self.roc = {}
        for grp in ["All", W, B]:
            m = np.ones(len(self.y), bool) if grp == "All" else self.g == grp
            fpr, tpr, _ = roc_curve(self.y[m], self.oof_mean["blind"][m])
            self.roc[grp] = (fpr, tpr)
        # calibration of the unweighted models
        rows = []
        for k in ["aware", "blind"]:
            for grp in [W, B]:
                m = self.g == grp
                p = np.clip(self.oof_mean[k][m], 1e-4, 1 - 1e-4)
                lg = np.log(p / (1 - p)).reshape(-1, 1)
                lr = LogisticRegression(C=1e6, max_iter=1000).fit(lg, self.y[m])
                rows.append(dict(strategy=k, group=grp, observed=self.y[m].mean(), mean_predicted=p.mean(),
                                 oe_ratio=self.y[m].mean() / p.mean(), slope=float(lr.coef_[0, 0]),
                                 intercept=float(lr.intercept_[0]), brier=brier_score_loss(self.y[m], p)))
        self.calibration = pd.DataFrame(rows)
        return self

    # ------------------------------------------------------------------ robustness of the fairness conclusions
    def sweep(self):
        _log("recall-target sweep ...")
        rows = []
        for t in SWEEP_TARGETS:
            pr, fl, _ = F.cv_evaluate(self.X, self.y, self.g, self.st, self.params, target=t,
                                      n_repeats=3, seed=self.seed + 1)
            summ, _ = F.bootstrap(self.y, self.g, fl, n_boot=300, seed=self.seed)
            summ["target"] = t
            rows.append(summ)
        self.sweep_table = pd.concat(rows, ignore_index=True)
        return self

    def sensitivity(self):
        _log("sensitivity analyses ...")
        rows = []
        # (a) evaluate only on patients whose outcome is reasonably settled: died, or alive with >= 36 months follow-up
        for months in (24, 36, 60):
            adeq = (self.y == 1) | (self.c["followup_months"].to_numpy() >= months)
            sub = {k: v[:, adeq] for k, v in self.flags.items()}
            summ, _ = F.bootstrap(self.y[adeq], self.g[adeq], sub, n_boot=300, seed=self.seed)
            summ["analysis"] = f"settled outcome (died or >= {months} mo follow-up), n={adeq.sum()}"
            rows.append(summ)
        # (b) point estimates with the group defined by genetic ancestry instead of self-reported race
        anc = self.c["ancestry"].to_numpy()
        arow = []
        for k, f in self.flags.items():
            for lab, m in [("EUR ancestry", anc == "EUR"), ("AFR / AFR-admixed ancestry", np.isin(anc, ["AFR", "AFR_ADMIX"]))]:
                pos, neg = m & (self.y == 1), m & (self.y == 0)
                arow.append(dict(strategy=k, group=lab, n=int(m.sum()), deaths=int(pos.sum()),
                                 recall=f[:, pos].mean(), fpr=f[:, neg].mean(), flag_rate=f[:, m].mean()))
        self.ancestry_table = pd.DataFrame(arow)
        self.sensitivity_table = pd.concat(rows, ignore_index=True)
        return self

    # ------------------------------------------------------------------ deployment models + SHAP
    def final_models(self):
        _log("fitting deployment models on the whole cohort ...")
        self.fits = M.fit_all(M.STRATEGIES, self.X, self.y, self.g, self.st, self.params, target=self.target,
                              seed=self.seed, n_repeats=4)
        return self

    def explain(self):
        _log("SHAP ...")
        fam = {"aware": D.FEATURES_AWARE, "blind": D.FEATURES_BLIND, "reweigh": D.FEATURES_BLIND}
        self.sv, self.base = {}, {}
        for k, feats in fam.items():
            self.sv[k], self.base[k] = explain.shap_matrix(self.fits[k].model, self.X, feats)
        sv, base = self.sv["blind"], self.base["blind"]
        self.margin = sv.sum(1).to_numpy() + base
        self.imp_group = explain.importance_by_group(sv, self.g)
        self.gap_decomp = explain.risk_gap_decomposition(sv, self.g, self.margin)
        self.direction = explain.direction_check(self.X, sv)
        self.profile = explain.decision_profile(sv, self.y, self.flags["blind"][0], self.g)
        self.agreement = {f"blind_vs_{k}": explain.explanation_agreement(self.sv["blind"], self.sv[k]) for k in ["aware", "reweigh"]}
        self.imp_models = pd.DataFrame({k: explain.global_importance(v) for k, v in self.sv.items()})
        _log("SHAP stability bootstrap ...")
        self.stability = explain.shap_stability(self.X, self.y, self.g, self.st, self.params, D.FEATURES_BLIND,
                                                n_boot=self.n_stability, seed=self.seed)
        return self

    # ------------------------------------------------------------------ everything
    def run_all(self):
        self.load().tune().audit_models().holdout().fairness().sweep().sensitivity().final_models().explain()
        self.headline()
        return self

    def headline(self) -> dict:
        s = self.summary.pivot(index="strategy", columns="metric", values="estimate")
        ci = {(r.strategy, r.metric): (r.lo, r.hi) for r in self.summary.itertuples()}
        h = {"target_recall": self.target}
        for k in s.index:
            h[k] = {m: float(s.loc[k, m]) for m in s.columns}
            h[k].update({f"{m}_ci": [float(v) for v in ci[(k, m)]] for m in ["tpr_gap", "fpr_gap", "tpr_B", "tpr_W", "fpr_B", "fpr_W", "tpr_all", "fpr_all", "eod"]})
        self.res["cv"] = h
        ho = self.holdout_table
        self.res["holdout"] = {k: {str(r.group): dict(recall=r.recall, lo=r.recall_lo, hi=r.recall_hi, fpr=r.fpr, n=int(r.n),
                                                      deaths=int(r.deaths), auc=r.auc, flag_rate=r.flag_rate, ppv=r.ppv, specificity=r.specificity)
                                for r in ho[ho.strategy == k].itertuples()} for k in ho.strategy.unique()}
        return self.res

    # ------------------------------------------------------------------ persistence
    def save(self):
        ART.mkdir(exist_ok=True)
        _log(f"writing artifacts to {ART} ...")
        # tables
        self.table1.to_csv(ART / "table1.csv", index=False)
        self.governance.to_csv(ART / "column_governance.csv", index=False)
        self.missingness.to_csv(ART / "missingness_audit.csv", index=False)
        self.ladder.to_csv(ART / "leakage_ladder.csv", index=False)
        self.bench.to_csv(ART / "model_benchmark.csv", index=False)
        self.tuning.to_csv(ART / "tuning_results.csv", index=False)
        self.holdout_table.to_csv(ART / "holdout_by_group.csv", index=False)
        self.summary.to_csv(ART / "fairness_cv_summary.csv", index=False)
        self.paired.to_csv(ART / "fairness_paired_vs_aware.csv", index=False)
        self.cv_thresholds.to_csv(ART / "cv_thresholds.csv", index=False)
        self.auc_group.to_csv(ART / "auc_by_group.csv", index=False)
        self.calibration.to_csv(ART / "calibration_by_group.csv", index=False)
        self.sweep_table.to_csv(ART / "recall_target_sweep.csv", index=False)
        self.sensitivity_table.to_csv(ART / "sensitivity_settled_outcome.csv", index=False)
        self.ancestry_table.to_csv(ART / "sensitivity_ancestry.csv", index=False)
        self.imp_group.to_csv(ART / "importance_black_vs_white.csv")
        self.gap_decomp.to_csv(ART / "risk_gap_decomposition.csv")
        self.direction.to_csv(ART / "shap_direction_check.csv", index=False)
        self.profile.to_csv(ART / "decision_profile.csv", index=False)
        self.imp_models.to_csv(ART / "importance_by_model.csv")
        self.stability.to_csv(ART / "stability_black.csv")
        # roc points
        roc = pd.concat([pd.DataFrame({"group": grp, "fpr": f, "tpr": t}) for grp, (f, t) in self.roc.items()])
        roc.to_csv(ART / "roc_by_group.csv", index=False)
        # cohort with out-of-fold risk and decisions
        coh = self.c.drop(columns=[c for c in self.c.columns if c.startswith("raw_")]).copy()
        coh["split"] = self.split.to_numpy()
        for f in D.FEATURES_AWARE:
            coh[f] = self.X[f].to_numpy()
        for k in self.oof_mean:
            coh[f"oof_risk_{k}"] = self.oof_mean[k]
            coh[f"flag_rate_{k}"] = self.flags[k].mean(0)
        coh.to_csv(ART / "cohort.csv", index=False)
        sv = pd.concat({k: v for k, v in self.sv.items()}, axis=1)
        sv.columns = [f"shap_{a}__{b}" for a, b in sv.columns]
        sv.insert(0, "patient_id", self.c["patient_id"].to_numpy())
        sv.to_csv(ART / "cohort_shap.csv", index=False)
        # models and thresholds
        thr = {}
        for key in ["aware", "blind", "reweigh"]:
            self.fits[key].model.save_model(str(ART / f"xgb_{key}.json"))
        for s in M.STRATEGIES:
            thr[s.key] = self.fits[s.key].thresholds
        meta = dict(self.res)
        meta.update(thresholds=thr, base_value=self.base, features_aware=D.FEATURES_AWARE, features_blind=D.FEATURES_BLIND,
                    labels=D.LABELS, seed=self.seed, n_repeats=self.n_repeats, n_boot=self.n_boot,
                    strategies={s.key: dict(label=s.label, family=s.family, note=s.note, features=list(s.features),
                                            reweigh=s.reweigh, group_thresholds=s.group_thresholds) for s in M.STRATEGIES},
                    risk_gap_total=self.gap_decomp.attrs.get("total_gap"), agreement=self.agreement,
                    holdout_thresholds=self.holdout_thresholds)
        import shap, sklearn, xgboost
        meta["versions"] = dict(xgboost=xgboost.__version__, shap=shap.__version__, sklearn=sklearn.__version__, pandas=pd.__version__)
        (ART / "meta.json").write_text(json.dumps(meta, indent=2, default=float))
        return self
