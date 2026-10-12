"""Interactive SHAP dashboard for the TCGA-BRCA mortality-risk XGBoost model.

Run:  streamlit run app.py
Everything shown is read from ./artifacts, which the notebook writes - nothing is re-trained here.
RESEARCH PROTOTYPE - not for clinical use.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import shap
import streamlit as st
from sklearn.metrics import precision_recall_curve, roc_auc_score, roc_curve
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parent
ART = ROOT / "artifacts"
sys.path.insert(0, str(ROOT / "src"))
from brca_xai import FEATURES, FEATURES_NO_RACE, LABELS, encode  # noqa: E402

# colour-blind-safe (Okabe-Ito) - one fixed colour per group everywhere
RC = {"Black": "#D55E00", "White": "#0072B2", "Asian": "#009E73", "All": "#555555"}
UP, DOWN = "#C2185B", "#3F6FB5"        # SHAP polarity: raises / lowers predicted risk
INK = "#6b7280"

st.set_page_config(page_title="SHAP explorer · TCGA-BRCA", page_icon="🎗️", layout="wide")


# --------------------------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------------------------
@st.cache_resource(show_spinner="Loading model …")
def load_models():
    meta = json.loads((ART / "meta.json").read_text())
    m, mn = XGBClassifier(), XGBClassifier()
    m.load_model(ART / "xgb_model.json")
    mn.load_model(ART / "xgb_model_norace.json")
    return meta, m, mn, shap.TreeExplainer(m), shap.TreeExplainer(mn)


@st.cache_data
def load_cohort() -> pd.DataFrame:
    return pd.read_csv(ART / "cohort.csv")


@st.cache_data
def load_csv(name):
    return pd.read_csv(ART / name, index_col=0)


if not (ART / "cohort.csv").exists():
    st.error("Artifacts not found. Run the notebook `breast_cancer_shap_implementation.ipynb` first.")
    st.stop()

meta, MODEL, MODEL_NR, EXPL, EXPL_NR = load_models()
cohort = load_cohort()
THR = meta["threshold_all_oof"]
BASE = meta["base_value"]
X_COLS = [f"x_{f}" for f in FEATURES]
S_COLS = [f"shap_{f}" for f in FEATURES]
Xc = cohort[X_COLS].rename(columns=lambda c: c[2:])
Sc = cohort[S_COLS].rename(columns=lambda c: c[5:])
y_all = cohort["died"].astype(int).values
sigmoid = lambda z: 1 / (1 + np.exp(-z))


def fmt_val(f, v):
    if pd.isna(v):
        return "unknown"
    if f == "age":
        return f"{v:.0f} y"
    if f == "t_stage":
        return f"T{int(v)}"
    if f == "n_stage":
        return f"N{int(v)}"
    return {1: "yes", 0: "no"}.get(int(v), str(v))


def style(fig, h=420, **kw):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=40, b=10), legend=dict(orientation="h", y=-0.18), **kw)
    return fig


# --------------------------------------------------------------------------------------------
# header
# --------------------------------------------------------------------------------------------
st.title("Explaining an XGBoost mortality-risk model with SHAP")
st.caption(f"TCGA-BRCA · {meta['n_patients']} women · {meta['n_events']} deaths · outcome: *{meta['target']}* · "
           "Univ. of Jos, Dept. of Computer Science")
st.warning("**Research prototype — not for clinical use.** Trained on a small public research cohort (TCGA). "
           "SHAP explains what the *model* does, not why disease outcomes differ. Race is self-reported and a proxy for "
           "factors not in the data.", icon="⚠️")

tabs = st.tabs(["🧑‍⚕️ Patient explainer", "🌍 Global SHAP", "⚖️ Black patients & equity", "🔎 Cohort explorer",
                "📈 Model & threshold", "ℹ️ About"])

# --------------------------------------------------------------------------------------------
# 1. patient explainer
# --------------------------------------------------------------------------------------------
HIST = ["Ductal", "Lobular", "Other"]
RECEPT = ["Unknown", "Positive", "Negative"]
DEFAULTS = dict(in_age=58, in_race="Black", in_t=2, in_n=0, in_m=False, in_er="Positive", in_pr="Positive",
                in_her2="Negative / not tested", in_hist="Ductal", in_model="With race flag")
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)


def load_patient():
    pid = st.session_state.pick
    if pid == "— enter manually —":
        return
    r = cohort[cohort.patient_id == pid].iloc[0]
    rec = lambda v: "Unknown" if pd.isna(v) else ("Positive" if v == 1 else "Negative")
    st.session_state.update(
        in_age=int(round(r["age"])), in_race=r["race"],
        in_t=int(r["t_stage"]) if pd.notna(r["t_stage"]) else 2, in_n=int(r["n_stage"]) if pd.notna(r["n_stage"]) else 0,
        in_m=bool(r["m_stage"] == 1), in_er=rec(r["er_pos"]), in_pr=rec(r["pr_pos"]),
        in_her2="Positive" if r["her2_pos"] == 1 else "Negative / not tested",
        in_hist=r["histology"] if r["histology"] in HIST else "Ductal")


def patient_frame():
    s = st.session_state
    num = lambda v: {"Positive": 1.0, "Negative": 0.0}.get(v, np.nan)
    return pd.DataFrame([dict(race=s.in_race, age=float(s.in_age), t_stage=float(s.in_t), n_stage=float(s.in_n),
                              m_stage=1.0 if s.in_m else 0.0, er_pos=num(s.in_er), pr_pos=num(s.in_pr),
                              her2_pos=1.0 if s.in_her2 == "Positive" else 0.0, histology=s.in_hist, menopause=np.nan)])


def predict(df_clean, race_blind=False):
    X = encode(df_clean)
    if race_blind:
        X = X[FEATURES_NO_RACE]
        return X, MODEL_NR.predict_proba(X)[:, 1], EXPL_NR.shap_values(X), float(EXPL_NR.expected_value)
    return X, MODEL.predict_proba(X)[:, 1], EXPL.shap_values(X), float(EXPL.expected_value)


def contribution_chart(feats, vals, phis, base, title):
    order = np.argsort(np.abs(phis))
    labels = [f"{LABELS[feats[i]]} = {fmt_val(feats[i], vals[i])}" for i in order]
    ph = np.array(phis)[order]
    fig = go.Figure(go.Bar(
        x=ph, y=labels, orientation="h", marker_color=[UP if v > 0 else DOWN for v in ph],
        text=[f"{'▲' if v > 0 else '▼'} ×{np.exp(v):.2f} odds" for v in ph], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}<br>SHAP %{x:+.3f} log-odds<br>odds multiplier ×%{customdata:.2f}<extra></extra>", customdata=np.exp(ph)))
    fig.add_vline(x=0, line_width=1, line_color=INK)
    fig.update_layout(title=title, xaxis_title="SHAP value (log-odds)  ←  lowers risk | raises risk  →",
                      xaxis=dict(range=[min(ph.min() * 1.6, -0.2), max(ph.max() * 1.6, 0.2)]))
    return style(fig, h=max(330, 36 * len(feats) + 120))


with tabs[0]:
    left, right = st.columns([1, 2.2], gap="large")
    with left:
        st.subheader("Patient")
        st.selectbox("Load a real cohort patient", ["— enter manually —"] + cohort.patient_id.tolist(), key="pick", on_change=load_patient,
                     help="Fills the form from a TCGA record. Race-specific browsing is in the equity tab.")
        st.slider("Age at diagnosis", 20, 90, key="in_age")
        st.radio("Race (self-reported)", ["White", "Black", "Asian"], key="in_race", horizontal=True)
        c1, c2 = st.columns(2)
        c1.select_slider("Tumour size (T)", [1, 2, 3, 4], key="in_t")
        c2.select_slider("Nodal status (N)", [0, 1, 2, 3], key="in_n", help="Not assessed (NX) is treated as N0, as in training.")
        st.checkbox("Distant metastasis (M1)", key="in_m", help="MX / not assessed is treated as M0, as in training.")
        c3, c4 = st.columns(2)
        c3.selectbox("ER status", RECEPT, key="in_er")
        c4.selectbox("PR status", RECEPT, key="in_pr")
        st.selectbox("HER2", ["Negative / not tested", "Positive"], key="in_her2")
        st.selectbox("Histology", HIST, key="in_hist")
        st.radio("Model", ["With race flag", "Race-blind twin"], key="in_model", help="The twin was trained without any race input.")

    blind = st.session_state.in_model == "Race-blind twin"
    dfp = patient_frame()
    X1, p1, phi1, base1 = predict(dfp, blind)
    p = float(p1[0])
    feats = list(X1.columns)
    flagged = p >= THR
    pct = float((cohort.risk_final < p).mean() * 100)

    with right:
        m1, m2, m3 = st.columns(3)
        m1.metric("Predicted mortality risk", f"{p:.1%}", f"{p - sigmoid(base1):+.1%} vs average patient", delta_color="off")
        m2.metric("Risk percentile in cohort", f"{pct:.0f}th")
        m3.metric(f"Screen at {THR:.1%} threshold", "FLAGGED" if flagged else "Not flagged",
                  help=f"The threshold keeps ≥{meta['target_recall']:.0%} recall (few missed deaths).")
        st.plotly_chart(contribution_chart(feats, X1.iloc[0].values, phi1[0], base1,
                                           f"Why this score?  baseline {sigmoid(base1):.1%} → {p:.1%}"), width="stretch")
        top = sorted(zip(feats, phi1[0]), key=lambda t: -abs(t[1]))[:3]
        st.markdown("**In plain words:** " + "; ".join(
            f"**{LABELS[f]}** ({fmt_val(f, X1.iloc[0][f])}) {'raises' if v > 0 else 'lowers'} the odds ×{np.exp(v):.2f}" for f, v in top) + ".")

        if not blind and st.session_state.in_race != "White":
            alt = dfp.copy(); alt["race"] = "White"
            _, pw, _, _ = predict(alt)
            st.info(f"**Race counterfactual:** with every clinical value unchanged but race recorded as White, the model would "
                    f"score **{pw[0]:.1%}** ({(pw[0] - p) * 100:+.2f} percentage points). A value near 0 means the model is not using the race flag.")

    st.subheader("What-if: how does risk change as one input varies?")
    sweep = st.radio("Vary", ["age", "t_stage", "n_stage"], format_func=lambda f: LABELS[f], horizontal=True)
    grid = {"age": np.arange(25, 91, 1), "t_stage": [1, 2, 3, 4], "n_stage": [0, 1, 2, 3]}[sweep]
    rows = []
    for rc in ["Black", "White", "Asian"]:
        d = pd.concat([dfp] * len(grid), ignore_index=True); d["race"] = rc; d[sweep] = grid
        _, pp, _, _ = predict(d, blind)
        rows.append(pd.DataFrame({"x": grid, "risk": pp, "race": rc}))
    sw = pd.concat(rows)
    fig = px.line(sw, x="x", y="risk", color="race", color_discrete_map=RC, markers=(sweep != "age"))
    fig.add_vline(x=float(st.session_state[{"age": "in_age", "t_stage": "in_t", "n_stage": "in_n"}[sweep]]), line_dash="dot", line_color=INK,
                  annotation_text="this patient")
    fig.add_hline(y=THR, line_dash="dash", line_color=INK, annotation_text="screening threshold")
    fig.update_layout(xaxis_title=LABELS[sweep], yaxis_title="predicted mortality risk", yaxis_tickformat=".0%")
    st.plotly_chart(style(fig, 360), width="stretch")
    st.caption("All other inputs held at the values on the left. Lines that sit on top of each other mean the model treats the groups identically for this feature.")

# --------------------------------------------------------------------------------------------
# 2. global SHAP
# --------------------------------------------------------------------------------------------
with tabs[1]:
    c1, c2 = st.columns([1, 3])
    with c1:
        grp = st.radio("Patients", ["All", "Black", "White", "Asian"], key="g_grp")
        top_n = st.slider("Features shown", 3, len(FEATURES), len(FEATURES))
    mask = np.ones(len(cohort), bool) if grp == "All" else (cohort.race == grp).values
    Sg, Xg = Sc[mask], Xc[mask]
    order = Sg.abs().mean().sort_values(ascending=False).index[:top_n].tolist()
    with c2:
        st.caption(f"**{grp}** — {mask.sum()} patients, {int(y_all[mask].sum())} deaths")
    a, b = st.columns(2)
    with a:
        imp = Sg.abs().mean()[order][::-1]
        fig = go.Figure(go.Bar(x=imp.values, y=[LABELS[f] for f in imp.index], orientation="h", marker_color=RC[grp],
                               hovertemplate="%{y}: %{x:.3f}<extra></extra>"))
        fig.update_layout(title="Global importance — mean |SHAP|", xaxis_title="mean |SHAP| (log-odds)")
        st.plotly_chart(style(fig, 440), width="stretch")
    with b:
        rngj = np.random.default_rng(0)
        fig = go.Figure()
        for i, f in enumerate(order[::-1]):
            v = Xg[f].values.astype(float)
            lo, hi = np.nanpercentile(v, [2, 98]) if np.nanstd(v) > 0 else (0, 1)
            col = np.clip((v - lo) / (hi - lo + 1e-9), 0, 1)
            fig.add_trace(go.Scatter(
                x=Sg[f], y=i + rngj.uniform(-0.3, 0.3, len(v)), mode="markers", showlegend=False,
                marker=dict(size=5, color=np.where(np.isnan(col), 0.5, col), colorscale="Cividis", opacity=0.75,
                            cmin=0, cmax=1, showscale=(i == 0), colorbar=dict(title="feature<br>value", tickvals=[0, 1], ticktext=["low", "high"], len=0.6)),
                customdata=np.c_[cohort.patient_id[mask], [fmt_val(f, t) for t in v]],
                hovertemplate=f"{LABELS[f]} = %{{customdata[1]}}<br>SHAP %{{x:+.3f}}<br>%{{customdata[0]}}<extra></extra>"))
        fig.add_vline(x=0, line_color=INK, line_width=1)
        fig.update_layout(title="SHAP summary (each dot = one patient)", xaxis_title="SHAP value (log-odds)",
                          yaxis=dict(tickmode="array", tickvals=list(range(len(order))), ticktext=[LABELS[f] for f in order[::-1]]))
        st.plotly_chart(style(fig, 440), width="stretch")

    st.subheader("Dependence: the shape of one feature’s effect")
    d1, d2, d3 = st.columns(3)
    fx = d1.selectbox("Feature (x)", FEATURES, format_func=lambda f: LABELS[f], key="dep_x")
    colorby = d2.selectbox("Colour by", ["race", "outcome"] + FEATURES, format_func=lambda f: LABELS.get(f, f.title()), key="dep_c")
    show_lines = d3.checkbox("Overlay binned means by race", value=True)
    dd = pd.DataFrame({"x": Xc[fx], "shap": Sc[fx], "race": cohort.race, "id": cohort.patient_id,
                       "outcome": np.where(y_all == 1, "died", "alive")})
    if colorby in FEATURES:
        dd["c"] = Xc[colorby]
        fig = px.scatter(dd, x="x", y="shap", color="c", color_continuous_scale="Cividis", hover_name="id", opacity=0.7,
                         labels={"c": LABELS[colorby]})
    else:
        cm = RC if colorby == "race" else {"died": "#B5179E", "alive": "#9aa0a6"}
        fig = px.scatter(dd, x="x" if fx != "age" else "x", y="shap", color=colorby, color_discrete_map=cm, hover_name="id", opacity=0.6)
    if show_lines:
        for rc in ["Black", "White"]:
            s_ = dd[dd.race == rc].dropna(subset=["x"])
            if s_.x.nunique() > 8:
                s_ = s_.assign(b=pd.qcut(s_.x, 8, duplicates="drop")).groupby("b", observed=True).agg(x=("x", "mean"), shap=("shap", "mean"))
            else:
                s_ = s_.groupby("x", as_index=False).agg(shap=("shap", "mean"))
            fig.add_trace(go.Scatter(x=s_.x, y=s_.shap, mode="lines+markers", name=f"{rc} mean", line=dict(color=RC[rc], width=3)))
    fig.add_hline(y=0, line_color=INK, line_width=1)
    fig.update_layout(xaxis_title=LABELS[fx], yaxis_title=f"SHAP value of {LABELS[fx]}")
    st.plotly_chart(style(fig, 430), width="stretch")

    with st.expander("Pairwise interactions (SHAP interaction values)"):
        @st.cache_data
        def interactions():
            return np.abs(EXPL.shap_interaction_values(Xc[FEATURES])).mean(0)
        M = interactions().copy(); np.fill_diagonal(M, 0)
        lab = [LABELS[f] for f in FEATURES]
        st.plotly_chart(style(px.imshow(M, x=lab, y=lab, color_continuous_scale="Blues", aspect="auto", labels=dict(color="mean |interaction|")), 480), width="stretch")

# --------------------------------------------------------------------------------------------
# 3. Black patients & equity
# --------------------------------------------------------------------------------------------
with tabs[2]:
    blk, wht = (cohort.race == "Black").values, (cohort.race == "White").values
    st.markdown(f"**{blk.sum()} Black patients ({int(y_all[blk].sum())} deaths)** vs **{wht.sum()} White ({int(y_all[wht].sum())} deaths)**. "
                "With so few Black events every estimate is uncertain; intervals come from the notebook.")

    st.subheader("1 · What does the model rely on for Black vs. White patients?")
    cmp_ = load_csv("importance_black_vs_white.csv")
    cmp_ = cmp_.sort_values("Black share")
    fig = go.Figure()
    fig.add_bar(y=cmp_.index, x=cmp_["White share"] * 100, orientation="h", name="White", marker_color=RC["White"])
    fig.add_bar(y=cmp_.index, x=cmp_["Black share"] * 100, orientation="h", name="Black", marker_color=RC["Black"])
    fig.update_layout(barmode="group", xaxis_title="share of total mean |SHAP| (%)")
    st.plotly_chart(style(fig, 460), width="stretch")
    st.caption("★ in the notebook marks differences whose 95% CI excludes 0 and that exceed 2 share-points.")

    st.subheader("2 · Why does the average predicted risk differ? (risk-gap decomposition)")
    gap = load_csv("risk_gap_decomposition.csv").sort_values("contribution to gap")
    fig = go.Figure(go.Bar(
        y=gap.index, x=gap["contribution to gap"], orientation="h",
        marker_color=[RC["Black"] if v > 0 else RC["White"] for v in gap["contribution to gap"]],
        error_x=dict(type="data", symmetric=False, array=gap.hi - gap["contribution to gap"], arrayminus=gap["contribution to gap"] - gap.lo, color=INK)))
    fig.add_vline(x=0, line_color=INK, line_width=1)
    fig.update_layout(xaxis_title="Δ mean SHAP (Black − White), log-odds  ·  bars right = raises Black patients’ predicted risk")
    st.plotly_chart(style(fig, 440), width="stretch")
    st.caption(f"Mean predicted risk: Black {cohort.risk_final[blk].mean():.1%} · White {cohort.risk_final[wht].mean():.1%}. Whiskers: 95% bootstrap CI.")

    st.subheader("3 · Does the model use the race flag directly?")
    Xcf = Xc.copy(); Xcf["race_black"] = 0.0
    delta = (MODEL.predict_proba(Xc[FEATURES])[:, 1] - MODEL.predict_proba(Xcf[FEATURES])[:, 1])[blk] * 100
    a, b = st.columns([1, 2])
    a.metric("Mean Δ risk if recorded White", f"{delta.mean():+.2f} pp")
    a.metric("Largest single-patient |Δ|", f"{np.abs(delta).max():.1f} pp")
    a.metric("Race-flag mean |SHAP|", f"{Sc['race_black'].abs().mean():.3f}", help="Compare with Age on the Global tab.")
    fig = px.histogram(x=delta, nbins=30, color_discrete_sequence=[RC["Black"]])
    fig.add_vline(x=0, line_color=INK)
    fig.update_layout(xaxis_title="change in predicted risk when race is flipped to White (percentage points)", yaxis_title="Black patients")
    b.plotly_chart(style(fig, 280), width="stretch")

    st.subheader("4 · Do errors fall equally on both groups? (threshold you choose)")
    thr = st.slider("Decision threshold", 0.03, 0.40, float(THR), 0.005, format="%.3f", key="eq_thr")
    rows = []
    for g_, m_ in [("Black", blk), ("White", wht)]:
        p_, y_ = cohort.risk_oof.values[m_], y_all[m_]
        yh = p_ >= thr
        tp, fn, fp, tn = ((yh & (y_ == 1)).sum(), (~yh & (y_ == 1)).sum(), (yh & (y_ == 0)).sum(), (~yh & (y_ == 0)).sum())
        rows.append(dict(Group=g_, n=len(y_), Deaths=int(y_.sum()), Recall=tp / max(tp + fn, 1), **{"Missed deaths (FN)": int(fn)},
                         **{"False-positive rate": fp / max(fp + tn, 1)}, Precision=tp / max(tp + fp, 1), AUC=roc_auc_score(y_, p_)))
    st.dataframe(pd.DataFrame(rows).set_index("Group").style.format({"Recall": "{:.0%}", "False-positive rate": "{:.0%}", "Precision": "{:.0%}", "AUC": "{:.2f}"}), width="stretch")
    rv = pd.read_csv(ART / "recall_vs_threshold.csv")
    fig = go.Figure()
    for g_ in ["Black", "White"]:
        fig.add_scatter(x=rv.threshold, y=rv[f"recall_{g_}"], name=g_, line=dict(color=RC[g_], width=3 if g_ == "Black" else 2))
    fig.add_vline(x=thr, line_dash="dash", line_color=INK)
    fig.update_layout(xaxis_title="decision threshold", yaxis_title="recall (share of deaths flagged)", yaxis_tickformat=".0%")
    st.plotly_chart(style(fig, 300), width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Calibration by race** (out-of-fold)")
        fig = go.Figure(); fig.add_scatter(x=[0, .5], y=[0, .5], mode="lines", line=dict(dash="dash", color=INK), name="perfect", showlegend=False)
        for g_, m_ in [("Black", blk), ("White", wht)]:
            d_ = pd.DataFrame({"p": cohort.risk_oof[m_].values, "y": y_all[m_]})
            d_ = d_.groupby(pd.qcut(d_.p, 4 if g_ == "Black" else 5, duplicates="drop"), observed=True).agg(p=("p", "mean"), y=("y", "mean"), n=("y", "size"))
            fig.add_scatter(x=d_.p, y=d_.y, mode="lines+markers", name=g_, line=dict(color=RC[g_]), text=d_.n, hovertemplate="predicted %{x:.1%}<br>observed %{y:.1%}<br>n=%{text}<extra></extra>")
        fig.update_layout(xaxis_title="mean predicted risk", yaxis_title="observed death rate", xaxis_tickformat=".0%", yaxis_tickformat=".0%")
        st.plotly_chart(style(fig, 320), width="stretch")
    with c2:
        st.markdown("**How stable is the Black-patient explanation?** (100 bootstrap re-trainings)")
        stb = load_csv("stability_black.csv")
        st.dataframe(stb[["importance share (median)", "2.5%", "97.5%", "P(top-3)"]].style.format("{:.2f}").background_gradient(subset=["P(top-3)"], cmap="Blues"), width="stretch", height=320)

    st.subheader("5 · Look at an individual Black patient")
    bl = cohort[blk].sort_values("risk_oof", ascending=False)
    pick = st.selectbox("Patient (sorted by predicted risk)", bl.patient_id,
                        format_func=lambda i: f"{i} · risk {bl.set_index('patient_id').risk_oof[i]:.0%} · {'DIED' if bl.set_index('patient_id').died[i] == 1 else 'alive/censored'}")
    r = cohort[cohort.patient_id == pick].iloc[0]
    st.plotly_chart(contribution_chart(FEATURES, Xc.loc[r.name].values, Sc.loc[r.name].values, BASE,
                                       f"{pick}: final-model risk {r.risk_final:.1%} (out-of-fold {r.risk_oof:.1%}) — outcome: {'died' if r.died == 1 else 'alive / censored'}, follow-up {r.os_months:.0f} months"), width="stretch")

# --------------------------------------------------------------------------------------------
# 4. cohort explorer
# --------------------------------------------------------------------------------------------
with tabs[3]:
    st.markdown("Filter the cohort and watch the risk distribution and the SHAP explanation change.")
    f1, f2, f3, f4 = st.columns(4)
    races = f1.multiselect("Race", ["Black", "White", "Asian"], default=["Black", "White", "Asian"])
    ar = f2.slider("Age", 20, 90, (20, 90))
    ts = f3.multiselect("T stage", [1, 2, 3, 4], default=[1, 2, 3, 4])
    ns = f4.multiselect("N stage", [0, 1, 2, 3], default=[0, 1, 2, 3])
    g1, g2, g3 = st.columns(3)
    er_f = g1.multiselect("ER", ["Positive", "Negative", "Unknown"], default=["Positive", "Negative", "Unknown"])
    out_f = g2.multiselect("Outcome", ["died", "alive / censored"], default=["died", "alive / censored"])
    sp_f = g3.multiselect("Data split", ["train", "val", "test"], default=["train", "val", "test"])
    erl = cohort.x_er_pos.map({1.0: "Positive", 0.0: "Negative"}).fillna("Unknown")
    m = (cohort.race.isin(races) & cohort.age.between(*ar) & (cohort.x_t_stage.isin(ts) | (cohort.x_t_stage.isna() & (len(ts) == 4)))
         & cohort.x_n_stage.isin(ns) & erl.isin(er_f) & pd.Series(np.where(y_all == 1, "died", "alive / censored"), index=cohort.index).isin(out_f)
         & cohort.split.isin(sp_f)).values
    sub = cohort[m]
    if len(sub) < 5:
        st.info("Fewer than 5 patients match — widen the filters.")
    else:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Patients", len(sub)); k2.metric("Deaths", int(sub.died.sum()), f"{sub.died.mean():.1%}", delta_color="off")
        k3.metric("Mean predicted risk", f"{sub.risk_oof.mean():.1%}"); k4.metric("Flagged high-risk", f"{(sub.risk_oof >= THR).mean():.0%}")
        a, b = st.columns(2)
        with a:
            fig = px.histogram(sub, x="risk_oof", color="race", color_discrete_map=RC, nbins=30, barmode="overlay", opacity=0.65, histnorm="probability density")
            fig.add_vline(x=THR, line_dash="dash", line_color=INK, annotation_text="threshold")
            fig.update_layout(xaxis_title="out-of-fold predicted risk", xaxis_tickformat=".0%")
            st.plotly_chart(style(fig, 340), width="stretch")
        with b:
            xv = st.selectbox("Scatter: x", ["age"] + [c for c in ["t_stage", "n_stage"]], format_func=lambda f: LABELS[f], key="ce_x")
            fig = px.scatter(sub.assign(outcome=np.where(sub.died == 1, "died", "alive / censored")), x=xv, y="risk_oof", color="race", color_discrete_map=RC,
                             symbol="outcome", symbol_map={"died": "x", "alive / censored": "circle"}, hover_name="patient_id", opacity=0.75)
            fig.update_layout(yaxis_title="out-of-fold predicted risk", yaxis_tickformat=".0%", xaxis_title=LABELS[xv])
            st.plotly_chart(style(fig, 340), width="stretch")
        ms = sub[S_COLS].abs().mean().rename(index=lambda c: LABELS[c[5:]]).sort_values()
        fig = go.Figure(go.Bar(x=ms.values, y=ms.index, orientation="h", marker_color=RC["All"]))
        fig.update_layout(title=f"What drives the model inside this selection (n={len(sub)})", xaxis_title="mean |SHAP|")
        st.plotly_chart(style(fig, 380), width="stretch")
        show = sub[["patient_id", "race", "age", "x_t_stage", "x_n_stage", "x_m_stage", "x_er_pos", "x_pr_pos", "x_her2_pos", "died", "os_months", "risk_oof", "split"]]
        st.dataframe(show.rename(columns=lambda c: c[2:] if c.startswith("x_") else c), width="stretch", height=260)
        st.download_button("Download selection (CSV)", show.to_csv(index=False), "selection.csv", "text/csv")

# --------------------------------------------------------------------------------------------
# 5. model & threshold
# --------------------------------------------------------------------------------------------
with tabs[4]:
    tm = meta["test_metrics"]
    c = st.columns(6)
    for col, (k, lab) in zip(c, [("AUC", "AUC"), ("Recall", "Recall"), ("Specificity", "Specificity"), ("Precision", "Precision"), ("F1", "F1"), ("Accuracy", "Accuracy")]):
        col.metric(f"Test {lab}", f"{tm[k]:.2f}")
    st.caption(f"Hold-out test split (n={meta['test_n']}); bootstrap CIs are in the notebook. Out-of-fold AUC over all patients: {meta['oof_auc_overall']:.2f}.")
    a, b = st.columns(2)
    fpr, tpr, _ = roc_curve(y_all, cohort.risk_oof)
    pr_, rc_, _ = precision_recall_curve(y_all, cohort.risk_oof)
    with a:
        fig = go.Figure(); fig.add_scatter(x=fpr, y=tpr, line=dict(color=RC["All"], width=2.5), name="ROC")
        fig.add_scatter(x=[0, 1], y=[0, 1], line=dict(dash="dash", color=INK), showlegend=False)
        fig.update_layout(title="ROC (out-of-fold)", xaxis_title="false-positive rate", yaxis_title="recall")
        st.plotly_chart(style(fig, 340), width="stretch")
    with b:
        fig = go.Figure(); fig.add_scatter(x=rc_, y=pr_, line=dict(color=RC["All"], width=2.5))
        fig.add_hline(y=y_all.mean(), line_dash="dash", line_color=INK, annotation_text="prevalence")
        fig.update_layout(title="Precision–recall (out-of-fold)", xaxis_title="recall", yaxis_title="precision")
        st.plotly_chart(style(fig, 340), width="stretch")
    st.subheader("Move the threshold")
    t2 = st.slider("Decision threshold", 0.03, 0.50, float(THR), 0.005, format="%.3f", key="mt_thr")
    yh = cohort.risk_oof.values >= t2
    tp, fn, fp, tn = int((yh & (y_all == 1)).sum()), int((~yh & (y_all == 1)).sum()), int((yh & (y_all == 0)).sum()), int((~yh & (y_all == 0)).sum())
    z = [[tn, fp], [fn, tp]]
    fig = px.imshow(z, text_auto=True, x=["predicted low", "predicted high"], y=["actually alive/censored", "actually died"], color_continuous_scale="Blues", aspect="auto")
    fig.update_layout(coloraxis_showscale=False)
    a, b = st.columns([1, 1])
    a.plotly_chart(style(fig, 300), width="stretch")
    b.metric("Recall", f"{tp / max(tp + fn, 1):.0%}"); b.metric("Specificity", f"{tn / max(tn + fp, 1):.0%}"); b.metric("Precision", f"{tp / max(tp + fp, 1):.0%}")
    st.subheader("Cohort description")
    st.dataframe(load_csv("table1.csv"), width="stretch")
    with st.expander("Model details"):
        st.json({k: meta[k] for k in ["best_params", "n_trees", "threshold_all_oof", "target_recall", "versions"]})

# --------------------------------------------------------------------------------------------
# 6. about
# --------------------------------------------------------------------------------------------
with tabs[5]:
    st.markdown(f"""
### How to read a SHAP explanation
* The model works in **log-odds**. Each feature adds or subtracts a **SHAP value** relative to the average patient (baseline risk **{sigmoid(BASE):.1%}**); the contributions sum exactly to the final score.
* **exp(SHAP)** is the multiplier on the *odds* – ▲ ×1.30 means 30 % higher odds of the adverse outcome than baseline from that feature alone.
* Colour on the summary plot is the feature's value (low → high); position is its push on risk.

### Design choices you should know about
* **Target.** TCGA-BRCA contains no benign cases, so the proposal's benign-vs-malignant task cannot be built. The model predicts death during follow-up; it is recall-first (threshold {THR:.1%}).
* **Missing data.** "Not recorded" for HER2, nodal status, M-stage and menopause was strongly tied to outcome (a registry artefact), so unknowns are mapped to clinical defaults (NX→N0, MX→M0, HER2 unrecorded→negative).
* **Race.** Included as an input *only* so its use can be audited. The race-blind twin performs the same. Do not infer causality from race attributions.
* **Small subgroups.** ~{int((cohort.race == 'Black').sum())} Black patients, ~{int(cohort[cohort.race == 'Black'].died.sum())} deaths: treat subgroup patterns as hypotheses.

### Ethics & data
Public, de-identified TCGA data (UCSC Xena + cBioPortal PanCancer Atlas). No personal data are collected by this app; values you type are not stored. Aligned with the study's GDPR / HIPAA / Nigeria Data Protection Act 2023 commitments.

### For the physician user study (Objective 4)
Suggested protocol: show clinicians the *Patient explainer* with and without the SHAP chart, and ask for (a) their own risk estimate, (b) trust (1–7 Likert), (c) agreement with the explanation, (d) whether the race what-if changed their view.
""")
