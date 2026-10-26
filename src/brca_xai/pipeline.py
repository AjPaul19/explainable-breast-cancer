"""End-to-end study orchestration.  The notebook and ``run_pipeline.py`` both drive this class, so the thesis
numbers, the notebook output and the dashboard can never drift apart.

    Study(spec="proposal").run_all().save()      # the revised proposal's predictor list (primary model)
    Study(spec="hardened").run_all().save()      # audit-hardened sensitivity specification

Specifications (``brca_xai.data.SPECS``):
  proposal    Table 3.2 of the revised proposal, as written.
  hardened    the same without the documentation artefacts the audit found (radiation / neoadjuvant blanks,
              NX / MX codes, race-not-recorded signal is kept as in the proposal but quantified).
"""
from __future__ import annotations

import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score, roc_curve

from . import audit, evaluate, explain
from . import data as D
from . import fairness as F
from . import modeling as M

warnings.filterwarnings("ignore")
ROOT = D.ROOT
ART_ROOT = ROOT / "artifacts"
FIG_ROOT = ROOT / "reports" / "figures"
W, B = D.PRIVILEGED, D.UNPRIVILEGED
SWEEP_TARGETS = [0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
MAIN = "aware"            # the proposal's model: race is one of the predictors


def _log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Study:
    def __init__(self, spec: str = "proposal", seed: int = 42, target: float = M.TARGET_RECALL, n_repeats: int = 5,
                 n_boot: int = 1000, n_stability: int = 100, n_trials: int = 60):
        self.spec, self.seed, self.target = spec, seed, target
        self.n_repeats, self.n_boot, self.n_stability, self.n_trials = n_repeats, n_boot, n_stability, n_trials
        self.art, self.fig = ART_ROOT / spec, FIG_ROOT / spec
        self.strategies = M.make_strategies(spec)
        self.feats = list(D.SPECS[spec])                           # inputs of the main (race-aware) model
        self.feats_blind = [f for f in self.feats if f not in D.RACE_FEATURES]
        self.main = MAIN
        self.res: dict = {"spec": spec}

    # ------------------------------------------------------------------ data
    def load(self):
        self.raw = D.load_raw()
        self.c = D.clean(self.raw)
        self.X = D.encode(self.c)
        self.y = self.c[D.TARGET].to_numpy()
        self.g = self.c["race"].to_numpy()
        self.wb = np.isin(self.g, D.GROUPS)                        # rows of the White / Black fairness audit
        self.st = D.strata(self.c).to_numpy()
        self.split = D.split_labels(self.c, self.seed)
        self.dev = (self.split == "dev").to_numpy()
        te = ~self.dev
        self.res["flow"] = dict(
            n_records=len(self.raw), n_deaths=int(self.y.sum()), prevalence=float(self.y.mean()),
            n_white=int((self.g == W).sum()), n_black=int((self.g == B).sum()), n_other=int((self.g == D.OTHER).sum()),
            n_asian=int((self.c.race_detail == "Asian").sum()), n_unknown_race=int((self.c.race_detail == "Unknown").sum()),
            deaths_white=int(self.y[self.g == W].sum()), deaths_black=int(self.y[self.g == B].sum()),
            deaths_other=int(self.y[self.g == D.OTHER].sum()), n_wb=int(self.wb.sum()), deaths_wb=int(self.y[self.wb].sum()),
            n_dev=int(self.dev.sum()), n_test=int(te.sum()), dev_deaths=int(self.y[self.dev].sum()), test_deaths=int(self.y[te].sum()),
            test_black=int((te & (self.g == B)).sum()), test_black_deaths=int((te & (self.g == B) & (self.y == 1)).sum()),
            median_followup=float(self.c.followup_months.median()), max_followup=float(self.c.followup_months.max()),
            living_lt60=float((self.c.loc[self.y == 0, "followup_months"] < 60).mean()),
            spw=float(M.class_weight(self.y[self.dev])), precision_floor=float(M.PRECISION_FLOOR_MULT * self.y[self.dev].mean()))
        self.table1 = D.table1(self.c)
        self.governance = D.column_governance()
        self.missingness = D.missingness_audit(self.raw)
        return self

    # ------------------------------------------------------------------ model selection
    def tune(self):
        _log(f"[{self.spec}] Bayesian tuning on the development set ...")
        Xd = self.X[self.dev].reset_index(drop=True)
        self.params, self.tuning = M.tune(Xd, self.y[self.dev], self.st[self.dev], self.feats, n_trials=self.n_trials, seed=self.seed)
        self.res["params"] = self.params
        return self

    def audit_models(self):
        _log(f"[{self.spec}] benchmark ...")
        self.bench = audit.benchmark(self.c, self.X, self.params, self.feats)
        if self.spec == "proposal":
            _log("leakage ladder, artefact ablation, specification comparison, survival check ...")
            self.ladder = audit.leakage_ladder(self.c, self.X, self.params)
            self.ablation = audit.ablation_ladder(self.c, self.X, self.params)
            self.spec_table = audit.spec_comparison(self.c, self.X, self.params)
            self.res["survival"] = evaluate.survival_check(self.X, self.c, self.params, self.feats, self.st, self.seed)
        return self

    # ------------------------------------------------------------------ hold-out test set (proposal 3.2.5)
    def holdout(self):
        _log(f"[{self.spec}] hold-out evaluation ...")
        dev, te = self.dev, ~self.dev
        yte, gte = self.y[te], self.g[te]
        fits = M.fit_all(self.strategies, self.X[dev], self.y[dev], self.g[dev], self.st[dev], self.params,
                         target=self.target, seed=self.seed)
        self.holdout_thresholds = {k: v.thresholds for k, v in fits.items()}
        # per-group table for every strategy
        rows, probs = [], {}
        for s in self.strategies:
            f = fits[s.key]
            p = f.proba(self.X[te]); probs[s.key] = p
            flag = (p >= f.threshold_for(gte)).astype(int)
            t = F.group_table(yte, flag, gte).reset_index(); t.insert(0, "strategy", s.key)
            t["auc"] = [roc_auc_score(yte[m], p[m]) if len(np.unique(yte[m])) > 1 else np.nan
                        for m in [np.ones(te.sum(), bool), gte == W, gte == B]]
            rows.append(t)
        self.holdout_table = pd.concat(rows, ignore_index=True)
        self.holdout_probs = probs
        # overall metrics with bootstrap CI: XGBoost + baselines under the same protocol
        base = evaluate.fit_baselines(self.X, self.y, self.st, dev, self.seed, self.target, self.feats)
        models = {"XGBoost (race-aware, primary)": (probs["aware"], fits["aware"].thresholds["global"]),
                  "XGBoost (race-blind)": (probs["blind"], fits["blind"].thresholds["global"])}
        for k, v in base.items():
            models[k] = (v["p_test"], v["thr"])
        parts = []
        for name, (p, thr) in models.items():
            t = evaluate.bootstrap_metrics(yte, p, thr, n_boot=self.n_boot, seed=self.seed); t.insert(0, "model", name)
            parts.append(t)
        # no-skill baseline: always predict "living"
        parts.append(pd.DataFrame([dict(model="Always 'living' (no skill)", metric="accuracy", estimate=1 - yte.mean(), lo=np.nan, hi=np.nan)]))
        self.test_metrics = pd.concat(parts, ignore_index=True)
        self.test_confusion = pd.DataFrame([dict(model=name, **{k: evaluate.threshold_metrics(yte, p, thr)[k] for k in ["tp", "fn", "fp", "tn"]}, threshold=float(thr))
                                            for name, (p, thr) in models.items()])
        self.baseline_info = {k: dict(hp=v["hp"], auc_cv=v["auc_cv"], thr=v["thr"]) for k, v in base.items()}
        # threshold rules on dev OOF -> test
        oof = M.oof_scores(self.strategies[0], self.X[dev].reset_index(drop=True), self.y[dev], self.g[dev], self.st[dev], self.params, seed=self.seed)
        rules = M.threshold_rules(self.y[dev], oof)
        pa = probs["aware"]
        self.rule_table = pd.DataFrame([dict(rule=k, threshold=v, **{m: evaluate.threshold_metrics(yte, pa, v)[m] for m in ["recall", "precision", "specificity", "f1", "flag_rate"]},
                                             dev_recall=evaluate.threshold_metrics(self.y[dev], oof, v)["recall"],
                                             dev_precision=evaluate.threshold_metrics(self.y[dev], oof, v)["precision"])
                                        for k, v in rules.items()])
        # overfitting control
        self.curve = evaluate.learning_curve(self.X, self.y, self.st, dev, self.params, self.feats, self.seed)
        return self

    # ------------------------------------------------------------------ repeated CV (all strategies) + fairness audit
    def fairness(self):
        _log(f"[{self.spec}] repeated {self.n_repeats}x5-fold CV of all strategies ...")
        self.probs, self.flags, thr = F.cv_evaluate(self.X, self.y, self.g, self.st, self.params, strategies=self.strategies,
                                                    target=self.target, n_repeats=self.n_repeats, seed=self.seed)
        self.cv_thresholds = F.summarise_thresholds(thr)
        wb, yw, gw = self.wb, self.y[self.wb], self.g[self.wb]
        fw = {k: v[:, wb] for k, v in self.flags.items()}
        _log("bootstrap ...")
        self.summary, self.draws = F.bootstrap(yw, gw, fw, n_boot=self.n_boot, seed=self.seed)
        rows = []
        for k in self.flags:
            if k == MAIN:
                continue
            for metric in ["tpr_gap", "fpr_gap", "abs_tpr_gap", "eod"]:
                d, lo, hi, p = F.paired_difference(self.draws, k, MAIN, metric)
                rows.append(dict(strategy=k, metric=metric, diff_vs_aware=d, lo=lo, hi=hi, prob_smaller=p))
        self.paired = pd.DataFrame(rows)
        self.oof_mean = {k: v.mean(0) for k, v in self.probs.items()}
        parts = []
        for k in ["aware", "blind", "reweigh"]:
            t = F.auc_by_group(yw, gw, self.probs[k][:, wb], n_boot=300, seed=self.seed); t.insert(0, "strategy", k); parts.append(t)
        self.auc_group = pd.concat(parts).reset_index()
        # whole-cohort (all 1,084 patients) operating characteristics with CI
        rng = np.random.default_rng(self.seed)
        draws = {k: [] for k in self.flags}
        for _ in range(min(self.n_boot, 500)):
            idx = rng.integers(0, len(self.y), len(self.y))
            for k, f in self.flags.items():
                ff, yy = f[:, idx], self.y[idx]
                tp = ff[:, yy == 1].mean(); fp = ff[:, yy == 0].mean(); fl = ff.mean()
                draws[k].append(dict(recall=tp, fpr=fp, flag_rate=fl, precision=(ff * (yy == 1)).sum() / max(ff.sum(), 1)))
        rows = []
        for k, f in self.flags.items():
            tp = f[:, self.y == 1].mean(); fp = f[:, self.y == 0].mean()
            pt = dict(recall=tp, fpr=fp, flag_rate=f.mean(), precision=(f * (self.y == 1)).sum() / f.sum())
            d = pd.DataFrame(draws[k])
            for m, v in pt.items():
                rows.append(dict(strategy=k, metric=m, estimate=float(v), lo=float(d[m].quantile(.025)), hi=float(d[m].quantile(.975))))
            for m, fn in [("auc_roc", roc_auc_score), ("pr_auc", average_precision_score)]:
                v = np.array([fn(self.y, p) for p in self.probs[k]])
                rows.append(dict(strategy=k, metric=m, estimate=float(v.mean()), lo=np.nan, hi=np.nan))
        self.cv_overall = pd.DataFrame(rows)
        # ROC / PR curves of the main model (race groups)
        self.roc = {}
        for grp in ["All", W, B]:
            m = np.ones(len(self.y), bool) if grp == "All" else self.g == grp
            fpr, tpr, _ = roc_curve(self.y[m], self.oof_mean[MAIN][m]); self.roc[grp] = (fpr, tpr)
        self._calibrate()
        return self

    def _calibrate(self):
        """Class weighting (scale_pos_weight) inflates raw scores, so they are *not* probabilities.  A single logistic
        recalibration (Platt) is fitted on all patients' out-of-fold scores; calibration is then compared across race groups
        with that one shared mapping (observed / expected ratio, within-group slope)."""
        self.platt, rows = {}, []
        for k in ["aware", "blind", "reweigh"]:
            z = np.log(np.clip(self.oof_mean[k], 1e-4, 1 - 1e-4) / (1 - np.clip(self.oof_mean[k], 1e-4, 1 - 1e-4)))
            lr = LogisticRegression(C=1e6, max_iter=1000).fit(z.reshape(-1, 1), self.y)
            a, b = float(lr.intercept_[0]), float(lr.coef_[0, 0])
            self.platt[k] = dict(intercept=a, slope=b)
            cal = 1 / (1 + np.exp(-(a + b * z)))
            if k == "reweigh":
                continue
            for grp in [W, B]:
                m = self.g == grp
                lrg = LogisticRegression(C=1e6, max_iter=1000).fit(z[m].reshape(-1, 1), self.y[m])
                rows.append(dict(strategy=k, group=grp, observed=self.y[m].mean(), mean_recalibrated=cal[m].mean(), oe_ratio=self.y[m].mean() / cal[m].mean(),
                                 raw_mean_score=self.oof_mean[k][m].mean(), within_group_slope=float(lrg.coef_[0, 0]),
                                 within_group_intercept=float(lrg.intercept_[0]), brier_recalibrated=brier_score_loss(self.y[m], cal[m])))
        self.calibration = pd.DataFrame(rows)
        self.res["platt"] = self.platt
        return self

    def sweep(self):
        _log(f"[{self.spec}] recall-target sweep ...")
        rows = []
        for t in SWEEP_TARGETS:
            pr, fl, _ = F.cv_evaluate(self.X, self.y, self.g, self.st, self.params, strategies=self.strategies, target=t,
                                      n_repeats=3, seed=self.seed + 1)
            summ, _ = F.bootstrap(self.y[self.wb], self.g[self.wb], {k: v[:, self.wb] for k, v in fl.items()}, n_boot=300, seed=self.seed)
            summ["target"] = t; rows.append(summ)
        self.sweep_table = pd.concat(rows, ignore_index=True)
        return self

    def model_sensitivity(self, n_configs: int = 5):
        """How much do the fairness estimates move across near-equivalent tuned configurations?  Re-runs the 5 x CV audit (3 repeats)
        for the best ``n_configs`` configurations of the Bayesian search plus a depth-1 additive model."""
        _log(f"[{self.spec}] model-selection sensitivity ...")
        tab = self.tuning.drop_duplicates(subset=["max_depth", "n_estimators"]).head(n_configs)
        cfgs = [(f"top-{i + 1}: depth {int(r.max_depth)}, {int(r.n_estimators)} trees", {k: (int(r[k]) if k in ("max_depth", "n_estimators") else float(r[k])) for k in M.DEFAULT_PARAMS})
                for i, (_, r) in enumerate(tab.iterrows())]
        cfgs.append(("depth-1 additive, 250 trees", {**M.DEFAULT_PARAMS, "max_depth": 1, "n_estimators": 250, "learning_rate": 0.03, "min_child_weight": 0.8, "reg_lambda": 5.0}))
        rows = []
        yw, gw = self.y[self.wb], self.g[self.wb]
        splits = list(RepeatedStratifiedKFold(n_splits=5, n_repeats=2, random_state=1).split(np.zeros(len(self.y)), self.st))
        for name, prm in cfgs:
            _, fl, _ = F.cv_evaluate(self.X, self.y, self.g, self.st, prm, strategies=self.strategies, target=self.target, n_repeats=3, seed=self.seed + 2)
            summ, _ = F.bootstrap(yw, gw, {k: v[:, self.wb] for k, v in fl.items()}, n_boot=200, seed=self.seed)
            sm = summ[summ.metric.isin(["tpr_gap", "fpr_gap", "eod"])].copy(); sm["config"] = name
            cv_auc, _ = M.cv_score(prm, self.X, self.y, splits, 5, 2, self.feats)
            sm["cv_auc"] = cv_auc
            rows.append(sm)
        self.model_sens = pd.concat(rows, ignore_index=True)
        return self

    def sensitivity(self):
        _log(f"[{self.spec}] sensitivity analyses ...")
        rows = []
        yw, gw = self.y[self.wb], self.g[self.wb]
        fu = self.c["followup_months"].to_numpy()[self.wb]
        for months in (24, 36, 60):
            adeq = (yw == 1) | (fu >= months)
            sub = {k: v[:, self.wb][:, adeq] for k, v in self.flags.items()}
            summ, _ = F.bootstrap(yw[adeq], gw[adeq], sub, n_boot=300, seed=self.seed)
            summ["analysis"] = f"settled outcome (died or >= {months} mo follow-up), n={adeq.sum()}"
            rows.append(summ)
        self.sensitivity_table = pd.concat(rows, ignore_index=True)
        anc = self.c["ancestry"].to_numpy()
        arow = []
        for k, f in self.flags.items():
            for lab, m in [("EUR ancestry", anc == "EUR"), ("AFR / AFR-admixed ancestry", np.isin(anc, ["AFR", "AFR_ADMIX"]))]:
                pos, neg = m & (self.y == 1), m & (self.y == 0)
                arow.append(dict(strategy=k, group=lab, n=int(m.sum()), deaths=int(pos.sum()), recall=f[:, pos].mean(),
                                 fpr=f[:, neg].mean(), flag_rate=f[:, m].mean()))
        self.ancestry_table = pd.DataFrame(arow)
        return self

    # ------------------------------------------------------------------ deployment models + SHAP
    def final_models(self):
        _log(f"[{self.spec}] fitting deployment models on all patients ...")
        self.fits = M.fit_all(self.strategies, self.X, self.y, self.g, self.st, self.params, target=self.target,
                              seed=self.seed, n_repeats=4)
        return self

    def explain(self):
        _log(f"[{self.spec}] SHAP and explanation quality ...")
        fam = {"aware": self.feats, "blind": self.feats_blind, "reweigh": self.feats_blind}
        self.sv, self.base = {}, {}
        for k, feats in fam.items():
            self.sv[k], self.base[k] = explain.shap_matrix(self.fits[k].model, self.X, feats)
        sv, base = self.sv[MAIN], self.base[MAIN]
        gw = self.g
        self.margin = sv.sum(1).to_numpy() + base
        self.imp_group = explain.importance_by_group(sv[self.wb], gw[self.wb])
        self.gap_decomp = explain.risk_gap_decomposition(sv[self.wb], gw[self.wb], self.margin[self.wb])
        self.direction = explain.direction_check(self.X, sv)
        self.profile = explain.decision_profile(sv[self.wb], self.y[self.wb], self.flags[MAIN][0][self.wb], gw[self.wb])
        self.agreement = {f"main_vs_{k}": explain.explanation_agreement(sv, self.sv[k]) for k in ["blind", "reweigh"]}
        self.imp_models = pd.DataFrame({k: explain.global_importance(v) for k, v in self.sv.items()})
        # explanation quality (proposal 3.2.6)
        model = self.fits[MAIN].model
        self.fidelity = explain.fidelity(model, self.X, self.feats)
        self.builtin = explain.builtin_agreement(model, sv)
        self.fold_stab = explain.fold_stability(self.X, self.y, self.st, self.params, self.feats, self.seed)
        self.alignment = explain.clinical_alignment(sv)
        self.race_shap = explain.race_check(sv, self.X, self.c)
        self.deletion = explain.deletion_test(model, self.X, self.y, sv, self.feats)
        _log("SHAP stability bootstrap ...")
        self.stability, self.boot_stab = explain.shap_stability(self.X, self.y, self.g, self.st, self.params, self.feats,
                                                                n_boot=self.n_stability, seed=self.seed)
        self.res["explain_quality"] = dict(fidelity=self.fidelity, fold_stability=self.fold_stab, bootstrap_stability=self.boot_stab,
                                           builtin=self.builtin.set_index("importance_type").spearman_with_shap.to_dict())
        return self

    # ------------------------------------------------------------------ everything
    def run_all(self):
        self.load().tune().audit_models().holdout().fairness().sweep().model_sensitivity().sensitivity().final_models().explain()
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
        o = self.cv_overall
        self.res["cv_overall"] = {k: {r.metric: [float(r.estimate), float(r.lo), float(r.hi)] for r in o[o.strategy == k].itertuples()} for k in o.strategy.unique()}
        tm = self.test_metrics
        self.res["test"] = {m: {r.metric: [float(r.estimate), float(r.lo), float(r.hi)] for r in tm[tm.model == m].itertuples()} for m in tm.model.unique()}
        ho = self.holdout_table
        self.res["holdout"] = {k: {str(r.group): dict(recall=r.recall, lo=r.recall_lo, hi=r.recall_hi, fpr=r.fpr, n=int(r.n), deaths=int(r.deaths),
                                                      auc=r.auc, flag_rate=r.flag_rate, ppv=r.ppv, specificity=r.specificity)
                                for r in ho[ho.strategy == k].itertuples()} for k in ho.strategy.unique()}
        return self.res

    # ------------------------------------------------------------------ persistence
    def save(self):
        a = self.art; a.mkdir(parents=True, exist_ok=True)
        _log(f"writing artifacts to {a} ...")
        tabs = dict(table1=self.table1, column_governance=self.governance, missingness_audit=self.missingness, model_benchmark=self.bench,
                    tuning_results=self.tuning, holdout_by_group=self.holdout_table, test_metrics=self.test_metrics,
                    test_confusion=self.test_confusion, threshold_rules=self.rule_table, learning_curve=self.curve,
                    fairness_cv_summary=self.summary, fairness_paired_vs_main=self.paired, cv_thresholds=self.cv_thresholds,
                    auc_by_group=self.auc_group, cv_overall=self.cv_overall, calibration_by_group=self.calibration,
                    recall_target_sweep=self.sweep_table, sensitivity_settled_outcome=self.sensitivity_table,
                    sensitivity_ancestry=self.ancestry_table, model_selection_sensitivity=self.model_sens, importance_by_group=self.imp_group, risk_gap_decomposition=self.gap_decomp,
                    shap_direction_check=self.direction, decision_profile=self.profile, importance_by_model=self.imp_models,
                    stability_black=self.stability, shap_builtin_agreement=self.builtin, clinical_alignment=self.alignment,
                    race_shap_check=self.race_shap, deletion_test=self.deletion)
        if self.spec == "proposal":
            tabs.update(leakage_ladder=self.ladder, artefact_ablation=self.ablation, spec_comparison=self.spec_table)
        for name, df in tabs.items():
            keep_index = name in ("importance_by_group", "risk_gap_decomposition", "importance_by_model", "stability_black")
            df.to_csv(a / f"{name}.csv", index=keep_index)
        pd.concat([pd.DataFrame({"group": grp, "fpr": f, "tpr": t}) for grp, (f, t) in self.roc.items()]).to_csv(a / "roc_by_group.csv", index=False)
        coh = self.c.drop(columns=[c for c in self.c.columns if c.startswith("raw_")]).copy()
        coh["split"] = self.split.to_numpy()
        for f in D.ALL_FEATURES:
            coh[f] = self.X[f].to_numpy()
        for k in self.oof_mean:
            coh[f"oof_risk_{k}"] = self.oof_mean[k]
            coh[f"flag_rate_{k}"] = self.flags[k].mean(0)
        coh.to_csv(a / "cohort.csv", index=False)
        sv = pd.concat({k: v for k, v in self.sv.items()}, axis=1)
        sv.columns = [f"shap_{x}__{y}" for x, y in sv.columns]
        sv.insert(0, "patient_id", self.c["patient_id"].to_numpy())
        sv.to_csv(a / "cohort_shap.csv", index=False)
        for key in ["aware", "blind", "reweigh"]:
            self.fits[key].model.save_model(str(a / f"xgb_{key}.json"))
        meta = dict(self.res)
        meta.update(thresholds={s.key: self.fits[s.key].thresholds for s in self.strategies}, base_value=self.base,
                    features=self.feats, features_blind=self.feats_blind, labels=D.LABELS, seed=self.seed, n_repeats=self.n_repeats,
                    n_boot=self.n_boot, strategies={s.key: dict(label=s.label, family=s.family, note=s.note, features=list(s.features),
                                                                reweigh=s.reweigh, group_thresholds=s.group_thresholds) for s in self.strategies},
                    risk_gap_total=self.gap_decomp.attrs.get("total_gap"), agreement=self.agreement, holdout_thresholds=self.holdout_thresholds,
                    baseline_info=self.baseline_info, test_confusion=self.test_confusion.to_dict("records"))
        import optuna, shap, sklearn, xgboost
        meta["versions"] = dict(xgboost=xgboost.__version__, shap=shap.__version__, sklearn=sklearn.__version__, pandas=pd.__version__, optuna=optuna.__version__)
        (a / "meta.json").write_text(json.dumps(meta, indent=2, default=float))
        return self
