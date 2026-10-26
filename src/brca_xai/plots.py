"""Thesis figures (PNG, 200 dpi).  Colour: Paul Tol colour-blind-safe pair, White = blue, Black = red;
neutral grey for everything else.  Every function takes a fitted :class:`~brca_xai.pipeline.Study`."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

from . import data as D
from . import modeling as M

CW, CB, GREY, INK = "#4477AA", "#EE6677", "#9AA0A6", "#222222"
COL = {D.PRIVILEGED: CW, D.UNPRIVILEGED: CB}
SHORT = {"aware": "Baseline\n(race-aware)", "blind": "Race-blind", "reweigh": "Reweighing",
         "gthr": "Group\nthresholds", "reweigh_gthr": "Reweighing +\ngroup thr."}
ORDER = ["aware", "blind", "reweigh", "gthr", "reweigh_gthr"]

plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 200, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#666", "axes.labelcolor": INK, "text.color": INK, "xtick.color": INK,
                     "ytick.color": INK, "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
                     "axes.grid": True, "grid.color": "#E6E8EB", "grid.linewidth": 0.8, "axes.axisbelow": True,
                     "font.family": "DejaVu Sans"})


def _save(fig, name, fig_dir):
    fig_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(fig_dir / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _pt(s, strategy, metric):
    r = s.summary[(s.summary.strategy == strategy) & (s.summary.metric == metric)].iloc[0]
    return r.estimate, r.lo, r.hi


# ---------------------------------------------------------------------------------------------
def fig_followup(s, d):
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    for grp in D.GROUPS:
        m = s.g == grp
        t, e = s.c.loc[m, "followup_months"].to_numpy(), s.y[m]
        o = np.argsort(t); t, e = t[o], e[o]
        at_risk, surv, xs, ys = len(t), 1.0, [0], [1.0]
        for ti in np.unique(t):
            d_ = e[t == ti].sum(); n = (t >= ti).sum()
            if d_:
                surv *= 1 - d_ / n; xs += [ti, ti]; ys += [ys[-1], surv]
        xs.append(t.max()); ys.append(surv)
        ax[0].plot(xs, ys, color=COL[grp], lw=2, label=f"{grp} (n={m.sum()})")
        ax[1].hist(t, bins=np.arange(0, 190, 12), alpha=.55, color=COL[grp], label=grp, density=True)
    ax[0].set(title="Kaplan-Meier overall survival", xlabel="Months since diagnosis", ylabel="Survival probability", ylim=(0.4, 1.02))
    ax[1].set(title="Follow-up length", xlabel="Months of follow-up", ylabel="Density")
    ax[0].legend(frameon=False); ax[1].legend(frameon=False)
    fig.suptitle("Black and White patients have similar survival and follow-up, so the label means the same for both", y=1.03, fontsize=10)
    _save(fig, "01_survival_followup.png", d)


def fig_leakage(s, d):
    t = s.ladder.iloc[::-1]
    fig, ax = plt.subplots(figsize=(8.4, 3.8))
    cols = [CW if i == len(t) - 1 else GREY for i in range(len(t))]
    ax.barh([r.split("  ")[1] if "  " in r else r for r in t.rung], t.auc, color=cols, height=.6)
    for i, v in enumerate(t.auc):
        ax.text(v + .005, i, f"{v:.2f}", va="center")
    ax.set(xlim=(.5, 1), xlabel="Cross-validated AUC", title="Why columns were excluded: each rung inflates AUC without any new biology")
    ax.axvline(.5, color="#666", lw=.8)
    _save(fig, "02_leakage_ladder.png", d)


def fig_benchmark(s, d):
    b = s.bench.copy()
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    y = np.arange(len(b))[::-1]
    names = [m.replace(" - used", " (used)") for m in b.model]
    ax[0].barh(y, b.auc, color=[CW if "used" in m else GREY for m in b.model], height=.6)
    ax[0].set(xlim=(.5, .72), xlabel="AUC (5x5 CV)", title="Discrimination"); ax[0].set_yticks(y, names)
    ax[1].barh(y, b.fpr_at_80_recall, color=[CW if "used" in m else GREY for m in b.model], height=.6)
    ax[1].set(xlim=(.4, .8), xlabel="False-positive rate when recall = 80 %", title="Cost of the recall target (lower is better)")
    for a, col in zip(ax, ["auc", "fpr_at_80_recall"]):
        for yi, v in zip(y, b[col]):
            a.text(v + .003, yi, f"{v:.3f}", va="center", fontsize=9)
    _save(fig, "03_model_benchmark.png", d)


def fig_roc(s, d):
    fig, ax = plt.subplots(figsize=(5.4, 5))
    for grp in D.GROUPS:
        f, t = s.roc[grp]
        a = s.auc_group[(s.auc_group.strategy == s.main) & (s.auc_group.group == grp)].iloc[0]
        ax.plot(f, t, color=COL[grp], lw=2, label=f"{grp}: AUC {a.auc:.2f} [{a.lo:.2f}-{a.hi:.2f}]")
    ax.plot([0, 1], [0, 1], color="#999", ls="--", lw=1)
    ax.axhline(s.target, color=INK, lw=.8, ls=":"); ax.text(.02, s.target + .015, f"recall target {s.target:.0%}", fontsize=8)
    ax.set(xlabel="False-positive rate", ylabel="Recall (true-positive rate)", title="ROC by race (out-of-fold)")
    ax.legend(frameon=False, loc="lower right")
    _save(fig, "04_roc_by_group.png", d)


def fig_group_rates(s, d):
    fig, ax = plt.subplots(1, 2, figsize=(11.5, 4), sharex=True)
    x = np.arange(len(ORDER)); w = .36
    for j, (metric, title) in enumerate([("tpr", "Recall: share of deaths the model flags"), ("fpr", "False-alarm rate: share of survivors flagged")]):
        for k, (grp, key) in enumerate([(D.PRIVILEGED, "W"), (D.UNPRIVILEGED, "B")]):
            est = [_pt(s, st, f"{metric}_{key}") for st in ORDER]
            v = np.array([e[0] for e in est]); lo = v - np.array([e[1] for e in est]); hi = np.array([e[2] for e in est]) - v
            ax[j].bar(x + (k - .5) * w, v, w, color=COL[grp], label=grp, yerr=[lo, hi], capsize=3, error_kw=dict(lw=1, ecolor="#444"))
            for xi, vi in zip(x + (k - .5) * w, v):
                ax[j].text(xi, 0.03, f"{vi:.2f}", ha="center", color="white", fontsize=8, fontweight="bold")
        ax[j].set_title(title); ax[j].set_xticks(x, [SHORT[k] for k in ORDER], fontsize=8.5); ax[j].set_ylim(0, 1.05)
    ax[0].axhline(s.target, color=INK, ls=":", lw=1); ax[0].legend(frameon=False, loc="upper left", ncol=2)
    fig.suptitle("Repeated-CV decisions at the recall-first threshold (95 % bootstrap CI)", y=1.02, fontsize=10)
    _save(fig, "05_rates_by_race.png", d)


def fig_gaps(s, d):
    fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.8), sharey=True)
    y = np.arange(len(ORDER))[::-1]
    for a, metric, title in [(ax[0], "tpr_gap", "Recall gap (Black - White)\n0 = equal opportunity"),
                             (ax[1], "fpr_gap", "False-alarm gap (Black - White)\npositive = Black over-flagged")]:
        for yi, st in zip(y, ORDER):
            e, lo, hi = _pt(s, st, metric)
            a.errorbar(e, yi, xerr=[[e - lo], [hi - e]], fmt="o", color=CB if st == "aware" else INK, capsize=3, ms=6)
            a.text(hi + .006, yi, f"{e:+.3f}", va="center", fontsize=8.5)
        a.axvline(0, color="#666", lw=1); a.set_title(title, fontsize=10)
        a.set_xlabel("Difference in rate (Black minus White), 95 % bootstrap CI")
    ax[0].set_yticks(y, [SHORT[k].replace("\n", " ") for k in ORDER])
    _save(fig, "06_gap_forest.png", d)


def fig_tradeoff(s, d):
    fig, ax = plt.subplots(figsize=(6.6, 4.4))
    for st in ORDER:
        fr = _pt(s, st, "flag_all")[0]; eo = _pt(s, st, "eod")[0]
        ax.scatter(fr, eo, s=90, color=CB if st == "aware" else CW, zorder=3)
        ax.annotate(SHORT[st].replace("\n", " "), (fr, eo), textcoords="offset points", xytext=(6, 5), fontsize=8.5)
    ax.set(xlabel="Share of ALL patients flagged (workload)", ylabel="Equalised-odds difference max(|dRecall|, |dFPR|)",
           title="Cost of fairness: lower-left is better")
    _save(fig, "07_tradeoff.png", d)


def fig_sweep(s, d):
    t = s.sweep_table
    fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.8), sharex=True)
    pal = {"aware": CB, "blind": CW, "reweigh": "#228833", "gthr": "#CCBB44", "reweigh_gthr": "#AA3377"}
    for a, metric, title in [(ax[0], "tpr_gap", "Recall gap (Black - White)"), (ax[1], "fpr_gap", "False-alarm gap (Black - White)")]:
        for st in ORDER:
            r = t[(t.strategy == st) & (t.metric == metric)].sort_values("target")
            a.plot(r.target, r.estimate, marker="o", color=pal[st], label=SHORT[st].replace("\n", " "), lw=1.8)
        a.axhline(0, color="#666", lw=1); a.set_title(title); a.set_xlabel("Recall target")
    ax[0].legend(frameon=False, fontsize=8)
    _save(fig, "08_recall_target_sweep.png", d)


def fig_holdout(s, d):
    h = s.holdout_table
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    x = np.arange(len(ORDER)); w = .36
    for k, grp in enumerate(D.GROUPS):
        r = h[h.group == grp].set_index("strategy").loc[ORDER]
        ax.bar(x + (k - .5) * w, r.recall, w, color=COL[grp], label=f"{grp} (n={int(r.n.iloc[0])}, deaths={int(r.deaths.iloc[0])})",
               yerr=[(r.recall - r.recall_lo).clip(lower=0), (r.recall_hi - r.recall).clip(lower=0)], capsize=3, error_kw=dict(lw=1, ecolor="#444"))
    ax.axhline(s.target, color=INK, ls=":", lw=1)
    ax.set_xticks(x, [SHORT[k] for k in ORDER], fontsize=8.5); ax.set_ylim(0, 1.1)
    ax.set(ylabel="Recall (Wilson 95 % CI)", title="Untouched hold-out test set: recall by race")
    ax.legend(frameon=False, loc="lower right", fontsize=8)
    _save(fig, "09_holdout_recall.png", d)


def fig_calibration(s, d):
    fig, ax = plt.subplots(figsize=(5.4, 5))
    raw = np.clip(s.oof_mean[s.main], 1e-4, 1 - 1e-4)
    a, b_ = s.platt[s.main]["intercept"], s.platt[s.main]["slope"]
    p = 1 / (1 + np.exp(-(a + b_ * np.log(raw / (1 - raw)))))          # one shared Platt mapping for both groups
    bins = np.quantile(p, [0, .25, .5, .75, 1.0]); bins[-1] += 1e-9
    for grp in D.GROUPS:
        m = s.g == grp
        idx = np.digitize(p[m], bins[1:-1])
        xs, ys = [], []
        for bb in range(len(bins) - 1):
            mm = idx == bb
            if mm.sum() >= 8:
                xs.append(p[m][mm].mean()); ys.append(s.y[m][mm].mean())
        ax.plot(xs, ys, marker="o", color=COL[grp], lw=2, label=grp)
    lim = float(max(p.max(), .5))
    ax.plot([0, lim], [0, lim], color="#999", ls="--"); ax.set(xlim=(0, lim), ylim=(0, lim), xlabel="Recalibrated predicted risk", ylabel="Observed death rate",
                                                       title="Calibration by race (out-of-fold, shared Platt mapping)")
    ax.legend(frameon=False)
    _save(fig, "10_calibration.png", d)


def fig_sensitivity(s, d):
    t = s.sensitivity_table
    fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.8), sharey=True)
    analyses = list(t.analysis.unique())
    y = np.arange(len(analyses))[::-1]
    for a, metric, title in [(ax[0], "tpr_gap", "Recall gap (Black - White)"), (ax[1], "fpr_gap", "False-alarm gap (Black - White)")]:
        for off, st, c_ in [(.15, "aware", CB), (-.15, "blind", CW)]:
            for yi, an in zip(y, analyses):
                r = t[(t.analysis == an) & (t.strategy == st) & (t.metric == metric)].iloc[0]
                a.errorbar(r.estimate, yi + off, xerr=[[r.estimate - r.lo], [r.hi - r.estimate]], fmt="o", color=c_, capsize=2,
                           label=SHORT[st].replace("\n", " ") if yi == y[0] else None)
        a.axvline(0, color="#666", lw=1); a.set_title(title)
    ax[0].set_yticks(y, [a.split(", n=")[0].replace("settled outcome ", "") + f"\n(n={a.split('n=')[1]})" for a in analyses], fontsize=8)
    ax[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Restricting evaluation to patients whose outcome is settled (reduces censoring noise)", y=1.02, fontsize=10)
    _save(fig, "11_sensitivity_settled.png", d)


# ---------------------------------------------------------------------------------------------
def fig_shap_global(s, d):
    sv = s.sv[s.main]
    fig = plt.figure(figsize=(7.6, 4.6))
    ex = shap.Explanation(sv.to_numpy(), base_values=np.full(len(sv), s.base[s.main]), data=s.X[s.feats].to_numpy(),
                          feature_names=[D.LABELS[f] for f in s.feats])
    shap.plots.beeswarm(ex, max_display=10, show=False, plot_size=None)
    plt.title("SHAP summary: what drives predicted risk of death")
    _save(plt.gcf(), "12_shap_beeswarm.png", d)


def fig_importance_group(s, d):
    t = s.imp_group.head(8).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    y = np.arange(len(t)); h = .38
    ax.barh(y + h / 2, t[D.PRIVILEGED], h, color=CW, label=D.PRIVILEGED)
    ax.barh(y - h / 2, t[D.UNPRIVILEGED], h, color=CB, label=D.UNPRIVILEGED)
    ax.set_yticks(y, t.label); ax.set(xlabel="Mean |SHAP| (log-odds)", title="Same features, same order of importance for both groups")
    ax.legend(frameon=False)
    _save(fig, "13_importance_by_race.png", d)


def fig_dependence(s, d):
    sv, X = s.sv[s.main], s.X
    fig, ax = plt.subplots(1, 3, figsize=(12, 3.6))
    for a, f in zip(ax, [f for f in ["age", "n_stage", "n_stage_h", "t_stage"] if f in s.feats][:3]):
        for grp in D.GROUPS:
            m = s.g == grp
            jitter = np.random.default_rng(0).normal(0, .06, m.sum()) if f != "age" else 0
            a.scatter(X.loc[m, f] + jitter, sv.loc[m, f], s=12, alpha=.5, color=COL[grp], label=grp)
        a.axhline(0, color="#666", lw=.8); a.set(xlabel=D.LABELS[f], ylabel="SHAP (log-odds)", title=D.LABELS[f])
    ax[0].legend(frameon=False)
    _save(fig, "14_dependence.png", d)


def fig_waterfalls(s, d):
    f = s.flags[s.main][0]
    cases = {}
    for name, m in [("true_positive_black", (s.y == 1) & (f == 1) & (s.g == D.UNPRIVILEGED)),
                    ("false_negative_black", (s.y == 1) & (f == 0) & (s.g == D.UNPRIVILEGED)),
                    ("true_negative_white", (s.y == 0) & (f == 0) & (s.g == D.PRIVILEGED))]:
        idx = np.where(m)[0]
        if len(idx):
            cases[name] = idx[np.argsort(s.oof_mean[s.main][idx])[len(idx) // 2]]
    for name, i in cases.items():
        ex = shap.Explanation(s.sv[s.main].iloc[i].to_numpy(), base_values=s.base[s.main], data=s.X[s.feats].iloc[i].to_numpy(),
                              feature_names=[D.LABELS[k] for k in s.feats])
        plt.figure(figsize=(7, 4))
        shap.plots.waterfall(ex, max_display=8, show=False)
        plt.title(f"{name.replace('_', ' ').title()}  ({s.c.patient_id.iloc[i]})", fontsize=10)
        _save(plt.gcf(), f"15_waterfall_{name}.png", d)


def fig_gap_decomp(s, d):
    t = s.gap_decomp.head(7).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.barh(t.label, t.contribution_to_gap, color=[CB if v > 0 else CW for v in t.contribution_to_gap], height=.6)
    ax.axvline(0, color="#666", lw=1)
    ax.set(xlabel="Contribution to the Black - White gap in mean predicted log-odds",
           title=f"Why the model scores groups differently (total gap {s.gap_decomp.attrs['total_gap']:+.3f})")
    _save(fig, "16_risk_gap_decomposition.png", d)


def fig_profile(s, d):
    p = s.profile
    p = p[p.outcome.isin(["TP (caught death)", "FN (missed death)"])]
    feats = list(s.imp_group.index[:6])
    fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.8), sharey=True)
    for a, grp in zip(ax, D.GROUPS):
        q = p[p.group == grp].set_index("outcome")[feats].T
        y = np.arange(len(feats)); h = .38
        a.barh(y + h / 2, q["TP (caught death)"], h, color=COL[grp], label="Caught deaths (TP)")
        a.barh(y - h / 2, q["FN (missed death)"], h, color=GREY, label="Missed deaths (FN)")
        a.set_yticks(y, [D.LABELS[f] for f in feats]); a.axvline(0, color="#666", lw=1)
        n_fn = int(p[(p.group == grp) & (p.outcome.str.startswith("FN"))].n.iloc[0])
        a.set_title(f"{grp} (missed deaths n={n_fn})"); a.set_xlabel("Mean SHAP (log-odds)")
    ax[0].legend(frameon=False, fontsize=8)
    fig.suptitle("What pulled missed deaths below the threshold?", y=1.02, fontsize=10)
    _save(fig, "17_missed_deaths_profile.png", d)


def fig_stability(s, d):
    t = s.stability.head(9).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    y = np.arange(len(t))
    ax.errorbar(t.mean_rank, y, xerr=[t.mean_rank - t.rank_lo, t.rank_hi - t.mean_rank], fmt="o", color=CB, capsize=3)
    ax.set_yticks(y, t.label); ax.invert_xaxis()
    ax.set(xlabel="Importance rank among Black patients (1 = most important), 95 % of bootstraps",
           title="Only the top of the ranking is stable (30 deaths)")
    _save(fig, "18_shap_stability_black.png", d)


def fig_mitigation_explanations(s, d):
    t = s.imp_models.loc[s.imp_group.index[:8]].iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    y = np.arange(len(t)); h = .27
    for i, (k, c_) in enumerate([("aware", CB), ("blind", CW), ("reweigh", "#228833")]):
        ax.barh(y + (1 - i) * h, t[k], h, color=c_, label={"aware": "Baseline (race-aware)", "blind": "Race-blind", "reweigh": "Reweighing"}[k])
    ax.set_yticks(y, [D.LABELS[f] for f in t.index]); ax.set(xlabel="Mean |SHAP|", title="Mitigation leaves the explanations almost unchanged")
    if "race_black" in s.imp_models.index:
        ax.text(.99, .02, f"race flag in baseline: {s.imp_models.loc['race_black', 'aware']:.3f}", transform=ax.transAxes, ha="right", fontsize=8)
    ax.legend(frameon=False)
    _save(fig, "19_explanations_under_mitigation.png", d)


def fig_workflow(s, d):
    steps = [("1 Data audit", "38 columns -> governance\nleakage & missingness\nTable 3.2 predictors"),
             ("2 Model", "XGBoost + class weights\nBayesian tuning, 5-fold CV\nbaselines, 80/20 split"),
             ("3 Recall-first", "threshold = highest score\ncatching 80 % of deaths\n(learned in-fold)"),
             ("4 SHAP", "global / local / by race\nfidelity, stability,\nclinical alignment"),
             ("5 Fairness (ext.)", "5 strategies x 25 folds\nbootstrap, paired CI\nsensitivity analyses"),
             ("6 Dashboard", "patient explainer\nfairness lab\nuser-study kit")]
    fig, ax = plt.subplots(figsize=(11.5, 2.6)); ax.axis("off"); ax.set_xlim(0, 6); ax.set_ylim(0, 1)
    for i, (t, b) in enumerate(steps):
        ax.add_patch(plt.Rectangle((i + .06, .12), .88, .76, fc="#EEF3F8", ec=CW, lw=1.4, joinstyle="round"))
        ax.text(i + .5, .74, t, ha="center", va="center", fontweight="bold", fontsize=10)
        ax.text(i + .5, .38, b, ha="center", va="center", fontsize=8)
        if i < len(steps) - 1:
            ax.annotate("", xy=(i + 1.06, .5), xytext=(i + .94, .5), arrowprops=dict(arrowstyle="->", color=INK, lw=1.4))
    _save(fig, "00_workflow.png", d)


def fig_framework(s, d):
    """Conceptual framework (proposal 3.2.8): where SHAP sits in a clinical decision-support pipeline."""
    fig, ax = plt.subplots(figsize=(11.5, 4.4)); ax.axis("off"); ax.set_xlim(0, 12); ax.set_ylim(0, 4.4)
    boxes = [(0.2, 2.6, "Data input", "baseline clinicopathological\nrecord (T, N, M, age, PAM50 ...)"),
             (2.5, 2.6, "Risk prediction", "XGBoost score +\nrecall-first threshold"),
             (4.8, 2.6, "Explanation", "SHAP waterfall (local)\nSHAP summary (global)"),
             (7.1, 2.6, "Clinician review", "plausibility check vs\nprognostic knowledge"),
             (9.4, 2.6, "Decision", "closer follow-up / usual care\n(clinician decides)")]
    for x, y, t, b in boxes:
        ax.add_patch(plt.Rectangle((x, y), 2.1, 1.3, fc="#EEF3F8", ec=CW, lw=1.4))
        ax.text(x + 1.05, y + 1.0, t, ha="center", fontweight="bold", fontsize=10)
        ax.text(x + 1.05, y + .45, b, ha="center", va="center", fontsize=8)
    for x in [2.3, 4.6, 6.9, 9.2]:
        ax.annotate("", xy=(x + .2, 3.25), xytext=(x, 3.25), arrowprops=dict(arrowstyle="->", lw=1.4))
    gates = [(0.2, 0.3, "Governance gate", "leakage ladder, informative-\nmissingness audit"),
             (4.8, 0.3, "Trust checks", "fidelity, stability, direction,\nrace-attribution check"),
             (9.4, 0.3, "Feedback & monitoring", "group-wise recall / false-alarm\nrates with CI; user study")]
    for x, y, t, b in gates:
        ax.add_patch(plt.Rectangle((x, y), 2.1, 1.1, fc="#FDF1F3", ec=CB, lw=1.4))
        ax.text(x + 1.05, y + .82, t, ha="center", fontweight="bold", fontsize=9)
        ax.text(x + 1.05, y + .37, b, ha="center", va="center", fontsize=7.5)
    for x in (1.25, 5.85, 10.45):
        ax.annotate("", xy=(x, 2.6), xytext=(x, 1.4), arrowprops=dict(arrowstyle="->", color=CB, lw=1.2, ls="--"))
    ax.text(6.0, 2.05, "outcomes and clinician feedback re-enter model updates", fontsize=8, color="#555", ha="center")
    _save(fig, "20_conceptual_framework.png", d)


def fig_learning_curve(s, d):
    c = s.curve
    fig, ax = plt.subplots(figsize=(6.4, 4))
    ax.plot(c.trees, c.train, color=GREY, lw=2, label="Training (dev set)")
    ax.plot(c.trees, c.cv, color=CW, lw=2, label="5-fold CV (dev set)")
    ax.fill_between(c.trees, c.cv - c.cv_sd, c.cv + c.cv_sd, color=CW, alpha=.15)
    ax.plot(c.trees, c.test, color=CB, lw=2, label="Hold-out test")
    ax.axvline(s.params["n_estimators"], color=INK, ls=":", lw=1)
    ax.set(xlabel="Boosting rounds", ylabel="AUC", title="Overfitting control: train vs CV vs test AUC")
    ax.legend(frameon=False)
    _save(fig, "21_learning_curve.png", d)


def fig_pr(s, d):
    from sklearn.metrics import precision_recall_curve
    yte = s.y[~s.dev]; p = s.holdout_probs[s.main]
    pr, rc, _ = precision_recall_curve(yte, p)
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    ax.plot(rc, pr, color=CW, lw=2, label="Hold-out PR curve")
    ax.axhline(yte.mean(), color="#999", ls="--", lw=1)
    ax.text(.02, yte.mean() + .012, f"no-skill = prevalence {yte.mean():.2f}", fontsize=8)
    for _, r in s.rule_table.iterrows():
        ax.scatter(r.recall, r.precision, s=50, zorder=3, color=CB if "primary" in r.rule else INK)
        ax.annotate(r.rule.replace(" (primary)", "*"), (r.recall, r.precision), textcoords="offset points", xytext=(5, 4), fontsize=7)
    ax.set(xlabel="Recall", ylabel="Precision", ylim=(0, 1.02), title="Hold-out precision-recall; points = threshold rules (* primary)")
    ax.legend(frameon=False, loc="upper right")
    _save(fig, "22_precision_recall.png", d)


def fig_test_forest(s, d):
    t = s.test_metrics
    models = [m for m in t.model.unique() if "Always" not in m]
    fig, ax = plt.subplots(1, 3, figsize=(11.5, 3.6), sharey=True)
    y = np.arange(len(models))[::-1]
    for a, metric, title in zip(ax, ["recall", "auc_roc", "pr_auc"], ["Recall", "AUC-ROC", "PR-AUC"]):
        for yi, m in zip(y, models):
            r = t[(t.model == m) & (t.metric == metric)].iloc[0]
            a.errorbar(r.estimate, yi, xerr=[[r.estimate - r.lo], [r.hi - r.estimate]], fmt="o", color=CB if "primary" in m else INK, capsize=3)
        a.set_title(title)
    ax[2].axvline(s.y[~s.dev].mean(), color="#999", ls="--", lw=1)
    ax[0].set_yticks(y, models, fontsize=8)
    fig.suptitle("Hold-out test performance, bootstrap 95 % CI (dashed = no-skill PR-AUC)", y=1.02, fontsize=10)
    _save(fig, "23_test_forest.png", d)


def fig_ablation(s, d):
    if not hasattr(s, "ablation"):
        return
    a = s.ablation.iloc[::-1]
    fig, ax = plt.subplots(figsize=(8.8, 4))
    ax.barh(a.variant, a.auc, color=[CB if i == len(a) - 1 else GREY for i in range(len(a))], height=.6)
    for i, v in enumerate(a.auc):
        ax.text(v + .004, i, f"{v:.3f}", va="center", fontsize=9)
    ax.set(xlim=(.5, .8), xlabel="Cross-validated AUC", title="Where the proposal specification's extra AUC comes from")
    _save(fig, "24_artefact_ablation.png", d)


def fig_race_missing(s, d):
    r = s.race_shap
    if r.empty:
        return
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.4))
    ax[0].bar(r.patients, r.share_of_total_attribution, color=[CW, CB], width=.55)
    ax[0].set(ylabel="Share of total |SHAP| in race columns", title="Race attribution")
    ax[1].bar(r.patients, r.death_rate, color=[CW, CB], width=.55)
    ax[1].set(ylabel="Death rate", title="Observed mortality")
    for a_, col in zip(ax, ["share_of_total_attribution", "death_rate"]):
        for i, v in enumerate(r[col]):
            a_.text(i, v + .005, f"{v:.0%}", ha="center", fontsize=9)
    _save(fig, "25_race_missing_signal.png", d)


def fig_deletion(s, d):
    t = s.deletion
    fig, ax = plt.subplots(figsize=(5.6, 3.8))
    ax.plot(t.k, t.auc_top_shap, marker="o", color=CB, lw=2, label="remove the k most-attributed features")
    ax.plot(t.k, t.auc_random, marker="o", color=GREY, lw=2, label="remove k random features")
    ax.set(xlabel="k features blanked per patient", ylabel="AUC", title="Faithfulness (deletion) test")
    ax.legend(frameon=False, fontsize=8)
    _save(fig, "26_deletion_test.png", d)


def make_all(s, fig_dir=None):
    d = fig_dir or s.fig
    fns = [fig_workflow, fig_framework, fig_followup, fig_benchmark, fig_roc, fig_group_rates, fig_gaps, fig_tradeoff, fig_sweep,
           fig_holdout, fig_calibration, fig_sensitivity, fig_shap_global, fig_importance_group, fig_dependence,
           fig_waterfalls, fig_gap_decomp, fig_profile, fig_stability, fig_mitigation_explanations,
           fig_learning_curve, fig_pr, fig_test_forest, fig_race_missing, fig_deletion]
    if hasattr(s, "ladder"):
        fns += [fig_leakage, fig_ablation]
    for fn in fns:
        fn(s, d)
    return d
