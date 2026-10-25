"""Streamlit dashboard: recall-first death-risk model for TCGA-BRCA, SHAP explanations and a race-fairness lab.

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
ART = ROOT / "artifacts"
sys.path.insert(0, str(ROOT / "src"))
from brca_xai import data as D  # noqa: E402

BLUE, RED, GREY = "#4477AA", "#EE6677", "#9AA0A6"
COL = {"White": BLUE, "Black": RED}
KEYS = ["aware", "blind", "reweigh", "gthr", "reweigh_gthr"]

st.set_page_config(page_title="Recall-first BRCA mortality · fairness lab", page_icon="🎗️", layout="wide")

if not (ART / "meta.json").exists():
    st.error("No artifacts found. Run `python run_pipeline.py` first.")
    st.stop()


@st.cache_data
def meta():
    return json.loads((ART / "meta.json").read_text())


@st.cache_data
def csv(name):
    return pd.read_csv(ART / name)


@st.cache_resource
def model(key):
    m = xgb.XGBClassifier()
    m.load_model(str(ART / f"xgb_{key}.json"))
    return m


M = meta()
LAB = M["labels"]
STRAT = M["strategies"]
SUMMARY = csv("fairness_cv_summary.csv")


def est(strategy, metric):
    r = SUMMARY[(SUMMARY.strategy == strategy) & (SUMMARY.metric == metric)].iloc[0]
    return r.estimate, r.lo, r.hi


def wilson(k, n, z=1.96):
    if n == 0:
        return np.nan, np.nan
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0, c - h), min(1, c + h)


def style(fig, h=380, **kw):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white", paper_bgcolor="white",
                      font=dict(size=13), legend=dict(orientation="h", y=1.12), **kw)
    fig.update_xaxes(gridcolor="#E6E8EB"); fig.update_yaxes(gridcolor="#E6E8EB")
    return fig


st.title("🎗️ Predicting death during follow-up in TCGA-BRCA — recall first, fairness audited")
st.caption("University of Jos MSc project · XGBoost + SHAP · White vs Black patients · research prototype, not for clinical use")

tabs = st.tabs(["Overview", "Patient explainer", "Fairness lab", "Threshold explorer", "Global SHAP", "Data audit", "Cohort", "About"])

# --------------------------------------------------------------------------------------------- overview
with tabs[0]:
    fl = M["flow"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Patients (White + Black)", fl["n_cohort"], f"{fl['n_black']} Black · {fl['n_white']} White")
    c2.metric("Deaths in follow-up", fl["deaths"], f"{fl['deaths_black']} Black · {fl['deaths_white']} White")
    r, lo, hi = est("blind", "tpr_all")
    c3.metric("Recall (race-blind, CV)", f"{r:.0%}", f"target {M['cv']['target_recall']:.0%}")
    r2, _, _ = est("blind", "fpr_all")
    c4.metric("Survivors flagged (cost)", f"{r2:.0%}", help="False-positive rate at the recall-first operating point")
    st.markdown(f"""
**What this does.** Using clinical information known at diagnosis (age, T / N / M stage, PAM50 subtype, histology), an XGBoost model scores
each patient's risk of dying during follow-up. The alarm threshold is **not 0.5**: it is the highest score that still catches
**{M['cv']['target_recall']:.0%} of deaths** (*recall first*), so a missed death is treated as far worse than a false alarm.

**Fairness question.** Does the model catch deaths equally often in Black and White patients (*equal opportunity*), and does it burden
one group with more false alarms? Five strategies are compared on repeated cross-validation with bootstrap confidence intervals.
""")
    a, b = est("aware", "tpr_gap"), est("aware", "fpr_gap")
    st.info(f"**Headline (baseline model).** Recall gap Black − White = **{a[0]:+.1%}** (95 % CI {a[1]:+.1%} to {a[2]:+.1%}); "
            f"false-alarm gap = **{b[0]:+.1%}** (CI {b[1]:+.1%} to {b[2]:+.1%}). With only {fl['deaths_black']} Black deaths the data cannot "
            "rule out a recall gap of ±14 points — absence of evidence, not evidence of absence.")
    st.image(str(ROOT / "reports" / "figures" / "05_rates_by_race.png"))

# --------------------------------------------------------------------------------------------- patient explainer
with tabs[1]:
    st.subheader("Explain one patient")
    left, right = st.columns([1, 1.4])
    with left:
        strategy = st.selectbox("Strategy", KEYS, index=2, format_func=lambda k: STRAT[k]["label"],
                                help=STRAT[KEYS[2]]["note"])
        s = STRAT[strategy]
        age = st.slider("Age at diagnosis", 25, 90, 58)
        t = st.select_slider("Tumour size (T)", [1, 2, 3, 4], 2)
        n = st.select_slider("Nodal status (N)", [0, 1, 2, 3], 0)
        m1 = st.checkbox("Distant metastasis (M1)")
        sub = st.selectbox("PAM50 subtype", ["LumA", "LumB", "Her2", "Basal", "Normal", "Not called"])
        hist = st.selectbox("Histology", ["Ductal", "Lobular", "Other"])
        prior = st.checkbox("Prior malignancy")
        race = st.radio("Patient's recorded race", ["White", "Black"], horizontal=True,
                        help="Only used by strategies that need it (race-aware input or group thresholds).")
    row = {"age": age, "t_stage": t, "n_stage": n, "m_stage": float(m1),
           "histology_lobular": float(hist == "Lobular"), "histology_other": float(hist == "Other"),
           "prior_dx": float(prior), "race_black": float(race == "Black")}
    for k, col in {"LumA": "sub_luma", "LumB": "sub_lumb", "Her2": "sub_her2", "Basal": "sub_basal", "Normal": "sub_normal"}.items():
        row[col] = (float(sub == k) if sub != "Not called" else np.nan)
    key = "aware" if "race_black" in s["features"] else ("reweigh" if s["reweigh"] else "blind")
    feats = s["features"]
    X1 = pd.DataFrame([row])[feats]
    mdl = model(key)
    p = float(mdl.predict_proba(X1)[0, 1])
    thr = M["thresholds"][strategy]
    thr_used = thr[race] if s["group_thresholds"] else thr["global"]
    flagged = p >= thr_used
    ex = shap.TreeExplainer(mdl)
    phi = ex.shap_values(X1)[0]
    base = float(np.ravel(ex.expected_value)[0])
    with right:
        c1, c2, c3 = st.columns(3)
        c1.metric("Predicted risk of death", f"{p:.1%}")
        c2.metric("Alarm threshold", f"{thr_used:.1%}", help="Highest score that still reaches the recall target on training data")
        c3.metric("Decision", "FLAG" if flagged else "not flagged")
        if flagged:
            st.warning("Flagged for closer follow-up. At this operating point most flagged patients survive — the alarm is deliberately sensitive.")
        else:
            st.success("Below the recall-first threshold.")
        order = np.argsort(np.abs(phi))[::-1][:9][::-1]
        names = [f"{LAB[feats[i]]} = {X1.iloc[0, i]:g}" if pd.notna(X1.iloc[0, i]) else f"{LAB[feats[i]]} = n/a" for i in order]
        vals = phi[order]
        fig = go.Figure(go.Bar(x=vals, y=names, orientation="h", marker_color=[RED if v > 0 else BLUE for v in vals]))
        fig.update_layout(title=f"Why this score? (log-odds; base {base:.2f} → {base + phi.sum():.2f})", xaxis_title="SHAP contribution")
        st.plotly_chart(style(fig, 420), width="stretch")
        st.caption("Red pushes risk up, blue pushes it down. Contributions sum exactly to the model's output.")

# --------------------------------------------------------------------------------------------- fairness lab
with tabs[2]:
    st.subheader("Does the model treat Black and White patients equally?")
    rows = []
    for k in KEYS:
        r = {"Strategy": STRAT[k]["label"], "Family": STRAT[k]["family"], "Needs race at prediction": "yes" if (STRAT[k]["group_thresholds"] or "race_black" in STRAT[k]["features"]) else "no"}
        for lab, mt in [("Recall White", "tpr_W"), ("Recall Black", "tpr_B"), ("Recall gap", "tpr_gap"), ("False-alarm White", "fpr_W"),
                        ("False-alarm Black", "fpr_B"), ("False-alarm gap", "fpr_gap"), ("Flagged overall", "flag_all")]:
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
    sw = csv("recall_target_sweep.csv")
    st.markdown("**Does the conclusion depend on the recall target?**")
    c1, c2 = st.columns(2)
    for col, (metric, title) in zip([c1, c2], [("tpr_gap", "Recall gap (Black − White)"), ("fpr_gap", "False-alarm gap (Black − White)")]):
        fig = go.Figure()
        for k in KEYS:
            r = sw[(sw.strategy == k) & (sw.metric == metric)].sort_values("target")
            fig.add_scatter(x=r.target, y=r.estimate, mode="lines+markers", name=STRAT[k]["label"].split(" (")[0])
        fig.add_hline(y=0, line_color="#666"); fig.update_layout(title=title, xaxis_title="Recall target")
        col.plotly_chart(style(fig, 340), width="stretch")
    st.markdown("**Paired bootstrap: did mitigation change the gap versus the baseline?**")
    pr = csv("fairness_paired_vs_aware.csv")
    pr = pr[pr.metric.isin(["tpr_gap", "fpr_gap", "eod"])].copy()
    pr["strategy"] = pr.strategy.map(lambda k: STRAT[k]["label"])
    pr["change vs baseline [95% CI]"] = pr.apply(lambda r: f"{r.diff_vs_aware:+.3f} [{r.lo:+.3f}, {r.hi:+.3f}]", axis=1)
    st.dataframe(pr[["strategy", "metric", "change vs baseline [95% CI]", "prob_smaller"]].rename(columns={"prob_smaller": "P(smaller)"}),
                 hide_index=True, width="stretch")
    st.caption("Negative = mitigation reduced the (signed) gap. An interval that includes 0 means the change is not distinguishable from noise.")
    st.markdown("**Hold-out test set (single split — very wide intervals)**")
    ho = csv("holdout_by_group.csv")
    ho["strategy"] = ho.strategy.map(lambda k: STRAT[k]["label"])
    ho["recall (95% CI)"] = ho.apply(lambda r: f"{r.recall:.0%} [{r.recall_lo:.0%}, {r.recall_hi:.0%}]", axis=1)
    st.dataframe(ho[["strategy", "group", "n", "deaths", "recall (95% CI)", "fpr", "auc"]].round(3), hide_index=True, width="stretch")

# --------------------------------------------------------------------------------------------- threshold explorer
with tabs[3]:
    st.subheader("Recall-first threshold explorer (out-of-fold risk, whole cohort)")
    coh = csv("cohort.csv")
    skey = st.selectbox("Score", ["blind", "reweigh", "aware"], format_func=lambda k: STRAT[k]["label"], key="thr_score")
    risk = coh[f"oof_risk_{skey}"].to_numpy()
    default = M["thresholds"][skey]["global"]
    thr_g = {"White": None, "Black": None}
    mode = st.radio("Threshold", ["One for everyone", "Separate per group"], horizontal=True)
    th_w = st.slider("White threshold" if mode != "One for everyone" else "Threshold", 0.02, 0.5, float(round(default, 3)), 0.005)
    th_b = st.slider("Black threshold", 0.02, 0.5, float(round(default, 3)), 0.005) if mode != "One for everyone" else th_w
    rows = []
    for grp, th in [("White", th_w), ("Black", th_b)]:
        m = coh.race.eq(grp).to_numpy()
        y = coh.died.to_numpy()[m]
        f = risk[m] >= th
        tp, fn, fp, tn = ((y == 1) & f).sum(), ((y == 1) & ~f).sum(), ((y == 0) & f).sum(), ((y == 0) & ~f).sum()
        lo, hi = wilson(tp, tp + fn)
        rows.append({"Group": grp, "Patients": int(m.sum()), "Deaths": int(tp + fn), "Caught": int(tp), "Missed": int(fn),
                     "Recall": tp / (tp + fn), "Recall CI": f"{lo:.0%}-{hi:.0%}", "False alarms": int(fp), "False-alarm rate": fp / (fp + tn),
                     "Flagged": (tp + fp) / m.sum()})
    t = pd.DataFrame(rows)
    st.dataframe(t.style.format({"Recall": "{:.1%}", "False-alarm rate": "{:.1%}", "Flagged": "{:.1%}"}), hide_index=True, width="stretch")
    grid = np.linspace(0.04, 0.4, 73)
    fig = go.Figure()
    for grp in ["White", "Black"]:
        m = coh.race.eq(grp).to_numpy(); y = coh.died.to_numpy()[m]
        fig.add_scatter(x=grid, y=[(risk[m][y == 1] >= g).mean() for g in grid], name=f"{grp} recall", line=dict(color=COL[grp]))
        fig.add_scatter(x=grid, y=[(risk[m][y == 0] >= g).mean() for g in grid], name=f"{grp} false-alarm rate", line=dict(color=COL[grp], dash="dot"))
    fig.add_vline(x=th_w, line_color=BLUE); fig.add_vline(x=th_b, line_color=RED, line_dash="dash")
    fig.update_layout(xaxis_title="Threshold on predicted risk", yaxis_title="Rate", yaxis_range=[0, 1.02])
    st.plotly_chart(style(fig, 420), width="stretch")
    st.caption("Out-of-fold scores (each patient scored by models that never saw them), averaged over repeats. The Black curves are jagged because only 30 patients died.")

# --------------------------------------------------------------------------------------------- global SHAP
with tabs[4]:
    st.subheader("What drives the model?")
    imp = csv("importance_black_vs_white.csv").rename(columns={"Unnamed: 0": "feature"})
    top = imp.head(10).iloc[::-1]
    fig = go.Figure()
    fig.add_bar(y=top.label, x=top["White"], orientation="h", name="White", marker_color=BLUE)
    fig.add_bar(y=top.label, x=top["Black"], orientation="h", name="Black", marker_color=RED)
    fig.update_layout(barmode="group", title="Mean |SHAP| by race (race-blind model)", xaxis_title="log-odds")
    st.plotly_chart(style(fig, 420), width="stretch")
    c1, c2 = st.columns(2)
    gd = csv("risk_gap_decomposition.csv").head(7).iloc[::-1]
    fig = go.Figure(go.Bar(y=gd.label, x=gd.contribution_to_gap, orientation="h", marker_color=[RED if v > 0 else BLUE for v in gd.contribution_to_gap]))
    fig.update_layout(title=f"Why average predicted risk differs by race (total {M['risk_gap_total']:+.3f} log-odds)")
    c1.plotly_chart(style(fig, 360), width="stretch")
    sb = csv("stability_black.csv").rename(columns={"Unnamed: 0": "feature"}).head(9).iloc[::-1]
    fig = go.Figure(go.Scatter(y=sb.label, x=sb.mean_rank, mode="markers", marker=dict(color=RED, size=9),
                               error_x=dict(type="data", symmetric=False, array=sb.rank_hi - sb.mean_rank, arrayminus=sb.mean_rank - sb.rank_lo)))
    fig.update_layout(title="Stability of importance rank among Black patients", xaxis_autorange="reversed", xaxis_title="rank (1 = most important)")
    c2.plotly_chart(style(fig, 360), width="stretch")
    sh = csv("cohort_shap.csv"); coh = csv("cohort.csv")
    feat = st.selectbox("Dependence plot", [f for f in M["features_blind"] if f not in ("prior_dx",)], format_func=lambda f: LAB[f])
    fig = go.Figure()
    rng = np.random.default_rng(0)
    for grp in ["White", "Black"]:
        m = coh.race.eq(grp)
        fig.add_scatter(x=coh.loc[m, feat] + (rng.normal(0, .05, m.sum()) if coh[feat].nunique() < 8 else 0), y=sh.loc[m, f"shap_blind__{feat}"],
                        mode="markers", name=grp, marker=dict(color=COL[grp], opacity=.55, size=6))
    fig.update_layout(xaxis_title=LAB[feat], yaxis_title="SHAP (log-odds)")
    st.plotly_chart(style(fig, 360), width="stretch")
    st.image(str(ROOT / "reports" / "figures" / "12_shap_beeswarm.png"))

# --------------------------------------------------------------------------------------------- data audit
with tabs[5]:
    st.subheader("Why some columns are not allowed in")
    lad = csv("leakage_ladder.csv")
    fig = go.Figure(go.Bar(y=lad.rung.iloc[::-1], x=lad.auc.iloc[::-1], orientation="h", marker_color=[GREY] * 4 + [BLUE]))
    fig.update_layout(title="Cross-validated AUC as forbidden columns are added", xaxis_range=[0.5, 1])
    st.plotly_chart(style(fig, 360), width="stretch")
    st.dataframe(lad[["rung", "note", "auc", "fpr_at_80_recall"]].round(3), hide_index=True, width="stretch")
    c1, c2 = st.columns(2)
    c1.markdown("**Death rate when a field is missing vs recorded**")
    c1.dataframe(csv("missingness_audit.csv").round(3), hide_index=True, width="stretch")
    c2.markdown("**Column governance (all 38 source columns)**")
    c2.dataframe(csv("column_governance.csv"), hide_index=True, width="stretch", height=420)

# --------------------------------------------------------------------------------------------- cohort
with tabs[6]:
    coh = csv("cohort.csv")
    c1, c2, c3 = st.columns(3)
    race_f = c1.multiselect("Race", ["White", "Black"], ["White", "Black"])
    out_f = c2.selectbox("Outcome", ["All", "Died", "Alive"])
    sub_f = c3.multiselect("PAM50", sorted(coh.subtype.dropna().unique()), [])
    v = coh[coh.race.isin(race_f)]
    if out_f != "All":
        v = v[v.died == (out_f == "Died")]
    if sub_f:
        v = v[v.subtype.isin(sub_f)]
    st.write(f"{len(v)} patients")
    cols = ["patient_id", "race", "died", "followup_months", "age", "t_stage", "n_stage", "m_stage", "subtype", "histology", "oof_risk_blind", "flag_rate_blind", "split"]
    st.dataframe(v[cols].round(3), hide_index=True, width="stretch", height=480)
    st.markdown("**Table 1**")
    st.dataframe(csv("table1.csv"), hide_index=True, width="stretch")

# --------------------------------------------------------------------------------------------- about
with tabs[7]:
    md = ROOT / "docs" / "MODEL_CARD.md"
    st.markdown(md.read_text(encoding="utf-8") if md.exists() else "Run `python tools/build_docs.py` to generate the model card.")
