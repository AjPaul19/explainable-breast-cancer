"""Streamlit dashboard: recall-first death-risk model for TCGA-BRCA, SHAP explanations, fairness lab and data audit.

    streamlit run app.py          (run `python run_pipeline.py` first to create ./artifacts)
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import shap
import streamlit as st
import xgboost as xgb

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))
from brca_xai import data as D  # noqa: E402

BLUE, RED, GREY = "#4477AA", "#EE6677", "#9AA0A6"
COL = {"White": BLUE, "Black": RED}
KEYS = ["aware", "blind", "reweigh", "gthr", "reweigh_gthr"]
SPEC_LABEL = {"proposal": "As proposed (Table 3.2 predictors)", "hardened": "Audit-hardened (no documentation artefacts)"}

st.set_page_config(page_title="Recall-first BRCA mortality · SHAP · fairness", page_icon="🎗️", layout="wide")
if not (ROOT / "artifacts" / "proposal" / "meta.json").exists():
    st.error("No artifacts found. Run `python run_pipeline.py` first.")
    st.stop()

spec = st.sidebar.radio("Model specification", list(SPEC_LABEL), format_func=SPEC_LABEL.get,
                        help="The proposal's predictor list reaches a higher AUC, but part of it comes from blank fields that track the outcome "
                             "(see the Data audit tab). The hardened model removes them.")
st.sidebar.caption("Research prototype for an MSc project. Not for clinical use.")
ART, FIG = ROOT / "artifacts" / spec, ROOT / "reports" / "figures" / spec


@st.cache_data
def meta(sp):
    return json.loads((ROOT / "artifacts" / sp / "meta.json").read_text())


@st.cache_data
def csv(sp, name):
    return pd.read_csv(ROOT / "artifacts" / sp / name)


@st.cache_resource
def model(sp, key):
    m = xgb.XGBClassifier()
    m.load_model(str(ROOT / "artifacts" / sp / f"xgb_{key}.json"))
    return m


M = meta(spec)
LAB, STRAT = M["labels"], M["strategies"]
SUMMARY = csv(spec, "fairness_cv_summary.csv")


def est(strategy, metric):
    r = SUMMARY[(SUMMARY.strategy == strategy) & (SUMMARY.metric == metric)].iloc[0]
    return r.estimate, r.lo, r.hi


def wilson(k, n, z=1.96):
    if n == 0:
        return np.nan, np.nan
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0, c - h), min(1, c + h)


def style(fig, h=380, **kw):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white", paper_bgcolor="white",
                      font=dict(size=13), legend=dict(orientation="h", y=1.12), **kw)
    fig.update_xaxes(gridcolor="#E6E8EB"); fig.update_yaxes(gridcolor="#E6E8EB")
    return fig


def img(name, **kw):
    f = FIG / name
    if f.exists():
        st.image(str(f), **kw)


st.title("🎗️ Death during follow-up in TCGA-BRCA: recall first, explained with SHAP, audited for fairness")
st.caption(f"University of Jos MSc project · XGBoost + SHAP · specification: **{SPEC_LABEL[spec]}**")
tabs = st.tabs(["Overview", "Patient explainer", "Performance", "Fairness lab", "Threshold explorer", "Explanations", "Data audit",
                "User study", "Framework", "Cohort", "About"])

# --------------------------------------------------------------------------------------------- overview
with tabs[0]:
    fl = M["flow"]
    ov = M["cv_overall"]["aware"]
    te = M["test"]["XGBoost (race-aware, primary)"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Patients", f"{fl['n_records']:,}", f"{fl['n_deaths']} deaths ({fl['prevalence']:.1%})")
    c2.metric("AUC-ROC (5×5 CV)", f"{ov['auc_roc'][0]:.2f}", f"PR-AUC {ov['pr_auc'][0]:.2f} vs {fl['prevalence']:.2f} no-skill")
    c3.metric("Recall (CV)", f"{ov['recall'][0]:.0%}", f"target {M['cv']['target_recall']:.0%}")
    c4.metric("Share of patients flagged", f"{ov['flag_rate'][0]:.0%}", f"precision {ov['precision'][0]:.0%}")
    st.markdown(f"""
**What this does.** From information known at diagnosis, an XGBoost model scores each patient's risk of dying during follow-up. The alarm threshold is
**not 0.5**: it is the highest score that still catches **{M['cv']['target_recall']:.0%} of deaths** (*recall first*), so a missed death is treated as far
worse than a false alarm. SHAP explains every score. The revised proposal's Objectives 1–5 are covered; Objective 4 (clinician study) ships as a ready-to-run kit.

**Extension to the proposal.** Do Black and White patients receive equal treatment from the model, and can mitigation help? (Fairness lab tab.)
""")
    a, b = est("aware", "tpr_gap"), est("aware", "fpr_gap")
    st.info(f"**Fairness headline (race-aware model).** Recall gap Black − White **{a[0]:+.1%}** (95 % CI {a[1]:+.1%} to {a[2]:+.1%}); false-alarm gap **{b[0]:+.1%}** "
            f"(CI {b[1]:+.1%} to {b[2]:+.1%}). Only {fl['deaths_black']} Black patients died, so the data cannot rule out a recall gap of about ±14 points.")
    if spec == "proposal":
        st.warning("**Audit warning.** Part of this specification's accuracy comes from *blank* fields (radiation therapy not recorded, NX / MX codes, race not recorded) that "
                   "track death in this registry. Switch to the audit-hardened specification in the sidebar to see performance without them.")
    img("00_workflow.png")

# --------------------------------------------------------------------------------------------- patient explainer
with tabs[1]:
    st.subheader("Explain one patient")
    left, right = st.columns([1, 1.4])
    with left:
        strategy = st.selectbox("Strategy", KEYS, index=0, format_func=lambda k: STRAT[k]["label"])
        s_ = STRAT[strategy]
        age = st.slider("Age at diagnosis", 25, 90, 58)
        t = st.select_slider("Tumour size (T)", ["unknown (TX)", 1, 2, 3, 4], 2)
        n = st.select_slider("Nodal status (N)", ["unknown (NX)", 0, 1, 2, 3], 0)
        m1 = st.selectbox("Distant metastasis (M)", ["M0", "M1", "unknown (MX)"])
        sub = st.selectbox("PAM50 subtype", ["LumA", "LumB", "Her2", "Basal", "Normal", "not called"])
        hist = st.selectbox("Histology", ["Ductal", "Lobular", "Other"])
        prior = st.checkbox("Prior malignancy")
        neo = st.checkbox("Neoadjuvant therapy")
        rad = st.selectbox("Radiation therapy", ["no", "yes", "not recorded"])
        race = st.selectbox("Recorded race", ["White", "Black", "Asian", "not recorded"])
    num = lambda v: np.nan if isinstance(v, str) else float(v)
    row = {"age": age, "t_stage": num(t), "n_stage": num(n), "m_stage": {"M0": 0.0, "M1": 1.0}.get(m1, np.nan),
           "histology_lobular": float(hist == "Lobular"), "histology_other": float(hist == "Other"), "prior_dx": float(prior),
           "neoadjuvant": float(neo), "radiation": {"no": 0.0, "yes": 1.0}.get(rad, np.nan),
           "race_black": np.nan if race == "not recorded" else float(race == "Black"),
           "race_asian": np.nan if race == "not recorded" else float(race == "Asian")}
    row["n_stage_h"] = 0.0 if np.isnan(row["n_stage"]) else row["n_stage"]
    row["m_stage_h"] = 0.0 if np.isnan(row["m_stage"]) else row["m_stage"]
    for k, col in D.SUBTYPE_COLS.items():
        row[col] = np.nan if sub == "not called" else float(sub == k)
    key = "aware" if any(f in s_["features"] for f in D.RACE_FEATURES) else ("reweigh" if s_["reweigh"] else "blind")
    feats = s_["features"]
    X1 = pd.DataFrame([row])[feats]
    mdl = model(spec, key)
    p = float(mdl.predict_proba(X1)[0, 1])
    thr = M["thresholds"][strategy]
    group = race if race in ("White", "Black") else None
    thr_used = thr[group] if (s_["group_thresholds"] and group) else thr["global"]
    flagged = p >= thr_used
    ex = shap.TreeExplainer(mdl)
    phi = ex.shap_values(X1)[0]
    base = float(np.ravel(ex.expected_value)[0])
    with right:
        pl = M["platt"][key]
        pc = 1 / (1 + np.exp(-(pl["intercept"] + pl["slope"] * np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4))))))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Model score", f"{p:.1%}", help="Class-weighted score used for ranking and the threshold; it is not a probability")
        c2.metric("Recalibrated risk", f"{pc:.1%}", help="Estimated probability of death during follow-up (logistic recalibration of out-of-fold scores)")
        c3.metric("Alarm threshold", f"{thr_used:.1%}", help="Highest score that still reaches the recall target on training data")
        c4.metric("Decision", "FLAG" if flagged else "not flagged")
        st.warning("Flagged for closer follow-up. At this operating point most flagged patients survive: the alarm is deliberately sensitive." if flagged
                   else "Below the recall-first threshold.")
        order = np.argsort(np.abs(phi))[::-1][:9][::-1]
        names = [f"{LAB[feats[i]]} = {X1.iloc[0, i]:g}" if pd.notna(X1.iloc[0, i]) else f"{LAB[feats[i]]} = not recorded" for i in order]
        vals = phi[order]
        fig = go.Figure(go.Bar(x=vals, y=names, orientation="h", marker_color=[RED if v > 0 else BLUE for v in vals]))
        fig.update_layout(title=f"Why this score? (log-odds; base {base:.2f} → {base + phi.sum():.2f})", xaxis_title="SHAP contribution")
        st.plotly_chart(style(fig, 420), width="stretch")
        st.caption("Red pushes risk up, blue pushes it down; contributions sum exactly to the model output. "
                   "Try setting radiation therapy or race to “not recorded” in the as-proposed model and watch the score move: a blank is treated as information.")

# --------------------------------------------------------------------------------------------- performance
with tabs[2]:
    st.subheader("Hold-out test set (20 %, bootstrap 95 % CI) and baselines trained under the same protocol")
    tm = csv(spec, "test_metrics.csv")
    pv = tm.assign(v=tm.apply(lambda r: f"{r.estimate:.3f}" + ("" if pd.isna(r.lo) else f" [{r.lo:.3f}, {r.hi:.3f}]"), axis=1)).pivot(index="model", columns="metric", values="v")
    cols = [c for c in ["recall", "precision", "specificity", "f1", "accuracy", "balanced_accuracy", "auc_roc", "pr_auc", "flag_rate"] if c in pv.columns]
    st.dataframe(pv[cols], width="stretch")
    st.caption(f"Accuracy must be read against the no-skill benchmark of {1 - M['flow']['test_deaths'] / M['flow']['n_test']:.1%} (always predict “living”). "
               f"The hold-out set has {M['flow']['test_deaths']} deaths, hence the wide intervals.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Confusion matrices (hold-out)**")
        st.dataframe(csv(spec, "test_confusion.csv").round(3), hide_index=True, width="stretch")
        st.markdown("**Threshold rules compared** (learned on the development set)")
        st.dataframe(csv(spec, "threshold_rules.csv").round(3), hide_index=True, width="stretch")
    with c2:
        img("22_precision_recall.png"); img("21_learning_curve.png")
    img("23_test_forest.png")
    st.markdown("**Cross-validated benchmark (5×5 CV, all patients)**")
    st.dataframe(csv(spec, "model_benchmark.csv").round(3), hide_index=True, width="stretch")

# --------------------------------------------------------------------------------------------- fairness lab
with tabs[3]:
    st.subheader("Does the model treat Black and White patients equally? (extension to the proposal)")
    rows = []
    for k in KEYS:
        r = {"Strategy": STRAT[k]["label"], "Family": STRAT[k]["family"],
             "Needs race at prediction": "yes" if (STRAT[k]["group_thresholds"] or any(f in STRAT[k]["features"] for f in D.RACE_FEATURES)) else "no"}
        for lab, mt in [("Recall White", "tpr_W"), ("Recall Black", "tpr_B"), ("Recall gap", "tpr_gap"), ("False-alarm White", "fpr_W"),
                        ("False-alarm Black", "fpr_B"), ("False-alarm gap", "fpr_gap")]:
            e, lo, hi = est(k, mt)
            r[lab] = f"{e:.1%}" if "gap" not in lab else f"{e:+.1%} [{lo:+.1%}, {hi:+.1%}]"
        rows.append(r)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    c1, c2 = st.columns(2)
    for col, (metric, title) in zip([c1, c2], [("tpr", "Recall (deaths caught)"), ("fpr", "False-alarm rate (survivors flagged)")]):
        fig = go.Figure()
        for grp, sfx in [("White", "W"), ("Black", "B")]:
            e = [est(k, f"{metric}_{sfx}") for k in KEYS]
            fig.add_bar(name=grp, x=[STRAT[k]["label"].split(" (")[0] for k in KEYS], y=[x[0] for x in e], marker_color=COL[grp],
                        error_y=dict(type="data", symmetric=False, array=[x[2] - x[0] for x in e], arrayminus=[x[0] - x[1] for x in e]))
        fig.update_layout(title=title, barmode="group", yaxis_range=[0, 1])
        col.plotly_chart(style(fig, 360), width="stretch")
    sw = csv(spec, "recall_target_sweep.csv")
    c1, c2 = st.columns(2)
    for col, (metric, title) in zip([c1, c2], [("tpr_gap", "Recall gap vs recall target"), ("fpr_gap", "False-alarm gap vs recall target")]):
        fig = go.Figure()
        for k in KEYS:
            r = sw[(sw.strategy == k) & (sw.metric == metric)].sort_values("target")
            fig.add_scatter(x=r.target, y=r.estimate, mode="lines+markers", name=STRAT[k]["label"].split(" (")[0])
        fig.add_hline(y=0, line_color="#666"); fig.update_layout(title=title, xaxis_title="Recall target")
        col.plotly_chart(style(fig, 340), width="stretch")
    ms_ = ROOT / "artifacts" / spec / "model_selection_sensitivity.csv"
    if ms_.exists():
        st.markdown("**Gaps depend on model selection** (percentage points across near-equivalent tuned configurations)")
        mm = pd.read_csv(ms_)
        mm = mm[mm.strategy.isin(["aware", "blind", "gthr"]) & mm.metric.isin(["tpr_gap", "fpr_gap"])].pivot_table(index=["strategy", "metric"], columns="config", values="estimate") * 100
        st.dataframe(mm.round(1), width="stretch")
    st.markdown("**Paired bootstrap: did mitigation change the gap versus the baseline?**")
    pr = csv(spec, "fairness_paired_vs_main.csv")
    pr = pr[pr.metric.isin(["tpr_gap", "fpr_gap", "eod"])].copy()
    pr["strategy"] = pr.strategy.map(lambda k: STRAT[k]["label"])
    pr["change vs baseline [95% CI]"] = pr.apply(lambda r: f"{r.diff_vs_aware:+.3f} [{r.lo:+.3f}, {r.hi:+.3f}]", axis=1)
    st.dataframe(pr[["strategy", "metric", "change vs baseline [95% CI]", "prob_smaller"]].rename(columns={"prob_smaller": "P(smaller)"}), hide_index=True, width="stretch")
    st.caption("An interval that includes 0 means the change is not distinguishable from noise. The Black group has only 30 deaths.")
    c1, c2 = st.columns(2)
    c1.markdown("**Sensitivity: only patients with settled outcomes**")
    se = csv(spec, "sensitivity_settled_outcome.csv")
    se = se[se.metric.isin(["fpr_gap", "tpr_gap"]) & se.strategy.isin(["aware", "blind", "reweigh"])]
    c1.dataframe(se.round(3), hide_index=True, width="stretch", height=300)
    c2.markdown("**Genetic ancestry instead of self-reported race**")
    c2.dataframe(csv(spec, "sensitivity_ancestry.csv").round(3), hide_index=True, width="stretch", height=300)

# --------------------------------------------------------------------------------------------- threshold explorer
with tabs[4]:
    st.subheader("Recall-first threshold explorer (out-of-fold scores, White and Black patients)")
    coh = csv(spec, "cohort.csv"); coh = coh[coh.race.isin(["White", "Black"])]
    skey = st.selectbox("Score", ["aware", "blind", "reweigh"], format_func=lambda k: STRAT[k]["label"], key="thr_score")
    risk = coh[f"oof_risk_{skey}"].to_numpy()
    default = M["thresholds"][skey]["global"]
    mode = st.radio("Threshold", ["One for everyone", "Separate per group"], horizontal=True)
    lo_, hi_ = float(np.quantile(risk, .02)), float(np.quantile(risk, .995))
    th_w = st.slider("White threshold" if mode != "One for everyone" else "Threshold", lo_, hi_, float(np.clip(default, lo_, hi_)), 0.005)
    th_b = st.slider("Black threshold", lo_, hi_, float(np.clip(default, lo_, hi_)), 0.005) if mode != "One for everyone" else th_w
    rows = []
    for grp, th in [("White", th_w), ("Black", th_b)]:
        m = coh.race.eq(grp).to_numpy(); y = coh.died.to_numpy()[m]; f = risk[m] >= th
        tp, fn, fp, tn = ((y == 1) & f).sum(), ((y == 1) & ~f).sum(), ((y == 0) & f).sum(), ((y == 0) & ~f).sum()
        lo, hi = wilson(tp, tp + fn)
        rows.append({"Group": grp, "Patients": int(m.sum()), "Deaths": int(tp + fn), "Caught": int(tp), "Missed": int(fn), "Recall": tp / (tp + fn),
                     "Recall CI": f"{lo:.0%}-{hi:.0%}", "False alarms": int(fp), "False-alarm rate": fp / (fp + tn), "Flagged": (tp + fp) / m.sum()})
    st.dataframe(pd.DataFrame(rows).style.format({"Recall": "{:.1%}", "False-alarm rate": "{:.1%}", "Flagged": "{:.1%}"}), hide_index=True, width="stretch")
    grid = np.linspace(lo_, hi_, 80)
    fig = go.Figure()
    for grp in ["White", "Black"]:
        m = coh.race.eq(grp).to_numpy(); y = coh.died.to_numpy()[m]
        fig.add_scatter(x=grid, y=[(risk[m][y == 1] >= g).mean() for g in grid], name=f"{grp} recall", line=dict(color=COL[grp]))
        fig.add_scatter(x=grid, y=[(risk[m][y == 0] >= g).mean() for g in grid], name=f"{grp} false-alarm rate", line=dict(color=COL[grp], dash="dot"))
    fig.add_vline(x=th_w, line_color=BLUE); fig.add_vline(x=th_b, line_color=RED, line_dash="dash")
    fig.update_layout(xaxis_title="Threshold on model score", yaxis_title="Rate", yaxis_range=[0, 1.02])
    st.plotly_chart(style(fig, 420), width="stretch")
    st.caption("Out-of-fold scores averaged over repeats. The Black curves are jagged because only 30 Black patients died.")

# --------------------------------------------------------------------------------------------- explanations
with tabs[5]:
    st.subheader("What drives the model, and can the explanations be trusted?")
    eq = M["explain_quality"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Fidelity (max SHAP error)", f"{eq['fidelity']['max_abs_error']:.1e}", help="|base + sum(SHAP) − model margin|, all patients")
    c2.metric("Stability across CV folds", f"ρ = {eq['fold_stability']['mean_spearman']:.2f}", help="Mean Spearman rank correlation of global importance across 10 fold models")
    c3.metric("Stability across bootstraps", f"ρ = {eq['bootstrap_stability']:.2f}")
    c4.metric("Agreement with XGBoost gain", f"ρ = {eq['builtin']['gain']:.2f}")
    imp = csv(spec, "importance_by_group.csv").rename(columns={"Unnamed: 0": "feature"})
    top = imp.head(10).iloc[::-1]
    fig = go.Figure()
    fig.add_bar(y=top.label, x=top["White"], orientation="h", name="White", marker_color=BLUE)
    fig.add_bar(y=top.label, x=top["Black"], orientation="h", name="Black", marker_color=RED)
    fig.update_layout(barmode="group", title="Mean |SHAP| by race", xaxis_title="log-odds")
    st.plotly_chart(style(fig, 440), width="stretch")
    c1, c2 = st.columns(2)
    c1.markdown("**Clinical alignment: top-ranked features vs established prognostic factors**")
    c1.dataframe(csv(spec, "clinical_alignment.csv").round(3), hide_index=True, width="stretch")
    c1.markdown("**Race attribution check**")
    c1.dataframe(csv(spec, "race_shap_check.csv").round(3), hide_index=True, width="stretch")
    c2.markdown("**Faithfulness (deletion) test**")
    c2.dataframe(csv(spec, "deletion_test.csv").round(3), hide_index=True, width="stretch")
    c2.markdown("**Direction vs clinical prior**")
    c2.dataframe(csv(spec, "shap_direction_check.csv").round(3), hide_index=True, width="stretch")
    c1, c2 = st.columns(2)
    gd = csv(spec, "risk_gap_decomposition.csv").head(7).iloc[::-1]
    fig = go.Figure(go.Bar(y=gd.label, x=gd.contribution_to_gap, orientation="h", marker_color=[RED if v > 0 else BLUE for v in gd.contribution_to_gap]))
    fig.update_layout(title=f"Why average model risk differs by race (total {M['risk_gap_total']:+.3f} log-odds)")
    c1.plotly_chart(style(fig, 360), width="stretch")
    sb = csv(spec, "stability_black.csv").rename(columns={"Unnamed: 0": "feature"}).head(9).iloc[::-1]
    fig = go.Figure(go.Scatter(y=sb.label, x=sb.mean_rank, mode="markers", marker=dict(color=RED, size=9),
                               error_x=dict(type="data", symmetric=False, array=sb.rank_hi - sb.mean_rank, arrayminus=sb.mean_rank - sb.rank_lo)))
    fig.update_layout(title="Importance rank among Black patients (bootstrap)", xaxis_autorange="reversed")
    c2.plotly_chart(style(fig, 360), width="stretch")
    sh = csv(spec, "cohort_shap.csv"); coh = csv(spec, "cohort.csv")
    feat = st.selectbox("Dependence plot", M["features"], format_func=lambda f: LAB[f])
    fig = go.Figure(); rng = np.random.default_rng(0)
    for grp in ["White", "Black"]:
        m = coh.race.eq(grp)
        fig.add_scatter(x=coh.loc[m, feat] + (rng.normal(0, .05, m.sum()) if coh[feat].nunique() < 8 else 0), y=sh.loc[m, f"shap_aware__{feat}"],
                        mode="markers", name=grp, marker=dict(color=COL[grp], opacity=.55, size=6))
    fig.update_layout(xaxis_title=LAB[feat], yaxis_title="SHAP (log-odds)")
    st.plotly_chart(style(fig, 360), width="stretch")
    img("12_shap_beeswarm.png")

# --------------------------------------------------------------------------------------------- data audit
with tabs[6]:
    st.subheader("Why the revised proposal's predictor list needs a second look")
    lad = csv("proposal", "leakage_ladder.csv")
    fig = go.Figure(go.Bar(y=lad.rung.iloc[::-1], x=lad.auc.iloc[::-1], orientation="h", marker_color=[RED, RED, GREY, BLUE, GREY]))
    fig.update_layout(title="Cross-validated AUC as columns are added (blue = proposal Table 3.2)", xaxis_range=[0.5, 1])
    st.plotly_chart(style(fig, 360), width="stretch")
    st.dataframe(lad[["rung", "note", "auc", "pr_auc", "precision_at_80_recall"]].round(3), hide_index=True, width="stretch")
    c1, c2 = st.columns(2)
    c1.markdown("**Where the proposal specification's extra AUC comes from**")
    c1.dataframe(csv("proposal", "artefact_ablation.csv")[["variant", "auc", "pr_auc"]].round(3), hide_index=True, width="stretch")
    c2.markdown("**Specifications compared**")
    c2.dataframe(csv("proposal", "spec_comparison.csv")[["spec", "auc", "pr_auc", "fpr_at_80_recall"]].round(3), hide_index=True, width="stretch")
    c1, c2 = st.columns(2)
    c1.markdown("**Death rate when a field is blank vs recorded**")
    c1.dataframe(csv("proposal", "missingness_audit.csv").round(3), hide_index=True, width="stretch")
    c2.markdown("**Column governance (all 38 source columns)**")
    c2.dataframe(csv("proposal", "column_governance.csv"), hide_index=True, width="stretch", height=420)

# --------------------------------------------------------------------------------------------- user study
with tabs[7]:
    st.subheader("Physician user study kit (Objective 4)")
    st.info("Instrument ready, **no data collected**. Run it with `userstudy/analyze_user_study.py` after recruitment and ethical approval.")
    cards = sorted((ROOT / "userstudy" / "case_cards").glob("case01_*.png")) if (ROOT / "userstudy").exists() else []
    if cards:
        c1, c2 = st.columns([1, 1.6])
        c1.image(str(cards[0]), caption="Condition A: risk score only"); c2.image(str(cards[1]), caption="Condition B: score + SHAP")
    q = ROOT / "userstudy" / "questionnaire.md"
    st.markdown(q.read_text(encoding="utf-8") if q.exists() else "Run `python tools/build_userstudy.py`.")

# --------------------------------------------------------------------------------------------- framework
with tabs[8]:
    st.subheader("Conceptual framework (proposal 3.2.8)")
    img("20_conceptual_framework.png")
    st.markdown("SHAP appears twice in the pipeline: as a **trust check** before deployment (fidelity, stability, direction, race attribution) and as a "
                "**bedside explanation**. The governance gate and group-wise monitoring are the two places where this study found that explainability and fairness meet.")

# --------------------------------------------------------------------------------------------- cohort
with tabs[9]:
    coh = csv(spec, "cohort.csv")
    c1, c2, c3 = st.columns(3)
    race_f = c1.multiselect("Race group", ["White", "Black", "Other"], ["White", "Black", "Other"])
    out_f = c2.selectbox("Outcome", ["All", "Died", "Alive"])
    sub_f = c3.multiselect("PAM50", sorted(coh.subtype.dropna().unique()), [])
    v = coh[coh.race.isin(race_f)]
    if out_f != "All":
        v = v[v.died == (out_f == "Died")]
    if sub_f:
        v = v[v.subtype.isin(sub_f)]
    st.write(f"{len(v)} patients")
    cols = ["patient_id", "race_detail", "died", "followup_months", "age", "t_stage", "n_stage", "m_stage", "subtype", "histology", "radiation", "oof_risk_aware", "split"]
    st.dataframe(v[cols].round(3), hide_index=True, width="stretch", height=460)
    st.markdown("**Table 1**")
    st.dataframe(csv(spec, "table1.csv"), hide_index=True, width="stretch")

# --------------------------------------------------------------------------------------------- about
with tabs[10]:
    md = ROOT / "docs" / "MODEL_CARD.md"
    st.markdown(md.read_text(encoding="utf-8") if md.exists() else "Run `python tools/build_docs.py` to generate the model card.")
